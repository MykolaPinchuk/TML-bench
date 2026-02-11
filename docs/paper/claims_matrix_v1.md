# Claims Matrix v1 (Draft v1)

Scope: quantitative claims in `docs/paper/draft_v1.md`.

| Claim ID | Draft location | Claim text (abridged) | Evidence type | Evidence path(s) | Verification note |
|---|---|---|---|---|---|
| C1 | Sec 1 | v6 uses frozen v5.5 canonical evidence | direct | `docs/plan/v6.md`; `HANDOFF.md` | Both state v6 draft-first from v5.5 canonical baseline. |
| C2 | Sec 1 | Suite has 4 competitions (`v5_all`) | direct | `results.md` | Canonical scope block. |
| C3 | Sec 1 | Profiles are simple/good/sota with 240/600/1200s | direct | `results.md` | Canonical scope block. |
| C4 | Sec 1 | Inclusion rule is full `12/12` cells with 5 runs | direct | `results.md` | Canonical scope block. |
| C5 | Sec 1 | `10` models currently complete | direct | `results.md` | Reporting policy + coverage snapshot. |
| C6 | Sec 2 | Prompt strategy fixed to `profiled1` | direct | `results.md` | Canonical scope block. |
| C7 | Sec 2 | Cell value = median of earliest 5 successful runs | direct | `results.md` | Method block in auto section. |
| C8 | Sec 2 | Canonical evidence comes from nine sqlite sources | direct | `results.md` | Source DB list has 9 files. |
| C9 | Sec 2 | Regeneration commands are refresh + coverage scripts | direct | `docs/plan/v6.md`; `HANDOFF.md` | Both list command pair as reproducibility flow. |
| C10 | Sec 2 | Freeze check reports `9/9`, `10`, `0` | direct | local command output (`python scripts/check_profiled1_canonical_coverage.py`) | Output: `sources_found=9/9`, `canonical_models=10`, `missing_cells=0`, `status=OK`. |
| C11 | Sec 3.1 | Churn sota best = `0.928000` (GPT OSS) | direct | `results.md` | churn table, sota row. |
| C12 | Sec 3.1 | Churn simple best = `0.926671` (MiniMax) | direct | `results.md` | churn table, simple row. |
| C13 | Sec 3.1 | NVIDIA churn sota = `0.813105` | direct | `results.md` | churn table, sota row. |
| C14 | Sec 3.2 | MiniMax best in all three foot-traffic profiles | direct | `results.md` | foot-traffic table across 3 rows. |
| C15 | Sec 3.2 | GLM 4.7 Flash foot-traffic sota = `0.107502`, IQR `0.070186..0.221725` | direct | `results.md`; `docs/reports/v5_5_canonical10_stability.md` | Median from canonical table; IQR from stability report. |
| C16 | Sec 3.3 | s5e10 sota best = `0.056190` (GLM-4.6-FP8) | direct | `results.md` | s5e10 table, sota row. |
| C17 | Sec 3.3 | s5e10 top models are tightly clustered | inference | `results.md` | Difference between best and many peers is near `1e-4`. |
| C18 | Sec 3.4 | s6e1 sota best = `8.699779` (MiniMax) | direct | `results.md` | s6e1 table, sota row. |
| C19 | Sec 3.4 | TNG good-baseline s6e1 = `10.199380`, IQR `9.088197..13.444163` | direct | `results.md`; `docs/reports/v5_5_canonical10_stability.md` | Median + IQR match. |
| C20 | Sec 4 | Stability report contains narrow and wide IQR cells | direct | `docs/reports/v5_5_canonical10_stability.md` | Observed in multiple tables. |
| C21 | Sec 4 | Nemotron s6e1 simple = `9.054929 (9.043837..10.604385)` | direct | `docs/reports/v5_5_canonical10_stability.md` | s6e1 section. |
| C22 | Sec 4 | DeepSeek foot-traffic good = `0.068627 (0.066899..0.166052)` | direct | `docs/reports/v5_5_canonical10_stability.md` | foot-traffic section. |
| C23 | Sec 5 | Combined14 status = `10/14`, remaining runs `143` | direct | `results.md` | Latest run status section. |
| C24 | Sec 5 | Deferred models and counts `56/50/29/8` | direct | `results.md` | Latest run status section. |
| C25 | Sec 5 | Security-hardening out of scope in v6 | direct | `docs/plan/v6.md` | Scope decision + non-goals. |
| C26 | Sec 6 | Repro commands documented in appendix file | direct | `docs/paper/repro_appendix_v1.md` | File exists with command block. |
| C27 | Sec 6 | Full claim traceability documented in matrix | direct | `docs/paper/claims_matrix_v1.md` | This file. |
