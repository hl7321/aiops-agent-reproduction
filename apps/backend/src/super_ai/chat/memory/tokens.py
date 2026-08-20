"""纯 LangChain 上下文 token 估算。"""

from collections.abc import Sequence

from langchain_core.messages import BaseMessage
from langchain_core.messages.utils import count_tokens_approximately


def estimate_context_tokens(messages: Sequence[BaseMessage]) -> int:
    """估算一次模型输入；不读取配置、不创建 client。"""
    result = count_tokens_approximately(messages)
    if result < 0:
        raise ValueError("token estimator 不得返回负数")
    return result
