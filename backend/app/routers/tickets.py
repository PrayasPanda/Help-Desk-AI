import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from .. import ai
from ..db import get_db
from ..models import Category, OverrideAuditLog, Priority, Reply, Role, Status, Ticket, User
from ..realtime import broker
from ..schemas import (
    AuditOut,
    ClassificationPatch,
    DraftOut,
    Paginated,
    SendReplyIn,
    TicketCreate,
    TicketDetailOut,
    TicketOut,
)
from ..security import get_current_user, require_agent

router = APIRouter(tags=["tickets"])


def _get_ticket_or_404(ticket_id: int, db: Session) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    return ticket


def _require_owner_or_agent(ticket: Ticket, user: User):
    if user.role != Role.agent and ticket.employee_id != user.id:
        # 404, not 403: an employee guessing IDs learns nothing about other tickets
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")


@router.get("/tickets", response_model=Paginated)
def list_tickets(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status_: Status | None = Query(default=None, alias="status"),
    category: Category | None = None,
    priority: Priority | None = None,
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    stmt = select(Ticket)
    if user.role != Role.agent:
        stmt = stmt.where(Ticket.employee_id == user.id)
    if status_:
        stmt = stmt.where(Ticket.status == status_)
    if category:
        stmt = stmt.where(Ticket.category == category)
    if priority:
        stmt = stmt.where(Ticket.priority == priority)
    if q:
        stmt = stmt.where(Ticket.title.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Ticket.created_at.desc()).offset((page - 1) * limit).limit(limit)).all()
    return Paginated(
        data=[TicketOut.model_validate(t) for t in rows],
        meta={"page": page, "limit": limit, "total": total},
    )


@router.post("/tickets", response_model=TicketOut, status_code=201)
def create_ticket(body: TicketCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != Role.employee:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only employees raise tickets")
    suggestion = ai.classify(body.title, body.description)
    ticket = Ticket(
        employee_id=user.id,
        title=body.title,
        description=body.description,
        attachment_filename=body.attachment_filename,
        category=suggestion["category"],
        priority=suggestion["priority"],
        ai_category=suggestion["category"],
        ai_priority=suggestion["priority"],
        ai_confidence=suggestion["confidence"],
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    out = TicketOut.model_validate(ticket)
    broker.publish({"type": "ticket:created", "ticket": out.model_dump(mode="json")}, to_agents=True)
    return out


@router.get("/tickets/{ticket_id}", response_model=TicketDetailOut)
def ticket_detail(ticket_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ticket = _get_ticket_or_404(ticket_id, db)
    _require_owner_or_agent(ticket, user)
    return ticket


@router.patch("/tickets/{ticket_id}/classification", response_model=TicketOut)
def override_classification(
    ticket_id: int,
    body: ClassificationPatch,
    agent: User = Depends(require_agent),
    db: Session = Depends(get_db),
):
    ticket = _get_ticket_or_404(ticket_id, db)
    for field, new in (("category", body.category), ("priority", body.priority)):
        old = getattr(ticket, field)
        if new is not None and new != old:
            db.add(OverrideAuditLog(
                ticket_id=ticket.id, agent_id=agent.id, field=field,
                old_value=old.value, new_value=new.value,
            ))
            setattr(ticket, field, new)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/tickets/{ticket_id}/draft-reply", response_model=DraftOut)
def generate_draft(ticket_id: int, agent: User = Depends(require_agent), db: Session = Depends(get_db)):
    ticket = _get_ticket_or_404(ticket_id, db)
    result = ai.draft_reply(ticket.title, ticket.description)
    return DraftOut(**result)


@router.post("/tickets/{ticket_id}/reply", response_model=TicketDetailOut)
def send_reply(
    ticket_id: int,
    body: SendReplyIn,
    agent: User = Depends(require_agent),
    db: Session = Depends(get_db),
):
    ticket = _get_ticket_or_404(ticket_id, db)
    if ticket.status == Status.resolved:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ticket already resolved")
    db.add(Reply(ticket_id=ticket.id, ai_draft=body.ai_draft, final_reply=body.final_reply,
                 citations=body.citations))
    ticket.status = Status.resolved
    db.commit()
    db.refresh(ticket)
    broker.publish(
        {"type": "ticket:resolved", "ticket_id": ticket.id, "status": "resolved"},
        to_agents=True, to_user_id=ticket.employee_id,
    )
    return ticket


@router.get("/tickets/{ticket_id}/audit-log", response_model=list[AuditOut])
def audit_log(ticket_id: int, agent: User = Depends(require_agent), db: Session = Depends(get_db)):
    ticket = _get_ticket_or_404(ticket_id, db)
    return ticket.audit_log


@router.get("/events")
async def events(request: Request, user: User = Depends(get_current_user)):
    """SSE stream. Auth via ?token= because EventSource can't set headers."""
    queue = broker.subscribe(user)

    async def stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15)
                    yield {"event": "message", "data": payload}
                except asyncio.TimeoutError:
                    yield {"comment": "keepalive"}
        finally:
            broker.unsubscribe(queue)

    return EventSourceResponse(stream())
