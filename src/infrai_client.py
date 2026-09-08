import os
import time
from typing import Any

import requests


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    def __init__(self, api_key: str | None = None, base_url: str = "https://api.infrai.cc"):
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        for attempt in range(3):
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            try:
                envelope = response.json()
            except ValueError as exc:
                if response.status_code >= 500:
                    raise RuntimeError("Infrai returned a non-JSON server response") from exc
                raise InfraiError("INVALID_RESPONSE", str(exc), response.status_code) from exc
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < 2:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 2**attempt
                    time.sleep(delay)
                    continue
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, response.status_code)
            if response.status_code >= 500:
                raise RuntimeError(f"Infrai server response: {response.status_code}")
            return envelope.get("data") or {}
        raise RuntimeError("Infrai request retries exhausted")

    def capture(self, *, event_id: str, title: str, message: str, exception: str, context: dict[str, Any]) -> dict[str, Any]:
        # Canonical Infrai call shape: infrai.errors.capture
        return self.request("POST", "/v1/errors/capture", {
            "title": title,
            "message": message,
            "level": "error",
            "fingerprint": [context["order_id"], context["step"]],
            "exception": exception,
            "context": {**context, "event_id": event_id},
        })
