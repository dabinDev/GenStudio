from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def utcnow() -> datetime:
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("usr"))
    external_user_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    nickname: Mapped[str] = mapped_column(String(128), default="")
    avatar_url: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    sessions: Mapped[list[SessionRecord]] = relationship(back_populates="user", cascade="all, delete-orphan")
    credentials: Mapped[list[UserCredential]] = relationship(back_populates="user", cascade="all, delete-orphan")
    admin_role_assignment: Mapped[AdminRoleAssignment | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )


class SessionRecord(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ses"))
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    client_ip: Mapped[str] = mapped_column(String(64), default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped[User] = relationship(back_populates="sessions")
    csrf_tokens: Mapped[list[SessionCsrfToken]] = relationship(back_populates="session", cascade="all, delete-orphan")


class SessionCsrfToken(Base):
    __tablename__ = "session_csrf_tokens"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("csrf"))
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    session: Mapped[SessionRecord] = relationship(back_populates="csrf_tokens")


class UserCredential(Base):
    __tablename__ = "user_credentials"
    __table_args__ = (UniqueConstraint("provider", "identifier", name="uq_user_credential_provider_identifier"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("cred"))
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="local")
    identifier: Mapped[str] = mapped_column(String(255), index=True)
    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    password_hash: Mapped[str] = mapped_column(String(512), default="")
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_failed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="credentials")


class UserCreditAccount(Base):
    __tablename__ = "user_credit_accounts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("credacct"))
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    reserved_balance: Mapped[int] = mapped_column(Integer, default=0)
    total_recharged: Mapped[int] = mapped_column(Integer, default=0)
    total_spent: Mapped[int] = mapped_column(Integer, default=0)
    total_refunded: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ctxn"))
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    amount: Mapped[int] = mapped_column(Integer, default=0)
    balance_after: Mapped[int] = mapped_column(Integer, default=0)
    reserved_after: Mapped[int] = mapped_column(Integer, default=0)
    capability: Mapped[str] = mapped_column(String(32), default="", index=True)
    model_group_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    sub_model_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    conversation_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    message_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    task_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    related_transaction_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    status: Mapped[str] = mapped_column(String(32), default="succeeded", index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    operator_user_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class CreditPricingRule(Base):
    __tablename__ = "credit_pricing_rules"
    __table_args__ = (
        UniqueConstraint("scope", "capability", "model_group_id", "sub_model_id", name="uq_credit_pricing_scope"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("cprice"))
    scope: Mapped[str] = mapped_column(String(64), index=True)
    capability: Mapped[str] = mapped_column(String(32), default="", index=True)
    model_group_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    sub_model_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    price: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(64), default="", index=True)
    updated_by: Mapped[str] = mapped_column(String(64), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_by: Mapped[str] = mapped_column(String(64), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("key"))
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    base_url: Mapped[str] = mapped_column(String(512))
    api_key_ciphertext: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    model_groups: Mapped[list[ModelGroup]] = relationship(back_populates="api_key")
    sub_models: Mapped[list[SubModel]] = relationship(back_populates="api_key")


class CatalogModel(Base):
    __tablename__ = "catalog_models"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("cat"))
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    model_name: Mapped[str] = mapped_column(String(255), index=True)
    model_type: Mapped[int] = mapped_column(Integer, default=0, index=True)
    capability: Mapped[str] = mapped_column(String(32), default="text", index=True)
    icon: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    input_hint: Mapped[str] = mapped_column(Text, default="")
    success_rate: Mapped[str] = mapped_column(String(32), default="")
    raw_json: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(64), default="kkyi")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    parameters: Mapped[list[CatalogModelParameter]] = relationship(
        back_populates="catalog_model",
        cascade="all, delete-orphan",
        order_by="CatalogModelParameter.sort_order",
    )
    channel_groups: Mapped[list[CatalogModelChannelGroup]] = relationship(
        back_populates="catalog_model",
        cascade="all, delete-orphan",
        order_by="CatalogModelChannelGroup.sort_order",
    )


class CatalogModelParameter(Base):
    __tablename__ = "catalog_model_parameters"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("catp"))
    catalog_model_id: Mapped[str] = mapped_column(String(64), ForeignKey("catalog_models.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(64), default="")
    display_name: Mapped[str] = mapped_column(String(255), default="")
    param_key: Mapped[str] = mapped_column(String(128), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    widget_type: Mapped[int] = mapped_column(Integer, default=0)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    default_value: Mapped[str] = mapped_column(Text, default="")
    function_tag: Mapped[str] = mapped_column(String(128), default="")
    max_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    raw_json: Mapped[str] = mapped_column(Text, default="")

    catalog_model: Mapped[CatalogModel] = relationship(back_populates="parameters")
    options: Mapped[list[CatalogModelParameterOption]] = relationship(
        back_populates="parameter",
        cascade="all, delete-orphan",
        order_by="CatalogModelParameterOption.sort_order",
    )


class CatalogModelParameterOption(Base):
    __tablename__ = "catalog_model_parameter_options"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("cato"))
    parameter_id: Mapped[str] = mapped_column(String(64), ForeignKey("catalog_model_parameters.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(64), default="")
    option_name: Mapped[str] = mapped_column(String(255), default="")
    option_value: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    max_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    price_factor: Mapped[str] = mapped_column(String(64), default="")
    raw_json: Mapped[str] = mapped_column(Text, default="")

    parameter: Mapped[CatalogModelParameter] = relationship(back_populates="options")


class CatalogModelChannelGroup(Base):
    __tablename__ = "catalog_model_channel_groups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("catg"))
    catalog_model_id: Mapped[str] = mapped_column(String(64), ForeignKey("catalog_models.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(64), default="")
    channel_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    group_name: Mapped[str] = mapped_column(String(255), default="")
    billing_type: Mapped[int] = mapped_column(Integer, default=0)
    input_token_price: Mapped[str] = mapped_column(String(64), default="")
    output_token_price: Mapped[str] = mapped_column(String(64), default="")
    base_price: Mapped[str] = mapped_column(String(64), default="")
    success_rate_24h: Mapped[str] = mapped_column(String(64), default="")
    avg_response_seconds_24h: Mapped[str] = mapped_column(String(64), default="")
    total_success_count: Mapped[str] = mapped_column(String(64), default="")
    total_fail_count: Mapped[str] = mapped_column(String(64), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    option_prices_json: Mapped[str] = mapped_column(Text, default="[]")
    raw_json: Mapped[str] = mapped_column(Text, default="")

    catalog_model: Mapped[CatalogModel] = relationship(back_populates="channel_groups")


class ModelGroup(Base):
    __tablename__ = "models"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("mdl"))
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    api_key_id: Mapped[str] = mapped_column(String(64), ForeignKey("api_keys.id", ondelete="CASCADE"), index=True)
    catalog_model_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("catalog_models.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    vendor: Mapped[str] = mapped_column(String(128), default="")
    capability: Mapped[str] = mapped_column(String(32))
    adapter: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    primary_sub_model_id: Mapped[str] = mapped_column(String(64), default="")
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    public_display_name: Mapped[str] = mapped_column(String(255), default="")
    public_description: Mapped[str] = mapped_column(Text, default="")
    input_hint: Mapped[str] = mapped_column(Text, default="")
    icon_url: Mapped[str] = mapped_column(Text, default="")
    public_tags_json: Mapped[str] = mapped_column(Text, default="[]")
    prompt_optimize_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    default_parameters_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    api_key: Mapped[ApiKey] = relationship(back_populates="model_groups")
    catalog_model: Mapped[CatalogModel | None] = relationship()
    sub_models: Mapped[list[SubModel]] = relationship(
        back_populates="model_group",
        cascade="all, delete-orphan",
    )


class SubModel(Base):
    __tablename__ = "sub_models"
    __table_args__ = (UniqueConstraint("model_group_id", "model_name", name="uq_sub_model_group_name"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("sub"))
    model_group_id: Mapped[str] = mapped_column(String(64), ForeignKey("models.id", ondelete="CASCADE"), index=True)
    api_key_id: Mapped[str] = mapped_column(String(64), ForeignKey("api_keys.id", ondelete="CASCADE"), index=True)
    catalog_model_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("catalog_models.id", ondelete="SET NULL"), nullable=True, index=True)
    model_name: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    capability: Mapped[str] = mapped_column(String(32))
    adapter: Mapped[str] = mapped_column(String(64))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    api_key: Mapped[ApiKey] = relationship(back_populates="sub_models")
    model_group: Mapped[ModelGroup] = relationship(back_populates="sub_models")
    catalog_model: Mapped[CatalogModel | None] = relationship()


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    __table_args__ = (
        UniqueConstraint("capability", "model_group_id", "template_type", name="uq_prompt_template_scope"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ptpl"))
    capability: Mapped[str] = mapped_column(String(32), index=True)
    model_group_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    template_type: Mapped[str] = mapped_column(String(64), default="prompt_optimize", index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[str] = mapped_column(String(64), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class PromptTemplateVersion(Base):
    __tablename__ = "prompt_template_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ptv"))
    template_id: Mapped[str] = mapped_column(String(64), ForeignKey("prompt_templates.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String(128), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[str] = mapped_column(String(64), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class AdminOperationLog(Base):
    __tablename__ = "admin_operation_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("alog"))
    admin_user_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str] = mapped_column(String(64), index=True)
    target_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    status: Mapped[str] = mapped_column(String(32), default="success", index=True)
    summary_json: Mapped[str] = mapped_column(Text, default="{}")
    ip_hash: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class AdminRoleAssignment(Base):
    __tablename__ = "admin_role_assignments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("arole"))
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(32), default="viewer", index=True)
    assigned_by: Mapped[str] = mapped_column(String(64), default="", index=True)
    note: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="admin_role_assignment")


class ModelHealthCheck(Base):
    __tablename__ = "model_health_checks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("mhc"))
    model_group_id: Mapped[str] = mapped_column(String(64), ForeignKey("models.id", ondelete="CASCADE"), index=True)
    sub_model_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    admin_user_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(String(512), default="")
    raw_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class TaskEvent(Base):
    __tablename__ = "task_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("tevt"))
    task_id: Mapped[str] = mapped_column(String(128), index=True)
    event_type: Mapped[str] = mapped_column(String(64), default="event", index=True)
    status: Mapped[str] = mapped_column(String(32), default="", index=True)
    capability: Mapped[str] = mapped_column(String(32), default="", index=True)
    endpoint: Mapped[str] = mapped_column(String(128), default="")
    user_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    model_group_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("models.id", ondelete="SET NULL"), nullable=True, index=True)
    sub_model_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("sub_models.id", ondelete="SET NULL"), nullable=True, index=True)
    conversation_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    message_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(String(512), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class CallLog(Base):
    __tablename__ = "call_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("log"))
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    model_group_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("models.id", ondelete="SET NULL"), nullable=True)
    sub_model_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("sub_models.id", ondelete="SET NULL"), nullable=True)
    capability: Mapped[str] = mapped_column(String(32))
    endpoint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    prompt_summary: Mapped[str] = mapped_column(String(512), default="")
    error_message: Mapped[str] = mapped_column(String(512), default="")
    raw_usage_json: Mapped[str] = mapped_column(Text, default="")
    request_params_json: Mapped[str] = mapped_column(Text, default="{}")
    response_summary_json: Mapped[str] = mapped_column(Text, default="{}")
    conversation_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    message_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    is_public_model: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("cnv"))
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    capability: Mapped[str] = mapped_column(String(32), default="text")
    model_group_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("models.id", ondelete="SET NULL"), nullable=True)
    sub_model_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("sub_models.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, index=True)

    messages: Mapped[list[ConversationMessage]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at",
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("msg"))
    conversation_id: Mapped[str] = mapped_column(String(64), ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    model_group_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("models.id", ondelete="SET NULL"), nullable=True)
    sub_model_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("sub_models.id", ondelete="SET NULL"), nullable=True)
    role: Mapped[str] = mapped_column(String(32))
    capability: Mapped[str] = mapped_column(String(32), default="text")
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="success")
    error_message: Mapped[str] = mapped_column(String(512), default="")
    can_retry: Mapped[bool] = mapped_column(Boolean, default=False)
    request_json: Mapped[str] = mapped_column(Text, default="")
    response_json: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    assets: Mapped[list[GeneratedAsset]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
    )


class GeneratedAsset(Base):
    __tablename__ = "generated_assets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ast"))
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str] = mapped_column(String(64), ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[str] = mapped_column(String(64), ForeignKey("conversation_messages.id", ondelete="CASCADE"), index=True)
    capability: Mapped[str] = mapped_column(String(32))
    asset_type: Mapped[str] = mapped_column(String(32))
    url: Mapped[str] = mapped_column(Text)
    thumbnail_url: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    message: Mapped[ConversationMessage] = relationship(back_populates="assets")
