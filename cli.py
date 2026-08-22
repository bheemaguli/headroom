#!/usr/bin/env python3
"""system-health-check — Netdata-backed resource tracking for Omarchy.

Queries a local (or remote) Netdata agent and prints current usage, multi-day
history (CloudWatch-style Average / Maximum / p95), and a sizing report.
The Omarchy bar plugin calls `panel --json` for its chip and popup.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

DEFAULT_URL = os.environ.get("SYSTEM_HEALTH_CHECK_URL", "http://127.0.0.1:19999")
# Presets shown in the bar panel (AWS console–style ranges).
PANEL_WINDOWS = ["1h", "24h", "7d", "14d", "30d"]
USER_AGENT = "system-health-check/1.1 (+omarchy-plugin)"
WINDOW_RE = re.compile(r"^(\d+)([smhd])$", re.IGNORECASE)
UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


class NetdataError(Exception):
    pass


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
    if raw in {"1h", "6h", "24h", "3d", "7d", "14d", "30d"}:
        # Fall through to regex for seconds; labels stay canonical.
        pass
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
    if seconds > 90 * 86400:
        raise ValueError("window too large (max 90d) — Netdata retention is finite")
    # Canonical label: prefer day form for multiples of 24h when unit is d.
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


def _get(url, timeout=4.0):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            ctype = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        raise NetdataError(f"HTTP {e.code} from {url}") from e
    except urllib.error.URLError as e:
        raise NetdataError(f"Netdata unreachable at {url}: {e.reason}") from e
    except TimeoutError as e:
        raise NetdataError(f"Timed out talking to {url}") from e

    if "json" in ctype or body[:1] in (b"{", b"["):
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise NetdataError(f"Invalid JSON from {url}") from e
    return body.decode("utf-8", errors="replace")


def api(base, path, params=None, timeout=4.0):
    base = base.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    if params:
        path = path + "?" + urllib.parse.urlencode(params, doseq=True)
    return _get(base + path, timeout=timeout)


def chart_data(base, chart, after, points=60, group="average", options="absolute", timeout=8.0):
    return api(
        base,
        "/api/v1/data",
        {
            "chart": chart,
            "after": str(-abs(int(after))),
            "points": str(int(points)),
            "group": group,
            "format": "json",
            "options": options,
        },
        timeout=timeout,
    )


def list_charts(base):
    data = api(base, "/api/v1/charts", timeout=6.0)
    charts = data.get("charts") if isinstance(data, dict) else None
    return charts if isinstance(charts, dict) else {}


def pick_chart(charts, candidates):
    for name in candidates:
        if name in charts:
            return name
    lower = {k.lower(): k for k in charts}
    for name in candidates:
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def find_chart_by_substr(charts, needles, prefer=None):
    prefer = prefer or []
    scored = []
    for cid, meta in charts.items():
        blob = " ".join(
            [
                cid,
                str(meta.get("name") or ""),
                str(meta.get("title") or ""),
                str(meta.get("context") or ""),
                str(meta.get("family") or ""),
            ]
        ).lower()
        if not all(n.lower() in blob for n in needles):
            continue
        score = 0
        for i, p in enumerate(prefer):
            if p.lower() in blob:
                score += 100 - i
        score -= len(cid) // 10
        scored.append((score, cid))
    if not scored:
        return None
    scored.sort(reverse=True)
    return scored[0][1]


def dimension_names(payload):
    """Return dimension names aligned with row values (Netdata 1.x + 2.x)."""
    names = payload.get("dimension_names")
    if names:
        return [str(n) for n in names]
    labels = payload.get("labels") or []
    if not labels:
        return []
    if str(labels[0]).lower() in ("time", "timestamp"):
        return [str(n) for n in labels[1:]]
    return [str(n) for n in labels]


def dimension_index(payload, name):
    names = [n.lower() for n in dimension_names(payload)]
    try:
        return names.index(str(name).lower())
    except ValueError:
        return None


def rows_from_payload(payload):
    """Return list of (timestamp, values_list) oldest-first."""
    result = payload.get("result") if isinstance(payload, dict) else None
    if isinstance(result, dict) and "data" in result:
        data = result["data"]
    elif isinstance(payload, dict) and "data" in payload:
        data = payload["data"]
    else:
        data = result if isinstance(result, list) else payload
    if not isinstance(data, list):
        return []
    rows = []
    for row in data:
        if not isinstance(row, (list, tuple)) or not row:
            continue
        try:
            ts = float(row[0])
            vals = [None if v is None else float(v) for v in row[1:]]
        except (TypeError, ValueError):
            continue
        rows.append((ts, vals))
    if len(rows) >= 2 and rows[0][0] > rows[-1][0]:
        rows.reverse()
    return rows


def percentile(values, p):
    clean = sorted(v for v in values if v is not None and isinstance(v, (int, float)))
    if not clean:
        return None
    if len(clean) == 1:
        return round(clean[0], 2)
    rank = (p / 100.0) * (len(clean) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(clean) - 1)
    frac = rank - lo
    return round(clean[lo] * (1 - frac) + clean[hi] * frac, 2)


def series_stats(values):
    clean = [v for v in values if v is not None and isinstance(v, (int, float))]
    if not clean:
        return {"avg": None, "max": None, "peak": None, "min": None, "p95": None, "samples": 0}
    peak = round(max(clean), 2)
    return {
        "avg": round(sum(clean) / len(clean), 2),
        "max": peak,
        "peak": peak,
        "min": round(min(clean), 2),
        "p95": percentile(clean, 95),
        "samples": len(clean),
    }


def cloudwatch_stats(avg_series, max_series=None):
    """AWS-style Average + Maximum (+ p95 from the average series)."""
    avg = series_stats(avg_series)
    if max_series:
        mx = series_stats(max_series)
        peak = mx["max"]
    else:
        peak = avg["max"]
    return {
        "avg": avg["avg"],
        "max": peak,
        "peak": peak,
        "min": avg["min"],
        "p95": avg["p95"],
        "samples": avg["samples"],
    }


def cpu_busy_series(base, after, points, group="average"):
    payload = chart_data(base, "system.cpu", after, points=points, group=group, options="absolute")
    names = dimension_names(payload)
    idle_i = dimension_index(payload, "idle")
    rows = rows_from_payload(payload)
    out = []
    for _ts, vals in rows:
        if idle_i is not None and idle_i < len(vals) and vals[idle_i] is not None:
            busy = max(0.0, min(100.0, 100.0 - float(vals[idle_i])))
        else:
            busy = 0.0
            for i, _name in enumerate(names):
                if i >= len(vals) or vals[i] is None:
                    continue
                busy += float(vals[i])
            busy = max(0.0, min(100.0, busy))
        out.append(round(busy, 2))
    return out


def ram_used_series(base, after, points, group="average"):
    payload = chart_data(base, "system.ram", after, points=points, group=group, options="absolute")
    names = [n.lower() for n in dimension_names(payload)]
    idx = {n: i for i, n in enumerate(names)}
    rows = rows_from_payload(payload)
    out = []
    for _ts, vals in rows:
        def get(key):
            i = idx.get(key)
            if i is None or i >= len(vals) or vals[i] is None:
                return None
            return float(vals[i])

        used = get("used")
        free = get("free")
        cached = get("cached")
        buffers = get("buffers")
        parts = [v for v in (used, free, cached, buffers) if v is not None]
        total = sum(parts) if parts else None
        if used is not None and total and total > 0:
            out.append(round(100.0 * used / total, 2))
        else:
            out.append(None)
    return out


def ram_snapshot(base):
    payload = chart_data(base, "system.ram", 60, points=3, options="absolute")
    names = [n.lower() for n in dimension_names(payload)]
    idx = {n: i for i, n in enumerate(names)}
    rows = rows_from_payload(payload)
    if not rows:
        return {"percent": None, "used_gb": None, "total_gb": None}

    vals = rows[-1][1]

    def get(key):
        i = idx.get(key)
        if i is None or i >= len(vals) or vals[i] is None:
            return None
        return float(vals[i])

    used = get("used") or 0.0
    free = get("free") or 0.0
    cached = get("cached") or 0.0
    buffers = get("buffers") or 0.0
    total = used + free + cached + buffers
    used_gb = used / 1024.0
    total_gb = total / 1024.0 if total else None
    percent = round(100.0 * used / total, 2) if total else None
    return {
        "percent": percent,
        "used_gb": round(used_gb, 2) if total else None,
        "total_gb": round(total_gb, 2) if total_gb else None,
        "cached_gb": round(cached / 1024.0, 2),
        "free_gb": round(free / 1024.0, 2),
    }


def discover_gpu_chart(charts):
    return (
        pick_chart(
            charts,
            [
                "nvidia_smi.gpu_utilization_gpu0",
                "nvidia_smi.gpu_utilization_0",
                "nvidia.gpu0_gpu_utilization",
                "nvidia_gpus.gpu_utilization_gpu0",
            ],
        )
        or find_chart_by_substr(charts, ["nvidia", "util"], prefer=["gpu_utilization", "utilization"])
        or find_chart_by_substr(charts, ["amdgpu", "busy"], prefer=["gpu_busy", "busy"])
        or find_chart_by_substr(charts, ["gpu", "util"], prefer=["utilization", "busy"])
    )


def first_dimension_series(base, chart, after, points, group="average"):
    if not chart:
        return []
    payload = chart_data(base, chart, after, points=points, group=group, options="absolute")
    names = [n.lower() for n in dimension_names(payload)]
    rows = rows_from_payload(payload)
    out = []
    for _ts, vals in rows:
        if not vals:
            out.append(None)
            continue
        chosen = None
        for prefer in ("gpu", "utilization", "busy", "used", "mem"):
            for i, name in enumerate(names):
                if prefer in name and i < len(vals) and vals[i] is not None:
                    chosen = float(vals[i])
                    break
            if chosen is not None:
                break
        if chosen is None:
            chosen = float(vals[0]) if vals[0] is not None else None
        out.append(None if chosen is None else round(chosen, 2))
    return out


def disk_used_percent(base, charts):
    chart = pick_chart(charts, ["disk_space./", "disk.space", "disk_space.root"]) or find_chart_by_substr(
        charts, ["disk", "space"], prefer=["disk_space./", "root"]
    )
    if not chart:
        return None
    payload = chart_data(base, chart, 120, points=3, options="absolute")
    names = [n.lower() for n in dimension_names(payload)]
    rows = rows_from_payload(payload)
    if not rows:
        return None
    vals = rows[-1][1]
    idx = {n: i for i, n in enumerate(names)}

    def get(*keys):
        for key in keys:
            i = idx.get(key)
            if i is not None and i < len(vals) and vals[i] is not None:
                return float(vals[i])
        return None

    avail = get("avail", "available", "free")
    used = get("used")
    if used is not None and avail is not None and (used + avail) > 0:
        return round(100.0 * used / (used + avail), 2)
    if used is not None and used <= 100:
        return round(used, 2)
    return None


def load_snapshot(base):
    try:
        payload = chart_data(base, "system.load", 120, points=3, options="absolute")
    except NetdataError:
        return {"load1": None, "load5": None, "load15": None}
    names = [n.lower() for n in dimension_names(payload)]
    rows = rows_from_payload(payload)
    if not rows:
        return {"load1": None, "load5": None, "load15": None}
    vals = rows[-1][1]
    idx = {n: i for i, n in enumerate(names)}

    def get(*keys):
        for key in keys:
            i = idx.get(key)
            if i is not None and i < len(vals) and vals[i] is not None:
                return round(float(vals[i]), 2)
        # Fall back to positional load1/5/15.
        return None

    load1 = get("load1", "1 minute", "1min")
    load5 = get("load5", "5 minutes", "5min")
    load15 = get("load15", "15 minutes", "15min")
    if load1 is None and len(vals) >= 1 and vals[0] is not None:
        load1 = round(float(vals[0]), 2)
    if load5 is None and len(vals) >= 2 and vals[1] is not None:
        load5 = round(float(vals[1]), 2)
    if load15 is None and len(vals) >= 3 and vals[2] is not None:
        load15 = round(float(vals[2]), 2)
    return {"load1": load1, "load5": load5, "load15": load15}


def info(base):
    return api(base, "/api/v1/info", timeout=3.0)


def build_now(base, charts):
    cpu_series = cpu_busy_series(base, 120, 5)
    ram = ram_snapshot(base)
    load = load_snapshot(base)
    gpu_chart = discover_gpu_chart(charts)
    gpu_series = first_dimension_series(base, gpu_chart, 120, 5) if gpu_chart else []
    disk = disk_used_percent(base, charts)
    return {
        "cpu": cpu_series[-1] if cpu_series else None,
        "ram": ram.get("percent"),
        "ram_used_gb": ram.get("used_gb"),
        "ram_total_gb": ram.get("total_gb"),
        "ram_cached_gb": ram.get("cached_gb"),
        "gpu": gpu_series[-1] if gpu_series else None,
        "gpu_chart": gpu_chart,
        "disk": disk,
        "load1": load.get("load1"),
        "load5": load.get("load5"),
        "load15": load.get("load15"),
    }


def window_stats(base, charts, seconds, points=None):
    """CloudWatch-style avg / max / p95 for CPU, RAM, GPU over a window."""
    points = points or points_for_window(seconds)
    gpu_chart = discover_gpu_chart(charts)

    # Composite metrics (CPU busy %, RAM %): peak = max of average buckets.
    # Single-dimension GPU: also query group=max for a truer Maximum.
    cpu_avg = cpu_busy_series(base, seconds, points, group="average")
    ram_avg = ram_used_series(base, seconds, points, group="average")
    gpu_avg = first_dimension_series(base, gpu_chart, seconds, points, group="average") if gpu_chart else []
    gpu_max = first_dimension_series(base, gpu_chart, seconds, points, group="max") if gpu_chart else []

    return {
        "cpu": cloudwatch_stats(cpu_avg),
        "ram": cloudwatch_stats(ram_avg),
        "gpu": cloudwatch_stats(gpu_avg, gpu_max),
        "seconds": seconds,
        "points": points,
    }


def series_for_window(base, charts, seconds):
    points = points_for_window(seconds)
    gpu_chart = discover_gpu_chart(charts)
    return {
        "cpu": cpu_busy_series(base, seconds, points),
        "ram": ram_used_series(base, seconds, points),
        "gpu": first_dimension_series(base, gpu_chart, seconds, points) if gpu_chart else [],
    }


def _first_metric(windows, metric, field, order=None):
    order = order or ("30d", "14d", "7d", "24h", "1h")
    for key in order:
        w = windows.get(key) or {}
        stat = w.get(metric) or {}
        if stat.get("samples"):
            val = stat.get(field)
            if val is not None:
                return val, key
    return None, None


def advice_from_windows(windows, now, focus=None):
    tips = []
    focus = focus or "7d"
    # Prefer the focus window, then fall back to whatever Netdata has retained.
    order = [focus] + [k for k in ("30d", "14d", "7d", "24h", "1h") if k != focus]

    ram_avg, ram_src = _first_metric(windows, "ram", "avg", order)
    ram_p95, _ = _first_metric(windows, "ram", "p95", order)
    ram_peak, _ = _first_metric(windows, "ram", "max", order)
    cpu_avg, cpu_src = _first_metric(windows, "cpu", "avg", order)
    cpu_peak, _ = _first_metric(windows, "cpu", "max", order)
    gpu_avg, gpu_src = _first_metric(windows, "gpu", "avg", order)
    gpu_peak, _ = _first_metric(windows, "gpu", "max", order)

    src = ram_src or cpu_src or gpu_src
    if src and src != focus:
        tips.append(f"Longer ranges are still filling — advice uses {src} until {focus} has data.")

    total = (now or {}).get("ram_total_gb")
    if ram_avg is not None and ram_avg >= 70:
        tips.append("RAM averages high — prefer more memory on the next computer.")
    elif ram_p95 is not None and ram_p95 >= 80:
        tips.append("RAM p95 is high — size memory for sustained load, not idle.")
    elif ram_peak is not None and ram_peak >= 85:
        tips.append("RAM peaks hard under load — size up if those workloads move with you.")
    elif total is not None and total <= 16 and ram_avg is not None and ram_avg >= 55:
        tips.append(f"You are often using over half of {total:g} GB RAM — 32 GB is a safer target.")

    if cpu_avg is not None and cpu_avg >= 45:
        tips.append("CPU stays busy for long stretches — prioritize sustained multi-core performance.")
    elif cpu_peak is not None and cpu_peak >= 90 and (cpu_avg or 0) < 25:
        tips.append("CPU spikes are short; a mid-range CPU is probably enough.")

    if gpu_avg is not None and gpu_avg >= 25:
        tips.append("GPU sees real use — look for a discrete GPU or a strong modern iGPU.")
    elif gpu_peak is not None and gpu_peak >= 70 and (gpu_avg or 0) < 10:
        tips.append("GPU peaks are rare; integrated graphics may be fine.")
    elif gpu_avg is None and gpu_peak is None and (now or {}).get("gpu") is None:
        tips.append("No GPU metrics from Netdata yet — enable the NVIDIA/AMD collector if you care about GPU headroom.")

    if len(tips) == 0 or (len(tips) == 1 and tips[0].startswith("Longer ranges")):
        tips.append("Nothing looks maxed over the sampled windows — mid-range CPU/RAM should cover daily use.")
    return tips


def panel_payload(base, focus_window="7d"):
    try:
        focus_label, focus_seconds = parse_window(focus_window)
    except ValueError:
        focus_label, focus_seconds = "7d", 7 * 86400

    try:
        meta = info(base)
        charts = list_charts(base)
        now = build_now(base, charts)

        window_labels = list(PANEL_WINDOWS)
        if focus_label not in window_labels:
            window_labels.append(focus_label)

        windows = {}
        for label in window_labels:
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
            "window_keys": list(PANEL_WINDOWS),
            "now": {},
            "windows": {},
            "series": {},
            "advice": [
                "Netdata is not reachable. Install it with: omarchy pkg add netdata",
                "Then: sudo systemctl enable --now netdata",
            ],
        }


def fmt_pct(v):
    if v is None:
        return "—"
    return f"{v:.0f}%"


def fmt_stat(stat):
    if not stat or stat.get("avg") is None:
        return "avg —   max —   p95 —"
    peak = stat.get("max", stat.get("peak"))
    return f"avg {fmt_pct(stat['avg']):>4}  max {fmt_pct(peak):>4}  p95 {fmt_pct(stat.get('p95')):>4}"


def print_human_status(payload):
    if payload.get("online"):
        print(f"Netdata  online  {payload.get('url')}")
        if payload.get("netdata_version"):
            print(f"version  {payload['netdata_version']}")
        if payload.get("hostname"):
            print(f"host     {payload['hostname']}")
    else:
        print(f"Netdata  offline  {payload.get('url')}")
        print(f"error    {payload.get('error')}")


def print_human_now(now):
    ram = now.get("ram")
    used = now.get("ram_used_gb")
    total = now.get("ram_total_gb")
    ram_s = fmt_pct(ram)
    if used is not None and total is not None:
        ram_s = f"{ram_s} ({used:g}/{total:g} GB)"
    print(f"CPU      {fmt_pct(now.get('cpu'))}")
    print(f"RAM      {ram_s}")
    print(f"GPU      {fmt_pct(now.get('gpu'))}")
    print(f"Disk     {fmt_pct(now.get('disk'))}")
    print(f"Load     {now.get('load1') or '—'}  {now.get('load5') or '—'}  {now.get('load15') or '—'}")


def print_human_history(stats, label):
    print(f"Window   {label}")
    for key in ("cpu", "ram", "gpu"):
        print(f"{key.upper():<8}{fmt_stat(stats.get(key))}")


def print_human_report(payload):
    print_human_status(payload)
    if not payload.get("online"):
        for tip in payload.get("advice") or []:
            print(f"- {tip}")
        return
    print()
    print_human_now(payload.get("now") or {})
    print()
    keys = payload.get("window_keys") or PANEL_WINDOWS
    for key in keys:
        w = (payload.get("windows") or {}).get(key)
        if not w:
            continue
        print_human_history(w, key)
        print()
    print("For your next computer")
    for tip in payload.get("advice") or []:
        print(f"- {tip}")


def open_dashboard(base):
    url = base.rstrip("/") + "/"
    try:
        import shutil
        import subprocess

        opener = shutil.which("xdg-open") or shutil.which("gio")
        if opener:
            subprocess.Popen([opener, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(url)
            return 0
    except OSError:
        pass
    print(url)
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="system-health-check",
        description="Track CPU/GPU/RAM over time via Netdata (CLI + Omarchy bar data source).",
    )
    p.add_argument("--url", default=DEFAULT_URL, help=f"Netdata base URL (default {DEFAULT_URL})")
    p.add_argument("--json", action="store_true", help="Machine-readable JSON on stdout")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Check whether Netdata is reachable")
    sub.add_parser("now", help="Current CPU / RAM / GPU / disk / load")

    h = sub.add_parser("history", help="Average / Maximum / p95 over a window (e.g. 7d, 14d, 30d)")
    h.add_argument("window", nargs="?", default="7d", help="Window like 24h, 7d, 14d, 30d")

    r = sub.add_parser("report", help="Sizing summary from Netdata history")
    r.add_argument("window", nargs="?", default="7d", help="Focus window for advice (e.g. 14d)")

    pan = sub.add_parser("panel", help="JSON payload for the Omarchy bar plugin")
    pan.add_argument("--window", default="7d", help="Focus window for sparklines + advice")

    c = sub.add_parser("charts", help="Sparkline series for a window")
    c.add_argument("window", nargs="?", default="7d", help="Window like 24h, 7d, 30d")

    sub.add_parser("open", help="Open the Netdata dashboard")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    base = args.url

    if args.cmd == "open":
        return open_dashboard(base)

    if args.cmd == "status":
        try:
            meta = info(base)
            hosts = meta.get("mirrored_hosts")
            payload = {
                "ok": True,
                "online": True,
                "url": base.rstrip("/"),
                "netdata_version": meta.get("version"),
                "os": meta.get("os_name"),
                "hostname": hosts[0] if isinstance(hosts, list) and hosts else None,
            }
        except NetdataError as e:
            payload = {"ok": False, "online": False, "url": base.rstrip("/"), "error": str(e)}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print_human_status(payload)
        return 0 if payload.get("online") else 1

    if args.cmd == "panel":
        payload = panel_payload(base, focus_window=args.window)
        print(json.dumps(payload, indent=2 if args.json else None))
        return 0 if payload.get("ok") else 1

    if args.cmd == "report":
        payload = panel_payload(base, focus_window=args.window)
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print_human_report(payload)
        return 0 if payload.get("ok") else 1

    if args.cmd == "now":
        try:
            charts = list_charts(base)
            now = build_now(base, charts)
            payload = {"ok": True, "online": True, "url": base.rstrip("/"), "now": now}
        except NetdataError as e:
            payload = {"ok": False, "online": False, "url": base.rstrip("/"), "error": str(e), "now": {}}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            if not payload.get("online"):
                print_human_status(payload)
            else:
                print_human_now(payload["now"])
        return 0 if payload.get("online") else 1

    if args.cmd == "history":
        try:
            label, seconds = parse_window(args.window)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
        try:
            charts = list_charts(base)
            stats = window_stats(base, charts, seconds)
            payload = {
                "ok": True,
                "online": True,
                "url": base.rstrip("/"),
                "window": label,
                "seconds": seconds,
                "stats": stats,
            }
        except NetdataError as e:
            payload = {"ok": False, "online": False, "url": base.rstrip("/"), "error": str(e), "window": args.window}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            if not payload.get("online"):
                print_human_status(payload)
            else:
                print_human_history(payload["stats"], label)
        return 0 if payload.get("online") else 1

    if args.cmd == "charts":
        try:
            label, seconds = parse_window(args.window)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
        try:
            charts = list_charts(base)
            payload = {
                "ok": True,
                "online": True,
                "url": base.rstrip("/"),
                "window": label,
                "series": series_for_window(base, charts, seconds),
            }
        except NetdataError as e:
            payload = {"ok": False, "online": False, "url": base.rstrip("/"), "error": str(e)}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            for key, series in (payload.get("series") or {}).items():
                print(f"{key}: {' '.join('—' if v is None else f'{v:.0f}' for v in series)}")
        return 0 if payload.get("online") else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
