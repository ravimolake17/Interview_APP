from __future__ import annotations

import argparse
from pathlib import Path

from agents.proctoring_agent.config import get_settings
from agents.proctoring_agent.db import SessionLocal, init_db
from agents.proctoring_agent.services.retention import purge_expired


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Agent5 local data-retention policy")
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--best-effort-overwrite", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    days = settings.retention_days if args.days is None else args.days
    if days < 1:
        raise SystemExit("retention days must be at least 1")
    init_db()
    with SessionLocal() as db:
        deleted = purge_expired(db, settings.resolved_storage_dir, days, overwrite=args.best_effort_overwrite)
    print(f"Deleted {len(deleted)} expired session(s).")
    for session_id in deleted:
        print(session_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
