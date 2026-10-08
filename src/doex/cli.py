"""CLI entry: ``doex``, ``doex --version``, ``doex doctor``."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="doex",
        description="Adaptive DoE / experiment-campaign GUI",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print package version and exit",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("doctor", help="Check runtime dependencies")
    sub.add_parser("gui", help="Launch GUI (default)")

    args = parser.parse_args(argv)

    if args.version:
        from doex import __version__

        print(__version__)
        return 0

    if args.command == "doctor":
        return _doctor()

    # Default: GUI (also ``doex gui``)
    return _launch_gui()


def _doctor() -> int:
    ok = True
    checks = [
        ("numpy", "numpy"),
        ("pandas", "pandas"),
        ("sklearn", "sklearn"),
        ("matplotlib", "matplotlib"),
        ("PyQt5", "PyQt5.QtWidgets"),
    ]
    for label, mod in checks:
        try:
            __import__(mod)
            print(f"OK  {label}")
        except Exception as exc:  # noqa: BLE001 — doctor must report any failure
            ok = False
            print(f"FAIL {label}: {exc}")
    return 0 if ok else 1


def _launch_gui() -> int:
    try:
        from doex.app import run_app
    except ImportError as exc:
        print(f"GUI import failed: {exc}", file=sys.stderr)
        return 1
    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
