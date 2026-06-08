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
    if cleaned.endswith("/chat/completions") or cleaned.endswith("/completions"):
        return cleaned
    if cleaned.endswith("/v1"):
        return f"{cleaned}/chat/completions"
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
        last_error: Optional[OpenAIChatError] = None
        for variant in self._payload_variants(payload):
            try:
                with urllib.request.urlopen(self._request(variant), timeout=self.config.timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))
                return self._extract_text(data)
            except urllib.error.HTTPError as e:
                error = self._build_http_error(e)
                if isinstance(error, OpenAIChatAuthenticationError):
                    raise error
                last_error = error
                if not self._is_payload_compat_error(error):
                    raise error
            except urllib.error.URLError as e:
                raise OpenAIChatError(f"{self.config.provider_label} API request failed: {e.reason}") from e
            except TimeoutError:
                raise OpenAIChatError(f"{self.config.provider_label} API request timed out after {self.config.timeout}s") from None
        raise last_error or OpenAIChatError(f"{self.config.provider_label} API request failed")

    def _complete_stream(self, payload: dict, callback: Callable[[str], None]) -> str:
        last_error: Optional[OpenAIChatError] = None
        for variant in self._payload_variants(payload):
            pieces: list[str] = []
            try:
                with urllib.request.urlopen(self._request(variant), timeout=self.config.timeout) as response:
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
                        delta = self._extract_delta(data)
                        if delta:
                            pieces.append(delta)
                            callback(delta)
                return "".join(pieces)
            except urllib.error.HTTPError as e:
                error = self._build_http_error(e)
                if isinstance(error, OpenAIChatAuthenticationError):
                    raise error
                last_error = error
                if not self._is_payload_compat_error(error):
                    raise error
            except urllib.error.URLError as e:
                raise OpenAIChatError(f"{self.config.provider_label} API request failed: {e.reason}") from e
            except TimeoutError:
                raise OpenAIChatError(f"{self.config.provider_label} API request timed out after {self.config.timeout}s") from None
        raise last_error or OpenAIChatError(f"{self.config.provider_label} API stream request failed")

    def _build_http_error(self, error: urllib.error.HTTPError) -> OpenAIChatError:
        body = error.read().decode("utf-8", errors="replace")
        message = f"{self.config.provider_label} API HTTP {error.code}: {body}"
        if error.code in {401, 403}:
            return OpenAIChatAuthenticationError(message)
        return OpenAIChatError(message)

    def _payload_variants(self, payload: dict) -> list[dict]:
        """Generate tolerant payload variants for OpenAI-compatible-but-not-identical APIs."""
        variants = [dict(payload)]
        if "max_tokens" in payload:
            alt = dict(payload)
            alt["max_completion_tokens"] = alt.pop("max_tokens")
            variants.append(alt)
        for base in list(variants):
            if "temperature" in base:
                alt = dict(base)
                alt.pop("temperature", None)
                variants.append(alt)

        seen = set()
        unique = []
        for item in variants:
            key = json.dumps(item, sort_keys=True, ensure_ascii=False)
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    def _is_payload_compat_error(self, error: OpenAIChatError) -> bool:
        text = str(error).lower()
        return (
            "http 400" in text
            and any(token in text for token in [
                "max_tokens",
                "max_completion_tokens",
                "temperature",
                "unsupported",
                "unrecognized",
                "unknown parameter",
                "extra fields",
                "invalid parameter",
            ])
        )

    def _extract_text(self, data: dict) -> str:
        choices = data.get("choices") or []
        if choices:
            first = choices[0] or {}
            message = first.get("message") or {}
            content = message.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
            if first.get("text"):
                return str(first.get("text"))
        if isinstance(data.get("output_text"), str):
            return data["output_text"]
        output = data.get("output")
        if isinstance(output, str):
            return output
        if isinstance(output, list):
            pieces = []
            for item in output:
                if isinstance(item, dict):
                    pieces.append(str(item.get("text") or item.get("content") or ""))
            if pieces:
                return "".join(pieces)
        raise OpenAIChatError(f"{self.config.provider_label} API did not return recognizable text: {data}")

    def _extract_delta(self, data: dict) -> str:
        choices = data.get("choices") or []
        if choices:
            first = choices[0] or {}
            delta = first.get("delta") or {}
            content = delta.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
            if first.get("text"):
                return str(first.get("text"))
        if isinstance(data.get("response"), str):
            return data["response"]
        if isinstance(data.get("text"), str):
            return data["text"]
        return ""
