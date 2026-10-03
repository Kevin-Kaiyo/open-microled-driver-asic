.PHONY: setup test sim evidence
setup:
	uv sync --locked
	uv run python scripts/fetch_models.py
test:
	uv run python -m unittest discover -s tests -v
	uv run python scripts/run_phase1.py --rtl-only
sim:
	uv run python scripts/run_phase1.py
evidence:
	uv run python scripts/run_phase1.py --publish-evidence
