from __future__ import annotations

import os
import time

from aiprod_adaptation.video_gen.video_adapter import VideoAdapter
from aiprod_adaptation.video_gen.video_request import VideoClipResult, VideoRequest


class KlingAdapter(VideoAdapter):
    """Kling v1.5 image-to-video adapter (Kuaishou Technology).

    Requires: KLING_API_KEY + KLING_API_SECRET env vars
    Excluded from mypy and CI — integration only.
    Docs: https://docs.qingque.cn/d/home/eZQDvGXc5KZQWrWM2Y-lX5bIL
    """

    MODEL: str = "kling-v1-5"
    BASE_URL: str = "https://api.klingai.com"

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("KLING_API_KEY", "")
        self._api_secret = api_secret or os.environ.get("KLING_API_SECRET", "")

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
        payload = {
            "model_name": self.MODEL,
            "image": request.image_url,
            "prompt": request.prompt,
            "duration": str(request.duration_sec),
            "cfg_scale": request.motion_score,
        }
        resp = requests.post(
            f"{self.BASE_URL}/v1/videos/image2video",
            json=payload,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        task_id = resp.json()["data"]["task_id"]

        # Poll until complete
        import time as _time
        while True:
            poll = requests.get(
                f"{self.BASE_URL}/v1/videos/image2video/{task_id}",
                headers=headers,
                timeout=30,
            )
            poll.raise_for_status()
            data = poll.json()["data"]
            status = data["task_status"]
            if status == "succeed":
                video_url = data["task_result"]["videos"][0]["url"]
                break
            if status == "failed":
                raise RuntimeError(f"Kling task {task_id} failed")
            _time.sleep(3)

        latency = int((time.monotonic() - t0) * 1000)
        return VideoClipResult(
            shot_id=request.shot_id,
            video_url=video_url,
            duration_sec=request.duration_sec,
            model_used=self.MODEL,
            latency_ms=latency,
        )
