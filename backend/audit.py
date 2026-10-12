"""Append-only audit trail: output/audit_trail.json is a JSON list, and every agent-loop step adds one entry.

Earlier entries are never dropped. Each write re-reads the list, appends and swaps the file in atomically (temp file
+ os.replace) under a file lock, so a crash mid-write cannot corrupt it. If the file is unreadable, it is renamed to
audit_trail.unreadable-<time>.json (kept, not deleted) and a new list starts.
"""

from __future__ import annotations

import fcntl
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any

from config import AUDIT_PATH, AUDIT_PREVIEW_CHARS
from models import AuditEntry

_lock = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def clip(value: Any, limit: int = AUDIT_PREVIEW_CHARS) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + f"... (+{len(text) - limit} chars)"


def _read() -> list[dict]:
    if not AUDIT_PATH.exists():
        return []
    try:
        data = json.loads(AUDIT_PATH.read_text(encoding="utf-8") or "[]")
        if isinstance(data, list):
            return data
    except ValueError:
        pass
    AUDIT_PATH.rename(AUDIT_PATH.with_name(f"audit_trail.unreadable-{datetime.now():%Y%m%d-%H%M%S}.json"))
    return []


def append(entry: AuditEntry) -> None:
    """Add one entry. Never raises: a failed audit write is reported on stderr instead of stopping the agents."""
    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _lock, open(AUDIT_PATH.with_name(".audit_trail.lock"), "w") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            entries = _read()
            entries.append(entry.model_dump(mode="json"))
            tmp = AUDIT_PATH.with_name(".audit_trail.json.tmp")
            tmp.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(tmp, AUDIT_PATH)
    except Exception as exc:  # the audit must never crash a ticket run
        import sys
        print(f"Warning: audit write failed: {exc}", file=sys.stderr)
