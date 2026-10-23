"""Command-line interface for cronsplain."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .core import CronError, explain


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="cronsplain",
        description="Explain a cron schedule in plain English.",
        epilog=(
            'examples:\n'
            '  cronsplain "*/15 9-17 * * 1-5"\n'
            '  cronsplain --json "0 9 * * MON-FRI"'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    result.add_argument(
        "-j", "--json", action="store_true", help="output a structured JSON object"
    )
    result.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    result.add_argument(
        "expression",
        nargs="*",
        help="five-field cron expression; reads stdin when omitted",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    argument_parser = parser()
    args = argument_parser.parse_args(argv)
    expression = " ".join(args.expression).strip()

    if not expression and not sys.stdin.isatty():
        expression = sys.stdin.read().strip()
    if not expression:
        argument_parser.print_usage(sys.stderr)
        print("cronsplain: error: a cron expression is required", file=sys.stderr)
        return 2

    try:
        result = explain(expression)
    except CronError as error:
        print(f"cronsplain: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["description"])
    return 0
