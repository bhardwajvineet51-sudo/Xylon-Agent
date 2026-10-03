"""Opportunity Analyzer: Problem -> Evidence -> Service.
Evidence is NOT written by the model: it must reference real audit checks / research facts by id,
and we attach the stored evidence text ourselves."""
from . import ai_client
from .catalog import SERVICES
from .sanitize import SYSTEM_GUARD


def analyze(company: dict, research: dict | None, audit: dict | None, wanted_service: str | None) -> list[dict]:
    pool = {}
    for c in (audit or {}).get("checks", []):
        if c["passed"] is not None:
            pool[f"check:{c['key']}"] = {"text": f"{c['label']}: {'PASS' if c['passed'] else 'FAIL'} — {c['evidence']}"}
    for i, f in enumerate((research or {}).get("facts", [])):
        pool[f"fact:{i}"] = {"text": f["claim"], "source_url": f["source_url"]}
    if not pool:
        return []
    listing = "\n".join(f"[{k}] {v['text']}" for k, v in pool.items())
    system = SYSTEM_GUARD + "\nYou are a services strategist for Xylon Technology."
    user = (
        f"Company: {company['name']} ({company.get('industry','')}). Service requested by the user: {wanted_service or 'none'}.\n"
        f"Allowed services: {SERVICES}\n\nEvidence items:\n{listing}\n\n"
        "Return JSON {\"opportunities\":[{\"problem\":str,\"evidence_refs\":[ids from the list],"
        "\"service\":one allowed service,\"rationale\":str}]}. Max 4. Recommend ONLY services directly supported "
        "by the evidence; do NOT recommend every service. Do not claim anything the evidence doesn't show "
        "(e.g. don't call a site slow or insecure unless a FAIL item says so)."
    )
    out, used = [], set()
    for o in ai_client.json_call(system, user).get("opportunities", [])[:4]:
        refs = [r for r in o.get("evidence_refs", []) if r in pool]
        if o.get("service") not in SERVICES or not refs or o["service"] in used:
            continue  # drop unsupported or off-catalogue recommendations
        used.add(o["service"])
        out.append({"problem": str(o.get("problem", ""))[:400], "service": o["service"],
                    "rationale": str(o.get("rationale", ""))[:500],
                    "evidence": [{"ref": r, **pool[r]} for r in refs]})
    return out
