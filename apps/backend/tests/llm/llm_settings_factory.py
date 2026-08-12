from super_ai.llm.config import LlmSettings


def make_settings(
    api_key: str = "test-api-key",
    chat_model: str = "qwen3.7-max",
) -> LlmSettings:
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
        "modelCapabilities": {
            "qwen3.7-max": {"contextWindowTokens": 262144},
            "qwen-next": {"contextWindowTokens": 131072},
        },
    })
