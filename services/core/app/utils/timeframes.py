from __future__ import annotations

import re


INTERVAL_RE = re.compile(r"^(\d+)(m|h|d|w)$")


def interval_to_seconds(interval: str) -> int:
    """Convert intervals like 1m/5m/1h/1d/1w into seconds."""
    m = INTERVAL_RE.match(interval.strip())
    if not m:
        raise ValueError(f"Unsupported interval '{interval}'. Use like 1m,5m,1h,1d,1w.")
    n = int(m.group(1))
    unit = m.group(2)
    if unit == "m":
        return n * 60
    if unit == "h":
        return n * 3600
    if unit == "d":
        return n * 86400
    if unit == "w":
        return n * 7 * 86400
    raise ValueError(f"Unsupported interval unit '{unit}'.")
