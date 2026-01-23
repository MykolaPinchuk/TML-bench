# playground-series-s6e1 (Phase 1)

This directory contains the canonical competition definition and preparation script for the benchmark.

## Canonical preparation (required)

Generate `public/` (agent-visible) and `private/` (holdout labels + scorer inputs) **only** via:

```bash
KAGGLE_CONFIG_DIR=secrets python competitions/playground-series-s6e1/prepare_competition.py --download
```

Notes:
- `competitions/playground-series-s6e1/public/` and `competitions/playground-series-s6e1/private/` are generated outputs and are gitignored.
- Do not hand-edit files under `public/` or `private/`. If you need to change the split or schema, update `spec.yaml` and re-run the script.

## What gets generated

- `public/train_public.csv`
- `public/test_public.csv`
- `public/sample_submission.csv`
- `public/README_task.md`
- `public/public_manifest.json`
- `private/holdout_labels.parquet`
- `private/split.json`

