# Reproducibility (Phase 4)

This repo aims to make benchmark runs auditable and repeatable (Phase 4: packaging + provenance; still not “secure” yet).

## Versions to pin

- Python: `3.10.x` (tested with `3.10.14`)
- Python deps: `requirements.txt`, `requirements-dev.txt`
- Kilo CLI: `0.25.1` (check with `kilo --version`)

## Environment setup

Create a virtualenv and install pinned deps:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements-dev.txt
```

## Provider setup (Kilo)

1) Put provider keys in `secrets/provider_apis.txt` (untracked). Example:

```text
chutes: <key>
nanogpt: <key>
nanogpt_base_url: https://.../v1
```

2) Configure Kilo providers:

```bash
python scripts/setup_kilo_providers.py --enable-exec
```

## Prepare competition data (Kaggle)

Example for `playground-series-s6e1`:

```bash
KAGGLE_CONFIG_DIR=secrets python competitions/playground-series-s6e1/prepare_competition.py --download
```

This creates:
- `competitions/<id>/public/` (agent-visible)
- `competitions/<id>/private/` (holdout labels; never mount into agent workspace)

Both are ignored by git; do not commit them.

## Run modes

### Host baseline (sanity)

```bash
python scripts/run_baseline.py --competition-dir competitions/playground-series-s6e1 --out tmp/submission.csv
```

Trivial constant baseline (useful as a floor):

```bash
python scripts/run_baseline.py --competition-dir competitions/playground-series-s6e1 --out tmp/submission.constant.csv --baseline-type constant
```

### Headless agent run (Kilo CLI)

```bash
python -m orchestrator.run_one auto --competition-id playground-series-s6e1 --provider chutes --model-id deepseek-ai/DeepSeek-V3.1-Terminus
```

### Sweep (batch)

```bash
python -m orchestrator.sweep --competition-id playground-series-s6e1 --models-path orchestrator/model_sets/v3_fast.json --runs-per-model 1 --concurrency 1
```

## Rebuild leaderboards

```bash
python -m orchestrator.leaderboard --import-results --write-root
```

## Run health report

Summarize success/timeout/invalid rates by model/config from `results/results.sqlite`:

```bash
python -m orchestrator.report
```

## Baseline normalization (absolute signal)

Compute and record two fixed host baselines per competition (`hgb` and `constant`) into the local sqlite DB:

```bash
python -m orchestrator.baselines --competition-id playground-series-s6e1
python -m orchestrator.baselines --competition-id bank-customer-churn-ict-u-ai
```

Then regenerate the root leaderboard to include baseline-normalized aggregates:

```bash
python -m orchestrator.leaderboard --write-root
```

## What gets recorded per run

Each run under `runs/<run_id>/` includes:
- `result.json` with `provenance`:
  - `spec_sha256`, `prompt_sha256`, `public_manifest_sha256`
  - `kilo_version`, `kilo_config_sha256` (redacted hash; no secrets)
- `artifacts/public_manifest.json` (hashed inventory of `competitions/<id>/public/`)

The root `LEADERBOARD.md` also includes a “Duplicate submissions (by normalized hash)” section to surface identical outputs.
