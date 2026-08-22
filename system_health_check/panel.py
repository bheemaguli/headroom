"""JSON payload builder for the Omarchy bar panel."""

from datetime import datetime, timezone

from .advice import advice_from_windows
from .client import NetdataError, info, list_charts
from .constants import PANEL_WINDOWS
from .metrics import build_now, series_for_window, window_stats
from .windows import parse_window


def panel_payload(base, focus_window="7d", extra_days=None):
    try:
        focus_label, focus_seconds = parse_window(focus_window)
    except ValueError:
        focus_label, focus_seconds = "7d", 7 * 86400

    try:
        meta = info(base)
        charts = list_charts(base)
        now = build_now(base, charts)

        # Preset tabs stay fixed; custom focus is computed separately.
        window_labels = list(PANEL_WINDOWS)
        compute_labels = list(window_labels)
        if focus_label not in compute_labels:
            compute_labels.append(focus_label)
        if extra_days is not None:
            days = int(extra_days)
            if 1 <= days <= 90:
                custom_label = f"{days}d"
                if custom_label not in compute_labels:
                    compute_labels.append(custom_label)

        windows = {}
        for label in compute_labels:
            _lbl, seconds = parse_window(label)
            windows[label] = window_stats(base, charts, seconds)

        series = series_for_window(base, charts, focus_seconds)
        hosts = meta.get("mirrored_hosts")
        hostname = hosts[0] if isinstance(hosts, list) and hosts else meta.get("os_name")

        return {
            "ok": True,
            "online": True,
            "url": base.rstrip("/"),
            "hostname": hostname,
            "os": meta.get("os_name"),
            "netdata_version": meta.get("version"),
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "focus": focus_label,
            "custom_days": int(extra_days) if extra_days not in (None, "") else None,
            "window_keys": window_labels,
            "now": now,
            "windows": windows,
            "series": series,
            "advice": advice_from_windows(windows, now, focus=focus_label),
        }
    except NetdataError as e:
        return {
            "ok": False,
            "online": False,
            "url": base.rstrip("/"),
            "error": str(e),
            "focus": focus_label,
            "custom_days": int(extra_days) if extra_days not in (None, "") else None,
            "window_keys": list(PANEL_WINDOWS),
            "now": {},
            "windows": {},
            "series": {},
            "advice": [
                "Netdata is not reachable. Install it with: omarchy pkg add netdata",
                "Then: sudo systemctl enable --now netdata",
            ],
        }
