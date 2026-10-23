"""Command-line interface for cronsplain."""

from __future__ import annotations

import getopt
import sys

from . import __version__
from .core import CronError, explain


USAGE = 'Usage: cronsplain [-j|--json] "<cron expression>"'
HELP = f'''{USAGE}

Explain a five-field cron schedule in plain English.
Reads standard input when the expression is omitted.

Options:
  -j, --json     Output a structured JSON object
  -h, --help     Show this help
  -v, --version  Show the version

Examples:
  cronsplain "*/15 9-17 * * 1-5"
  cronsplain --json "0 9 * * MON-FRI"'''


def main(argv: list[str] | None = None) -> int:
    try:
        options, parts = getopt.gnu_getopt(
            sys.argv[1:] if argv is None else argv, "jhv", ["json", "help", "version"]
        )
    except getopt.GetoptError as error:
        print(f"{USAGE}\ncronsplain: error: {error}", file=sys.stderr)
        return 2
    for option, _ in options:
        if option in ("-h", "--help"):
            print(HELP)
            return 0
        if option in ("-v", "--version"):
            print(f"cronsplain {__version__}")
            return 0
    expression = " ".join(parts).strip()

    if not expression and not sys.stdin.isatty():
        expression = sys.stdin.read().strip()
    if not expression:
        print(f"{USAGE}\ncronsplain: error: a cron expression is required", file=sys.stderr)
        return 2

    try:
        result = explain(expression)
    except CronError as error:
        print(f"cronsplain: {error}", file=sys.stderr)
        return 1

    if any(option in ("-j", "--json") for option, _ in options):
        import json

        print(json.dumps(result, indent=2))
    else:
        print(result["description"])
    return 0
