from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db_models import (
    AdminOperationLog,
    CreditPricingRule,
    CreditTransaction,
    ModelGroup,
    SubModel,
    SystemSetting,
    User,
    UserCreditAccount,
    new_id,
    utcnow,
)


CAPABILITIES = ("text", "image", "video")
DEFAULT_CAPABILITY_PRICES = {"text": 0, "image": 1, "video": 0}
SIGNUP_BONUS_ENABLED_KEY = "signup_bonus_enabled"
SIGNUP_BONUS_AMOUNT_KEY = "signup_bonus_amount"


@dataclass(frozen=True)
class CreditPriceEstimate:
    enabled: bool
    price: int
    source: str
    capability: str
    model_group_id: str = ""
    sub_model_id: str = ""


def json_dumps_safe(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def parse_json_object(value: str, fallback: Any) -> Any:
    try:
        parsed = json.loads(value or "")
    except Exception:
        return fallback
    return parsed if isinstance(parsed, type(fallback)) else fallback


def _coerce_non_negative_int(value: Any, field: str = "积分") -> int:
    try:
        amount = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail={"message": f"{field}必须是整数。"})
    if amount < 0:
        raise HTTPException(status_code=400, detail={"message": f"{field}不能为负数。"})
    return amount


def _normalize_capability(capability: str) -> str:
    clean = (capability or "").strip().lower()
    if clean not in CAPABILITIES:
        raise HTTPException(status_code=400, detail={"message": "不支持的创作类型。"})
    return clean


def get_or_create_credit_account(db: Session, user_id: str) -> UserCreditAccount:
    account = db.query(UserCreditAccount).filter(UserCreditAccount.user_id == user_id).first()
    if account:
        return account
    account = UserCreditAccount(user_id=user_id)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _get_capability_rule(db: Session, capability: str) -> CreditPricingRule | None:
    return (
        db.query(CreditPricingRule)
        .filter(
            CreditPricingRule.scope == "capability_default",
            CreditPricingRule.capability == capability,
            CreditPricingRule.model_group_id == "",
            CreditPricingRule.sub_model_id == "",
        )
        .first()
    )


def ensure_default_pricing_rules(db: Session) -> None:
    changed = False
    for capability, price in DEFAULT_CAPABILITY_PRICES.items():
        if _get_capability_rule(db, capability):
            continue
        db.add(
            CreditPricingRule(
                scope="capability_default",
                capability=capability,
                price=price,
                enabled=True,
            )
        )
        changed = True
    if changed:
        db.commit()


def set_capability_price(db: Session, capability: str, price: int, *, admin: User | None = None) -> CreditPricingRule:
    clean_capability = _normalize_capability(capability)
    clean_price = _coerce_non_negative_int(price, "积分价格")
    rule = _get_capability_rule(db, clean_capability)
    if not rule:
        rule = CreditPricingRule(scope="capability_default", capability=clean_capability)
        db.add(rule)
    rule.price = clean_price
    rule.enabled = True
    rule.updated_by = admin.id if admin else ""
    if admin and not rule.created_by:
        rule.created_by = admin.id
    db.commit()
    db.refresh(rule)
    return rule


def _get_model_rule(db: Session, model_group_id: str) -> CreditPricingRule | None:
    return (
        db.query(CreditPricingRule)
        .filter(
            CreditPricingRule.scope == "model_override",
            CreditPricingRule.model_group_id == model_group_id,
            CreditPricingRule.sub_model_id == "",
        )
        .first()
    )


def set_model_price(db: Session, admin: User, model_group_id: str, price: int) -> CreditPricingRule:
    clean_price = _coerce_non_negative_int(price, "积分价格")
    model = db.get(ModelGroup, model_group_id)
    if not model:
        raise HTTPException(status_code=404, detail={"message": "模型不存在。"})
    rule = _get_model_rule(db, model_group_id)
    if not rule:
        rule = CreditPricingRule(
            scope="model_override",
            capability=model.capability,
            model_group_id=model_group_id,
            created_by=admin.id,
        )
        db.add(rule)
    rule.capability = model.capability
    rule.price = clean_price
    rule.enabled = True
    rule.updated_by = admin.id
    db.commit()
    db.refresh(rule)
    return rule


def clear_model_price(db: Session, admin: User, model_group_id: str) -> None:
    rule = _get_model_rule(db, model_group_id)
    if not rule:
        return
    rule.enabled = False
    rule.updated_by = admin.id
    db.commit()


def get_setting(db: Session, key: str, default: str = "") -> str:
    item = db.get(SystemSetting, key)
    return item.value if item else default


def set_setting(db: Session, key: str, value: str, *, admin: User | None = None) -> SystemSetting:
    item = db.get(SystemSetting, key)
    if not item:
        item = SystemSetting(key=key)
        db.add(item)
    item.value = value
    item.updated_by = admin.id if admin else ""
    db.commit()
    db.refresh(item)
    return item


def get_credit_settings(db: Session) -> dict[str, Any]:
    ensure_default_pricing_rules(db)
    defaults = {
        capability: (_get_capability_rule(db, capability).price if _get_capability_rule(db, capability) else DEFAULT_CAPABILITY_PRICES[capability])
        for capability in CAPABILITIES
    }
    return {
        "defaults": defaults,
        "signupBonusEnabled": get_setting(db, SIGNUP_BONUS_ENABLED_KEY, "false").lower() == "true",
        "signupBonusAmount": int(get_setting(db, SIGNUP_BONUS_AMOUNT_KEY, "0") or "0"),
    }


def update_credit_settings(
    db: Session,
    admin: User,
    *,
    defaults: dict[str, Any] | None = None,
    signup_bonus_enabled: bool | None = None,
    signup_bonus_amount: Any | None = None,
) -> dict[str, Any]:
    if defaults:
        for capability, price in defaults.items():
            set_capability_price(db, str(capability), int(price), admin=admin)
    if signup_bonus_enabled is not None:
        set_setting(db, SIGNUP_BONUS_ENABLED_KEY, "true" if signup_bonus_enabled else "false", admin=admin)
    if signup_bonus_amount is not None:
        set_setting(db, SIGNUP_BONUS_AMOUNT_KEY, str(_coerce_non_negative_int(signup_bonus_amount, "注册送积分")), admin=admin)
    write_credit_admin_log(
        db,
        admin,
        action="update_credit_settings",
        target_type="credit_settings",
        summary=get_credit_settings(db),
    )
    return get_credit_settings(db)


def estimate_credit_price(
    db: Session,
    *,
    user: User | None,
    capability: str,
    model_group: ModelGroup | None,
    sub_model: SubModel | None,
) -> CreditPriceEstimate:
    clean_capability = _normalize_capability(capability)
    model_group_id = model_group.id if model_group else ""
    sub_model_id = sub_model.id if sub_model else ""
    if not model_group or not model_group.is_public:
        return CreditPriceEstimate(
            enabled=False,
            price=0,
            source="private_model",
            capability=clean_capability,
            model_group_id=model_group_id,
            sub_model_id=sub_model_id,
        )
    model_rule = _get_model_rule(db, model_group.id)
    if model_rule and model_rule.enabled:
        return CreditPriceEstimate(
            enabled=model_rule.price > 0,
            price=model_rule.price,
            source="model_override",
            capability=clean_capability,
            model_group_id=model_group.id,
            sub_model_id=sub_model_id,
        )
    ensure_default_pricing_rules(db)
    default_rule = _get_capability_rule(db, clean_capability)
    price = default_rule.price if default_rule and default_rule.enabled else DEFAULT_CAPABILITY_PRICES[clean_capability]
    return CreditPriceEstimate(
        enabled=price > 0,
        price=price,
        source="capability_default",
        capability=clean_capability,
        model_group_id=model_group.id,
        sub_model_id=sub_model_id,
    )


def write_credit_admin_log(
    db: Session,
    admin: User,
    *,
    action: str,
    target_type: str,
    target_id: str = "",
    status: str = "success",
    summary: dict[str, Any] | None = None,
) -> AdminOperationLog:
    item = AdminOperationLog(
        admin_user_id=admin.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        status=status,
        summary_json=json_dumps_safe(summary or {}),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _add_transaction(
    db: Session,
    account: UserCreditAccount,
    *,
    transaction_type: str,
    amount: int,
    status: str,
    reason: str = "",
    capability: str = "",
    model_group_id: str = "",
    sub_model_id: str = "",
    conversation_id: str = "",
    message_id: str = "",
    task_id: str = "",
    related_transaction_id: str = "",
    operator_user_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> CreditTransaction:
    transaction = CreditTransaction(
        user_id=account.user_id,
        type=transaction_type,
        amount=amount,
        balance_after=account.balance,
        reserved_after=account.reserved_balance,
        capability=capability,
        model_group_id=model_group_id,
        sub_model_id=sub_model_id,
        conversation_id=conversation_id,
        message_id=message_id,
        task_id=task_id,
        related_transaction_id=related_transaction_id,
        status=status,
        reason=reason,
        operator_user_id=operator_user_id,
        metadata_json=json_dumps_safe(metadata or {}),
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def admin_adjust_credits(db: Session, *, admin: User, target_user: User, amount: int, reason: str) -> CreditTransaction:
    clean_reason = reason.strip()
    if not clean_reason:
        raise HTTPException(status_code=400, detail={"message": "请填写积分调整原因。"})
    try:
        clean_amount = int(amount)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail={"message": "积分调整数量必须是整数。"})
    if clean_amount == 0:
        raise HTTPException(status_code=400, detail={"message": "积分调整数量不能为 0。"})
    account = get_or_create_credit_account(db, target_user.id)
    if account.balance + clean_amount < 0:
        raise HTTPException(status_code=400, detail={"message": "用户积分不足，不能扣成负数。"})
    account.balance += clean_amount
    if clean_amount > 0:
        account.total_recharged += clean_amount
    account.updated_at = utcnow()
    db.commit()
    db.refresh(account)
    transaction = _add_transaction(
        db,
        account,
        transaction_type="admin_adjustment",
        amount=clean_amount,
        status="succeeded",
        reason=clean_reason,
        operator_user_id=admin.id,
    )
    write_credit_admin_log(
        db,
        admin,
        action="adjust_credits",
        target_type="user",
        target_id=target_user.id,
        summary={"amount": clean_amount, "reason": clean_reason, "balance": account.balance},
    )
    return transaction


def grant_signup_bonus(db: Session, user: User) -> CreditTransaction | None:
    settings = get_credit_settings(db)
    amount = int(settings.get("signupBonusAmount") or 0)
    if not settings.get("signupBonusEnabled") or amount <= 0:
        get_or_create_credit_account(db, user.id)
        return None
    existing = (
        db.query(CreditTransaction.id)
        .filter(
            CreditTransaction.user_id == user.id,
            CreditTransaction.type == "signup_bonus",
        )
        .first()
    )
    if existing:
        get_or_create_credit_account(db, user.id)
        return None
    account = get_or_create_credit_account(db, user.id)
    account.balance += amount
    account.total_recharged += amount
    account.updated_at = utcnow()
    db.commit()
    db.refresh(account)
    return _add_transaction(
        db,
        account,
        transaction_type="signup_bonus",
        amount=amount,
        status="succeeded",
        reason="注册送积分",
    )


def reserve_generation_credits(
    db: Session,
    *,
    user: User,
    capability: str,
    price: int,
    model_group_id: str = "",
    sub_model_id: str = "",
    conversation_id: str = "",
    message_id: str = "",
    task_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> CreditTransaction | None:
    clean_price = _coerce_non_negative_int(price, "积分价格")
    if clean_price == 0:
        return None
    account = get_or_create_credit_account(db, user.id)
    if account.balance < clean_price:
        raise HTTPException(status_code=402, detail={"message": "积分不足，请充值后再生成。"})
    account.balance -= clean_price
    account.reserved_balance += clean_price
    account.updated_at = utcnow()
    db.commit()
    db.refresh(account)
    return _add_transaction(
        db,
        account,
        transaction_type="generation_reserve",
        amount=-clean_price,
        status="reserved",
        reason="生成任务预扣积分",
        capability=_normalize_capability(capability),
        model_group_id=model_group_id,
        sub_model_id=sub_model_id,
        conversation_id=conversation_id,
        message_id=message_id,
        task_id=task_id,
        metadata=metadata,
    )


def _related_transaction_exists(db: Session, reserve_id: str, transaction_type: str) -> bool:
    return (
        db.query(CreditTransaction.id)
        .filter(
            CreditTransaction.related_transaction_id == reserve_id,
            CreditTransaction.type == transaction_type,
        )
        .first()
        is not None
    )


def capture_generation_credits(db: Session, reserve_transaction_id: str) -> CreditTransaction | None:
    reserve = db.get(CreditTransaction, reserve_transaction_id)
    if not reserve or reserve.type != "generation_reserve":
        return None
    if reserve.status == "captured" or _related_transaction_exists(db, reserve.id, "generation_capture"):
        return None
    if reserve.status == "refunded" or _related_transaction_exists(db, reserve.id, "generation_refund"):
        return None
    account = get_or_create_credit_account(db, reserve.user_id)
    reserved_amount = abs(reserve.amount)
    account.reserved_balance = max(0, account.reserved_balance - reserved_amount)
    account.total_spent += reserved_amount
    account.updated_at = utcnow()
    reserve.status = "captured"
    db.commit()
    db.refresh(account)
    db.refresh(reserve)
    return _add_transaction(
        db,
        account,
        transaction_type="generation_capture",
        amount=0,
        status="succeeded",
        reason="生成任务成功确认消费",
        capability=reserve.capability,
        model_group_id=reserve.model_group_id,
        sub_model_id=reserve.sub_model_id,
        conversation_id=reserve.conversation_id,
        message_id=reserve.message_id,
        task_id=reserve.task_id,
        related_transaction_id=reserve.id,
    )


def refund_generation_credits(db: Session, reserve_transaction_id: str, *, reason: str = "生成失败自动退款") -> CreditTransaction | None:
    reserve = db.get(CreditTransaction, reserve_transaction_id)
    if not reserve or reserve.type != "generation_reserve":
        return None
    if reserve.status == "refunded" or _related_transaction_exists(db, reserve.id, "generation_refund"):
        return None
    if reserve.status == "captured" or _related_transaction_exists(db, reserve.id, "generation_capture"):
        return None
    account = get_or_create_credit_account(db, reserve.user_id)
    reserved_amount = abs(reserve.amount)
    account.balance += reserved_amount
    account.reserved_balance = max(0, account.reserved_balance - reserved_amount)
    account.total_refunded += reserved_amount
    account.updated_at = utcnow()
    reserve.status = "refunded"
    db.commit()
    db.refresh(account)
    db.refresh(reserve)
    return _add_transaction(
        db,
        account,
        transaction_type="generation_refund",
        amount=reserved_amount,
        status="succeeded",
        reason=reason,
        capability=reserve.capability,
        model_group_id=reserve.model_group_id,
        sub_model_id=reserve.sub_model_id,
        conversation_id=reserve.conversation_id,
        message_id=reserve.message_id,
        task_id=reserve.task_id,
        related_transaction_id=reserve.id,
    )


def find_reserved_transaction(
    db: Session,
    *,
    transaction_id: str = "",
    task_id: str = "",
    conversation_id: str = "",
    message_id: str = "",
) -> CreditTransaction | None:
    if transaction_id:
        item = db.get(CreditTransaction, transaction_id)
        if item and item.type == "generation_reserve":
            return item
    query = db.query(CreditTransaction).filter(CreditTransaction.type == "generation_reserve")
    if task_id:
        query = query.filter(CreditTransaction.task_id == task_id)
    if conversation_id:
        query = query.filter(CreditTransaction.conversation_id == conversation_id)
    if message_id:
        query = query.filter(CreditTransaction.message_id == message_id)
    return query.order_by(CreditTransaction.created_at.desc()).first()


def update_reserved_transaction_refs(
    db: Session,
    reserve: CreditTransaction | None,
    *,
    conversation_id: str = "",
    message_id: str = "",
    task_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> CreditTransaction | None:
    if not reserve:
        return None
    if conversation_id:
        reserve.conversation_id = conversation_id
    if message_id:
        reserve.message_id = message_id
    if task_id:
        reserve.task_id = task_id
    if metadata is not None:
        existing = parse_json_object(reserve.metadata_json, {})
        if not isinstance(existing, dict):
            existing = {}
        existing.update(metadata)
        reserve.metadata_json = json_dumps_safe(existing)
    db.commit()
    db.refresh(reserve)
    return reserve


def list_credit_transactions(
    db: Session,
    *,
    user_id: str = "",
    limit: int = 50,
) -> list[CreditTransaction]:
    query = db.query(CreditTransaction)
    if user_id:
        query = query.filter(CreditTransaction.user_id == user_id)
    return query.order_by(CreditTransaction.created_at.desc()).limit(min(max(limit, 1), 200)).all()


def serialize_credit_account(account: UserCreditAccount | None) -> dict[str, Any] | None:
    if not account:
        return None
    return {
        "id": account.id,
        "userId": account.user_id,
        "balance": account.balance,
        "reservedBalance": account.reserved_balance,
        "totalRecharged": account.total_recharged,
        "totalSpent": account.total_spent,
        "totalRefunded": account.total_refunded,
        "createdAt": account.created_at,
        "updatedAt": account.updated_at,
    }


def serialize_credit_transaction(item: CreditTransaction) -> dict[str, Any]:
    return {
        "id": item.id,
        "userId": item.user_id,
        "type": item.type,
        "amount": item.amount,
        "balanceAfter": item.balance_after,
        "reservedAfter": item.reserved_after,
        "capability": item.capability,
        "modelGroupId": item.model_group_id,
        "subModelId": item.sub_model_id,
        "conversationId": item.conversation_id,
        "messageId": item.message_id,
        "taskId": item.task_id,
        "relatedTransactionId": item.related_transaction_id,
        "status": item.status,
        "reason": item.reason,
        "operatorUserId": item.operator_user_id,
        "metadata": parse_json_object(item.metadata_json, {}),
        "createdAt": item.created_at,
    }


def serialize_price_estimate(estimate: CreditPriceEstimate) -> dict[str, Any]:
    return {
        "enabled": estimate.enabled,
        "price": estimate.price,
        "source": estimate.source,
        "capability": estimate.capability,
        "modelGroupId": estimate.model_group_id,
        "subModelId": estimate.sub_model_id,
    }
