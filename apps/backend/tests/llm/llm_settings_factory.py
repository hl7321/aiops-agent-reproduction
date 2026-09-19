from super_ai.llm.config import LlmSettings


def make_settings(
    api_key: str = "test-api-key",
    chat_model: str = "qwen3.7-max",
    chat_base_url: str = "",
    chat_api_key: str = "",
) -> LlmSettings:
    capabilities: dict[str, dict[str, int]] = {
        "qwen3.7-max": {"contextWindowTokens": 262144},
        "qwen-next": {"contextWindowTokens": 131072},
    }
    # 换 chat 模型时规格要求必须登记上下文窗口，这里让任意模型名都能拿到一条登记。
    capabilities.setdefault(chat_model, {"contextWindowTokens": 65536})
    return LlmSettings.model_validate({
        "llm": {
            "provider": "qwen-openai",
            "apiKey": api_key,
            "baseUrl": "https://dashscope.example/compatible-mode/v1",
            "chat": {
                "model": chat_model,
                "temperature": 0.2,
                "timeoutSeconds": 120,
                "maxRetries": 2,
                "baseUrl": chat_base_url,
                "apiKey": chat_api_key,
            },
            "embedding": {
                "model": "text-embedding-v4",
                "dimensions": 1024,
                "batchSize": 10,
                "timeoutSeconds": 120,
                "maxRetries": 2,
            },
            "rerank": {
                "model": "qwen3-vl-rerank",
                "endpoint": "https://dashscope.example/api/v1/services/rerank",
                "timeoutSeconds": 120,
                "maxRetries": 2,
            },
        },
        "modelCapabilities": capabilities,
    })
