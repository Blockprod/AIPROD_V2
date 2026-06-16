from __future__ import annotations

import os
import time

from aiprod_adaptation.adapters.errors import (
    AdapterError,
    AdapterFailureCategory,
    require_http_url,
)
from aiprod_adaptation.video_gen.video_adapter import VideoAdapter
from aiprod_adaptation.video_gen.video_request import VideoClipResult, VideoRequest


class KlingAdapter(VideoAdapter):
    """Kling 3.0 image-to-video adapter (Kuaishou Technology).

    Requires: KLING_API_KEY + KLING_API_SECRET env vars
    Excluded from mypy and CI — integration only.
    Docs: https://docs.qingque.cn/d/home/eZQDvGXc5KZQWrWM2Y-lX5bIL
    """

    MODEL: str = "kling-v3"
    BASE_URL: str = "https://api.klingai.com"

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        deadline_sec: float = 300.0,
        poll_interval_sec: float = 3.0,
    ) -> None:
        self._api_key = api_key or os.environ.get("KLING_API_KEY", "")
        self._api_secret = api_secret or os.environ.get("KLING_API_SECRET", "")
        self._deadline_sec = deadline_sec
        self._poll_interval_sec = poll_interval_sec

    def _jwt_token(self) -> str:
        import jwt

        payload = {
            "iss": self._api_key,
            "exp": int(time.time()) + 1800,
            "nbf": int(time.time()) - 5,
        }
        return str(jwt.encode(payload, self._api_secret, algorithm="HS256"))

    def generate(self, request: VideoRequest) -> VideoClipResult:
        import requests

        t0 = time.monotonic()
        headers = {
            "Authorization": f"Bearer {self._jwt_token()}",
            "Content-Type": "application/json",
        }
        payload: dict[str, str | float] = {
            "model_name": self.MODEL,
            "image": request.image_url,
            "prompt": request.prompt,
            "duration": str(request.duration_sec),
            "cfg_scale": request.motion_score,
            "camera_type": "professional",
        }
        resp = requests.post(
            f"{self.BASE_URL}/v1/videos/image2video",
            json=payload,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        try:
            task_id = resp.json()["data"]["task_id"]
        except (KeyError, TypeError, ValueError) as exc:
            raise AdapterError(
                "Kling create response is malformed.", provider="kling",
                category=AdapterFailureCategory.MALFORMED_RESPONSE,
                request_id=request.shot_id,
            ) from exc
        if not isinstance(task_id, str) or not task_id:
            raise AdapterError(
                "Kling returned an empty task id.", provider="kling",
                category=AdapterFailureCategory.MALFORMED_RESPONSE,
                request_id=request.shot_id,
            )

        # Poll until complete
        import time as _time
        deadline = time.monotonic() + self._deadline_sec
        while time.monotonic() < deadline:
            poll = requests.get(
                f"{self.BASE_URL}/v1/videos/image2video/{task_id}",
                headers=headers,
                timeout=30,
            )
            poll.raise_for_status()
            try:
                data = poll.json()["data"]
                status = data["task_status"]
            except (KeyError, TypeError, ValueError) as exc:
                raise AdapterError(
                    "Kling polling response is malformed.", provider="kling",
                    category=AdapterFailureCategory.MALFORMED_RESPONSE,
                    request_id=request.shot_id,
                ) from exc
            if status == "succeed":
                try:
                    candidate = data["task_result"]["videos"][0]["url"]
                except (KeyError, IndexError, TypeError) as exc:
                    raise AdapterError(
                        "Kling success response has no video URL.", provider="kling",
                        category=AdapterFailureCategory.MALFORMED_RESPONSE,
                        request_id=request.shot_id,
                    ) from exc
                video_url = require_http_url(
                    candidate, provider="kling", request_id=request.shot_id
                )
                break
            if status == "failed":
                raise AdapterError(
                    f"Kling task {task_id} failed.", provider="kling",
                    category=AdapterFailureCategory.UNAVAILABLE,
                    request_id=request.shot_id,
                )
            if status not in {"submitted", "processing", "pending"}:
                raise AdapterError(
                    f"Kling returned unknown task status {status!r}.", provider="kling",
                    category=AdapterFailureCategory.MALFORMED_RESPONSE,
                    request_id=request.shot_id,
                )
            _time.sleep(self._poll_interval_sec)
        else:
            raise AdapterError(
                f"Kling task {task_id} exceeded {self._deadline_sec:.0f}s deadline.",
                provider="kling", category=AdapterFailureCategory.TIMEOUT,
                retryable=True, request_id=request.shot_id,
            )

        latency = int((time.monotonic() - t0) * 1000)
        return VideoClipResult(
            shot_id=request.shot_id,
            video_url=video_url,
            duration_sec=request.duration_sec,
            model_used=self.MODEL,
            latency_ms=latency,
        )
