"""Outreach Generator. Writes only from supplied evidence; drafts always start as DRAFT."""
from . import ai_client
from .catalog import CHANNELS
from .sanitize import SYSTEM_GUARD

LIMITS = {"email": "under 120 words", "linkedin": "under 70 words, no subject", "whatsapp": "under 60 words, casual but professional, no subject",
          "followup": "under 50 words, polite nudge", "proposal": "under 150 words, introduces a proposal"}
OPT_OUT = "\n\nIf this isn't relevant, just let me know and I won't follow up."


def generate(company: dict, channel: str, opportunity: dict | None, contact_name: str | None, sender: str) -> dict:
    if channel not in CHANNELS:
        raise ValueError("Unknown channel")
    obs = [e["text"] for e in (opportunity or {}).get("evidence", [])][:2]
    system = SYSTEM_GUARD + "\nYou write concise, human B2B outreach for Xylon Technology."
    user = (
        f"Channel: {channel} ({LIMITS[channel]})\nCompany: {company['name']} — {company.get('industry','')}\n"
        f"Recipient: {contact_name or company['name'] + ' team'}\n"
        f"Observation(s) you may reference (verified data only): {obs or 'none available'}\n"
        f"Opportunity: {(opportunity or {}).get('problem','none identified')}\n"
        f"Service to mention: {(opportunity or {}).get('service','none')}\n\n"
        "Structure: greeting; 'I came across <company> while researching <industry>'; ONE specific observation "
        "(only if provided); how Xylon Technology can help; soft CTA offering a few ideas; sign off 'Best,\\n"
        f"{sender}'. Rules: no hype, no 'revolutionary', no invented stats, no fake familiarity, no claims "
        "beyond the observations. Return JSON {\"subject\":str,\"body\":str} (subject empty unless email)."
    )
    d = ai_client.json_call(system, user)
    body = str(d.get("body", "")).strip()[:1500]
    if channel in ("email", "followup", "proposal"):
        body += OPT_OUT
    return {"subject": str(d.get("subject", ""))[:200] if channel == "email" else "", "body": body}
