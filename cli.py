#!/usr/bin/env python3
"""headroom — thin entry for Omarchy QML and PATH wrappers.

Queries a local (or remote) Netdata agent and prints current usage, multi-day
history (CloudWatch-style Average / Maximum / p95), and sizing advice.
The Omarchy bar plugin calls `panel` for its chip and popup.
"""

import sys

from headroom.cli import main

if __name__ == "__main__":
    sys.exit(main())
