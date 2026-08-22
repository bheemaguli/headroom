"""Headroom advice from history — is this machine still enough?"""

from .windows import human_window


def _metric(window, name, field):
    stat = (window or {}).get(name) or {}
    if not stat.get("samples"):
        return None
    return stat.get(field)


def advice_from_windows(windows, now, focus=None):
    """Capacity tips for the selected range only (no cross-window fallback)."""
    focus = focus or "7d"
    phrase = human_window(focus)
    lead = f"Based on {phrase} usage analysis"
    window = (windows or {}).get(focus) or {}

    ram_avg = _metric(window, "ram", "avg")
    ram_p95 = _metric(window, "ram", "p95")
    ram_peak = _metric(window, "ram", "max")
    cpu_avg = _metric(window, "cpu", "avg")
    cpu_peak = _metric(window, "cpu", "max")
    gpu_avg = _metric(window, "gpu", "avg")
    gpu_peak = _metric(window, "gpu", "max")

    if all(v is None for v in (ram_avg, ram_p95, ram_peak, cpu_avg, cpu_peak, gpu_avg, gpu_peak)):
        return ["Not enough data to analyse this range yet."]

    tips = []
    total = (now or {}).get("ram_total_gb")

    if ram_avg is not None and ram_avg >= 70:
        tips.append("RAM averages high — this machine is short on memory headroom.")
    elif ram_p95 is not None and ram_p95 >= 80:
        tips.append("RAM p95 is high — size memory for sustained load, not idle.")
    elif ram_peak is not None and ram_peak >= 85 and (ram_avg or 0) < 50:
        tips.append(
            "RAM peaked hard but average stayed modest — treat that as a possible one-off "
            "unless those workloads follow you."
        )
    elif ram_peak is not None and ram_peak >= 85:
        tips.append("RAM peaks hard under load — size up if those workloads stay with you.")
    elif total is not None and total <= 16 and ram_avg is not None and ram_avg >= 55:
        tips.append(f"You are often using over half of {total:g} GB RAM — 32 GB is a safer target.")

    if cpu_avg is not None and cpu_avg >= 45:
        tips.append("CPU stays busy for long stretches — prioritize sustained multi-core performance.")
    elif cpu_peak is not None and cpu_peak >= 90 and (cpu_avg or 0) < 25:
        tips.append("CPU spikes look short or one-off; a mid-range CPU is probably enough.")

    if gpu_avg is not None and gpu_avg >= 25:
        tips.append("GPU sees real use — look for a discrete GPU or a strong modern iGPU.")
    elif gpu_peak is not None and gpu_peak >= 70 and (gpu_avg or 0) < 10:
        tips.append("GPU peaks are rare; integrated graphics may be fine.")
    elif gpu_avg is None and gpu_peak is None and (now or {}).get("gpu") is None:
        tips.append(
            "No GPU metrics from Netdata yet — enable the NVIDIA/AMD collector if you care about GPU headroom."
        )

    if not tips:
        tips.append(f"{lead}, nothing looks maxed — this machine should cover this period's use.")
    else:
        first = tips[0]
        # Lowercase only normal sentence case; keep acronyms like CPU/RAM.
        if first and first[0].isupper() and (len(first) == 1 or not first[1].isupper()):
            first = first[0].lower() + first[1:]
        tips[0] = f"{lead}, {first}"
    return tips
