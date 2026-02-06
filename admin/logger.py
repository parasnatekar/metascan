from datetime import datetime, timezone
from db import db

auth_logs = db["auth_logs"]
search_logs = db["search_logs"]
admin_logs = db["admin_logs"]
perf_logs = db["perf_logs"]

def log_auth(email: str, success: bool, role: str = None, reason: str = None):
    auth_logs.insert_one({
        "ts": datetime.now(timezone.utc),
        "email": (email or "").strip().lower(),
        "success": bool(success),
        "role": role,
        "reason": reason
    })

def log_search(email: str, query: str, results_count: int, filters: dict = None):
    search_logs.insert_one({
        "ts": datetime.now(timezone.utc),
        "email": (email or "").strip().lower(),
        "query": query,
        "results_count": int(results_count),
        "filters": filters or {}
    })

def log_admin(actor_email: str, action: str, target: str = "", meta: dict = None):
    admin_logs.insert_one({
        "timestamp": datetime.now(timezone.utc),
        "actor_email": (actor_email or "").strip().lower(),
        "action": action,
        "target": target,
        "meta": meta or {}
    })

def log_perf(stage: str, ms: int, meta: dict = None):
    perf_logs.insert_one({
        "ts": datetime.now(timezone.utc),
        "stage": stage,
        "ms": int(ms),
        "meta": meta or {}
    })
