# Working in the framework

## Before every commit

1. Run `black .` (pinned in `requirements-dev.txt`, configured in `pyproject.toml`).
2. Run `black --check .` and the tests (`python -m pytest tests -q`).
3. Commit only when both pass.

GitHub runs `black --check .` and fails the build if any file would change.
