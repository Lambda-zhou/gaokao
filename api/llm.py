from fastapi import APIRouter

from core.llm_client import llm_client
from core.models import LLMRequestConfig

router = APIRouter(prefix="/llm", tags=["llm"])


@router.post("/test")
async def test_llm_config(config: LLMRequestConfig):
    """Validate a user-provided OpenAI-compatible LLM config.

    The API key is only used for this request and is never persisted.
    """
    return llm_client.test_request_config(config)
