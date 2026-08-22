#!/usr/bin/env python3
"""system-health-check — thin entry for Omarchy QML and PATH wrappers.

Queries a local (or remote) Netdata agent and prints current usage, multi-day
history (CloudWatch-style Average / Maximum / p95), and a sizing report.
The Omarchy bar plugin calls `panel --json` for its chip and popup.
"""

import sys

from system_health_check.cli import main

if __name__ == "__main__":
    sys.exit(main())
