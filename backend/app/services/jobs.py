"""In-memory job tracker for the lead search progress UI.
Single-process only; for multi-worker deployments move this to Redis or an n8n workflow."""
import threading, uuid

_jobs: dict[str, dict] = {}
_lock = threading.Lock()
STAGES = ["Searching", "Verifying websites", "Extracting public contacts", "Saving results"]


def create(user_id: int) -> str:
    jid = uuid.uuid4().hex
    with _lock:
        _jobs[jid] = {"user_id": user_id, "stage": 0, "stages": STAGES, "state": "running", "result": None, "error": None}
    return jid


def update(jid: str, **kw):
    with _lock:
        _jobs[jid].update(kw)


def get(jid: str, user_id: int):
    j = _jobs.get(jid)
    return j if j and j["user_id"] == user_id else None
