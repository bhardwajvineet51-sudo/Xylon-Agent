"""Human approval gate: DRAFT -> (user edits/approves) -> APPROVED -> (explicit send) -> SENT.
There is no bulk-send endpoint by design."""
import logging, smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from ..config import settings
from ..db import get_db
from ..limiter import limiter
from ..models import Lead, OutreachMessage, User
from ..security import current_user
from .leads import iso, log_act

log = logging.getLogger("xylon.outreach")
router = APIRouter(prefix="/api/outreach", tags=["outreach"])


def own_msg(db: Session, user: User, mid: int) -> OutreachMessage:
    m = db.query(OutreachMessage).join(Lead).filter(OutreachMessage.id == mid, Lead.user_id == user.id).first()
    if not m:
        raise HTTPException(404, "Message not found")
    return m


@router.get("")
def list_messages(status: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = db.query(OutreachMessage).join(Lead).filter(Lead.user_id == user.id)
    if status:
        q = q.filter(OutreachMessage.status == status)
    return [{"id": m.id, "lead_id": m.lead_id, "company": m_company(db, m), "channel": m.channel, "subject": m.subject,
             "body": m.body, "status": m.status, "created_at": iso(m.created_at)}
            for m in q.order_by(OutreachMessage.created_at.desc()).limit(200).all()]


def m_company(db, m):
    return db.get(Lead, m.lead_id).company.name


class Edit(BaseModel):
    subject: str = Field("", max_length=300)
    body: str = Field(min_length=1, max_length=4000)


@router.patch("/{mid}")
def edit(mid: int, body: Edit, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = own_msg(db, user, mid)
    if m.status == "SENT":
        raise HTTPException(409, "Sent messages cannot be edited")
    m.subject, m.body = body.subject, body.body
    m.status, m.approved_at = "DRAFT", None  # any edit invalidates a previous approval
    db.commit()
    return {"ok": True}


@router.post("/{mid}/approve")
def approve(mid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = own_msg(db, user, mid)
    if m.status == "SENT":
        raise HTTPException(409, "Already sent")
    m.status, m.approved_at = "APPROVED", datetime.now(timezone.utc)
    db.get(Lead, m.lead_id).outreach_status = "APPROVED"
    log_act(db, user.id, m.lead_id, "message_approved", m.channel); db.commit()
    return {"ok": True}


class Send(BaseModel):
    to: EmailStr | None = None  # required for email; must be chosen by the user


@router.post("/{mid}/send")
@limiter.limit("10/minute")
def send(request: Request, mid: int, body: Send, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = own_msg(db, user, mid)
    if m.status != "APPROVED":
        raise HTTPException(409, "Message must be approved before sending")
    lead = db.get(Lead, m.lead_id)
    if m.channel == "email":
        if not body.to:
            raise HTTPException(422, "Recipient email required")
        if not settings.smtp_host or not settings.smtp_from:
            raise HTTPException(503, "SMTP is not configured; copy the message and send it manually, then mark as sent")
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = settings.smtp_from, str(body.to), m.subject or "Introduction"
        msg.set_content(m.body)
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
                s.starttls()
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
        except Exception:
            log.exception("SMTP send failed")
            raise HTTPException(502, "Email provider rejected or failed to send the message")
        m.recipient = str(body.to)
    # LinkedIn/WhatsApp: no API integration in MVP; user sends manually and confirms here.
    now = datetime.now(timezone.utc)
    m.status, m.sent_at = "SENT", now
    lead.outreach_status, lead.last_contacted = "SENT", now
    if lead.status in ("NEW", "RESEARCHED", "QUALIFIED", "MESSAGE_DRAFTED"):
        lead.status = "CONTACTED"
    log_act(db, user.id, lead.id, "message_sent", f"{m.channel} {m.recipient or '(manual)'}"); db.commit()
    return {"ok": True}
