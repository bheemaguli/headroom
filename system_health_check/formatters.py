"""Human-readable stdout formatting for CLI commands."""

from .constants import PANEL_WINDOWS


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
