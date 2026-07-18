from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from .models import Category, Priority, Role, Status


# ---- auth ----
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: Role = Role.employee


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    role: Role

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    user: UserOut


# ---- tickets ----
class TicketCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=5000)
    attachment_filename: str | None = Field(default=None, max_length=255)


class ReplyOut(BaseModel):
    ai_draft: str
    final_reply: str
    citations: list
    sent_at: datetime

    model_config = {"from_attributes": True}


class TicketOut(BaseModel):
    id: int
    title: str
    description: str
    attachment_filename: str | None
    status: Status
    category: Category
    priority: Priority
    ai_category: Category
    ai_priority: Priority
    ai_confidence: float | None
    employee: UserOut
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AuditOut(BaseModel):
    id: int
    field: str
    old_value: str
    new_value: str
    agent: UserOut
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketDetailOut(TicketOut):
    reply: ReplyOut | None
    audit_log: list[AuditOut]


class ClassificationPatch(BaseModel):
    category: Category | None = None
    priority: Priority | None = None


class DraftOut(BaseModel):
    draft: str
    citations: list[str]


class SendReplyIn(BaseModel):
    ai_draft: str
    final_reply: str = Field(min_length=1, max_length=10000)
    citations: list[str] = []


class Paginated(BaseModel):
    data: list[TicketOut]
    meta: dict
