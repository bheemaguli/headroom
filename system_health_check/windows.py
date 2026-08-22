"""Parse and resolve history window labels."""

from .constants import MAX_WINDOW_SECONDS, UNIT_SECONDS, WINDOW_RE


def parse_window(text):
    """Parse '30d', '14d', '24h', '90m' → (label, seconds)."""
    raw = str(text or "").strip().lower()
    aliases = {
        "1d": "24h",
        "day": "24h",
        "today": "24h",
        "week": "7d",
        "month": "30d",
    }
    raw = aliases.get(raw, raw)
    m = WINDOW_RE.match(raw)
    if not m:
        raise ValueError(
            f"invalid window '{text}' — use Ns/Nm/Nh/Nd (e.g. 24h, 7d, 30d)"
        )
    amount = int(m.group(1))
    unit = m.group(2).lower()
    if amount <= 0:
        raise ValueError(f"window must be positive: {text}")
    seconds = amount * UNIT_SECONDS[unit]
    if seconds > MAX_WINDOW_SECONDS:
        raise ValueError("window too large (max 90d) — Netdata retention is finite")
    label = f"{amount}{unit}"
    return label, seconds


def points_for_window(seconds):
    """Enough buckets for a smooth series without hammering Netdata."""
    if seconds <= 3600:
        return 60
    if seconds <= 86400:
        return 96
    if seconds <= 7 * 86400:
        return 168
    if seconds <= 14 * 86400:
        return 168
    return 180


def resolve_window(window=None, days=None):
    """Resolve CLI window / --days into (label, seconds)."""
    if days is not None:
        days = int(days)
        if days < 1 or days > 90:
            raise ValueError("--days must be between 1 and 90")
        return parse_window(f"{days}d")
    return parse_window(window or "7d")


def human_window(label):
    """7d → '7 day', 24h → '24 hour' (for 'Based on … usage analysis')."""
    try:
        canonical, _seconds = parse_window(label)
    except ValueError:
        return str(label or "selected")
    m = WINDOW_RE.match(canonical)
    if not m:
        return canonical
    amount = int(m.group(1))
    unit = m.group(2).lower()
    names = {"s": "second", "m": "minute", "h": "hour", "d": "day"}
    return f"{amount} {names.get(unit, unit)}"
