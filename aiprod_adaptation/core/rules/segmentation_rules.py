"""
Segmentation rules — single source of truth for pass1_segment.py.

LOCATION_PHRASES : trigger phrases that signal a new location (and thus a new scene).
TIME_PHRASES     : trigger phrases that signal a time shift (and thus a new scene).
"""

from __future__ import annotations

LOCATION_PHRASES: list[str] = [
    "in the ",
    "inside the ",
    "at the ",
    "entered the ",
    "arrived at ",
    "moved to ",
]

TIME_PHRASES: list[str] = [
    "the following morning",
    "the next day",
    "hours later",
    "meanwhile",
    "later",
]
