from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UserOut(BaseModel):
    id: str
    externalUserId: str
    email: str
    phone: str
    nickname: str
    avatarUrl: str


class DevLoginRequest(BaseModel):
    externalUserId: str = "dev-user"
    email: str = "dev@genstudio.local"
    nickname: str = "开发用户"
    phone: str = ""
    avatarUrl: str = ""


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


class SubModelOut(BaseModel):
    id: str
    modelName: str
    displayName: str
    capability: str
    adapter: str
    isPrimary: bool
    status: str


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
    subModels: list[SubModelOut] = Field(default_factory=list)


class SyncModelsResult(BaseModel):
    model: ModelOut
    models: list[str]
    durationMs: int
    raw: dict[str, Any]


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
