from fastapi import APIRouter, Depends
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import OverrideAuditLog, Reply, Ticket, User
from ..security import require_agent

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def metrics(agent: User = Depends(require_agent), db: Session = Depends(get_db)):
    by_status = dict(db.execute(select(Ticket.status, func.count()).group_by(Ticket.status)).all())
    by_category = dict(db.execute(select(Ticket.category, func.count()).group_by(Ticket.category)).all())

    # median seconds from ticket creation to reply sent
    median_seconds = db.scalar(
        select(func.percentile_cont(0.5).within_group(
            func.extract("epoch", Reply.sent_at - Ticket.created_at)
        )).join(Ticket, Reply.ticket_id == Ticket.id)
    )

    total_tickets = db.scalar(select(func.count()).select_from(Ticket)) or 0
    overridden = db.scalar(
        select(func.count(distinct(OverrideAuditLog.ticket_id)))
        .where(OverrideAuditLog.field == "category")
    ) or 0

    return {
        "by_status": {s.value: c for s, c in by_status.items()},
        "by_category": {c.value: n for c, n in by_category.items()},
        "median_resolution_seconds": float(median_seconds) if median_seconds is not None else None,
        "category_override_rate": round(overridden / total_tickets, 4) if total_tickets else 0.0,
        "total_tickets": total_tickets,
    }
