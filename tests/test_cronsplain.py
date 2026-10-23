import json
import os
from itertools import combinations
from pathlib import Path
import subprocess
import sys
import unittest

from cronsplain import CronError, explain

ROOT = Path(__file__).resolve().parents[1]


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

    def test_field_local_steps(self):
        cases = {
            "*/1 * * * *": "Every minute.",
            "*/90 * * * *": "At minute 0 past every hour.",
            "*/7 * * * *": "At 0, 7, 14, 21, 28, 35, 42, 49, and 56 minutes past every hour.",
            "*/59 * * * *": "At 0 and 59 minutes past every hour.",
            "0-59/15 * * * *": "Every 15 minutes.",
            "5-5/90 * * * *": "At minute 5 past every hour.",
            "0 */2 * * *": "At minute 0 past every 2 hours.",
            "0 */5 * * *": "At 12:00 AM, 5:00 AM, 10:00 AM, 3:00 PM, and 8:00 PM every day.",
            "0 */24 * * *": "At 12:00 AM every day.",
            "0 */90 * * *": "At 12:00 AM every day.",
            "*/60 9-10 * * *": "At 9:00 AM and 10:00 AM every day.",
            "0-5/90 9 * * *": "At 9:00 AM every day.",
            "*/7 9-10 * * *": (
                "At minutes 0, 7, 14, 21, 28, 35, 42, 49, and 56 past hours 9 and 10 every day."
            ),
        }
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertEqual(explain(expression)["description"], expected)

    def test_complete_fields_and_singleton_ranges(self):
        cases = {
            "0-59 0-23 * * *": "Every minute.",
            "* 9,17 * * *": "Every minute during the 9:00 AM and 5:00 PM hours.",
            "* 9 * * *": "Every minute from 9:00 AM through 9:59 AM.",
            "0 9 * * 0-7": "At 9:00 AM every day.",
            "0 9 * * SUN-7": "At 9:00 AM every day.",
            "0 9 * * 0,7": "At 9:00 AM on Sunday.",
            "0 9 * * 7-7": "At 9:00 AM on Sunday.",
            "0 9 * JAN-DEC *": "At 9:00 AM every day.",
            "0 9 * */1 *": "At 9:00 AM every day.",
            "0 9 * JAN-JAN *": "At 9:00 AM every day in January.",
            "0 9 * * 6,7": "At 9:00 AM on Saturday through Sunday.",
        }
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertEqual(explain(expression)["description"], expected)

    def test_day_matching_uses_leading_star_not_complete_values(self):
        cases = {
            "0 9 */1 * MON": ("At 9:00 AM on Monday.", 0),
            "0 9 1-31 * MON": ("At 9:00 AM every day.", 1),
            "0 9 1 * */1": ("At 9:00 AM on the 1st day of the month.", 0),
            "0 9 1 * 0-7": ("At 9:00 AM every day.", 1),
            "0 9 *,1 * MON": ("At 9:00 AM on Monday.", 0),
            "0 9 1,* * MON": ("At 9:00 AM every day.", 1),
            "0 9 1 * *,MON": ("At 9:00 AM on the 1st day of the month.", 0),
            "0 9 1 * MON,*": ("At 9:00 AM every day.", 1),
        }
        for expression, (expected, warnings) in cases.items():
            with self.subTest(expression=expression):
                result = explain(expression)
                self.assertEqual(result["description"], expected)
                self.assertEqual(len(result["warnings"]), warnings)

    def test_restricted_day_conjunctions(self):
        month_days = (
            "the 1st, 3rd, 5th, 7th, 9th, 11th, 13th, 15th, 17th, 19th, "
            "21st, 23rd, 25th, 27th, 29th, and 31st days of the month"
        )
        result = explain("0 9 */2 * MON")
        self.assertEqual(
            result["description"], f"At 9:00 AM when it is {month_days} and it is Monday."
        )
        self.assertEqual(result["warnings"], [])
        both_steps = explain("0 9 */2 * */2")
        self.assertIn("and it is Sunday, Tuesday, Thursday, and Saturday", both_steps["description"])
        for field in ("*/2,2", "2,*/2"):
            result = explain(f"0 9 {field} * MON")
            with self.subTest(field=field):
                self.assertEqual("either" in result["description"], not field.startswith("*"))
                self.assertEqual(len(result["warnings"]), int(not field.startswith("*")))

    def test_all_shortcuts(self):
        aliases = {
            "@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *",
            "@monthly": "0 0 1 * *", "@weekly": "0 0 * * 0",
            "@daily": "0 0 * * *", "@midnight": "0 0 * * *", "@hourly": "0 * * * *",
        }
        for alias, expanded in aliases.items():
            with self.subTest(alias=alias):
                result = explain(alias.upper())
                self.assertEqual(result["normalized"], expanded)
                self.assertEqual(result["description"], explain(expanded)["description"])
        reboot = explain(" @REBOOT ")
        self.assertEqual(reboot["normalized"], "@reboot")
        self.assertEqual(reboot["description"], "At system startup.")
        self.assertIsNone(reboot["fields"])
        self.assertTrue(reboot["warnings"])

    def test_json_contract_and_normalization(self):
        result = explain("  00\t09 * jan-mar mon-fri  ")
        self.assertEqual(set(result), {"input", "normalized", "description", "fields", "warnings"})
        self.assertEqual(result["input"], "00\t09 * jan-mar mon-fri")
        self.assertEqual(result["normalized"], "00 09 * JAN-MAR MON-FRI")
        self.assertEqual(set(result["fields"]), {"minute", "hour", "dayOfMonth", "month", "dayOfWeek"})
        for field in result["fields"].values():
            self.assertEqual(set(field), {"expression", "human", "values"})
            self.assertIsInstance(field["expression"], str)
            self.assertIsInstance(field["human"], str)
            self.assertEqual(field["values"], sorted(set(field["values"])))
        self.assertEqual(result["fields"]["month"]["values"], [1, 2, 3])

    def test_mutating_a_result_does_not_change_later_results(self):
        result = explain("0 9 * * MON-FRI")
        result["fields"]["minute"]["values"].append(59)
        result["fields"]["dayOfWeek"]["values"].clear()
        result["warnings"].append("changed")
        result["fields"].clear()
        fresh = explain("0 9 * * MON-FRI")
        self.assertEqual(fresh["fields"]["minute"]["values"], [0])
        self.assertEqual(fresh["fields"]["dayOfWeek"]["values"], [1, 2, 3, 4, 5])
        self.assertEqual(fresh["warnings"], [])

    def test_invalid_inputs_raise_cron_error(self):
        invalid = (
            None, 42, "", " ", "* * * *", "* * * * * *", "@unknown",
            "60 * * * *", "* 24 * * *", "* * 0 * *", "* * * 13 *", "* * * * 8",
            "-1 * * * *", "* -1 * * *", "* * 32 * *", "* * * 0 *", "* * * * -1",
            "1,,2 * * * *", ",1 * * * *", "1, * * * *", "1- * * * *", "2-1 * * * *",
            "1-2-3 * * * *", "*/0 * * * *", "*/-1 * * * *", "*//2 * * * *",
            "1/2 * * * *", "*/1.0 * * * *", "1-4/ * * * *", "*/1/2 * * * *",
            "0-99/999 * * * *", "* * * DEC-JAN *", "* * * * FRI-MON",
            "JAN * * * *", "* * * MON *", "* * * * ?", "* * L * *", "* * * * MON#2",
            "² * * * *", "*/² * * * *", "٠ * * * *", "1-² * * * *", "*/١ * * * *",
            "9" * 5000 + " * * * *",
        )
        for expression in invalid:
            with self.subTest(expression=str(expression)[:60]):
                with self.assertRaises(CronError):
                    explain(expression)

    def test_generated_field_values(self):
        definitions = (
            ("minute", 0, 59), ("hour", 0, 23), ("dayOfMonth", 1, 31),
            ("month", 1, 12), ("dayOfWeek", 0, 7),
        )
        for index, (key, low, high) in enumerate(definitions):
            selections = [(str(value), {value}) for value in range(low, high + 1)]
            for start, end in combinations(range(low, high + 1), 2):
                for step in (1, 2, 3, 7, 100):
                    expected = {
                        value for value in range(low, high + 1)
                        if start <= value <= end and (value - start) % step == 0
                    }
                    selections.append((f"{start}-{end}/{step}", expected))
            selections.append(("1-5/2,2,4,1,3,5", {1, 2, 3, 4, 5}))
            for token, expected in selections:
                pieces = ["*"] * 5
                pieces[index] = token
                with self.subTest(field=key, token=token):
                    if key == "dayOfWeek":
                        expected = {value % 7 for value in expected}
                    actual = explain(" ".join(pieces))["fields"][key]["values"]
                    self.assertEqual(actual, sorted(expected))


class CliTests(unittest.TestCase):
    @staticmethod
    def run_cli(*args, stdin=""):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "cronsplain", *args],
            input=stdin,
            text=True,
            capture_output=True,
            env=environment,
            cwd=ROOT.parent,
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
        for option in ("--compact", "-c"):
            with self.subTest(option=option):
                result = self.run_cli(option, "0 9 * * *")
                self.assertEqual(result.returncode, 2)
                self.assertIn(option, result.stderr)
                self.assertEqual(result.stdout, "")

    def test_short_and_long_json_flags_match(self):
        short = self.run_cli("-j", "0 9 * * MON-FRI")
        long = self.run_cli("--json", "0 9 * * MON-FRI")
        self.assertEqual(short.returncode, 0)
        self.assertEqual(short.stdout, long.stdout)

    def test_options_after_expression_and_separate_fields(self):
        after = self.run_cli("0 9 * * MON-FRI", "-j")
        separate = self.run_cli("-j", "0", "9", "*", "*", "MON-FRI")
        self.assertEqual(after.returncode, 0)
        self.assertEqual(after.stdout, separate.stdout)

    def test_json_from_stdin(self):
        result = self.run_cli("-j", stdin="@hourly\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), explain("@hourly"))

    def test_help_and_version(self):
        for option in ("-h", "--help", "-v", "--version"):
            with self.subTest(option=option):
                result = self.run_cli(option)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stderr, "")
                self.assertIn("cronsplain", result.stdout)
                if option in ("-h", "--help"):
                    self.assertIn("--json", result.stdout)
                    self.assertNotIn("--compact", result.stdout)

    def test_invalid_usage(self):
        for args in ((), ("",), ("--nope",), ("--json=yes",)):
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("Usage:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_invalid_expressions_have_no_tracebacks(self):
        for expression in ("60 * * * *", "² * * * *", "*/² * * * *", "9" * 5000 + " * * * *"):
            with self.subTest(expression=expression[:40]):
                result = self.run_cli("-j", expression)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn("cronsplain:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_option_terminator(self):
        result = self.run_cli("-j", "--", "0 9 * * MON-FRI")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), explain("0 9 * * MON-FRI"))


if __name__ == "__main__":
    unittest.main()
