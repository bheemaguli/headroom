"""Shared constants.

PANEL_WINDOWS must stay in sync with Model.js PRESET_WINDOWS and
manifest.json barWidget.schema defaultWindow options.
"""

import os
import re

DEFAULT_URL = os.environ.get("SYSTEM_HEALTH_CHECK_URL", "http://127.0.0.1:19999")
# Presets shown in the bar panel (AWS console–style ranges).
PANEL_WINDOWS = ["1h", "24h", "7d", "14d", "30d"]
USER_AGENT = "system-health-check/1.3 (+omarchy-plugin)"
WINDOW_RE = re.compile(r"^(\d+)([smhd])$", re.IGNORECASE)
UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
MAX_WINDOW_SECONDS = 90 * 86400
