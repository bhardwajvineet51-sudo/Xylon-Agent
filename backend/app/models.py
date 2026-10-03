"""Database models. Every tenant-owned row carries user_id (directly or via lead/company)."""
from datetime import datetime, timezone
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def now():
    return datetime.now(timezone.utc)


LEAD_STATUSES = ["NEW", "RESEARCHED", "QUALIFIED", "MESSAGE_DRAFTED", "CONTACTED", "REPLIED",
                 "MEETING", "PROPOSAL", "WON", "LOST", "NOT_INTERESTED"]


class Stamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class User(Base, Stamped):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120), default="")


class Company(Base, Stamped):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("user_id", "domain"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    website: Mapped[str | None] = mapped_column(String(500))
    domain: Mapped[str] = mapped_column(String(255))
    industry: Mapped[str] = mapped_column(String(160), default="")
    country: Mapped[str] = mapped_column(String(80), default="")
    region: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    contacts = relationship("Contact", cascade="all, delete-orphan", back_populates="company")


class Contact(Base, Stamped):
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    title: Mapped[str] = mapped_column(String(160), default="")
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(60))
    linkedin: Mapped[str | None] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(500))
    # True only when WE saw the value on the cited page (regex extraction). Search-reported
    # decision makers are stored with verified=False.
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    company = relationship("Company", back_populates="contacts")


class Lead(Base, Stamped):
    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("user_id", "company_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="NEW", index=True)
    outreach_status: Mapped[str] = mapped_column(String(20), default="NONE")
    source: Mapped[str | None] = mapped_column(String(500))
    match_reason: Mapped[str] = mapped_column(Text, default="")  # AI inference from lead search
    required_service: Mapped[str | None] = mapped_column(String(80))
    last_contacted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_followup: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str] = mapped_column(Text, default="")
    company = relationship("Company")
    opportunities = relationship("Opportunity", cascade="all, delete-orphan")
    messages = relationship("OutreachMessage", cascade="all, delete-orphan")


class ResearchReport(Base, Stamped):
    __tablename__ = "research_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    facts: Mapped[list] = mapped_column(JSON, default=list)        # [{claim, source_url}]
    inferences: Mapped[list] = mapped_column(JSON, default=list)   # [{statement, basis}]  (NOT facts)
    sources: Mapped[list] = mapped_column(JSON, default=list)      # [url]
    pages_fetched: Mapped[list] = mapped_column(JSON, default=list)


class WebsiteAudit(Base, Stamped):
    __tablename__ = "website_audits"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(500))
    score: Mapped[int | None] = mapped_column(Integer)
    checks: Mapped[list] = mapped_column(JSON, default=list)
    strengths: Mapped[list] = mapped_column(JSON, default=list)
    problems: Mapped[list] = mapped_column(JSON, default=list)
    opportunities: Mapped[list] = mapped_column(JSON, default=list)
    recommendations: Mapped[list] = mapped_column(JSON, default=list)
    not_assessed: Mapped[list] = mapped_column(JSON, default=list)


class Opportunity(Base, Stamped):
    __tablename__ = "opportunities"
    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    problem: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSON, default=list)  # [{ref, text, source_url?}] from real data
    service: Mapped[str] = mapped_column(String(80))
    rationale: Mapped[str] = mapped_column(Text, default="")
    is_inference: Mapped[bool] = mapped_column(Boolean, default=True)


class OutreachMessage(Base, Stamped):
    __tablename__ = "outreach_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(20))  # email|linkedin|whatsapp|followup|proposal
    subject: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")  # DRAFT|APPROVED|SENT
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recipient: Mapped[str | None] = mapped_column(String(255))


class FollowUp(Base, Stamped):
    __tablename__ = "followups"
    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    note: Mapped[str] = mapped_column(Text, default="")
    done: Mapped[bool] = mapped_column(Boolean, default=False)


class Activity(Base):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
