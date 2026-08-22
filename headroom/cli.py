"""CLI entry: argparse + command dispatch."""

import argparse
import json
import shutil
import subprocess
import sys

from .client import NetdataError, info, list_charts
from .constants import DEFAULT_URL
from .export import export_csv
from .formatters import (
    print_human_history,
    print_human_now,
    print_human_report,
    print_human_status,
)
from .metrics import build_now, series_for_window, window_stats
from .panel import panel_payload
from .windows import resolve_window


def open_dashboard(base):
    url = base.rstrip("/") + "/"
    try:
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
        prog="headroom",
        description="Track CPU/GPU/RAM headroom over time via Netdata (CLI + Omarchy bar data source).",
    )
    p.add_argument("--url", default=DEFAULT_URL, help=f"Netdata base URL (default {DEFAULT_URL})")
    p.add_argument("--json", action="store_true", help="Machine-readable JSON on stdout")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Check whether Netdata is reachable")
    sub.add_parser("now", help="Current CPU / RAM / GPU / disk / load")

    h = sub.add_parser("history", help="Average / Maximum / p95 over a window (e.g. 7d, 14d, 30d)")
    h.add_argument("window", nargs="?", default="7d", help="Window like 24h, 7d, 14d, 30d")
    h.add_argument("--days", type=int, help="Shortcut for Nd (1–90), overrides window")

    r = sub.add_parser("report", help="Sizing summary from Netdata history")
    r.add_argument("window", nargs="?", default="7d", help="Focus window for advice (e.g. 14d)")
    r.add_argument("--days", type=int, help="Shortcut for Nd (1–90), overrides window")

    pan = sub.add_parser("panel", help="JSON payload for the Omarchy bar plugin")
    pan.add_argument("--window", default="7d", help="Focus window for sparklines + advice")
    pan.add_argument("--days", type=int, help="Focus last N days and add that range to the panel")
    pan.add_argument("--extra-days", type=int, help="Also include a custom Nd preset in window keys")

    c = sub.add_parser("charts", help="Sparkline series for a window")
    c.add_argument("window", nargs="?", default="7d", help="Window like 24h, 7d, 30d")
    c.add_argument("--days", type=int, help="Shortcut for Nd (1–90), overrides window")

    ex = sub.add_parser("export", help="Export avg/max/p95 header + time series as CSV")
    ex.add_argument("window", nargs="?", default="7d", help="Window like 24h, 7d, 14d")
    ex.add_argument("--days", type=int, help="Shortcut for Nd (1–90), overrides window")
    ex.add_argument("-o", "--output", default="-", help="File path, directory, or - for stdout")

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
        focus = args.window
        extra = getattr(args, "extra_days", None)
        if args.days is not None:
            try:
                focus, _seconds = resolve_window(days=args.days)
            except ValueError as e:
                print(str(e), file=sys.stderr)
                return 2
            extra = args.days if extra is None else extra
        payload = panel_payload(base, focus_window=focus, extra_days=extra)
        print(json.dumps(payload, indent=2 if args.json else None))
        return 0 if payload.get("ok") else 1

    if args.cmd == "report":
        try:
            label, _seconds = resolve_window(args.window, getattr(args, "days", None))
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
        payload = panel_payload(base, focus_window=label, extra_days=getattr(args, "days", None))
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
            label, seconds = resolve_window(args.window, getattr(args, "days", None))
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
            payload = {
                "ok": False,
                "online": False,
                "url": base.rstrip("/"),
                "error": str(e),
                "window": args.window,
            }
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
            label, seconds = resolve_window(args.window, getattr(args, "days", None))
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

    if args.cmd == "export":
        try:
            label, seconds = resolve_window(args.window, getattr(args, "days", None))
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
        try:
            out = export_csv(base, label, seconds, path=args.output)
        except NetdataError as e:
            print(str(e), file=sys.stderr)
            return 1
        if out != "-" and not args.json:
            print(out)
        elif args.json:
            print(json.dumps({"ok": True, "path": out, "window": label}, indent=2))
        return 0

    return 2
