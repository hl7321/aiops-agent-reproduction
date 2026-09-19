"""只从显式本地 JSON 合并结果构建的模型 typed settings。"""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

from super_ai.llm.errors import ModelConfigurationError
from super_ai.project_config import load_project_config


class _SettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


def _validate_http_url(value: str) -> str:
    normalized = value.strip()
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("必须是 http/https URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL 不得包含凭据")
    return normalized.rstrip("/")


def _blank_to_none(value: object) -> object:
    """模板里必须可提交的空串，语义等于"没有覆盖这一项"。"""
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _validate_optional_http_url(value: str | None) -> str | None:
    return None if value is None else _validate_http_url(value)


class ChatSettings(_SettingsModel):
    model: str = Field(min_length=1)
    temperature: float = Field(ge=0, le=2)
    timeout_seconds: float = Field(alias="timeoutSeconds", gt=0)
    max_retries: int = Field(alias="maxRetries", ge=0, le=10)
    # chat 可以单独指向另一个 OpenAI-compatible 端点与另一把凭据，
    # 例如 chat 用 DeepSeek、embedding 与 rerank 继续留在百炼。
    base_url: str | None = Field(default=None, alias="baseUrl")
    api_key: SecretStr | None = Field(default=None, alias="apiKey")

    _base_url_blank = field_validator("base_url", mode="before")(_blank_to_none)
    _base_url_is_http = field_validator("base_url")(_validate_optional_http_url)
    _api_key_blank = field_validator("api_key", mode="before")(_blank_to_none)


class EmbeddingSettings(_SettingsModel):
    model: Literal["text-embedding-v4"]
    dimensions: Literal[1024]
    batch_size: int = Field(alias="batchSize", ge=1, le=10)
    timeout_seconds: float = Field(alias="timeoutSeconds", gt=0)
    max_retries: int = Field(alias="maxRetries", ge=0, le=10)


class RerankSettings(_SettingsModel):
    model: Literal["qwen3-vl-rerank"]
    endpoint: str
    timeout_seconds: float = Field(alias="timeoutSeconds", gt=0)
    max_retries: int = Field(alias="maxRetries", ge=0, le=10)

    _endpoint_is_http = field_validator("endpoint")(_validate_http_url)


class LlmSection(_SettingsModel):
    # 这是一个部署形态标签，会被写进 readiness 结果；chat 与 embedding/rerank
    # 可能来自不同厂商，所以不能再写死成某一家。
    provider: str = Field(min_length=1)
    api_key: SecretStr = Field(alias="apiKey")
    base_url: str = Field(alias="baseUrl")
    chat: ChatSettings
    embedding: EmbeddingSettings
    rerank: RerankSettings

    _base_url_is_http = field_validator("base_url")(_validate_http_url)


class ModelCapability(_SettingsModel):
    context_window_tokens: int = Field(alias="contextWindowTokens", gt=0)


class LlmSettings(_SettingsModel):
    llm: LlmSection
    model_capabilities: dict[str, ModelCapability] = Field(
        alias="modelCapabilities",
        min_length=1,
    )

    @property
    def provider(self) -> str:
        return self.llm.provider

    @property
    def api_key(self) -> SecretStr:
        return self.llm.api_key

    @property
    def base_url(self) -> str:
        return self.llm.base_url

    @property
    def chat(self) -> ChatSettings:
        return self.llm.chat

    @property
    def embedding(self) -> EmbeddingSettings:
        return self.llm.embedding

    @property
    def rerank(self) -> RerankSettings:
        return self.llm.rerank

    def capability_for_chat(self) -> ModelCapability:
        try:
            return self.model_capabilities[self.chat.model]
        except KeyError as error:
            path = f"modelCapabilities.{self.chat.model}.contextWindowTokens"
            raise ModelConfigurationError(
                f"LLM 配置校验失败: {path}"
                f"（换 chat 模型时需要在 modelCapabilities 里补一条与模型同名的登记）"
            ) from error

    def require_api_key(self) -> str:
        value = self.api_key.get_secret_value().strip()
        if not value:
            raise ModelConfigurationError("llm.apiKey 必须在被忽略的本地 JSON 中配置")
        return value

    def chat_base_url(self) -> str:
        """chat 生效端点：配置了覆盖就用覆盖，否则回退到顶层。"""
        return self.chat.base_url or self.llm.base_url

    def chat_api_key(self) -> str:
        """chat 生效凭据：配置了非空覆盖就用覆盖，否则回退到顶层。"""
        if self.chat.api_key is not None:
            value = self.chat.api_key.get_secret_value().strip()
            if value:
                return value
        return self.require_api_key()

    def chat_redaction_keys(self) -> tuple[str, ...]:
        """chat 分支脱敏用的密钥集合。

        同时收进生效 key 与顶层 key：多替换一层不会有副作用，漏掉一层就是凭据泄露。
        """
        keys: list[str] = []
        for candidate in (self.llm.api_key, self.chat.api_key):
            value = candidate.get_secret_value().strip() if candidate is not None else ""
            if value and value not in keys:
                keys.append(value)
        return tuple(keys)


def load_llm_settings(project_path: Path, user_path: Path) -> LlmSettings:
    """加载显式 JSON 路径并只校验 P06 拥有的 LLM sections。"""
    merged = load_project_config(project_path, user_path)
    candidate = {
        "llm": merged.get("llm"),
        "modelCapabilities": merged.get("modelCapabilities"),
    }
    try:
        settings = LlmSettings.model_validate(candidate)
    except ValidationError as error:
        paths = sorted(
            {
                ".".join(str(item) for item in issue["loc"])
                for issue in error.errors(
                    include_url=False,
                    include_context=False,
                    include_input=False,
                )
            }
        )
        locations = ", ".join(path or "llm" for path in paths)
        raise ModelConfigurationError(f"LLM 配置校验失败: {locations}") from error
    settings.capability_for_chat()
    return settings
