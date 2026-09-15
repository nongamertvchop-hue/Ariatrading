"""Backward-compatible alias for the hardened MT5 runtime CLI.

Historically this project exposed ``live.runtime_cli`` and later introduced
``live.live_runtime_cli`` with stronger validation, control-plane support, and
runtime safety limits. Keeping two implementations caused the documented CLI
entrypoints to drift. This module now delegates to the single hardened path.
"""

from live.live_runtime_cli import build_parser, main

__all__ = ["build_parser", "main"]


if __name__ == "__main__":
    main()
