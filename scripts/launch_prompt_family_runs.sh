#!/usr/bin/env bash
set -euo pipefail

# Launch prompt-family evaluation runs (Chutes-only, v5_core suite).
#
# This script is meant to be started from the repo root:
#   bash scripts/launch_prompt_family_runs.sh
#
# It launches long-running jobs and writes logs under tmp/prompt_family_runs/.
# See docs/experiments/prompt_families_v5_core.md for the locked experiment design.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/tmp/prompt_family_runs"
mkdir -p "$LOG_DIR"
RUN_TS="$(date -u +%Y%m%d_%H%M%SZ)"

MODELS_PATH="$ROOT/orchestrator/model_sets/v3_fast.json"
SUITE_PATH="$ROOT/orchestrator/suites/v5_core.json"

TIMEGATED_DB="$ROOT/results/exp_promptfam_timegated.sqlite"
BUDGETAWARE_DB="$ROOT/results/exp_promptfam_budgetaware.sqlite"
BASELINE_PATCH_DB="$ROOT/results/exp_promptfam_baseline_patch.sqlite"

ONLY_PROVIDER="chutes"
CONCURRENCY="2"
RUNS_PER_MODEL="1"

echo "repo_root: $ROOT"
echo "suite_path: $SUITE_PATH"
echo "models_path: $MODELS_PATH"
echo "provider: $ONLY_PROVIDER"
echo "runs_per_model: $RUNS_PER_MODEL"
echo "concurrency: $CONCURRENCY"
echo "log_dir: $LOG_DIR"
echo

echo "=== [1/3] time-gated (current) ==="
echo "db: $TIMEGATED_DB"
TIMEGATED_LOG="$LOG_DIR/timegated_${RUN_TS}.log"
ln -sf "$(basename "$TIMEGATED_LOG")" "$LOG_DIR/timegated.log"
echo "log: $TIMEGATED_LOG"
(
  cd "$ROOT"
  set +e
  python -m orchestrator.suite \
    --models-path "$MODELS_PATH" \
    --profile good-baseline \
    --prompt-profile good-baseline-timegated \
    --runs-per-model "$RUNS_PER_MODEL" \
    --concurrency "$CONCURRENCY" \
    --db-path "$TIMEGATED_DB" \
    --mode pf_timegated \
    --resume-any-status
  RC_600=$?
  python -m orchestrator.suite \
    --models-path "$MODELS_PATH" \
    --profile sota-xgb \
    --prompt-profile sota-xgb-timegated \
    --runs-per-model "$RUNS_PER_MODEL" \
    --concurrency "$CONCURRENCY" \
    --db-path "$TIMEGATED_DB" \
    --mode pf_timegated \
    --resume-any-status
  RC_1200=$?
  echo "exit_codes: good-baseline(600)=$RC_600 sota-xgb(1200)=$RC_1200"
  exit 0
) >"$TIMEGATED_LOG" 2>&1 &
echo "started PID=$!"
echo

echo "=== [2/3] budget-aware (current; fixed prompt_profile across budgets) ==="
echo "db: $BUDGETAWARE_DB"
BUDGETAWARE_LOG="$LOG_DIR/budgetaware_${RUN_TS}.log"
ln -sf "$(basename "$BUDGETAWARE_LOG")" "$LOG_DIR/budgetaware.log"
echo "log: $BUDGETAWARE_LOG"
(
  cd "$ROOT"
  set +e
  python -m orchestrator.suite \
    --models-path "$MODELS_PATH" \
    --profile simple-baseline \
    --budget-seconds 240 \
    --prompt-profile budget-aware \
    --runs-per-model "$RUNS_PER_MODEL" \
    --concurrency "$CONCURRENCY" \
    --db-path "$BUDGETAWARE_DB" \
    --mode pf_budgetaware \
    --resume-any-status
  RC_240=$?
  python -m orchestrator.suite \
    --models-path "$MODELS_PATH" \
    --profile good-baseline \
    --budget-seconds 600 \
    --prompt-profile budget-aware \
    --runs-per-model "$RUNS_PER_MODEL" \
    --concurrency "$CONCURRENCY" \
    --db-path "$BUDGETAWARE_DB" \
    --mode pf_budgetaware \
    --resume-any-status
  RC_600=$?
  python -m orchestrator.suite \
    --models-path "$MODELS_PATH" \
    --profile sota-xgb \
    --budget-seconds 1200 \
    --prompt-profile budget-aware \
    --runs-per-model "$RUNS_PER_MODEL" \
    --concurrency "$CONCURRENCY" \
    --db-path "$BUDGETAWARE_DB" \
    --mode pf_budgetaware \
    --resume-any-status
  RC_1200=$?
  echo "exit_codes: budgetaware_240=$RC_240 budgetaware_600=$RC_600 budgetaware_1200=$RC_1200"
  exit 0
) >"$BUDGETAWARE_LOG" 2>&1 &
echo "started PID=$!"
echo

echo "=== [3/3] baseline patch (rerun missing ps-s6e1 @ 600 good-baseline, Chutes-only) ==="
BASELINE_SHA="f41af8d21a5e3fda3827b0d2b890f121d9a98028"
WORKTREE_DIR="$ROOT/tmp/worktrees/baseline_f41af8d2"
PATCH_MODELS="$ROOT/tmp/models_chutes_5.json"

mkdir -p "$(dirname "$WORKTREE_DIR")"

if ! git -C "$ROOT" worktree list | rg -q "$WORKTREE_DIR"; then
  echo "creating worktree: $WORKTREE_DIR @ $BASELINE_SHA"
  git -C "$ROOT" worktree add -f "$WORKTREE_DIR" "$BASELINE_SHA" >/dev/null
else
  echo "worktree already present: $WORKTREE_DIR"
fi

BASELINE_COMP_DIR="$WORKTREE_DIR/competitions/playground-series-s6e1"
if [ ! -e "$BASELINE_COMP_DIR/public" ]; then
  mkdir -p "$BASELINE_COMP_DIR"
  ln -s "$ROOT/competitions/playground-series-s6e1/public" "$BASELINE_COMP_DIR/public"
fi
if [ ! -e "$BASELINE_COMP_DIR/private" ] && [ -e "$ROOT/competitions/playground-series-s6e1/private" ]; then
  ln -s "$ROOT/competitions/playground-series-s6e1/private" "$BASELINE_COMP_DIR/private"
fi

cat >"$PATCH_MODELS" <<'JSON'
{
  "name": "chutes_5",
  "description": "Chutes-only 5-model set (for prompt-family experiments).",
  "models": [
    {"provider": "chutes", "model_id": "deepseek-ai/DeepSeek-V3.1-Terminus", "label": "DeepSeek V3.1 Terminus (Chutes)"},
    {"provider": "chutes", "model_id": "Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8", "label": "Qwen3 Coder 480B A35B Instruct FP8 (Chutes)"},
    {"provider": "chutes", "model_id": "zai-org/GLM-4.6-FP8", "label": "GLM 4.6 FP8 (Chutes)"},
    {"provider": "chutes", "model_id": "meta-llama/Meta-Llama-3.1-8B-Instruct", "label": "Llama 3.1 8B Instruct (Chutes)"},
    {"provider": "chutes", "model_id": "microsoft/Phi-3.5-mini-instruct", "label": "Phi 3.5 Mini Instruct (Chutes)"}
  ]
}
JSON

echo "db: $BASELINE_PATCH_DB"
BASELINE_PATCH_LOG="$LOG_DIR/baseline_patch_${RUN_TS}.log"
ln -sf "$(basename "$BASELINE_PATCH_LOG")" "$LOG_DIR/baseline_patch.log"
echo "log: $BASELINE_PATCH_LOG"
(
  cd "$WORKTREE_DIR"
  set +e
  python -m orchestrator.sweep \
    --competition-id playground-series-s6e1 \
    --models-path "$PATCH_MODELS" \
    --profile good-baseline \
    --runs-per-model "$RUNS_PER_MODEL" \
    --concurrency "$CONCURRENCY" \
    --db-path "$BASELINE_PATCH_DB" \
    --only-provider "$ONLY_PROVIDER" \
    --resume-any-status
  RC_PATCH=$?
  echo "exit_code: baseline_patch=$RC_PATCH"
  exit 0
) >"$BASELINE_PATCH_LOG" 2>&1 &
echo "started PID=$!"
echo

echo "Launched all jobs."
echo "Tail logs:"
echo "  tail -f $LOG_DIR/timegated.log"
echo "  tail -f $LOG_DIR/budgetaware.log"
echo "  tail -f $LOG_DIR/baseline_patch.log"
