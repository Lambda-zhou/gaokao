import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional


class OpenAIChatError(RuntimeError):
    """Base error for OpenAI-compatible chat calls."""


class OpenAIChatAuthenticationError(OpenAIChatError):
    """API key/token is missing, expired, or rejected by the provider."""


@dataclass(frozen=True)
class OpenAIChatConfig:
    provider_label: str
    api_key: str
    base_url: str
    model: str
    timeout: int = 40


def normalize_chat_completions_url(base_url: str) -> str:
    """Accept an OpenAI-compatible root ending in /v1 or a full /chat/completions URL."""
    cleaned = (base_url or "").rstrip("/")
    if not cleaned:
        return ""
    if cleaned.endswith("/chat/completions"):
        return cleaned
    return f"{cleaned}/chat/completions"


class OpenAIChatClient:
    """Small dependency-free OpenAI Chat Completions adapter.

    Works with most providers that expose the OpenAI-compatible
    POST /v1/chat/completions contract, including ModelScope, DeepSeek-compatible
    gateways, OpenAI-compatible proxies, and local inference gateways.
    """

    def __init__(self, config: OpenAIChatConfig):
        self.config = OpenAIChatConfig(
            provider_label=config.provider_label or "OpenAI-compatible",
            api_key=(config.api_key or "").strip(),
            base_url=normalize_chat_completions_url(config.base_url),
            model=(config.model or "").strip(),
            timeout=config.timeout,
        )

    def is_available(self) -> bool:
        return bool(self.config.api_key and self.config.base_url and self.config.model)

    def complete(
        self,
        messages: list[dict],
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 3200,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        if not self.is_available():
            raise OpenAIChatError("OpenAI-compatible endpoint is incomplete: api_key/base_url/model are required")

        payload_messages = []
        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})
        payload_messages.extend(messages)
        payload = {
            "model": self.config.model,
            "messages": payload_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if stream_callback:
            payload["stream"] = True
            return self._complete_stream(payload, stream_callback)
        return self._complete_json(payload)

    def test_connection(self) -> dict:
        """Send a tiny chat completion request and return a non-secret diagnostic result."""
        text = self.complete(
            [{"role": "user", "content": "Reply with OK only."}],
            system_prompt="You are a connection test. Reply with OK only.",
            temperature=0,
            max_tokens=16,
        )
        return {
            "ok": True,
            "provider": self.config.provider_label,
            "model": self.config.model,
            "base_url": self.config.base_url,
            "sample": text[:80],
        }

    def _request(self, payload: dict) -> urllib.request.Request:
        return urllib.request.Request(
            self.config.base_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream" if payload.get("stream") else "application/json",
            },
            method="POST",
        )

    def _complete_json(self, payload: dict) -> str:
        try:
            with urllib.request.urlopen(self._request(payload), timeout=self.config.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            self._raise_http_error(e)
        except urllib.error.URLError as e:
            raise OpenAIChatError(f"{self.config.provider_label} API request failed: {e.reason}") from e
        except TimeoutError:
            raise OpenAIChatError(f"{self.config.provider_label} API request timed out after {self.config.timeout}s") from None

        choices = data.get("choices") or []
        if not choices:
            raise OpenAIChatError(f"{self.config.provider_label} API did not return choices: {data}")
        return choices[0].get("message", {}).get("content", "")

    def _complete_stream(self, payload: dict, callback: Callable[[str], None]) -> str:
        pieces: list[str] = []
        try:
            with urllib.request.urlopen(self._request(payload), timeout=self.config.timeout) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or line.startswith(":"):
                        continue
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if line == "[DONE]":
                        break
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {}).get("content") or ""
                    if delta:
                        pieces.append(delta)
                        callback(delta)
        except urllib.error.HTTPError as e:
            self._raise_http_error(e)
        except urllib.error.URLError as e:
            raise OpenAIChatError(f"{self.config.provider_label} API request failed: {e.reason}") from e
        except TimeoutError:
            raise OpenAIChatError(f"{self.config.provider_label} API request timed out after {self.config.timeout}s") from None
        return "".join(pieces)

    def _raise_http_error(self, error: urllib.error.HTTPError):
        body = error.read().decode("utf-8", errors="replace")
        message = f"{self.config.provider_label} API HTTP {error.code}: {body}"
        if error.code in {401, 403}:
            raise OpenAIChatAuthenticationError(message) from error
        raise OpenAIChatError(message) from error
