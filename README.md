# cronsplain

`cronsplain` turns a standard five-field cron expression into plain English. It is a small Python CLI with no runtime dependencies and can also emit structured JSON for scripts.

```console
$ cronsplain "0 9 * * MON-FRI"
At 9:00 AM on Monday through Friday.

$ cronsplain --json "*/15 9-17 * * 1-5"
{
  "input": "*/15 9-17 * * 1-5",
  "normalized": "*/15 9-17 * * 1-5",
  "description": "Every 15 minutes from 9:00 AM through 5:45 PM on Monday through Friday.",
  "fields": {
    "minute": {
      "expression": "*/15",
      "human": "0, 15, 30, and 45",
      "values": [0, 15, 30, 45]
    }
  },
  "warnings": []
}
```

## Install

Python 3.9 or newer is required. For an isolated command-line installation:

```sh
pipx install .
```

For development:

```sh
python -m pip install -e .
python -m unittest discover -s tests
```

The source checkout can also be run directly:

```sh
PYTHONPATH=src python -m cronsplain "30 8 * * 1-5"
echo "0 0 1 JAN *" | PYTHONPATH=src python -m cronsplain --json
```

## Supported syntax

- Five fields: minute, hour, day of month, month, and day of week
- Wildcards (`*`), lists (`1,15`), ranges (`MON-FRI`), and steps (`*/10`, `1-20/2`)
- Three-letter English month and weekday names, case-insensitively
- `@yearly`, `@annually`, `@monthly`, `@weekly`, `@daily`, `@midnight`, `@hourly`, and `@reboot`
- Sunday as either `0` or `7`

When both day-of-month and day-of-week are restricted, the description and JSON warning call out traditional cron's OR behavior.

## Library API

```python
from cronsplain import explain

result = explain("0 9 * * MON-FRI")
print(result["description"])
```
