"""Backward-compatible alias for the hardened MT5 runtime CLI.

The project historically exposed two runtime CLI implementations. Keeping
both implementations allows safety and account-selection fixes to drift. This
module now delegates to the single hardened entrypoint.
"""

from live.live_runtime_cli import build_parser, main

__all__ = ["build_parser", "main"]


if __name__ == "__main__":
    main()
