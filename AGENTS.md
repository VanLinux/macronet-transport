# AGENTS.md — MacroNet Transport

## Project purpose
MacroNet Transport is an open-source, educational desktop application for the classic four-step transportation-demand model. Its purpose is to teach and verify transportation modeling, not merely display final numbers. Preserve traceability of assumptions, equations, units, intermediate results and final outputs.

## Governance and authorship
- Copyright © 2026 Héctor Alonso Benítez García. Preserve existing copyright notices and credit.
- License: GNU GPL version 3 only (SPDX-License-Identifier: GPL-3.0-only). Do not change licensing or introduce incompatible dependencies without explicit approval.
- Do not commit secrets, credentials, personal travel data or private datasets.
- Never push directly to `main`, force-push, or merge without explicit approval. Work in dedicated branches and submit descriptive pull requests. Avoid unrelated refactors.

## Current stack and compatibility
- Python >=3.11, PySide6, NumPy, pandas, NetworkX, Matplotlib; packaging with hatchling.
- Primary development on Linux (Fedora and Ubuntu). Preserve Windows 11 compatibility. Prefer portable pathlib paths, platform-neutral code and documented GUI assumptions.
- Maintain the current `src/macronet` package layout and existing public entry points unless a change is explicitly approved.

## Scientific quality
- Keep numerical/model logic separate from presentation/UI code.
- Do not silently alter model formulas, defaults, units, calibration factors or demand assumptions.
- State algorithmic assumptions and limitations, including convergence criteria where relevant.
- Validate outputs with small, manually checkable cases; use deterministic inputs and numeric tolerances for floating-point comparisons.
- The present four-step workflow comprises trip generation/attraction, trip distribution, mode choice, and network assignment. Existing methods include gravitational distribution, logit mode choice and all-or-nothing assignment. Preserve their behavior unless specifically requested.

## Development workflow
1. Read `README.md`, `pyproject.toml` and applicable files under `docs/` before making architectural or scientific changes.
2. Keep changes minimal and focused, and update documentation for behavior or API changes.
3. Add or update tests in `tests/` for every model, bug fix or important behavior change.
4. Run `python -m pytest` and `python -m ruff check .` when dependencies are available. Report both pass/fail results accurately; do not claim checks were run if they were not.
5. If a task requires GUI tests in headless Linux, use `QT_QPA_PLATFORM=offscreen` as appropriate, and disclose any limitations.
6. Provide a pull request summary covering changes, mathematical assumptions, test evidence, and cross-platform implications.

## Useful commands
```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m macronet
```

## Approval boundaries
Ask before replacing a scientific method, changing licensing, modifying release/versioning strategy, removing datasets, adding costly or restrictive services, or restructuring the application.
