#!/usr/bin/env python3
"""system-health-check — Netdata-backed resource tracking for Omarchy.

Queries a local (or remote) Netdata agent and prints current usage, multi-window
history, and a short laptop-sizing report. The Omarchy bar plugin calls
`panel --json` for its chip and popup.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

DEFAULT_URL = os.environ.get("SYSTEM_HEALTH_CHECK_URL", "http://127.0.0.1:19999")
WINDOWS = {
    "1h": 3600,
    "6h": 6 * 3600,
    "24h": 24 * 3600,
    "7d": 7 * 24 * 3600,
}
USER_AGENT = "system-health-check/1.0 (+omarchy-plugin)"


class NetdataError(Exception):
    pass


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


def chart_data(base, chart, after, points=60, group="average", options="absolute", timeout=6.0):
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
        # Prefer shorter / more specific chart ids.
        score -= len(cid) // 10
        scored.append((score, cid))
    if not scored:
        return None
    scored.sort(reverse=True)
    return scored[0][1]


def dimension_index(payload, name):
    names = payload.get("dimension_names") or payload.get("labels") or []
    try:
        return list(names).index(name)
    except ValueError:
        return None


def rows_from_payload(payload):
    """Return list of (timestamp, values_list) newest-last when possible."""
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
    # Netdata often returns newest first.
    if len(rows) >= 2 and rows[0][0] > rows[-1][0]:
        rows.reverse()
    return rows


def series_stats(values):
    clean = [v for v in values if v is not None and isinstance(v, (int, float))]
    if not clean:
        return {"avg": None, "peak": None, "min": None, "samples": 0}
    return {
        "avg": round(sum(clean) / len(clean), 2),
        "peak": round(max(clean), 2),
        "min": round(min(clean), 2),
        "samples": len(clean),
    }


def cpu_busy_series(base, after, points):
    payload = chart_data(base, "system.cpu", after, points=points, options="absolute")
    names = list(payload.get("dimension_names") or [])
    idle_i = dimension_index(payload, "idle")
    rows = rows_from_payload(payload)
    out = []
    for _ts, vals in rows:
        if idle_i is not None and idle_i < len(vals) and vals[idle_i] is not None:
            busy = max(0.0, min(100.0, 100.0 - float(vals[idle_i])))
        else:
            busy = 0.0
            for i, name in enumerate(names):
                if name == "idle" or i >= len(vals) or vals[i] is None:
                    continue
                busy += float(vals[i])
            busy = max(0.0, min(100.0, busy))
        out.append(round(busy, 2))
    return out


def ram_used_series(base, after, points):
    # Prefer available-based accounting when Netdata exposes it.
    charts = None
    try:
        charts = list_charts(base)
    except NetdataError:
        charts = {}

    avail_chart = pick_chart(charts, ["mem.available", "system.ram_available"]) if charts else None
    if avail_chart:
        # Some installs expose available as a percent or absolute — handle both via system.ram.
        pass

    payload = chart_data(base, "system.ram", after, points=points, options="absolute")
    names = [str(n).lower() for n in (payload.get("dimension_names") or [])]
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
        # Netdata system.ram values are MiB.
        parts = [v for v in (used, free, cached, buffers) if v is not None]
        total = sum(parts) if parts else None
        if used is not None and total and total > 0:
            out.append(round(100.0 * used / total, 2))
        else:
            out.append(None)
    return out


def ram_snapshot(base):
    payload = chart_data(base, "system.ram", 5, points=2, options="absolute")
    names = [str(n).lower() for n in (payload.get("dimension_names") or [])]
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


def discover_gpu_mem_chart(charts):
    return (
        pick_chart(
            charts,
            [
                "nvidia_smi.mem_usage_gpu0",
                "nvidia_smi.memory_allocated_gpu0",
                "nvidia.gpu0_mem_usage",
            ],
        )
        or find_chart_by_substr(charts, ["nvidia", "mem"], prefer=["mem_usage", "memory"])
        or find_chart_by_substr(charts, ["amdgpu", "vram"], prefer=["vram", "memory"])
    )


def first_dimension_series(base, chart, after, points):
    if not chart:
        return []
    payload = chart_data(base, chart, after, points=points, options="absolute")
    rows = rows_from_payload(payload)
    out = []
    for _ts, vals in rows:
        if not vals:
            out.append(None)
            continue
        # Prefer a dimension that looks like a percentage / busy metric.
        names = [str(n).lower() for n in (payload.get("dimension_names") or [])]
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
    payload = chart_data(base, chart, 30, points=2, options="absolute")
    names = [str(n).lower() for n in (payload.get("dimension_names") or [])]
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
        payload = chart_data(base, "system.load", 30, points=2, options="absolute")
    except NetdataError:
        return {"load1": None, "load5": None, "load15": None}
    names = [str(n).lower() for n in (payload.get("dimension_names") or [])]
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
        return None

    return {
        "load1": get("load1", "1 minute", "1min"),
        "load5": get("load5", "5 minutes", "5min"),
        "load15": get("load15", "15 minutes", "15min"),
    }


def info(base):
    return api(base, "/api/v1/info", timeout=3.0)


def build_now(base, charts):
    cpu_series = cpu_busy_series(base, 10, 3)
    ram = ram_snapshot(base)
    load = load_snapshot(base)
    gpu_chart = discover_gpu_chart(charts)
    gpu_series = first_dimension_series(base, gpu_chart, 10, 3) if gpu_chart else []
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


def window_stats(base, charts, seconds, points):
    gpu_chart = discover_gpu_chart(charts)
    return {
        "cpu": series_stats(cpu_busy_series(base, seconds, points)),
        "ram": series_stats(ram_used_series(base, seconds, points)),
        "gpu": series_stats(first_dimension_series(base, gpu_chart, seconds, points) if gpu_chart else []),
    }


def advice_from_windows(windows, now):
    tips = []
    day = windows.get("24h") or windows.get("7d") or {}
    week = windows.get("7d") or day

    ram_peak = (day.get("ram") or {}).get("peak")
    ram_avg = (day.get("ram") or {}).get("avg")
    cpu_peak = (day.get("cpu") or {}).get("peak")
    cpu_avg = (day.get("cpu") or {}).get("avg")
    gpu_avg = (week.get("gpu") or {}).get("avg")
    gpu_peak = (week.get("gpu") or {}).get("peak")

    total = (now or {}).get("ram_total_gb")
    if ram_avg is not None and ram_avg >= 70:
        tips.append("RAM averages high — prefer more memory on the next laptop.")
    elif ram_peak is not None and ram_peak >= 85:
        tips.append("RAM peaks hard under load — size up if those workloads move with you.")
    elif total is not None and total <= 16 and ram_avg is not None and ram_avg >= 55:
        tips.append(f"You are often using over half of {total:g} GB RAM — 32 GB is a safer laptop target.")

    if cpu_avg is not None and cpu_avg >= 45:
        tips.append("CPU stays busy for long stretches — prioritize sustained multi-core performance.")
    elif cpu_peak is not None and cpu_peak >= 90 and (cpu_avg or 0) < 25:
        tips.append("CPU spikes are short; a mid-range laptop CPU is probably enough.")

    if gpu_avg is not None and gpu_avg >= 25:
        tips.append("GPU sees real use — look for a discrete GPU or a strong modern iGPU.")
    elif gpu_peak is not None and gpu_peak >= 70 and (gpu_avg or 0) < 10:
        tips.append("GPU peaks are rare; integrated graphics may be fine.")
    elif gpu_avg is None and gpu_peak is None:
        tips.append("No GPU metrics from Netdata yet — install/enable the NVIDIA/AMD collector if you care about GPU headroom.")

    if not tips:
        tips.append("Nothing looks maxed over the sampled windows — mid-range CPU/RAM should cover daily use.")
    return tips


def panel_payload(base):
    try:
        meta = info(base)
        charts = list_charts(base)
        now = build_now(base, charts)
        windows = {
            "1h": window_stats(base, charts, WINDOWS["1h"], 60),
            "24h": window_stats(base, charts, WINDOWS["24h"], 96),
            "7d": window_stats(base, charts, WINDOWS["7d"], 84),
        }
        series = {
            "cpu": cpu_busy_series(base, WINDOWS["24h"], 48),
            "ram": ram_used_series(base, WINDOWS["24h"], 48),
            "gpu": first_dimension_series(base, discover_gpu_chart(charts), WINDOWS["24h"], 48),
        }
        return {
            "ok": True,
            "online": True,
            "url": base.rstrip("/"),
            "hostname": meta.get("mirrored_hosts", [None])[0] if isinstance(meta.get("mirrored_hosts"), list) else meta.get("os_name"),
            "os": meta.get("os_name"),
            "netdata_version": meta.get("version"),
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "now": now,
            "windows": windows,
            "series": series,
            "advice": advice_from_windows(windows, now),
        }
    except NetdataError as e:
        return {
            "ok": False,
            "online": False,
            "url": base.rstrip("/"),
            "error": str(e),
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
        return "avg —  peak —"
    return f"avg {fmt_pct(stat['avg']):>4}  peak {fmt_pct(stat['peak']):>4}"


def print_human_status(payload):
    if payload.get("online"):
        print(f"Netdata  online  {payload.get('url')}")
        if payload.get("netdata_version"):
            print(f"version  {payload['netdata_version']}")
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


def print_human_history(windows, label):
    print(f"Window   {label}")
    for key in ("cpu", "ram", "gpu"):
        print(f"{key.upper():<8}{fmt_stat(windows.get(key))}")


def print_human_report(payload):
    print_human_status(payload)
    if not payload.get("online"):
        for tip in payload.get("advice") or []:
            print(f"- {tip}")
        return
    print()
    print_human_now(payload.get("now") or {})
    print()
    for key in ("1h", "24h", "7d"):
        w = (payload.get("windows") or {}).get(key)
        if not w:
            continue
        print_human_history(w, key)
        print()
    print("Advice")
    for tip in payload.get("advice") or []:
        print(f"- {tip}")


def open_dashboard(base):
    url = base.rstrip("/") + "/"
    # Prefer xdg-open on Omarchy; fall back to printing the URL.
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
    h = sub.add_parser("history", help="Average and peak usage over a window")
    h.add_argument("window", nargs="?", default="24h", choices=sorted(WINDOWS.keys()))
    r = sub.add_parser("report", help="Laptop-sizing summary from Netdata history")
    r.add_argument("window", nargs="?", default="24h", choices=sorted(WINDOWS.keys()))
    sub.add_parser("panel", help="JSON payload for the Omarchy bar plugin")
    c = sub.add_parser("charts", help="Sparkline series for a window")
    c.add_argument("window", nargs="?", default="24h", choices=sorted(WINDOWS.keys()))
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
            payload = {
                "ok": True,
                "online": True,
                "url": base.rstrip("/"),
                "netdata_version": meta.get("version"),
                "os": meta.get("os_name"),
            }
        except NetdataError as e:
            payload = {"ok": False, "online": False, "url": base.rstrip("/"), "error": str(e)}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print_human_status(payload)
        return 0 if payload.get("online") else 1

    if args.cmd == "panel":
        payload = panel_payload(base)
        print(json.dumps(payload, indent=2 if args.json else None))
        return 0 if payload.get("ok") else 1

    if args.cmd == "report":
        payload = panel_payload(base)
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
        seconds = WINDOWS[args.window]
        try:
            charts = list_charts(base)
            stats = window_stats(base, charts, seconds, 96 if seconds >= 86400 else 60)
            payload = {"ok": True, "online": True, "url": base.rstrip("/"), "window": args.window, "stats": stats}
        except NetdataError as e:
            payload = {"ok": False, "online": False, "url": base.rstrip("/"), "error": str(e), "window": args.window}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            if not payload.get("online"):
                print_human_status(payload)
            else:
                print_human_history(payload["stats"], args.window)
        return 0 if payload.get("online") else 1

    if args.cmd == "charts":
        seconds = WINDOWS[args.window]
        try:
            charts = list_charts(base)
            payload = {
                "ok": True,
                "online": True,
                "url": base.rstrip("/"),
                "window": args.window,
                "series": {
                    "cpu": cpu_busy_series(base, seconds, 48),
                    "ram": ram_used_series(base, seconds, 48),
                    "gpu": first_dimension_series(base, discover_gpu_chart(charts), seconds, 48),
                },
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
