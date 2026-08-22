"""Parse Netdata chart payloads into series and CloudWatch-style stats."""


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
