from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal  # noqa: E402
from app.user_maintenance import merge_duplicate_users_by_identity  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge duplicate users by normalized email or phone.")
    parser.add_argument("--apply", action="store_true", help="Apply changes. Without this flag the command is dry-run only.")
    parser.add_argument(
        "--identity",
        default="",
        help="Optional filter, for example cage_ben@sina.com or 18800001111.",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        summary = merge_duplicate_users_by_identity(db, apply=args.apply, identity_filter=args.identity)
        if args.apply:
            db.commit()
        else:
            db.rollback()

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    if not args.apply and summary["mergedUsers"]:
        print("\nDry-run only. Re-run with --apply to merge these users.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    os.chdir(ROOT)
    raise SystemExit(main())
