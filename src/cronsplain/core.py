"""Parser and English formatter for standard five-field cron expressions."""

from __future__ import annotations

from typing import Any

MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
WEEKDAYS = (
    "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
)

FIELD_DEFINITIONS = (
    {"key": "minute", "label": "minute", "min": 0, "max": 59},
    {"key": "hour", "label": "hour", "min": 0, "max": 23},
    {"key": "dayOfMonth", "label": "day of month", "min": 1, "max": 31},
    {"key": "month", "label": "month", "min": 1, "max": 12, "names": MONTHS},
    {"key": "dayOfWeek", "label": "day of week", "min": 0, "max": 7, "names": WEEKDAYS},
)

ALIASES = {
    "@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *", "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *", "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}


class CronError(ValueError):
    """Raised when a cron expression cannot be parsed."""


def _format_list(items: list[Any]) -> str:
    rendered = [str(item) for item in items]
    if not rendered:
        return ""
    if len(rendered) == 1:
        return rendered[0]
    if len(rendered) == 2:
        return f"{rendered[0]} and {rendered[1]}"
    return f"{', '.join(rendered[:-1])}, and {rendered[-1]}"


def _ordinal(value: int) -> str:
    suffix = "th" if 11 <= value % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def _format_time(hour: int, minute: int) -> str:
    return f"{hour % 12 or 12}:{minute:02d} {'AM' if hour < 12 else 'PM'}"


def _integer(value: str, label: str) -> int:
    if value.isascii() and value.isdecimal():
        try:
            return int(value)
        except ValueError:
            pass
    raise CronError(f"Invalid {label}: {value}")


def _parse_number(value: str, definition: dict[str, Any]) -> int:
    for index, name in enumerate(definition.get("names", ())):
        if name[:3].upper() == value:
            return index + definition["min"]
    return _integer(value, f"{definition['label']} value")


def _assert_in_range(value: int, definition: dict[str, Any]) -> None:
    if not definition["min"] <= value <= definition["max"]:
        raise CronError(
            f"{definition['label'].capitalize()} must be between {definition['min']} "
            f"and {definition['max']}; received {value}"
        )


def _values_from_part(part: str, definition: dict[str, Any]) -> range:
    base, slash, step_text = part.partition("/")
    step = _integer(step_text, f"{definition['label']} step") if slash else 1
    if step == 0:
        raise CronError(f"Invalid {definition['label']} step: {step_text}")

    if base == "*":
        start, end = definition["min"], definition["max"]
    elif "-" in base:
        range_parts = base.split("-")
        if len(range_parts) != 2 or not all(range_parts):
            raise CronError(f"Invalid {definition['label']} range: {base}")
        start, end = (_parse_number(value, definition) for value in range_parts)
        _assert_in_range(start, definition)
        _assert_in_range(end, definition)
        if start > end:
            raise CronError(f"Invalid descending {definition['label']} range: {base}")
    else:
        if slash:
            raise CronError(f"A {definition['label']} step requires * or a range; received {part}")
        start = end = _parse_number(base, definition)
        _assert_in_range(start, definition)

    return range(start, end + 1, step)


def _parse_field(expression: str, definition: dict[str, Any]) -> dict[str, Any]:
    values: set[int] = set()
    for part in expression.split(","):
        values.update(_values_from_part(part, definition))
    is_weekday = definition["key"] == "dayOfWeek"
    if is_weekday and 7 in values:
        values.remove(7)
        values.add(0)
    return {
        "expression": expression,
        "values": sorted(values),
        "full": len(values) == (7 if is_weekday else definition["max"] - definition["min"] + 1),
        "star": expression.startswith("*"),
    }


def _describe_named_values(field: dict[str, Any], names: tuple[str, ...], offset: int = 0) -> str:
    values = field["values"]
    ordered = values[1:] + values[:1] if offset == 0 and values[0] == 0 and values[-1] == 6 else values
    if len(ordered) > 1 and all((b - a) % len(names) == 1 for a, b in zip(ordered, ordered[1:])):
        return f"{names[ordered[0] - offset]} through {names[ordered[-1] - offset]}"
    return _format_list([names[value - offset] for value in values])


def _interval(values: list[int], period: int) -> int:
    """Return an evenly spaced cycle's step, starting at zero, or zero otherwise."""
    step = values[1] if len(values) > 1 and values[0] == 0 else 0
    return step if step and period % step == 0 and values == list(range(0, period, step)) else 0


def _describe_minute_hour(minute: dict[str, Any], hour: dict[str, Any]) -> tuple[str, bool]:
    """Return the time clause and whether daily repetition is already implied."""
    minutes, hours = minute["values"], hour["values"]
    minute_step = _interval(minutes, 60)
    interval = "Every minute" if minute["full"] else f"Every {minute_step} minutes"
    if hour["full"]:
        if minute_step:
            return interval, True
        if len(minutes) == 1:
            return f"At minute {minutes[0]} past every hour", True
        return f"At {_format_list(minutes)} minutes past every hour", True
    if minute_step and hours[-1] - hours[0] + 1 == len(hours):
        return (
            f"{interval} from {_format_time(hours[0], minutes[0])} "
            f"through {_format_time(hours[-1], minutes[-1])}", True
        )
    if minute["full"]:
        return f"Every minute during the {_format_list([_format_time(h, 0) for h in hours])} hours", True
    hour_step = _interval(hours, 24)
    if len(minutes) == 1 and hour_step:
        return f"At minute {minutes[0]} past every {hour_step} hours", True
    if len(minutes) * len(hours) <= 12:
        return f"At {_format_list([_format_time(h, m) for h in hours for m in minutes])}", False
    return f"At minutes {_format_list(minutes)} past hours {_format_list(hours)}", False


def _describe_days(day_of_month: dict[str, Any], day_of_week: dict[str, Any], warnings: list[str]) -> str:
    # Cronie uses AND when either day field starts with '*', even in a list.
    either = not (day_of_month["star"] or day_of_week["star"])
    if either:
        warnings.append(
            "Both day-of-month and day-of-week are restricted. In traditional cron "
            "they use OR semantics, though some implementations differ."
        )
    month_full, week_full = day_of_month["full"], day_of_week["full"]
    if (month_full and week_full) or (either and (month_full or week_full)):
        return "every day"
    if month_full:
        return f"on {_describe_named_values(day_of_week, WEEKDAYS)}"
    month_days = (
        f"{_format_list([_ordinal(value) for value in day_of_month['values']])} "
        f"{'day' if len(day_of_month['values']) == 1 else 'days'} of the month"
    )
    if week_full:
        return f"on the {month_days}"
    week_days = _describe_named_values(day_of_week, WEEKDAYS)
    return f"when {'either ' if either else ''}it is the {month_days} {'or' if either else 'and'} it is {week_days}"


def _describe_months(month: dict[str, Any]) -> str:
    return "" if month["full"] else f" in {_describe_named_values(month, MONTHS, 1)}"


def _field_json(field: dict[str, Any], definition: dict[str, Any]) -> dict[str, Any]:
    values = field["values"]
    if field["full"]:
        human = f"every {definition['label']}"
    elif "names" in definition:
        human = _describe_named_values(field, definition["names"], definition["min"])
    else:
        human = _format_list(values)
    return {"expression": field["expression"], "human": human, "values": values}


def explain(expression: str) -> dict[str, Any]:
    """Parse and explain a standard five-field cron expression."""
    if not isinstance(expression, str) or not expression.strip():
        raise CronError("Cron expression must be a non-empty string")
    original = expression.strip()
    lower = original.lower()
    if lower == "@reboot":
        return {
            "input": original,
            "normalized": "@reboot",
            "description": "At system startup.",
            "fields": None,
            "warnings": ["@reboot is event-based and does not represent a recurring calendar schedule."],
        }

    pieces = ALIASES.get(lower, original).upper().split()
    if len(pieces) != len(FIELD_DEFINITIONS):
        raise CronError(
            "Expected 5 fields (minute hour day-of-month month day-of-week); "
            f"received {len(pieces)}"
        )
    parsed = {
        definition["key"]: _parse_field(pieces[index], definition)
        for index, definition in enumerate(FIELD_DEFINITIONS)
    }
    warnings: list[str] = []
    time, daily_implied = _describe_minute_hour(parsed["minute"], parsed["hour"])
    days = _describe_days(parsed["dayOfMonth"], parsed["dayOfWeek"], warnings)
    months = _describe_months(parsed["month"])
    description = f"{time}{'' if daily_implied and days == 'every day' else f' {days}'}{months}."
    return {
        "input": original,
        "normalized": " ".join(pieces),
        "description": description,
        "fields": {
            definition["key"]: _field_json(parsed[definition["key"]], definition)
            for definition in FIELD_DEFINITIONS
        },
        "warnings": warnings,
    }
