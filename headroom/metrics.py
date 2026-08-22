"""Derive CPU / RAM / GPU / disk / load metrics from Netdata charts."""

from .client import NetdataError, chart_data
from .discover import discover_gpu_chart, find_chart_by_substr, pick_chart
from .parse import cloudwatch_stats, dimension_index, dimension_names, rows_from_payload
from .windows import points_for_window


def cpu_busy_rows(base, after, points, group="average"):
    payload = chart_data(base, "system.cpu", after, points=points, group=group, options="absolute")
    names = dimension_names(payload)
    idle_i = dimension_index(payload, "idle")
    rows = rows_from_payload(payload)
    out = []
    for ts, vals in rows:
        if idle_i is not None and idle_i < len(vals) and vals[idle_i] is not None:
            busy = max(0.0, min(100.0, 100.0 - float(vals[idle_i])))
        else:
            busy = 0.0
            for i, _name in enumerate(names):
                if i >= len(vals) or vals[i] is None:
                    continue
                busy += float(vals[i])
            busy = max(0.0, min(100.0, busy))
        out.append((ts, round(busy, 2)))
    return out


def cpu_busy_series(base, after, points, group="average"):
    return [v for _ts, v in cpu_busy_rows(base, after, points, group=group)]


def ram_used_rows(base, after, points, group="average"):
    payload = chart_data(base, "system.ram", after, points=points, group=group, options="absolute")
    names = [n.lower() for n in dimension_names(payload)]
    idx = {n: i for i, n in enumerate(names)}
    rows = rows_from_payload(payload)
    out = []
    for ts, vals in rows:

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
            out.append((ts, round(100.0 * used / total, 2)))
        else:
            out.append((ts, None))
    return out


def ram_used_series(base, after, points, group="average"):
    return [v for _ts, v in ram_used_rows(base, after, points, group=group)]


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


def first_dimension_rows(base, chart, after, points, group="average"):
    if not chart:
        return []
    payload = chart_data(base, chart, after, points=points, group=group, options="absolute")
    names = [n.lower() for n in dimension_names(payload)]
    rows = rows_from_payload(payload)
    out = []
    for ts, vals in rows:
        if not vals:
            out.append((ts, None))
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
        out.append((ts, None if chosen is None else round(chosen, 2)))
    return out


def first_dimension_series(base, chart, after, points, group="average"):
    return [v for _ts, v in first_dimension_rows(base, chart, after, points, group=group)]


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


def series_rows_for_window(base, charts, seconds):
    """Timestamped rows for CSV export: (ts, cpu, ram, gpu)."""
    points = points_for_window(seconds)
    gpu_chart = discover_gpu_chart(charts)
    cpu = {ts: v for ts, v in cpu_busy_rows(base, seconds, points)}
    ram = {ts: v for ts, v in ram_used_rows(base, seconds, points)}
    gpu = (
        {ts: v for ts, v in first_dimension_rows(base, gpu_chart, seconds, points)}
        if gpu_chart
        else {}
    )
    timestamps = sorted(set(cpu) | set(ram) | set(gpu))
    return [(ts, cpu.get(ts), ram.get(ts), gpu.get(ts)) for ts in timestamps]
