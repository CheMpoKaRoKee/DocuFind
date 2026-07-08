"""Developer CLI for checking core bootstrap wiring."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.utils.logger import LOG_CATEGORIES, get_logger, setup_logging


def bootstrap_check() -> int:
    log_dir = setup_logging(portable=True)
    logger = get_logger("app")
    logger.info("Bootstrap check completed")

    payload = {
        "status": "ok",
        "project_root": str(Path.cwd()),
        "log_dir": str(log_dir),
        "log_categories": sorted(LOG_CATEGORIES),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="docufind-dev", description="DocuFind Local developer utilities")
    subparsers = parser.add_subparsers(dest="command")

    check_parser = subparsers.add_parser("bootstrap-check", help="Verify bootstrap logging and package imports")
    check_parser.set_defaults(func=lambda _args: bootstrap_check())

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

