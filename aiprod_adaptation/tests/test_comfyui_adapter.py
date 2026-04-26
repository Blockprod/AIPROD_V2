"""
pytest test suite — ComfyUIAdapter + FluxKontextAdapter Phase 3

Covers:
  CU-01 — ComfyUIAdapter.generate() with mock server returns valid ImageResult
  CU-02 — Polling timeout: /history never returns completed → ImageResult model_used="error"
  CU-03 — FluxKontextAdapter builds correct Kontext preservation prompt
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from aiprod_adaptation.image_gen.comfyui_adapter import ComfyUIAdapter
from aiprod_adaptation.image_gen.flux_kontext_adapter import (
    _KONTEXT_PRESERVATION_CLAUSE,
    FluxKontextAdapter,
)
from aiprod_adaptation.image_gen.image_request import ImageRequest

_MINIMAL_WORKFLOW: dict = {
    "6":  {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": ""}},
    "11": {"class_type": "LoadImageFromURL", "inputs": {"url": ""}},
    "25": {"class_type": "KSampler", "inputs": {"seed": 42}},
    "9":  {"class_type": "SaveImage", "inputs": {"images": ["27", 0], "filename_prefix": "test"}},
}

_REQUEST = ImageRequest(
    shot_id="SH0001",
    scene_id="SC001",
    prompt="A detective stands in a rain-soaked alley.",
    reference_image_url="http://example.com/char.png",
    seed=1234,
)


# ---------------------------------------------------------------------------
# CU-01 — Successful generation with mock server
# ---------------------------------------------------------------------------


class TestComfyUIAdapterSuccess:
    def test_generate_returns_valid_image_result(self) -> None:
        adapter = ComfyUIAdapter(
            workflow_template=_MINIMAL_WORKFLOW,
            api_url="http://localhost:8188",
            poll_interval=0.0,
            timeout=10.0,
        )

        submit_response = MagicMock()
        submit_response.status_code = 200
        submit_response.json.return_value = {"prompt_id": "abc-123"}
        submit_response.raise_for_status = MagicMock()

        history_response = MagicMock()
        history_response.status_code = 200
        history_response.json.return_value = {
            "abc-123": {
                "outputs": {
                    "9": {
                        "images": [{"filename": "aiprod_test_00001.png"}]
                    }
                }
            }
        }

        image_response = MagicMock()
        image_response.status_code = 200
        image_response.content = b"FAKE_IMAGE_BYTES"

        with patch("aiprod_adaptation.image_gen.comfyui_adapter._requests") as mock_req:
            mock_req.post.return_value = submit_response
            mock_req.get.side_effect = [history_response, image_response]

            result = adapter.generate(_REQUEST)

        assert result.shot_id == "SH0001"
        assert result.model_used == "comfyui"
        assert "aiprod_test_00001.png" in result.image_url
        assert result.image_b64 != ""
        assert result.latency_ms >= 0


# ---------------------------------------------------------------------------
# CU-02 — Timeout: /history never completes
# ---------------------------------------------------------------------------


class TestComfyUIAdapterTimeout:
    def test_timeout_returns_error_result(self) -> None:
        adapter = ComfyUIAdapter(
            workflow_template=_MINIMAL_WORKFLOW,
            api_url="http://localhost:8188",
            poll_interval=0.0,
            timeout=0.001,   # near-zero timeout → immediate expiry
        )

        submit_response = MagicMock()
        submit_response.status_code = 200
        submit_response.json.return_value = {"prompt_id": "abc-999"}
        submit_response.raise_for_status = MagicMock()

        # /history always returns empty (job never completes)
        history_response = MagicMock()
        history_response.status_code = 200
        history_response.json.return_value = {}

        with patch("aiprod_adaptation.image_gen.comfyui_adapter._requests") as mock_req:
            mock_req.post.return_value = submit_response
            mock_req.get.return_value = history_response

            result = adapter.generate(_REQUEST)

        assert result.model_used == "error"
        assert result.image_url == "error://comfyui-timeout"
        assert result.shot_id == "SH0001"


# ---------------------------------------------------------------------------
# CU-03 — FluxKontextAdapter builds correct preservation prompt
# ---------------------------------------------------------------------------


class TestFluxKontextAdapterPrompt:
    def test_build_location_prompt_contains_preservation_clause(self) -> None:
        prompt = FluxKontextAdapter.build_location_prompt(
            "a neon-lit cyberpunk market at night"
        )
        assert "Change the background to a neon-lit cyberpunk market at night" in prompt
        assert _KONTEXT_PRESERVATION_CLAUSE in prompt

    def test_generate_appends_clause_when_missing(self) -> None:
        adapter = FluxKontextAdapter(api_url="http://localhost:8188")

        submit_response = MagicMock()
        submit_response.status_code = 200
        submit_response.json.return_value = {"prompt_id": "kontext-001"}
        submit_response.raise_for_status = MagicMock()

        history_response = MagicMock()
        history_response.status_code = 200
        history_response.json.return_value = {
            "kontext-001": {
                "outputs": {
                    "9": {"images": [{"filename": "kontext_00001.png"}]}
                }
            }
        }
        image_response = MagicMock()
        image_response.status_code = 200
        image_response.content = b"FAKE"

        req = ImageRequest(
            shot_id="SH0002",
            scene_id="SC001",
            prompt="Change the background to a dark forest.",
            reference_image_url="http://example.com/char.png",
        )

        with patch("aiprod_adaptation.image_gen.comfyui_adapter._requests") as mock_req:
            mock_req.post.return_value = submit_response
            mock_req.get.side_effect = [history_response, image_response]

            result = adapter.generate(req)

        # Verify the patched workflow text node contains the preservation clause
        call_args = mock_req.post.call_args
        submitted_workflow = call_args.kwargs["json"]["prompt"]
        assert _KONTEXT_PRESERVATION_CLAUSE in submitted_workflow["6"]["inputs"]["text"]
        assert result.model_used == "flux-kontext"
