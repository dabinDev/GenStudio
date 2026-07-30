from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.db_models import GeneratedAsset


def test_generated_asset_defaults_to_local_pending() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        asset = GeneratedAsset(
            user_id="user-1",
            conversation_id="conversation-1",
            message_id="message-1",
            capability="image",
            asset_type="image",
            url="/api/assets/generated/result.png",
        )
        db.add(asset)
        db.flush()

        assert asset.storage_status == "local_pending"
        assert asset.local_expires_at is None
        assert asset.size_bytes == 0
        assert asset.sync_attempts == 0
