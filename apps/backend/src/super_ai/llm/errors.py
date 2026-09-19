"""模型配置和 provider 边界的安全错误。"""


class ModelConfigurationError(ValueError):
    """本地模型配置无效且错误消息不包含配置 input。"""


class ModelProviderError(RuntimeError):
    """已在 provider 边界脱敏的外部模型调用错误。"""


def sanitize_exception(error: Exception, *api_keys: str) -> ModelProviderError:
    """精确替换本次调用涉及的全部 API key，不附加配置或 headers。

    接受多把 key 是因为 chat 可以配置独立凭据：一次 chat 失败时，
    生效 key 与顶层 key 都需要替换掉，避免另一把凭据从错误文本里漏出去。
    """
    message = str(error) or type(error).__name__
    for api_key in api_keys:
        if api_key:
            message = message.replace(api_key, "[redacted]")
    return ModelProviderError(message)
