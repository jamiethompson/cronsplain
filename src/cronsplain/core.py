"""Parser and English formatter for standard five-field cron expressions."""

from __future__ import annotations

import re
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


def _format_list(items: list[Any], conjunction: str = "and") -> str:
    rendered = [str(item) for item in items]
    if not rendered:
        return ""
    if len(rendered) == 1:
        return rendered[0]
    if len(rendered) == 2:
        return f"{rendered[0]} {conjunction} {rendered[1]}"
    return f"{', '.join(rendered[:-1])}, {conjunction} {rendered[-1]}"


def _ordinal(value: int) -> str:
    suffix = "th" if 11 <= value % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def _format_time(hour: int, minute: int) -> str:
    return f"{hour % 12 or 12}:{minute:02d} {'AM' if hour < 12 else 'PM'}"


def _simple_range(expression: str) -> tuple[str, str] | None:
    match = re.fullmatch(r"([A-Z]+|\d+)-([A-Z]+|\d+)", expression)
    return match.groups() if match else None


def _lookup_name(value: str, definition: dict[str, Any]) -> int | None:
    for index, name in enumerate(definition.get("names", ())):
        if name[:3].upper() == value.upper():
            return index + (1 if definition["key"] == "month" else 0)
    return None


def _parse_number(value: str, definition: dict[str, Any]) -> int:
    if value.isdigit():
        return int(value)
    named = _lookup_name(value, definition)
    if named is not None:
        return named
    raise CronError(f"Invalid {definition['label']} value: {value}")


def _assert_in_range(value: int, definition: dict[str, Any]) -> None:
    if not definition["min"] <= value <= definition["max"]:
        raise CronError(
            f"{definition['label'].capitalize()} must be between {definition['min']} "
            f"and {definition['max']}; received {value}"
        )


def _values_from_part(part: str, definition: dict[str, Any]) -> list[int]:
    pieces = part.split("/")
    if len(pieces) > 2:
        raise CronError(f"Invalid {definition['label']} segment: {part}")
    base = pieces[0]
    step_text = pieces[1] if len(pieces) == 2 else None
    if step_text is None:
        step = 1
    elif not step_text.isdigit() or int(step_text) < 1:
        raise CronError(f"Invalid {definition['label']} step: {step_text}")
    else:
        step = int(step_text)

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
        if step_text is not None:
            raise CronError(f"A {definition['label']} step requires * or a range; received {part}")
        start = end = _parse_number(base, definition)
        _assert_in_range(start, definition)

    values = list(range(start, end + 1, step))
    if definition["key"] == "dayOfWeek":
        values = [0 if value == 7 else value for value in values]
    return values


def _parse_field(expression: str, definition: dict[str, Any]) -> dict[str, Any]:
    if not expression or " " in expression:
        raise CronError(f"Invalid {definition['label']}: {expression or 'empty value'}")
    values = [
        value
        for part in expression.split(",")
        for value in _values_from_part(part, definition)
    ]
    return {
        "expression": expression.upper(),
        "values": sorted(set(values)),
        "wildcard": expression == "*",
    }


def _describe_named_values(field: dict[str, Any], names: tuple[str, ...], offset: int = 0) -> str:
    value_range = _simple_range(field["expression"])
    if value_range:
        def index_for(token: str) -> int:
            if token.isdigit():
                value = 0 if offset == 0 and int(token) == 7 else int(token)
                return value - offset
            return next(index for index, name in enumerate(names) if name[:3].upper() == token)
        return f"{names[index_for(value_range[0])]} through {names[index_for(value_range[1])]}"
    return _format_list([names[value - offset] for value in field["values"]])


def _describe_minute_hour(minute: dict[str, Any], hour: dict[str, Any]) -> str:
    minute_step = re.fullmatch(r"\*/(\d+)", minute["expression"])
    hour_step = re.fullmatch(r"\*/(\d+)", hour["expression"])
    hour_range = _simple_range(hour["expression"])
    if minute["wildcard"] and hour["wildcard"]:
        return "Every minute"
    if minute_step and hour["wildcard"]:
        return f"Every {minute_step.group(1)} minutes"
    if (minute_step or minute["wildcard"]) and hour_range:
        interval = f"Every {minute_step.group(1)} minutes" if minute_step else "Every minute"
        return (
            f"{interval} from {_format_time(hour['values'][0], minute['values'][0])} "
            f"through {_format_time(hour['values'][-1], minute['values'][-1])}"
        )
    if minute["wildcard"] and len(hour["values"]) == 1:
        return f"Every minute during the {hour['values'][0]}:00 hour"
    if len(minute["values"]) == 1 and hour_step:
        return f"At minute {minute['values'][0]} past every {hour_step.group(1)} hours"
    if len(minute["values"]) == 1 and len(hour["values"]) == 1:
        return f"At {_format_time(hour['values'][0], minute['values'][0])}"
    if hour["wildcard"]:
        if len(minute["values"]) == 1:
            return f"At minute {minute['values'][0]} past every hour"
        return f"At {_format_list(minute['values'])} minutes past every hour"
    if len(minute["values"]) * len(hour["values"]) <= 12:
        times = [_format_time(h, m) for h in hour["values"] for m in minute["values"]]
        return f"At {_format_list(times)}"
    return f"At minutes {_format_list(minute['values'])} past hours {_format_list(hour['values'])}"


def _describe_days(day_of_month: dict[str, Any], day_of_week: dict[str, Any], warnings: list[str]) -> str:
    if day_of_month["wildcard"] and day_of_week["wildcard"]:
        return "every day"
    month_days = (
        f"{_format_list([_ordinal(value) for value in day_of_month['values']])} "
        f"{'day' if len(day_of_month['values']) == 1 else 'days'} of the month"
    )
    week_days = _describe_named_values(day_of_week, WEEKDAYS)
    if day_of_month["wildcard"]:
        return f"on {week_days}"
    if day_of_week["wildcard"]:
        return f"on the {month_days}"
    warnings.append(
        "Both day-of-month and day-of-week are restricted. In traditional cron "
        "they use OR semantics, though some implementations differ."
    )
    return f"when either it is the {month_days} or it is {week_days}"


def _describe_months(month: dict[str, Any]) -> str:
    return "" if month["wildcard"] else f" in {_describe_named_values(month, MONTHS, 1)}"


def _field_json(field: dict[str, Any], definition: dict[str, Any]) -> dict[str, Any]:
    values = field["values"]
    if field["wildcard"]:
        human = f"every {definition['label']}"
    elif definition["key"] == "month":
        human = _format_list([MONTHS[value - 1] for value in values])
    elif definition["key"] == "dayOfWeek":
        human = _format_list([WEEKDAYS[value] for value in values])
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

    pieces = ALIASES.get(lower, original).split()
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
    time = _describe_minute_hour(parsed["minute"], parsed["hour"])
    days = _describe_days(parsed["dayOfMonth"], parsed["dayOfWeek"], warnings)
    months = _describe_months(parsed["month"])
    every_day_is_implied = (
        parsed["dayOfMonth"]["wildcard"]
        and parsed["dayOfWeek"]["wildcard"]
        and re.search(r"\bevery\b", time, re.IGNORECASE)
    )
    description = f"{time}{'' if every_day_is_implied else f' {days}'}{months}."
    return {
        "input": original,
        "normalized": " ".join(piece.upper() for piece in pieces),
        "description": description,
        "fields": {
            definition["key"]: _field_json(parsed[definition["key"]], definition)
            for definition in FIELD_DEFINITIONS
        },
        "warnings": warnings,
    }
