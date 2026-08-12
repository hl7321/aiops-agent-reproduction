"""模型配置和 provider 边界的安全错误。"""


class ModelConfigurationError(ValueError):
    """本地模型配置无效且错误消息不包含配置 input。"""


class ModelProviderError(RuntimeError):
    """已在 provider 边界脱敏的外部模型调用错误。"""


def sanitize_exception(error: Exception, api_key: str) -> ModelProviderError:
    """精确替换当前配置 API key 的每次出现，不附加配置或 headers。"""
    message = str(error) or type(error).__name__
    if api_key:
        message = message.replace(api_key, "[redacted]")
    return ModelProviderError(message)
