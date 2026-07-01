from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db  # noqa: E402
from app.db_models import User  # noqa: E402
from app.prompt_library_service import import_prompt_scene_templates  # noqa: E402

DEFAULT_SOURCE_PATH = Path("E:/windows/Desktop/yuque_prompt_full_index.js")


def parse_yuque_index_source(source: str) -> dict[str, Any]:
    clean = source.strip()
    if not clean:
        raise ValueError("Yuque prompt index file is empty.")
    if clean.startswith("{"):
        payload = json.loads(clean)
    else:
        match = re.search(r"export\s+const\s+\w+\s*=\s*(\{.*?\})\s*;\s*export\s+default\s+\w+\s*;?\s*$", clean, re.S)
        if not match:
            raise ValueError("Could not find exported Yuque prompt index object.")
        payload = json.loads(match.group(1))
    if not isinstance(payload, dict) or not isinstance(payload.get("prompts"), list):
        raise ValueError("Yuque prompt index must contain a prompts list.")
    return payload


def resolve_admin_user(db, admin_email: str) -> User:
    admin = db.query(User).filter(User.email == admin_email).one_or_none()
    if not admin:
        raise ValueError(f"Admin user not found: {admin_email}")
    return admin


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Yuque image prompt templates into GenStudio.")
    parser.add_argument("--path", default=os.getenv("GENSTUDIO_YUQUE_PROMPT_PATH", str(DEFAULT_SOURCE_PATH)))
    parser.add_argument("--admin-email", default=os.getenv("GENSTUDIO_IMPORT_ADMIN_EMAIL", "cage_ben@sina.com"))
    parser.add_argument("--replace", action="store_true", help="Disable templates missing from the imported file.")
    args = parser.parse_args()

    source_path = Path(args.path)
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    init_db()
    index = parse_yuque_index_source(source_path.read_text(encoding="utf-8"))
    with SessionLocal() as db:
        admin = resolve_admin_user(db, args.admin_email)
        summary = import_prompt_scene_templates(db, admin, index, replace=args.replace)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
