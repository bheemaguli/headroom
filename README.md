# System Health Check

Netdata-backed CPU · RAM · GPU tracking for [Omarchy](https://omarchy.org) — a bar chip with history, plus a CLI for laptop-sizing reports.

Netdata does the collecting. This project is the Omarchy UI and command-line front end.

## Requirements

- Omarchy (for the bar plugin)
- [Netdata](https://www.netdata.cloud/) listening locally (default `http://127.0.0.1:19999`)
- Python 3

```bash
omarchy pkg add netdata
sudo systemctl enable --now netdata
```

## Install (Omarchy plugin)

```bash
omarchy plugin add https://github.com/bheemaguli/system-health-check.git --enable
```

Optional CLI on your PATH:

```bash
ln -sf ~/.config/omarchy/plugins/bheemaguli.system-health-check/bin/system-health-check ~/.local/bin/system-health-check
```

Or run from a checkout:

```bash
./bin/system-health-check report
```

## Bar chip

Shows live **CPU · RAM · GPU** percentages from Netdata (e.g. `12·48·5`).

| Input | Action |
|-------|--------|
| Click | Open history panel |
| Middle-click | Refresh |
| Right-click | Open Netdata dashboard |

Panel keyboard: `←` `→` window · `1`/`2`/`3` · `r` refresh · `o` Netdata · Esc close

### What the panel shows

- **Now** — CPU, RAM (with GB), GPU, load, disk
- **History** — avg / peak for 1h · 24h · 7d
- **Last 24h** — sparklines
- **For your next laptop** — short advice from those windows

## CLI

```bash
system-health-check status
system-health-check now
system-health-check history 24h
system-health-check report
system-health-check charts 7d
system-health-check open
system-health-check panel          # JSON for the bar plugin
```

Flags:

```bash
system-health-check --url http://127.0.0.1:19999 report
system-health-check --json now
```

`SYSTEM_HEALTH_CHECK_URL` overrides the default Netdata base URL.

## Settings (bar widget)

| Key | Default | Meaning |
|-----|---------|---------|
| `netdataUrl` | `http://127.0.0.1:19999` | Netdata base URL |
| `refreshSeconds` | `15` | How often the chip refreshes |
| `cpuWarnPercent` | `85` | Chip warning threshold |
| `ramWarnPercent` | `80` | Chip warning threshold |
| `gpuWarnPercent` | `80` | Chip warning threshold |

## Two machines

Same install on each box:

```bash
omarchy plugin add https://github.com/bheemaguli/system-health-check.git --enable
omarchy pkg add netdata && sudo systemctl enable --now netdata
```

After a week, run `system-health-check report` (or read the panel advice) before you buy.

## Remove

```bash
omarchy plugin remove bheemaguli.system-health-check
```

## License

MIT
