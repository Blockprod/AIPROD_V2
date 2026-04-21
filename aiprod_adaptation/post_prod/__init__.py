"""
Post-production package: audio TTS generation + timeline assembly.
"""

from aiprod_adaptation.post_prod.audio_adapter import AudioAdapter, NullAudioAdapter
from aiprod_adaptation.post_prod.audio_request import (
    AudioRequest,
    AudioResult,
    ProductionOutput,
    TimelineClip,
)
from aiprod_adaptation.post_prod.audio_synchronizer import AudioSynchronizer
from aiprod_adaptation.post_prod.ffmpeg_exporter import FFmpegExporter
from aiprod_adaptation.post_prod.ssml_builder import SSMLBuilder

__all__ = [
    "AudioAdapter",
    "NullAudioAdapter",
    "AudioRequest",
    "AudioResult",
    "ProductionOutput",
    "TimelineClip",
    "AudioSynchronizer",
    "FFmpegExporter",
    "SSMLBuilder",
]
