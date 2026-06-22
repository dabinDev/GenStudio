from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

db_path = os.path.join(tempfile.gettempdir(), "genstudio-admin-dashboard-test.sqlite3")
if os.path.exists(db_path):
    os.remove(db_path)

os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["GENSTUDIO_SECRET_KEY"] = "test-secret"

from app.admin_service import admin_dashboard_metrics
from app.database import Base
from app.db_models import ApiKey, CallLog, Conversation, ConversationMessage, CreditTransaction, GeneratedAsset, ModelGroup, User, utcnow


def make_db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_user(db: Session, email: str, external_id: str) -> User:
    user = User(
        external_user_id=external_id,
        email=email,
        nickname=email.split("@")[0],
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_admin_dashboard_metrics_counts_calls_timeouts_and_reserved_credits() -> None:
    db = make_db()
    user = make_user(db, "user-dashboard@example.com", "user-dashboard")
    admin = make_user(db, "cage_ben@sina.com", "admin-dashboard")
    api_key = ApiKey(
        user_id=admin.id,
        name="Public image key",
        base_url="https://token.example.com",
        api_key_ciphertext="encrypted",
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    model = ModelGroup(
        user_id=admin.id,
        api_key_id=api_key.id,
        name="Image Model",
        vendor="OpenAI",
        capability="image",
        adapter="image-openai",
        description="public image model",
        is_public=True,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    now = utcnow()
    captured_reserve = CreditTransaction(
        user_id=user.id,
        type="generation_reserve",
        amount=-3,
        reserved_after=0,
        capability="image",
        model_group_id=model.id,
        status="captured",
        created_at=now,
    )
    db.add(captured_reserve)
    db.commit()
    db.refresh(captured_reserve)
    db.add_all(
        [
            CallLog(
                user_id=user.id,
                model_group_id=model.id,
                capability="image",
                endpoint="/api/proxy/image",
                status="success",
                duration_ms=900,
                raw_usage_json='{"total_tokens": 12}',
                response_summary_json='{"queueMs": 250}',
                is_public_model=True,
                created_at=now,
            ),
            CallLog(
                user_id=user.id,
                model_group_id=model.id,
                capability="image",
                endpoint="/api/proxy/image",
                status="error",
                duration_ms=130000,
                error_message="timeout",
                raw_usage_json='{"credits": 2}',
                response_summary_json='{"queue_seconds": 1}',
                is_public_model=True,
                created_at=now,
            ),
            CreditTransaction(
                user_id=user.id,
                type="generation_reserve",
                amount=-1,
                reserved_after=1,
                capability="image",
                model_group_id=model.id,
                status="succeeded",
                created_at=now,
            ),
            CreditTransaction(
                user_id=user.id,
                type="generation_capture",
                amount=0,
                reserved_after=0,
                capability="image",
                model_group_id=model.id,
                related_transaction_id=captured_reserve.id,
                status="succeeded",
                created_at=now,
            ),
        ]
    )
    db.commit()

    metrics = admin_dashboard_metrics(db, range_key="30d")

    assert metrics["totals"]["totalCalls"] == 2
    assert metrics["totals"]["failedCalls"] == 1
    assert metrics["totals"]["timeoutCalls"] == 1
    assert metrics["totals"]["averageQueueMs"] == 625
    assert metrics["totals"]["quotaUnits"] == 14
    assert metrics["capabilityBreakdown"][0]["capability"] == "image"
    assert metrics["creditSummary"]["reserved"] == 1
    assert metrics["creditSummary"]["spent"] == 3
    assert metrics["activeUsers"][0]["publicModelCalls"] == 2
    assert metrics["activeUsers"][0]["privateModelCalls"] == 0
    assert "publicCalls" not in metrics["activeUsers"][0]
    assert "privateCalls" not in metrics["activeUsers"][0]


def test_admin_dashboard_trend_day_bucket_count_follows_selected_range() -> None:
    db = make_db()
    user = make_user(db, "range-user@example.com", "range-user")
    db.add(
        CallLog(
            user_id=user.id,
            capability="text",
            endpoint="/api/proxy/text",
            status="success",
            duration_ms=100,
            created_at=utcnow() - timedelta(days=89),
        )
    )
    db.commit()

    metrics = admin_dashboard_metrics(db, range_key="90d")

    assert len(metrics["trends"]["day"]) == 90
    assert metrics["trends"]["day"][0]["totalCalls"] == 1


def test_admin_record_detail_includes_message_assets_and_call_log() -> None:
    from app.admin_service import admin_record_detail

    db = make_db()
    user = make_user(db, "detail@example.com", "detail-user")
    conversation = Conversation(
        user_id=user.id,
        title="Detail conversation",
        capability="image",
        status="active",
    )
    db.add(conversation)
    db.flush()
    message = ConversationMessage(
        conversation_id=conversation.id,
        user_id=user.id,
        role="assistant",
        capability="image",
        content="done",
        status="success",
        request_json='{"prompt":"draw a quiet studio"}',
        response_json='{"taskId":"task_123"}',
    )
    db.add(message)
    db.flush()
    db.add(
        GeneratedAsset(
            user_id=user.id,
            conversation_id=conversation.id,
            message_id=message.id,
            capability="image",
            asset_type="image",
            url="/api/assets/generated/result.png",
        )
    )
    db.add(
        CallLog(
            user_id=user.id,
            capability="image",
            endpoint="/api/proxy/image",
            status="success",
            duration_ms=321,
            message_id=message.id,
            conversation_id=conversation.id,
            response_summary_json='{"taskId":"task_123","status":"completed"}',
        )
    )
    db.commit()

    detail = admin_record_detail(db, message.id)

    assert detail["id"] == message.id
    assert detail["assets"][0]["url"] == "/api/assets/generated/result.png"
    assert detail["timeline"][-1]["status"] == "success"


def test_admin_task_timeline_uses_task_id() -> None:
    from app.admin_service import admin_task_timeline

    db = make_db()
    user = make_user(db, "timeline@example.com", "timeline-user")
    db.add_all(
        [
            CallLog(
                user_id=user.id,
                capability="video",
                endpoint="/api/proxy/video/query",
                status="error",
                duration_ms=456,
                response_summary_json='{"taskId":"task_1","status":"failed"}',
            ),
            CallLog(
                user_id=user.id,
                capability="video",
                endpoint="/api/proxy/video/query",
                status="success",
                duration_ms=123,
                response_summary_json='{"taskId":"task_10","status":"completed"}',
            ),
            CallLog(
                user_id=user.id,
                capability="video",
                endpoint="/api/proxy/video/query",
                status="success",
                duration_ms=222,
                response_summary_json='{"id":"task_1","status":"unrelated"}',
            ),
        ]
    )
    db.commit()

    timeline = admin_task_timeline(db, "task_1")

    assert timeline["taskId"] == "task_1"
    assert len(timeline["events"]) == 1
    assert timeline["events"][0]["status"] == "error"
    assert timeline["events"][0]["responseSummary"]["taskId"] == "task_1"


def test_admin_task_timeline_includes_structured_task_events() -> None:
    from app.admin_service import admin_task_timeline, record_task_event

    db = make_db()
    user = make_user(db, "event-user@example.com", "event-user")

    record_task_event(
        db,
        task_id="task_event_1",
        event_type="submitted",
        status="processing",
        user_id=user.id,
        capability="video",
        endpoint="/api/proxy/video/create",
        message="任务已提交",
        payload={"providerTaskId": "task_event_1"},
    )
    record_task_event(
        db,
        task_id="task_event_1",
        event_type="completed",
        status="success",
        user_id=user.id,
        capability="video",
        endpoint="/api/proxy/video/query",
        duration_ms=4200,
        message="任务完成",
        payload={"videoUrl": "https://cdn.example.com/video.mp4"},
    )
    db.commit()

    timeline = admin_task_timeline(db, "task_event_1")

    assert [event["eventType"] for event in timeline["events"]] == ["submitted", "completed"]
    assert timeline["events"][0]["source"] == "task_event"
    assert timeline["events"][1]["payload"]["videoUrl"] == "https://cdn.example.com/video.mp4"
