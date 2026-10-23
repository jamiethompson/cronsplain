# cronsplain

`cronsplain` explains standard five-field cron expressions in plain English or structured JSON.

```console
$ cronsplain "*/15 9-17 * * MON-FRI"
Every 15 minutes from 9:00 AM through 5:45 PM on Monday through Friday.
```

## Install

Python 3.9 or newer is required. Install the command directly from GitHub with [pipx](https://pipx.pypa.io/):

```sh
pipx install git+https://github.com/jamiethompson/cronsplain.git
```

Then run it from any directory:

```sh
cronsplain "0 9 * * MON-FRI"
```

To upgrade later:

```sh
pipx upgrade cronsplain
```

## Usage

Pass the expression as one quoted argument:

```console
$ cronsplain "30 8 * * 1-5"
At 8:30 AM on Monday through Friday.
```

Use `-j` or `--json` for structured output:

```sh
cronsplain -j "0 9 * * MON-FRI"
cronsplain --json "0 9 * * MON-FRI"
```

The JSON object includes the original and normalized expressions, the English description, parsed values for every field, and any semantic warnings.

Expressions can also be piped over standard input:

```sh
echo "0 0 1 JAN *" | cronsplain
```

Available options:

```text
-j, --json     Output structured JSON
-h, --help     Show help
-v, --version  Show the version
```

## Supported syntax

- Five fields: minute, hour, day of month, month, and day of week
- Wildcards (`*`), lists (`1,15`), ranges (`MON-FRI`), and steps (`*/10`, `1-20/2`)
- Three-letter English month and weekday names, case-insensitively
- `@yearly`, `@annually`, `@monthly`, `@weekly`, `@daily`, `@midnight`, `@hourly`, and `@reboot`
- Sunday as either `0` or `7`

When both day-of-month and day-of-week are restricted, the description and JSON warning call out traditional cron's OR behavior.

## Development

Clone the repository and create a virtual environment:

```sh
git clone https://github.com/jamiethompson/cronsplain.git
cd cronsplain
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Run the test suite:

```sh
python -m unittest discover -s tests
```

Run directly from a source checkout without installing:

```sh
PYTHONPATH=src python -m cronsplain "30 8 * * 1-5"
```

## Library API

```python
from cronsplain import explain

result = explain("0 9 * * MON-FRI")
print(result["description"])
```
