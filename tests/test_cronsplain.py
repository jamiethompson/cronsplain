import json
import os
import subprocess
import sys
import unittest

from cronsplain import CronError, explain


class ExplainTests(unittest.TestCase):
    def test_daily_schedule(self):
        self.assertEqual(explain("0 9 * * *")["description"], "At 9:00 AM every day.")
        self.assertEqual(explain("*/5 * * * *")["description"], "Every 5 minutes.")
        self.assertEqual(explain("0 * * * *")["description"], "At minute 0 past every hour.")

    def test_weekday_business_hours(self):
        self.assertEqual(
            explain("*/15 9-17 * * MON-FRI")["description"],
            "Every 15 minutes from 9:00 AM through 5:45 PM on Monday through Friday.",
        )

    def test_lists_as_concrete_times(self):
        self.assertEqual(
            explain("0,30 9,17 * * *")["description"],
            "At 9:00 AM, 9:30 AM, 5:00 PM, and 5:30 PM every day.",
        )

    def test_shortcut(self):
        result = explain("@weekly")
        self.assertEqual(result["normalized"], "0 0 * * 0")
        self.assertEqual(result["description"], "At 12:00 AM on Sunday.")

    def test_sunday_as_seven(self):
        self.assertEqual(explain("0 0 * * 7")["fields"]["dayOfWeek"]["values"], [0])
        self.assertEqual(
            explain("0 0 * * 5-7")["description"],
            "At 12:00 AM on Friday through Sunday.",
        )

    def test_dom_dow_warning(self):
        result = explain("0 9 1 * MON")
        self.assertIn("either", result["description"])
        self.assertEqual(len(result["warnings"]), 1)

    def test_invalid_value(self):
        with self.assertRaisesRegex(CronError, "between 0 and 59"):
            explain("60 * * * *")

    def test_invalid_field_count(self):
        with self.assertRaisesRegex(CronError, "Expected 5 fields"):
            explain("0 9 * *")

    def test_month_range(self):
        self.assertEqual(
            explain("0 0 1 JAN-MAR *")["description"],
            "At 12:00 AM on the 1st day of the month in January through March.",
        )


class CliTests(unittest.TestCase):
    @staticmethod
    def run_cli(*args, stdin=None):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = "src"
        return subprocess.run(
            [sys.executable, "-m", "cronsplain", *args],
            input=stdin,
            text=True,
            capture_output=True,
            env=environment,
            check=False,
        )

    def test_plain_english(self):
        result = self.run_cli("0 9 * * *")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "At 9:00 AM every day.")

    def test_json(self):
        result = self.run_cli("--json", "0 9 * * MON-FRI")
        self.assertEqual(result.returncode, 0)
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed["description"], "At 9:00 AM on Monday through Friday.")
        self.assertEqual(parsed["fields"]["dayOfWeek"]["values"], [1, 2, 3, 4, 5])
        self.assertIn('\n  "input"', result.stdout)

    def test_stdin(self):
        result = self.run_cli(stdin="30 8 * * 1-5\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "At 8:30 AM on Monday through Friday.")

    def test_compact_option_does_not_exist(self):
        result = self.run_cli("--compact", "0 9 * * *")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unrecognized arguments: --compact", result.stderr)


if __name__ == "__main__":
    unittest.main()
