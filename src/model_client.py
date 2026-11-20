"""외부 LLM 호출을 한 곳으로 제한하는 얇은 Anthropic 클라이언트."""

from __future__ import annotations

from dataclasses import dataclass
import json
import time
import urllib.error
import urllib.request


ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_COUNT_URL = "https://api.anthropic.com/v1/messages/count_tokens"  # 무료, 토큰 수만 셈


class ModelClientError(RuntimeError):
    """모델 호출 또는 응답 형식 오류."""


@dataclass(frozen=True)
class ModelResponse:
    text: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    elapsed_seconds: float
    stop_reason: str | None = None  # "max_tokens"면 출력 한도에 걸려 답이 잘린 것


class AnthropicClient:
    def __init__(self, api_key: str, *, timeout: int = 300) -> None:
        self.api_key = api_key.strip()
        self.timeout = timeout
        self.usage: list[dict[str, object]] = []
        if not self.api_key:
            raise ModelClientError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")

    def _post(self, url: str, body: dict) -> dict:
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise ModelClientError(f"모델 API 오류 {exc.code}: {detail}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelClientError(f"모델 응답을 받을 수 없습니다: {exc}") from exc

    def count_tokens(self, *, model: str, system: str, user: str) -> int:
        """보낼 입력의 토큰 수 (요금 없음). 비용 계산용."""
        payload = self._post(
            ANTHROPIC_COUNT_URL,
            {"model": model, "system": system, "messages": [{"role": "user", "content": user}]},
        )
        return int(payload.get("input_tokens") or 0)

    def complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
        thinking: dict | None = None,
    ) -> ModelResponse:
        payload_body = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if thinking:  # 예: Sonnet 5.5는 {"type": "between_tools"}로 답하기 전 '생각'을 끈다
            payload_body["thinking"] = thinking
        body = json.dumps(payload_body).encode("utf-8")
        request = urllib.request.Request(
            ANTHROPIC_MESSAGES_URL,
            data=body,
            method="POST",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise ModelClientError(f"모델 API 오류 {exc.code}: {detail}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelClientError(f"모델 응답을 받을 수 없습니다: {exc}") from exc

        text = "".join(
            str(block.get("text") or "")
            for block in payload.get("content") or []
            if isinstance(block, dict)
        ).strip()
        if not text:
            raise ModelClientError("모델 응답 텍스트가 비어 있습니다.")

        usage = payload.get("usage") or {}
        elapsed = round(time.monotonic() - started, 2)
        record = {
            "model": model,
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "elapsed_seconds": elapsed,
        }
        self.usage.append(record)
        return ModelResponse(
            text=text,
            model=model,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            elapsed_seconds=elapsed,
            stop_reason=payload.get("stop_reason"),
        )
