import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session
from ..config import settings
from ..db import SessionLocal, get_db
from ..limiter import limiter
from ..models import (LEAD_STATUSES, Activity, Company, Contact, Lead, Opportunity, OutreachMessage,
                      ResearchReport, User, WebsiteAudit)
from ..security import current_user
from ..services import auditor, fetcher, jobs, lead_finder, opportunity, outreach, researcher
from ..services.catalog import CHANNELS, SERVICES

log = logging.getLogger("xylon.leads")
router = APIRouter(prefix="/api", tags=["leads"])


# ---------- helpers ----------
def own_lead(db: Session, user: User, lead_id: int) -> Lead:
    """Authorization: a lead is only reachable by its owner."""
    lead = db.query(Lead).filter_by(id=lead_id, user_id=user.id).first()
    if not lead:
        raise HTTPException(404, "Lead not found")
    return lead


def log_act(db, user_id, lead_id, type_, detail=""):
    db.add(Activity(user_id=user_id, lead_id=lead_id, type=type_, detail=detail[:1000]))


def iso(d):
    return d.isoformat() if d else None


def company_out(c: Company):
    return {"id": c.id, "name": c.name, "website": c.website, "industry": c.industry, "country": c.country,
            "region": c.region, "description": c.description}


def contact_out(c: Contact):
    return {"id": c.id, "name": c.name, "title": c.title, "email": c.email, "phone": c.phone,
            "linkedin": c.linkedin, "source_url": c.source_url, "verified": c.verified}


def lead_out(l: Lead, db: Session | None = None):
    primary = next((c for c in l.company.contacts), None)
    services = sorted({o.service for o in l.opportunities})
    return {"id": l.id, "status": l.status, "outreach_status": l.outreach_status, "source": l.source,
            "match_reason": l.match_reason, "required_service": l.required_service,
            "last_contacted": iso(l.last_contacted), "next_followup": iso(l.next_followup), "notes": l.notes,
            "created_at": iso(l.created_at), "company": company_out(l.company),
            "contact": contact_out(primary) if primary else None,
            "recommended_services": services,
            "opportunity": l.opportunities[0].problem if l.opportunities else None}


def latest(db, model, company_id):
    return db.query(model).filter_by(company_id=company_id).order_by(model.created_at.desc()).first()


def fresh(row) -> bool:
    if not row:
        return False
    ts = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - ts < timedelta(days=settings.cache_days)


# ---------- Lead Finder (async job with progress) ----------
class FindRequest(BaseModel):
    country: str = Field(min_length=2, max_length=80)
    region: str | None = Field(None, max_length=80)
    industry: str = Field(min_length=2, max_length=120)
    count: int = Field(10, ge=1, le=30)
    service: str | None = None
    company_size: str | None = Field(None, max_length=60)
    keywords: str | None = Field(None, max_length=200)
    require_website: bool = True
    recent_activity: bool = False

    @field_validator("service")
    @classmethod
    def _svc(cls, v):
        if v and v not in SERVICES:
            raise ValueError("Unknown service")
        return v


def _run_find(job_id: str, user_id: int, req: dict):
    db = SessionLocal()
    try:
        cands, urls = lead_finder.search(req)
        jobs.update(job_id, stage=1)
        verified = lead_finder.verify_all(cands, req)
        jobs.update(job_id, stage=2)  # contacts are extracted inside verify; stage kept for UI clarity
        jobs.update(job_id, stage=3)
        saved = []
        for c in verified:
            domain = c["domain"]
            if db.query(Company).filter_by(user_id=user_id, domain=domain).first():
                continue  # no duplicates / no re-research of known companies
            comp = Company(user_id=user_id, name=str(c["name"])[:255], website=c.get("website"), domain=domain,
                           industry=str(c.get("industry") or req["industry"])[:160],
                           country=str(c.get("country") or req["country"])[:80], region=req.get("region") or "",
                           description=str(c.get("description", ""))[:2000])
            db.add(comp); db.flush()
            ct = c.get("contacts")
            if ct and (ct["emails"] or ct["phones"] or ct["linkedin"]):
                db.add(Contact(company_id=comp.id, email=(ct["emails"] or [None])[0], phone=(ct["phones"] or [None])[0],
                               linkedin=(ct["linkedin"] or [None])[0], source_url=ct["source_url"], verified=True))
            lead = Lead(user_id=user_id, company_id=comp.id, source=c.get("source_url"),
                        match_reason=str(c.get("reason", ""))[:1000], required_service=req.get("service"))
            db.add(lead); db.flush()
            log_act(db, user_id, lead.id, "lead_found", f"Found via search: {req['industry']}, {req['country']}")
            saved.append(lead.id)
        db.commit()
        leads = db.query(Lead).filter(Lead.id.in_(saved)).all() if saved else []
        jobs.update(job_id, state="done", result=[lead_out(l) for l in leads],
                    info=f"{len(cands)} candidates, {len(verified)} verified, {len(saved)} new")
    except HTTPException as e:
        jobs.update(job_id, state="error", error=e.detail)
    except Exception:
        log.exception("Lead search failed")
        jobs.update(job_id, state="error", error="Lead search failed. Check server logs.")
    finally:
        db.close()


@router.post("/leads/find", status_code=202)
@limiter.limit("5/minute")
def find_leads(request: Request, body: FindRequest, bg: BackgroundTasks, user: User = Depends(current_user)):
    jid = jobs.create(user.id)
    bg.add_task(_run_find, jid, user.id, body.model_dump())
    return {"job_id": jid}


@router.get("/jobs/{job_id}")
def job_status(job_id: str, user: User = Depends(current_user)):
    j = jobs.get(job_id, user.id)
    if not j:
        raise HTTPException(404, "Job not found")
    return j


# ---------- CRM ----------
@router.get("/leads")
def list_leads(q: str | None = None, status: str | None = None, country: str | None = None,
               sort: str = "created_at", order: str = "desc", limit: int = 200,
               db: Session = Depends(get_db), user: User = Depends(current_user)):
    qs = db.query(Lead).join(Company).filter(Lead.user_id == user.id)
    if q:
        like = f"%{q.strip()[:80]}%"
        qs = qs.filter(or_(Company.name.ilike(like), Company.industry.ilike(like), Company.domain.ilike(like)))
    if status in LEAD_STATUSES:
        qs = qs.filter(Lead.status == status)
    if country:
        qs = qs.filter(Company.country.ilike(country[:80]))
    cols = {"created_at": Lead.created_at, "company": Company.name, "status": Lead.status,
            "next_followup": Lead.next_followup, "last_contacted": Lead.last_contacted}
    col = cols.get(sort, Lead.created_at)
    qs = qs.order_by(col.asc() if order == "asc" else col.desc()).limit(min(limit, 500))
    return [lead_out(l) for l in qs.all()]


@router.get("/leads/{lead_id}")
def lead_detail(lead_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    l = own_lead(db, user, lead_id)
    r, a = latest(db, ResearchReport, l.company_id), latest(db, WebsiteAudit, l.company_id)
    acts = db.query(Activity).filter_by(lead_id=l.id, user_id=user.id).order_by(Activity.created_at.desc()).limit(100).all()
    return {**lead_out(l),
            "contacts": [contact_out(c) for c in l.company.contacts],
            "research": {"facts": r.facts, "inferences": r.inferences, "sources": r.sources,
                         "pages_fetched": r.pages_fetched, "created_at": iso(r.created_at)} if r else None,
            "audit": {"url": a.url, "score": a.score, "checks": a.checks, "strengths": a.strengths, "problems": a.problems,
                      "opportunities": a.opportunities, "recommendations": a.recommendations,
                      "not_assessed": a.not_assessed, "created_at": iso(a.created_at)} if a else None,
            "opportunities": [{"id": o.id, "problem": o.problem, "service": o.service, "rationale": o.rationale,
                               "evidence": o.evidence, "is_inference": o.is_inference} for o in l.opportunities],
            "messages": [{"id": m.id, "channel": m.channel, "subject": m.subject, "body": m.body, "status": m.status,
                          "created_at": iso(m.created_at), "sent_at": iso(m.sent_at)} for m in
                         sorted(l.messages, key=lambda m: m.created_at, reverse=True)],
            "activities": [{"type": x.type, "detail": x.detail, "created_at": iso(x.created_at)} for x in acts]}


class LeadPatch(BaseModel):
    status: str | None = None
    notes: str | None = Field(None, max_length=5000)
    next_followup: datetime | None = None
    contact: dict | None = None  # {name,title,email,phone,linkedin}: manual entry by the user


@router.patch("/leads/{lead_id}")
def save_lead(lead_id: int, body: LeadPatch, db: Session = Depends(get_db), user: User = Depends(current_user)):
    l = own_lead(db, user, lead_id)
    data = body.model_dump(exclude_unset=True)
    if "status" in data:
        if data["status"] not in LEAD_STATUSES:
            raise HTTPException(422, "Invalid status")
        if data["status"] != l.status:
            log_act(db, user.id, l.id, "status_changed", f"{l.status} -> {data['status']}")
        l.status = data["status"]
    if "notes" in data:
        l.notes = data["notes"]
    if "next_followup" in data:
        l.next_followup = data["next_followup"]
    if data.get("contact"):
        c = data["contact"]
        row = l.company.contacts[0] if l.company.contacts else Contact(company_id=l.company_id)
        for k in ("name", "title", "email", "phone", "linkedin"):
            if k in c and isinstance(c[k], (str, type(None))):
                setattr(row, k, (c[k] or None) if k in ("email", "phone", "linkedin") else (c[k] or "")[:160])
        row.verified = False  # manually entered; we did not check it
        db.add(row)
    db.commit()
    log_act(db, user.id, l.id, "lead_saved"); db.commit()
    return lead_out(l)


# ---------- Manual, cached AI actions (cost control) ----------
class Force(BaseModel):
    force: bool = False


def _need_site(l: Lead):
    if not l.company.website:
        raise HTTPException(422, "This company has no website on record")


@router.post("/leads/{lead_id}/research")
@limiter.limit("10/minute")
def research_company(request: Request, lead_id: int, body: Force = Force(), db: Session = Depends(get_db),
                     user: User = Depends(current_user)):
    l = own_lead(db, user, lead_id); _need_site(l)
    existing = latest(db, ResearchReport, l.company_id)
    if fresh(existing) and not body.force:
        return {"cached": True}
    c = l.company
    res = researcher.research({"name": c.name, "website": c.website, "industry": c.industry, "country": c.country})
    db.add(ResearchReport(company_id=c.id, facts=res["facts"], inferences=res["inferences"],
                          sources=res["sources"], pages_fetched=res["pages_fetched"]))
    for pc in res["page_contacts"]:  # verified: seen on the page
        have = {(x.email, x.phone) for x in c.contacts}
        e, p = (pc["emails"] or [None])[0], (pc["phones"] or [None])[0]
        if (e, p) not in have:
            db.add(Contact(company_id=c.id, email=e, phone=p, linkedin=(pc["linkedin"] or [None])[0],
                           source_url=pc["source_url"], verified=True))
    for d in res["decision_makers"]:  # cited by search, not verified by us
        if not any(x.name == d["name"] for x in c.contacts):
            db.add(Contact(company_id=c.id, name=d["name"], title=d["title"], source_url=d["source_url"], verified=False))
    if l.status == "NEW":
        l.status = "RESEARCHED"
    log_act(db, user.id, l.id, "researched", f"{len(res['facts'])} sourced facts"); db.commit()
    return {"cached": False}


@router.post("/leads/{lead_id}/audit")
@limiter.limit("10/minute")
def audit_website(request: Request, lead_id: int, body: Force = Force(), db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    l = own_lead(db, user, lead_id); _need_site(l)
    if fresh(latest(db, WebsiteAudit, l.company_id)) and not body.force:
        return {"cached": True}
    try:
        res = auditor.audit_url(l.company.website)
    except fetcher.FetchError as e:
        raise HTTPException(422, f"Could not audit website: {e}")
    db.add(WebsiteAudit(company_id=l.company_id, url=res["url"], score=res["score"], checks=res["checks"],
                        strengths=res["strengths"], problems=res["problems"], opportunities=res["opportunities"],
                        recommendations=res["recommendations"], not_assessed=res["not_assessed"]))
    log_act(db, user.id, l.id, "audited", f"Score {res['score']}"); db.commit()
    return {"cached": False}


@router.post("/leads/{lead_id}/opportunities")
@limiter.limit("10/minute")
def find_opportunities(request: Request, lead_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    l = own_lead(db, user, lead_id)
    r, a = latest(db, ResearchReport, l.company_id), latest(db, WebsiteAudit, l.company_id)
    if not (r or a):
        raise HTTPException(422, "Run research or a website audit first so there is evidence to analyze")
    c = l.company
    ops = opportunity.analyze({"name": c.name, "industry": c.industry},
                              {"facts": r.facts} if r else None, {"checks": a.checks} if a else None, l.required_service)
    db.query(Opportunity).filter_by(lead_id=l.id).delete()
    for o in ops:
        db.add(Opportunity(lead_id=l.id, **o, is_inference=True))
    log_act(db, user.id, l.id, "opportunities", f"{len(ops)} supported opportunities"); db.commit()
    return {"count": len(ops)}


class GenOutreach(BaseModel):
    channel: str = "email"
    opportunity_id: int | None = None


@router.post("/leads/{lead_id}/outreach")
@limiter.limit("15/minute")
def generate_outreach(request: Request, lead_id: int, body: GenOutreach, db: Session = Depends(get_db),
                      user: User = Depends(current_user)):
    l = own_lead(db, user, lead_id)
    if body.channel not in CHANNELS:
        raise HTTPException(422, "Unknown channel")
    ops = l.opportunities
    op = next((o for o in ops if o.id == body.opportunity_id), ops[0] if ops else None)
    named = next((c.name for c in l.company.contacts if c.name), None)
    c = l.company
    draft = outreach.generate({"name": c.name, "industry": c.industry}, body.channel,
                              {"problem": op.problem, "service": op.service, "evidence": op.evidence} if op else None,
                              named, settings.sender_name)
    m = OutreachMessage(lead_id=l.id, channel=body.channel, subject=draft["subject"], body=draft["body"])
    db.add(m)
    l.outreach_status = "DRAFT"
    if l.status in ("NEW", "RESEARCHED", "QUALIFIED"):
        l.status = "MESSAGE_DRAFTED"
    log_act(db, user.id, l.id, "message_drafted", body.channel); db.commit()
    return {"id": m.id}
