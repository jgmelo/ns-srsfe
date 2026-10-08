# CLAUDE.md — SRS-FE

Design calculator (Textual TUI) for the resonant TIA front end of an SRS photodetector.

## Source of truth
- `docs/SPEC.md` defines formulas, parameters, tools, warnings, TUI layout, key map and
  golden values. Read the relevant section before each milestone.
- If the spec looks wrong or ambiguous: stop and ask. Do not silently deviate.
  When a change is agreed, update SPEC.md in the same commit as the code.

## Commands
- Install: `pip install -e ".[dev]"`
- Tests: `pytest -q`
- Run: `python -m srsfe`

## Conventions
- Python ≥ 3.11, type hints everywhere, `dataclasses` (frozen for results).
- **SI units internally, always.** Engineering prefixes only at the UI boundary
  (`core/units.py`). Every field's unit lives in its metadata in `core/params.py`.
- Identifiers exactly as in SPEC §3 (`r_f`, `f_0`, `t_dwell`, …).
- `core/` is pure: no textual, no matplotlib, no file I/O except `core/profiles.py`.
  Core functions take explicit arguments, never the whole `Params`.
- `plots/figures.py` returns Figures and never calls `plt.show()`.
- Numerics with numpy; no other scientific dependencies.
- Keys are declared next to the data they act on; never hard-code a key in a screen.

## Testing
- Write tests together with each module; a milestone is done only when `pytest -q` is green.
- Golden values: SPEC §9, loaded from `profiles/golden.json` via `tests/conftest.py`.
  Use `pytest.approx(rel=1e-3)`; dB values `abs=0.01`.
- Each warning in SPEC §5 needs one test where it fires and one where it does not.
- TUI: smoke tests with `App.run_test()` (pytest-asyncio) — screens open, keys navigate,
  calculate fills results. No pixel tests.

## Milestones (do in order; one at a time; summarize and wait for review after each)
- **M0** Scaffold: pyproject, package skeleton, `profiles/golden.json`, empty test passes.
- **M1** `params.py` (fields + metadata + validation), `units.py`, `profiles.py` (+ round-trip
  and migration tests).
- **M2** `tank.py`: `z_f`, `tank_from_dwell` (both q_modes), `tank_from_lc`.
- **M3** `spectrum.py`: I₀, q_p, I_pk, harmonics table, signal.
- **M4** `noise.py`: densities, v_rms, SNR, shot_clear, lock-in ENBW and SNR; `moku.py`.
- **M5** `budget.py` + `warnings.py` (W01–W09).
- **M6** `tools/` registry, Design and Analyze tools, `sweep.py`; Result JSON round-trip.
- **M7** `plots/figures.py` + `plots/runner.py` (tests: figures build without error,
  using the Agg backend).
- **M8** TUI shell: app, header/dirty flag, launcher, profiles screen, dialogs.
- **M9** Generic tool screen: groups, field highlighting, eng inputs, results table,
  warnings panel, plot menu, full key map + collision test.
- **M10** Polish: F1 help overlay, settings screen, last-used profile, stale-result greying.

## Don't
- Don't store derived values in profiles.
- Don't add features beyond SPEC (log ideas in `docs/IDEAS.md` instead).
- Don't change golden values to make tests pass — find the bug or ask.
