"""向量存储配置和生命周期的稳定错误。"""


class VectorStoreError(RuntimeError):
    """不泄露配置凭据的向量存储边界错误。"""


class VectorStoreConfigurationError(VectorStoreError):
    """显式本地 JSON 中的 vectorStore 配置无效。"""


class VectorStoreNotConnectedError(VectorStoreError):
    """需要显式 connect 的操作在连接前被调用。"""


def sanitize_vector_store_exception(error: Exception, secret: str) -> VectorStoreError:
    message = str(error) or type(error).__name__
    if secret:
        message = message.replace(secret, "[redacted]")
    return VectorStoreError(message)
