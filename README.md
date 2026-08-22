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
system-health-check history 14d
system-health-check history 30d
system-health-check report 14d
system-health-check charts 7d
system-health-check open
system-health-check panel --window 7d
```

Any `Ns` / `Nm` / `Nh` / `Nd` window works (max 90d), subject to what Netdata still has stored.

```bash
system-health-check --json history 14d
SYSTEM_HEALTH_CHECK_URL=http://127.0.0.1:19999 system-health-check report 30d
```

## Settings (bar widget)

| Key | Default | Meaning |
|-----|---------|---------|
| `netdataUrl` | `http://127.0.0.1:19999` | Netdata base URL |
| `defaultWindow` | `7d` | Initial history range |
| `refreshSeconds` | `15` | Chip refresh interval |
| `cpuWarnPercent` | `85` | Warning threshold |
| `ramWarnPercent` | `80` | Warning threshold |
| `gpuWarnPercent` | `80` | Warning threshold |

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
