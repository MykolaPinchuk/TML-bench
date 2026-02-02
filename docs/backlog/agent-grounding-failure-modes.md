# Agent Grounding Failure Modes (Backlog Note)

Status: **backlog / optional**

This document captures a meta-discussion about a common coding-agent failure mode: responding from “pattern intuition” instead of re-grounding on the current repo state. It is intended as a reference for future workflow improvements.

**Do not read by default.** Only consult this if you are actively debugging agent reliability, response quality, or workflow ergonomics.

---

## Problem statement

Coding agents often operate correctly when *executing* tasks (because the code itself provides feedback), but can be unreliable during *discussion* phases (design choices, interpretations of policy, “what should we do next?”). A frequent failure mode:

- The agent answers quickly from experience/patterns.
- It does not first re-check the authoritative local context (handoff, prompt profiles, ADRs, etc.).
- It may confidently opine on an incorrect interpretation (e.g., mixing up `>=` vs `<=` in a gating condition).
- Only after being challenged does it re-open the relevant files and revise.

This is costly because discussion often drives the next expensive action (runs, sweeps, refactors) and can lead to:

- wasted compute/time,
- wrong experiments,
- changes that regress reliability,
- reduced operator trust.

The core issue is **insufficient grounding at decision time**, not lack of raw capability.

---

## Why this happens (root causes)

### 1) “Pattern-first” bias under latency pressure
When asked for an opinion, the agent selects a plausible schema from prior experience and answers immediately, especially if the prompt resembles common patterns (“time left gate”, “reasoning phase”, “endgame”).

### 2) Context drift across turns
Even if the agent read the right documents earlier, it may not reliably re-apply the exact details when a later question arrives, particularly if:
- there were many intervening operations,
- multiple similar policies exist (variants across profiles),
- the new question is phrased slightly differently.

### 3) Ambiguity not treated as a blocker
Human phrasing can be underspecified (e.g., “6 minutes left” could mean “trigger at <=360s” or “trigger when >=360s remain”). Agents often resolve ambiguity internally rather than asking a 1-line clarifying question.

### 4) Tool-use asymmetry
Agents are trained/optimized to use tools for code execution and file edits, but often under-use tools for “thinking” tasks where grounding would help most.

---

## Design goals for mitigations

We want mitigations that are:

- **Generally applicable** across coding workflows (not repo-specific).
- **Lightweight** (seconds, not minutes).
- **Non-invasive** (no big infrastructure changes required).
- **Composable** (works with any existing repo conventions).
- **Fail-soft** (still useful even if only partially adopted).

---

## Proposed lightweight mitigations

### A) “Ground-first” micro-protocol (60–90 seconds)

Before giving an opinion that depends on local repo state:

1) Identify the likely “source of truth” artifacts (max 2–3).
2) Open/read them quickly.
3) Extract 1–2 factual anchors (“the policy says X, cap is Y”).
4) Only then provide the opinion.

Notes:
- This should be treated like a **pre-flight check** for reasoning, similar to running tests before refactoring.
- It’s especially valuable when the next step is expensive (long runs / sweeps / releases).

### B) “Anchor → inference” response format

Write answers in two parts:

- **Verified anchors:** 1–3 bullets of what the agent actually checked (file, key condition, default).
- **Inference / recommendation:** reasoning derived from those anchors.

Benefits:
- Forces the agent to ground.
- Makes errors easier to detect (operator can challenge the anchor).
- Works well in teams (shared understanding of facts vs opinions).

### C) “Ambiguity tripwire” (ask 1 question)

If a statement can plausibly map to >1 implementation (like `>=` vs `<=`, “minutes left” vs “minutes remaining”), the agent must ask a single clarifying question *before evaluating*.

Example patterns that should trigger the tripwire:
- threshold direction (`>=`, `<=`, “at least”, “only when close to”, “by the end”),
- scope (“all profiles” vs “only sota-xgb”),
- preconditions (“only after valid output exists”),
- where to measure time (wall clock, internal timeout, stage-based, etc.).

### D) “Session invariants” scratchpad (tiny)

Maintain a tiny per-session scratchpad (5–10 lines) for “active constraints / decisions”, updated when a policy changes.

Examples of content:
- “Reasoning gate: only after valid artifact exists; condition X; cap Y.”
- “Provider policy: use Chutes/OpenRouter; NanoGPT retired.”

This can live as:
- a section in `agent_logs/current.md`, or
- a short “Notes” snippet in the current task log.

Benefits:
- Reduces re-reading overhead while still remaining grounded.
- Helps with multi-turn drift.

### E) “Fast self-correction” norm

When the agent detects (or is told) it answered without grounding:

1) Re-open the source-of-truth file(s).
2) Restate the anchors.
3) Revise the recommendation accordingly.

Key is to make this routine and fast (not defensive), and to explicitly separate:
- what was assumed vs verified,
- how the recommendation changes given verified facts.

---

## Where this helps most (high-leverage situations)

- Any change to prompts, evaluation protocol, budgets, scoring, or privacy boundaries.
- “What do you think?” questions that precede expensive experiments.
- Debugging inconsistent results (monotonicity, variance, selection-regret).
- Policy or process questions (providers, model sets, allowed tools).

---

## Minimal adoption suggestion (if ever implemented)

If you want the smallest possible change with decent impact, adopt only:

1) **Ambiguity tripwire** (ask 1 clarifying question).
2) **Anchor → inference** structure for repo-specific opinions.

This costs little and prevents the worst “confidently wrong” outputs.

---

## Optional (heavier) ideas, not recommended for now

These are more invasive and should only be considered if lightweight measures are insufficient:

- Automated “citations” to local files for any repo-specific claim (requires tooling/UX).
- Repo-wide policy registry (structured YAML/JSON) to reduce ambiguity (maintenance cost).
- Mandatory checklists enforced by the harness (slower iteration; can feel bureaucratic).

---

## Example failure pattern (abstracted)

Human: proposes a change described informally (“6 minutes left reasoning enhancement”).

Common agent failure:
- interprets phrasing in a common-but-wrong way,
- doesn’t re-check the exact existing policy text,
- gives a recommendation that is mismatched to the actual current implementation.

Lightweight prevention:
- open the relevant handoff/prompt profile,
- extract 1 anchor (“current gate is X and only after condition Y”),
- ask 1 clarifying question if still ambiguous,
- then recommend.

