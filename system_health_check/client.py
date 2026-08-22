"""HTTP client for the Netdata agent API."""

import json
import urllib.error
import urllib.parse
import urllib.request

from .constants import USER_AGENT


class NetdataError(Exception):
    pass


def _get(url, timeout=4.0):
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
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


def info(base):
    return api(base, "/api/v1/info", timeout=3.0)
