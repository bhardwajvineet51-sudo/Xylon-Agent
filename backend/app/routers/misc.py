from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import LEAD_STATUSES, FollowUp, Lead, User
from ..security import current_user
from .leads import iso, log_act, own_lead

router = APIRouter(prefix="/api", tags=["misc"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = dict(db.query(Lead.status, func.count()).filter(Lead.user_id == user.id).group_by(Lead.status).all())
    pipeline = [{"status": s, "count": rows.get(s, 0)} for s in LEAD_STATUSES]
    g = lambda *s: sum(rows.get(x, 0) for x in s)
    return {"cards": {"total": sum(rows.values()), "new": g("NEW"), "qualified": g("QUALIFIED"),
                      "messages_drafted": g("MESSAGE_DRAFTED"), "contacted": g("CONTACTED"),
                      "replies": g("REPLIED"), "meetings": g("MEETING"), "won": g("WON")},
            "pipeline": pipeline}


class FU(BaseModel):
    lead_id: int
    due_date: datetime
    note: str = Field("", max_length=1000)


@router.get("/followups")
def followups(db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = db.query(FollowUp).join(Lead).filter(Lead.user_id == user.id).order_by(FollowUp.done, FollowUp.due_date)
    return [{"id": f.id, "lead_id": f.lead_id, "company": db.get(Lead, f.lead_id).company.name,
             "due_date": iso(f.due_date), "note": f.note, "done": f.done} for f in q.limit(300).all()]


@router.post("/followups")
def add_followup(body: FU, db: Session = Depends(get_db), user: User = Depends(current_user)):
    lead = own_lead(db, user, body.lead_id)
    db.add(FollowUp(lead_id=lead.id, due_date=body.due_date, note=body.note))
    lead.next_followup = body.due_date
    log_act(db, user.id, lead.id, "followup_set", body.note); db.commit()
    return {"ok": True}


@router.post("/followups/{fid}/done")
def done(fid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    f = db.query(FollowUp).join(Lead).filter(FollowUp.id == fid, Lead.user_id == user.id).first()
    if not f:
        raise HTTPException(404, "Follow-up not found")
    f.done = True; db.commit()
    return {"ok": True}
