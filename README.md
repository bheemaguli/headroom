# System Health Check

Netdata-backed CPU · RAM · GPU tracking for [Omarchy](https://omarchy.org) — a bar chip with CloudWatch-style history, plus a CLI for sizing your next computer.

Netdata does the collecting. This project is the Omarchy UI and command-line front end.

## Requirements

- Omarchy (for the bar plugin)
- [Netdata](https://www.netdata.cloud/) listening locally (default `http://127.0.0.1:19999`)
- Python 3

```bash
omarchy pkg add netdata
sudo systemctl enable --now netdata
```

Leave Netdata running for days/weeks so longer ranges (`14d`, `30d`) fill in. Retention is limited by Netdata’s disk quota (`multidb-disk-quota`).

## Install (Omarchy plugin)

```bash
omarchy plugin add https://github.com/bheemaguli/system-health-check.git --enable
```

Optional CLI on your PATH:

```bash
ln -sf ~/.config/omarchy/plugins/bheemaguli.system-health-check/bin/system-health-check ~/.local/bin/system-health-check
```

## Bar chip

Shows live **CPU · RAM · GPU** percentages (e.g. `12·48·5`).

| Input | Action |
|-------|--------|
| Click | Open history panel |
| Middle-click | Refresh |
| Right-click | Open Netdata dashboard |

Panel: ranges **1h · 24h · 7d · 14d · 30d** with **avg / max / p95**, trend sparkline for the selected range, and **For your next computer** advice.

Keyboard: `←` `→` range · `1`–`5` · `r` refresh · `o` Netdata · Esc close

## CLI

```bash
system-health-check status
system-health-check now
system-health-check history 7d
system-health-check history --days 12
system-health-check report --days 14
system-health-check charts 7d
system-health-check export 7d -o ~/Downloads/
system-health-check export --days 14 -o ./usage-14d.csv
system-health-check open
system-health-check panel --window 7d --extra-days 12
```

`--days N` is a shortcut for last N days (1–90). `export` writes a CSV with avg/max/min/p95 in the header comments and a timestamped series body.

Any `Ns` / `Nm` / `Nh` / `Nd` window works (max 90d), subject to what Netdata still has stored.

```bash
system-health-check --json history --days 14
SYSTEM_HEALTH_CHECK_URL=http://127.0.0.1:19999 system-health-check report 30d
```

## Settings (bar widget)

| Key | Default | Meaning |
|-----|---------|---------|
| `netdataUrl` | `http://127.0.0.1:19999` | Netdata base URL |
| `defaultWindow` | `7d` | Initial history range |
| `customDays` | `0` | Extra Nd preset (0 = off) |
| `refreshSeconds` | `15` | Chip refresh interval |
| `cpuWarnPercent` | `85` | Warning threshold |
| `ramWarnPercent` | `80` | Warning threshold |
| `gpuWarnPercent` | `80` | Warning threshold |

In the panel: set **Last N days** → **Apply**, or **Export CSV** (saves under `~/Downloads`).

## Two machines

```bash
omarchy plugin add https://github.com/bheemaguli/system-health-check.git --enable
omarchy pkg add netdata && sudo systemctl enable --now netdata
```

After a week or more: `system-health-check report 14d` (or the panel advice).

## Remove

```bash
omarchy plugin remove bheemaguli.system-health-check
```

## License

MIT
