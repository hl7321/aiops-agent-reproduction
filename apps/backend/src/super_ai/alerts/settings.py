"""只从本地 JSON 深合并结果加载告警与 CLS 日志配置。"""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from super_ai.project_config import ProjectConfigError, load_project_config

AlertSourceType = Literal["prometheus-v1", "alertmanager-v2"]


class BasicAuthSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AlertSourceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    name: str = Field(min_length=1)
    source_type: AlertSourceType = Field(alias="type")
    base_url: str = Field(alias="baseUrl")
    timeout_seconds: float = Field(alias="timeoutSeconds", gt=0, le=300)
    basic_auth: BasicAuthSettings | None = Field(default=None, alias="basicAuth")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("source name 不能为空")
        return normalized

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("source baseUrl 必须是 HTTP(S) URL")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("source baseUrl 禁止 userinfo")
        return normalized


class PrometheusAlertsSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sources: tuple[AlertSourceSettings, ...] = ()

    @model_validator(mode="after")
    def validate_unique_names(self) -> PrometheusAlertsSettings:
        names = [source.name for source in self.sources]
        if len(set(names)) != len(names):
            raise ValueError("source name 必须唯一")
        return self


class ClsLogUploadSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    endpoint: str = ""
    region: str = ""
    logset_id: str = Field(default="", alias="logsetId")
    topic_id: str = Field(default="", alias="topicId")
    secret_id: str = Field(default="", alias="secretId")
    secret_key: str = Field(default="", alias="secretKey")

    def require_upload_ready(self) -> ClsLogUploadSettings:
        values = (self.endpoint, self.region, self.topic_id, self.secret_id, self.secret_key)
        if any(not value.strip() for value in values):
            raise ProjectConfigError("clsLogUpload 配置不完整")
        parsed = urlsplit(self.endpoint.strip())
        unsafe = (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or bool(parsed.query)
            or bool(parsed.fragment)
        )
        if unsafe:
            raise ProjectConfigError("clsLogUpload endpoint 配置无效")
        return self


def load_alert_settings(project_path: Path, user_path: Path) -> PrometheusAlertsSettings:
    merged = load_project_config(project_path, user_path)
    raw = merged.get("prometheusAlerts", {})
    try:
        return PrometheusAlertsSettings.model_validate(raw)
    except ValidationError as error:
        raise ProjectConfigError("prometheusAlerts 配置校验失败") from error


def load_cls_log_upload_settings(project_path: Path, user_path: Path) -> ClsLogUploadSettings:
    merged = load_project_config(project_path, user_path)
    raw = merged.get("clsLogUpload", {})
    try:
        return ClsLogUploadSettings.model_validate(raw)
    except ValidationError as error:
        raise ProjectConfigError("clsLogUpload 配置校验失败") from error
