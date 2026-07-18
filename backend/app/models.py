import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    employee = "employee"
    agent = "agent"


class Status(str, enum.Enum):
    open = "open"
    resolved = "resolved"


class Category(str, enum.Enum):
    IT = "IT"
    HR = "HR"
    Finance = "Finance"
    Admin = "Admin"
    Other = "Other"


class Priority(str, enum.Enum):
    Low = "Low"
    Medium = "Medium"
    High = "High"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    tickets: Mapped[list["Ticket"]] = relationship(back_populates="employee")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    attachment_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.open, index=True)
    # current values (agent can override); initialized from the AI suggestion
    category: Mapped[Category] = mapped_column(Enum(Category), index=True)
    priority: Mapped[Priority] = mapped_column(Enum(Priority))
    # original AI suggestion, never mutated after creation
    ai_category: Mapped[Category] = mapped_column(Enum(Category))
    ai_priority: Mapped[Priority] = mapped_column(Enum(Priority))
    ai_confidence: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    employee: Mapped[User] = relationship(back_populates="tickets")
    reply: Mapped["Reply | None"] = relationship(back_populates="ticket", uselist=False)
    audit_log: Mapped[list["OverrideAuditLog"]] = relationship(back_populates="ticket", order_by="OverrideAuditLog.created_at")


class Reply(Base):
    __tablename__ = "replies"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), unique=True)
    ai_draft: Mapped[str] = mapped_column(Text)
    final_reply: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON, default=list)  # [{"article": title}]
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    ticket: Mapped[Ticket] = relationship(back_populates="reply")


class OverrideAuditLog(Base):
    __tablename__ = "override_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    field: Mapped[str] = mapped_column(String(20))  # "category" | "priority"
    old_value: Mapped[str] = mapped_column(String(20))
    new_value: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    ticket: Mapped[Ticket] = relationship(back_populates="audit_log")
    agent: Mapped[User] = relationship()
