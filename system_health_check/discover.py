"""Locate Netdata charts by name or fuzzy metadata match."""


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
