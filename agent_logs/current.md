# agent_logs/current.md

## Agent
- id: agent05

## Timestamp (Pacific)
- start: 2026-01-27

## Intent
- v5 (Phase 5): multi-competition benchmark + publishable leaderboard artifact (one-command reruns; deterministic outputs).

## Notes
- Do not commit secrets, Kaggle data, run artifacts, or sqlite DBs (see `.gitignore`).

## Log

- 2026-01-27 (Pacific): v5 branch initialized from merged v4 on `master`. Next: implement a first-class multi-competition runner + artifact packaging so reruns are cheap and reproducible across all 4 competitions.
- 2026-01-27 (Pacific): Handoff: `HANDOFF.md` updated to Phase 5, logs rotated (`agent04` archived), and v5 init commits created. Ready for next agent to start implementing the Phase 5 multi-competition runner + artifact packaging.
- 2026-01-27 (Pacific): Onboarded on v5. Repo is stable; `pytest -q` passes (11 tests). Current focus is Phase 5 “one command” multi-competition benchmark run + deterministic publishable artifact packaging (suite = 4 competitions; model sets under `orchestrator/model_sets/`). Next: design/implement a first-class multi-competition runner entrypoint that drives `orchestrator.sweep` / leaderboard refresh and emits a reproducible results bundle under `results/`.
- 2026-01-27 (Pacific): Added SOTA tier plumbing: `xgboost` pinned in `requirements.txt`, new `sota-xgb` prompt/sweep profile (1200s), and a `--budget-seconds` override for `run_one create/auto` + `orchestrator.sweep`. Added `orchestrator.sweep --resume` to skip already-recorded runs (DB-backed) and unit tests for resume/profile helpers. `pytest -q` passes (15 tests).
- 2026-01-27 (Pacific): Implemented Phase 5 multi-competition entrypoint `python -m orchestrator.suite` with default suite `orchestrator/suites/v5_core.json` (wraps `orchestrator.sweep` per competition, then refreshes root leaderboard). Docs updated (`README.md`, `docs/overview.md`, `REPRODUCIBILITY.md`); tests added; checkpoints committed on v5; `pytest -q` passes (18 tests).
- 2026-01-27 (Pacific): Ran long sweeps overnight-ish:
  - `good-baseline` across suite (runs-per-model=2, resume-any-status): mostly successful; saw one invalid submission on `playground-series-s5e10` (extra columns) and one headless timeout at 1200s boundary.
  - `sota-xgb` across suite (runs-per-model=1, resume-any-status): completed with one timeout.
  - Added missing per-competition prompt overrides for the 3 remaining competitions to reduce schema mistakes.
  - Added a small (5s) headless grace window for budget enforcement to avoid false timeouts near the boundary.
  - Refreshed leaderboard snapshots via `python -m orchestrator.leaderboard --import-results --write-root`.
- 2026-01-27 (Pacific): Follow-up: reran one previously invalid `good-baseline` run (`playground-series-s5e10`, `nanogpt` `mistralai/devstral-2-123b-instruct-2512`) after adding the competition override; new run succeeded and leaderboards refreshed.
- 2026-01-27 (Pacific): Follow-up: reran the previously timed-out `sota-xgb` case (`playground-series-s6e1`, `chutes` `microsoft/Phi-3.5-mini-instruct`); new run succeeded quickly and leaderboards refreshed.
- 2026-01-27 (Pacific): Updated prompting to use explicit prompt-profile snippets in `RUN_INSTRUCTIONS.md` (`simple-baseline`, `good-baseline`, `sota-xgb`) while avoiding model-specific optimization hints; profiles now emphasize using the full budget and iterative improvement, and allow multiple intermediate submissions as long as the best is left as `submission.csv`.
- 2026-01-28 (Pacific): Added OpenRouter support and ran `openrouter` models; discovered Kilo startup could hit a retired model (`mistralai/devstral-2512:free`) from `~/.kilocode/cli/global/global-state.json`, causing headless runs to stall until timeout. Fixed provider setup to keep Kilo’s default/global state on a known-good model and reran OpenRouter (successes recorded).
- 2026-01-28 (Pacific): Prompt-profile philosophy refined (no ML technique hints; emphasize time budget + maximize performance). Added leaderboard columns for time-used fraction. Observed OpenRouter models sometimes stop very early despite larger budgets (runtime_used << budget).
- 2026-01-28/29 (Pacific): **Major regression identified** after prompt + headless changes: OSS reruns under the “new prompts” showed sharp drops in success rates (many `timeout: no submission.csv produced`). Root cause appears to be models attempting IDE/extension tools in headless mode (`readFile`, `newFileCreated`, `updateTodoList`) which either do not execute or create empty files (e.g., `newFileCreated` with `content_len=0`), so the agent never actually writes `train_model.py` / `submission.csv`.
- 2026-01-29 (Pacific): Apples-to-apples rerun DB created: `results/results_oss_promptrefresh_v3.sqlite` (not committed) and snapshots committed. Conclusion: “new prompt” comparisons are confounded by headless tooling mismatch; the fix should focus on forcing shell-only workflows + explicit file verification rather than reverting the whole prompt philosophy.
- 2026-01-29 (Pacific): OpenRouter credits issue: `google/gemini-2.5-flash` exhausted credits; removed it from model sets and forced OpenRouter defaults to `x-ai/grok-4.1-fast` only.
