# Contributing

Thanks for helping! Issues and pull requests are welcome in Vietnamese or English.

## Setup

    python3 -m venv .venv && . .venv/bin/activate
    pip install -e '.[all]'
    python3 -m unittest discover -s tests -v

## Ground rules

- Keep the core dependency-free (stdlib only); optional features go behind extras in `pyproject.toml`.
- Every extracted passage must keep a location that points back to the original.
- Automated checks may flag problems but must never mark semantic or scientific accuracy as passed.
- Tests use small **synthetic** text. Do not commit copyrighted books/papers, API keys or personal data.
- New source connectors: read [docs/connectors.md](docs/connectors.md). No paywall/login/anti-bot circumvention.
- No network calls in tests.

## Pull requests

One topic per PR, with tests. Describe what changed and how you verified it.
