from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class UserOut(BaseModel):
    id: str
    externalUserId: str
    email: str
    phone: str
    nickname: str
    avatarUrl: str
    isAdmin: bool = False


class DevLoginRequest(BaseModel):
    externalUserId: str = "dev-user"
    email: str = "dev@genstudio.local"
    nickname: str = "开发用户"
    phone: str = ""
    avatarUrl: str = ""


class RegisterRequest(BaseModel):
    email: str = ""
    phone: str = ""
    password: str
    nickname: str = ""

    @field_validator("email", "phone", "nickname")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("密码至少需要 8 位。")
        if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
            raise ValueError("密码需要同时包含字母和数字。")
        return value

    @model_validator(mode="after")
    def validate_identifier(self) -> RegisterRequest:
        if not self.email and not self.phone:
            raise ValueError("请填写邮箱或手机号。")
        return self


class LoginRequest(BaseModel):
    identifier: str
    password: str

    @field_validator("identifier")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        return value.strip().lower()


class ProfileUpdateRequest(BaseModel):
    nickname: str | None = None
    phone: str | None = None
    avatarUrl: str | None = None

    @field_validator("nickname", "phone", "avatarUrl")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class ApiKeyCreate(BaseModel):
    name: str
    baseUrl: str
    apiKey: str


class ApiKeyOut(BaseModel):
    id: str
    name: str
    baseUrl: str
    status: str
    createdAt: datetime


class CatalogParameterOptionOut(BaseModel):
    id: str
    optionName: str
    optionValue: str
    description: str
    maxCount: int | None = None
    isDefault: bool
    sortOrder: int
    priceFactor: str


class CatalogParameterOut(BaseModel):
    id: str
    displayName: str
    paramKey: str
    description: str
    widgetType: int
    isRequired: bool
    defaultValue: str
    functionTag: str
    maxCount: int | None = None
    sortOrder: int
    options: list[CatalogParameterOptionOut] = Field(default_factory=list)


class CatalogChannelGroupOut(BaseModel):
    id: str
    channelId: str
    groupName: str
    billingType: int
    inputTokenPrice: str
    outputTokenPrice: str
    basePrice: str
    successRate24h: str
    avgResponseSeconds24h: str
    totalSuccessCount: str
    totalFailCount: str
    sortOrder: int
    optionPrices: list[dict[str, Any]] = Field(default_factory=list)


class CatalogModelOut(BaseModel):
    id: str
    displayName: str
    modelName: str
    modelType: int
    capability: str
    icon: str
    description: str
    inputHint: str
    successRate: str
    source: str
    parameters: list[CatalogParameterOut] = Field(default_factory=list)
    channelGroups: list[CatalogChannelGroupOut] = Field(default_factory=list)


class SubModelOut(BaseModel):
    id: str
    modelName: str
    displayName: str
    capability: str
    adapter: str
    isPrimary: bool
    status: str
    catalogModelId: str | None = None
    catalog: CatalogModelOut | None = None


class ModelCreate(BaseModel):
    name: str
    vendor: str = ""
    capability: str
    adapter: str
    description: str = ""
    baseUrl: str
    apiKey: str
    primaryModelName: str
    availableModelNames: list[str] = Field(default_factory=list)
    catalogModelId: str | None = None
    isPublic: bool = False


class ModelUpdate(BaseModel):
    name: str | None = None
    vendor: str | None = None
    capability: str | None = None
    adapter: str | None = None
    description: str | None = None
    baseUrl: str | None = None
    apiKey: str | None = None
    primaryModelName: str | None = None
    availableModelNames: list[str] | None = None
    catalogModelId: str | None = None
    isPublic: bool | None = None


class ModelOut(BaseModel):
    id: str
    name: str
    vendor: str
    capability: str
    adapter: str
    description: str
    apiKeyId: str
    baseUrl: str
    primarySubModelId: str
    primaryModelName: str
    isPublic: bool
    canEdit: bool
    catalogModelId: str | None = None
    catalog: CatalogModelOut | None = None
    subModels: list[SubModelOut] = Field(default_factory=list)
    publicDisplayName: str = ""
    publicDescription: str = ""
    inputHint: str = ""
    iconUrl: str = ""
    publicTags: list[str] = Field(default_factory=list)
    promptOptimizeEnabled: bool = True
    defaultParameters: dict[str, Any] = Field(default_factory=dict)


class AdminModelUpdate(BaseModel):
    publicDisplayName: str | None = None
    publicDescription: str | None = None
    inputHint: str | None = None
    iconUrl: str | None = None
    publicTags: list[str] | None = None
    promptOptimizeEnabled: bool | None = None
    defaultParameters: dict[str, Any] | None = None
    isPublic: bool | None = None


class PromptTemplateOut(BaseModel):
    id: str
    capability: str
    modelGroupId: str
    templateType: str
    name: str
    content: str
    enabled: bool
    updatedBy: str
    createdAt: datetime
    updatedAt: datetime


class PromptTemplateUpdate(BaseModel):
    capability: str | None = None
    modelGroupId: str | None = None
    templateType: str | None = None
    name: str | None = None
    content: str | None = None
    enabled: bool | None = None


class AdminUserOut(BaseModel):
    id: str
    externalUserId: str
    email: str
    phone: str
    nickname: str
    avatarUrl: str
    status: str
    isAdmin: bool
    createdAt: datetime
    updatedAt: datetime


class AdminUserUpdate(BaseModel):
    email: str | None = None
    phone: str | None = None
    nickname: str | None = None
    avatarUrl: str | None = None
    status: str | None = None


class AdminOverviewOut(BaseModel):
    totalCalls: int
    successCalls: int
    failedCalls: int
    failureRate: float
    averageDurationMs: int
    publicModelCalls: int
    privateModelCalls: int


class AdminCreationAssetOut(BaseModel):
    type: str
    url: str
    thumbnailUrl: str = ""


class AdminCreationRecordOut(BaseModel):
    id: str
    user: AdminUserOut | None = None
    modelName: str
    capability: str
    status: str
    prompt: str
    response: str
    createdAt: datetime
    durationMs: int = 0
    taskId: str = ""
    assets: list[AdminCreationAssetOut] = Field(default_factory=list)
    requestParams: dict[str, Any] = Field(default_factory=dict)
    responseSummary: dict[str, Any] = Field(default_factory=dict)
    errorMessage: str = ""


class AdminAuditLogOut(BaseModel):
    id: str
    adminUserId: str | None = None
    action: str
    targetType: str
    targetId: str
    status: str
    summary: dict[str, Any] = Field(default_factory=dict)
    createdAt: datetime


class KkyiCatalogSyncRequest(BaseModel):
    bearerToken: str = ""
    modelType: int = 0


class KkyiCatalogSyncResult(BaseModel):
    synced: int
    models: list[CatalogModelOut]


class SyncModelsResult(BaseModel):
    model: ModelOut
    models: list[str]
    durationMs: int
    raw: dict[str, Any]


class PromptOptimizeRequest(BaseModel):
    capability: str = "text"
    prompt: str
    keywords: str = ""
    subModelId: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    referenceCount: int = 0

    @field_validator("capability")
    @classmethod
    def normalize_capability(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"text", "image", "video"}:
            raise ValueError("不支持的创作类型。")
        return normalized

    @field_validator("prompt", "keywords")
    @classmethod
    def trim_prompt_text(cls, value: str) -> str:
        return value.strip()


class PromptOptimizeResult(BaseModel):
    prompt: str
    raw: dict[str, Any] = Field(default_factory=dict)


class CallLogOut(BaseModel):
    id: str
    capability: str
    endpoint: str
    status: str
    durationMs: int
    promptSummary: str
    errorMessage: str
    createdAt: datetime


class ConversationCreate(BaseModel):
    title: str = ""
    capability: str = "text"
    modelGroupId: str | None = None
    subModelId: str | None = None


class GeneratedAssetOut(BaseModel):
    id: str
    capability: str
    assetType: str
    url: str
    thumbnailUrl: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    createdAt: datetime


class ConversationMessageOut(BaseModel):
    id: str
    role: str
    capability: str
    content: str
    status: str
    errorMessage: str
    canRetry: bool
    modelGroupId: str | None
    subModelId: str | None
    assets: list[GeneratedAssetOut] = Field(default_factory=list)
    createdAt: datetime


class ConversationOut(BaseModel):
    id: str
    title: str
    capability: str
    modelGroupId: str | None
    subModelId: str | None
    status: str
    createdAt: datetime
    updatedAt: datetime
    messages: list[ConversationMessageOut] = Field(default_factory=list)
