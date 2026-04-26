from __future__ import annotations

import time


def now_ms() -> int:
    return int(time.time() * 1000)


def format_clock(ms: int) -> str:
    seconds = max(0, ms // 1000)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_citation_range(start_ms: int, end_ms: int) -> str:
    return f"[{format_clock(start_ms)}–{format_clock(end_ms)}]"
