"""CSV export of history summary + time series."""

import csv
import sys
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from .client import info, list_charts
from .metrics import series_rows_for_window, window_stats


def export_csv(base, label, seconds, path=None):
    """Write summary + time series CSV. Returns the output path or '-' for stdout."""
    charts = list_charts(base)
    stats = window_stats(base, charts, seconds)
    rows = series_rows_for_window(base, charts, seconds)
    meta = info(base)
    hosts = meta.get("mirrored_hosts")
    host = hosts[0] if isinstance(hosts, list) and hosts else (meta.get("os_name") or "host")
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    buf = StringIO()
    buf.write(f"# system-health-check export window={label} host={host} generated={generated}\n")
    for metric in ("cpu", "ram", "gpu"):
        s = stats.get(metric) or {}
        buf.write(
            "# {m} avg={avg} max={mx} min={mn} p95={p95} samples={n}\n".format(
                m=metric,
                avg=s.get("avg"),
                mx=s.get("max"),
                mn=s.get("min"),
                p95=s.get("p95"),
                n=s.get("samples"),
            )
        )
    writer = csv.writer(buf)
    writer.writerow(["timestamp_utc", "timestamp_unix", "cpu_pct", "ram_pct", "gpu_pct"])
    for ts, cpu, ram, gpu in rows:
        try:
            iso = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (OverflowError, OSError, ValueError):
            iso = ""
        writer.writerow(
            [
                iso,
                int(ts) if ts is not None else "",
                "" if cpu is None else cpu,
                "" if ram is None else ram,
                "" if gpu is None else gpu,
            ]
        )

    text = buf.getvalue()
    if not path or path == "-":
        sys.stdout.write(text)
        return "-"

    out = Path(path).expanduser()
    treat_as_dir = str(path).endswith(("/", "\\")) or out.suffix == "" or out.is_dir()
    if treat_as_dir:
        out.mkdir(parents=True, exist_ok=True)
        out = out / f"system-health-{label}-{generated.replace(':', '')}.csv"
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return str(out)
