# a2a_notes.md

Agent-to-agent operational notes for TML-bench.

Purpose:
- Preserve hard lessons from failed runs.
- Prevent long async stalls that waste operator time.
- Define a strict run-launch and monitoring contract for future agents.

## Primary objective (do not forget)
- This project exists to run many evaluations reliably and produce useful score tables across models/competitions/configurations.
- Throughput matters, but reliability is the hard requirement.
- A run that dies early and is discovered hours later is a critical failure, even if commands were "correct".

## Reliability mandate (explicit)
- Do not start a new long run unless logging is sufficient to explain why the previous run failed.
- After every run ends (success or failure), generate and read a postmortem before launching the next run.
- If root cause is unknown from logs, treat that as a blocking bug in orchestration/logging, not an operational nuisance.

## What went wrong before
- Runs were launched in ad-hoc shells without a stable control plane (no durable PID/status metadata).
- Multi-stage scripts could stop after one non-zero stage, so later profiles never started.
- Parallel sweep mode used to batch DB imports at the end; if parent process died, completed runs were not persisted to sqlite.
- Progress reporting relied on live terminal context that the operator could not inspect independently.
- `systemd-run --user` launcher initially missed shell PATH context; detached runs failed with `FileNotFoundError: 'kilo'` despite `kilo` existing interactively.
- `v5_5_topup3models_r5_20260206_r4` failed with a real OOM kill (not a stale-status artifact): systemd reported `Result=oom-kill`, peak memory ~19.4G, swap peak ~1.3G.
- Root trigger in that run: concurrent `foot-traffic` retries for `openai/gpt-oss-120b-TEE` generated dense one-hot features including `id` (~51k unique values), causing single-process RAM spikes (~15+ GB anon RSS) and host pressure.

## Non-negotiable run contract
When asked to "start a long run", always provide these immediately after launch:
1. `run_name`
2. `pid`
3. exact `log` path
4. exact `status` file path
5. 2 copy-paste monitor commands (`status` + `tail -f`)

If any item is missing, the launch is incomplete.

## Mandatory post-launch checks
Within 2 minutes of launch:
1. Confirm process is alive (`ps` by pid).
2. Confirm log is updating.
3. Confirm status file heartbeat is updating.
4. Confirm run moved into first real sweep stage.

If any check fails:
- restart immediately with the reliable launcher,
- report failure cause and new run metadata in the same reply.

## Required tooling for long async runs
- Use `python scripts/async_suite_runner.py start ...` for multi-hour suites.
- Do not use one-off `nohup ...` or backgrounded ad-hoc command chains for critical batches.
- Keep `--resume` on, and retry profiles until cells are filled or retry budget is exhausted.
- Use `python scripts/async_suite_runner.py diagnose --run-name <name>` after completion/crash and persist conclusions in `agent_logs/current.md`.
- If launcher is `systemd`, pass environment explicitly (`PATH` at minimum; also `HOME/PYENV/NVM` when present) and verify with an immediate `which kilo` probe.
- For `foot-traffic` + weaker reasoning models on short budgets, avoid high concurrency. Start at `--concurrency 1` and only increase after a clean pass.
- Suite-level safety is now implemented in `orchestrator/suite.py`: `foot-traffic-wuerzburg-retail-forecasting-2-0` is capped to `concurrency=1` automatically, even if global concurrency is higher.

## Persistence policy
- Prefer sweep paths where progress is persisted continuously, not only at job end.
- If using parallel sweep mode, ensure completed runs are imported to DB as each run finishes.

## Communication policy
- Never say "running" without verifiable metadata (pid/log/status).
- Never say "paused" without stating:
  - whether process exists,
  - exact stage/profile,
  - last log timestamp.
- If a run failed early, say it explicitly and estimate wasted wall-clock time.
- Report the concrete root cause evidence source (`status.json`, `events.jsonl`, `postmortem.md`, and log tail), not only the symptom.

## Handoff policy
- Record every async launch in `agent_logs/current.md` with:
  - mode, db path, model set, suite, runs-per-model, concurrency
  - run_name/pid/log/status
  - latest observed state and blockers
