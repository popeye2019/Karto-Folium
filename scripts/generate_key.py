#!/usr/bin/env python
from __future__ import annotations

import secrets


def main() -> int:
    """Generate a random Flask secret key."""
    print(secrets.token_hex(32))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
