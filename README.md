# Headroom

Netdata-backed CPU · RAM · GPU **headroom** for [Omarchy](https://omarchy.org) — a bar chip with CloudWatch-style history, plus a CLI that answers whether this machine is still enough for the long run.

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
omarchy plugin add https://github.com/bheemaguli/headroom.git --enable
```

Optional CLI on your PATH:

```bash
ln -sf ~/.config/omarchy/plugins/bheemaguli.headroom/bin/headroom ~/.local/bin/headroom
```

## Bar chip

Shows live **CPU · RAM · GPU** percentages (e.g. `12·48·5`).

| Input | Action |
|-------|--------|
| Click | Open history panel |
| Middle-click | Refresh |
| Right-click | Open Netdata dashboard |

Panel: ranges **1h · 24h · 7d · 14d · 30d** with **avg / max / p95**, trend sparkline for the selected range, and **Is this machine enough?** advice.

Keyboard: `←` `→` range · `1`–`5` · `r` refresh · `o` Netdata · Esc close

## CLI

```bash
headroom status
headroom now
headroom history 7d
headroom history --days 12
headroom report --days 14
headroom charts 7d
headroom export 7d -o ~/Downloads/
headroom export --days 14 -o ./usage-14d.csv
headroom open
headroom panel --window 7d --extra-days 12
```

`--days N` is a shortcut for last N days (1–90). `export` writes a CSV with avg/max/min/p95 in the header comments and a timestamped series body.

Any `Ns` / `Nm` / `Nh` / `Nd` window works (max 90d), subject to what Netdata still has stored.

```bash
headroom --json history --days 14
HEADROOM_URL=http://127.0.0.1:19999 headroom report 30d
```

## Settings (bar widget)

| Key | Default | Meaning |
|-----|---------|---------|
| `netdataUrl` | `http://127.0.0.1:19999` | Netdata base URL |
| `defaultWindow` | `7d` | Initial history range |
| `customDays` | `0` | Remembered custom day count for the **C** tab (0 = unset) |
| `refreshSeconds` | `15` | Chip refresh interval |
| `cpuWarnPercent` | `85` | Warning threshold |
| `ramWarnPercent` | `80` | Warning threshold |
| `gpuWarnPercent` | `80` | Warning threshold |

In the panel: **C** opens a custom day range (input is labeled **days**), **✓** applies it. Advice always follows the selected history range. The history section’s **Export ↓** control saves CSV under `~/Downloads`; the NOW section’s refresh icon reloads live metrics.

## Two machines

```bash
omarchy plugin add https://github.com/bheemaguli/headroom.git --enable
omarchy pkg add netdata && sudo systemctl enable --now netdata
```

After a week or more: `headroom report 14d` (or the panel advice).

## Remove

```bash
omarchy plugin remove bheemaguli.headroom
```

Migrating from `bheemaguli.system-health-check`: remove the old plugin, then add Headroom and re-enable it on the bar.

## Development

Omarchy still loads from the plugin root (`BarWidget.qml`, `Panel.qml`, `cli.py`). Logic lives in the `headroom/` package; `cli.py` is a thin shim so the bar and `bin/headroom` keep the same paths.

```bash
# from the repo root
python3 -m unittest discover -s tests -v
python3 cli.py status
python3 -m headroom history 7d
```

Preset ranges (`1h` · `24h` · `7d` · `14d` · `30d`) are duplicated in `headroom/constants.py`, `Model.js`, and `manifest.json` — keep them in sync when changing tabs.

## License

MIT
