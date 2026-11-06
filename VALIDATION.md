# Validation on 2026-10-22

The first three tasks are materialized and ready for candidate commands. No frontier model was invoked, and no real model benchmark scores have been produced.

| Check | Result |
| --- | --- |
| Orchestrator unit/integration tests | 15 passed |
| Full snapshot verification | All 3 passed |
| Candidate history excludes future reference commit | All 3 passed |
| Original source checkout preserved | Its four pre-existing modified files remain unchanged by this work |
| Baseline Portal API builds | All 3 passed |
| Baseline Bot API builds | All 3 passed |
| Baseline Functions builds | All 3 passed |
| Baseline frontend TypeScript checks | All 3 passed using Node 22.22.3 in Docker |
| Parallel candidate container smoke run | All 3 completed and submissions captured |
| Evaluator packet creation and JSON validation | All 3 passed |

The runner tests cover separate histories without remotes, capture of committed/uncommitted/new/ignored/deleted source, capture independent of candidate Git metadata, symlink preservation, argument substitution without shell interpretation, invalid configuration, unavailable tasks, weighted scoring, malformed judgments, process failures, timeout child cleanup, cancellation, bounded concurrency, and the complete candidate/evaluator subprocess workflow.

The full-repository Docker smoke run is `runs/20261022T120051Z-54d56cc1`. It used a deterministic JavaScript fixture and a deterministic Python evaluator. Its zero scores are schema fixtures, not model performance measurements. The candidate fixture confirmed the prompt and full source were available while host reference paths were unavailable inside its container. Each evaluator then received the corresponding baseline, captured submission, and real reference tree.

Detailed backend and frontend build commands and logs are under `private/validation/`. The initial frontend attempts installed dependencies through a macOS bind mount and timed out at five minutes. Retrying with an anonymous Docker volume for `node_modules` completed in approximately 160 seconds per task, including `npx tsc -b`. The passing retries used `npm ci --ignore-scripts --no-audit --no-fund`; this validates TypeScript compilation, not Vite bundling, browser behavior, or dependency install scripts.

No live application was started, no database was reseeded, no telephony or CRM request was made, and no paid prompt tests ran. Runtime integration testing and model/evaluator calibration remain work for actual benchmark runs. Provision isolated SQL/storage dependencies for any parallel integration tests, as described in README.md.

The current instruction overlays change only AGENTS.md for tasks 1 and 3, and AGENTS.md plus AspenAI.Portal.Frontend/AGENTS.md for task 2. All other copied instruction files were already identical to the historical versions. The complete copied instruction set is hashed in each snapshot manifest.

## Portable bootstrap validation on 2026-11-02

All 22 unit/integration tests passed, including seven bootstrap tests covering fresh and incremental builds, repeat invocations, unchanged source checkouts, preserved inspection edits, missing/shallow history, changed instructions, failed verification cleanup, partial outputs, and corrupted references.

A temporary Git repository was created using the benchmark's actual `.gitignore`, then cloned into an empty directory. Its 39 tracked files totaled approximately 265 KB, with no generated repositories or run data. Running `python3 bootstrap.py --source /Users/taogroves/repos/AspenAI` in that fresh clone rebuilt and verified all three tasks without any files from the original `private/` directory. All baseline file manifests, reference file manifests, instruction hashes, and source tree IDs matched the original benchmark. The fresh clone's Git working tree remained clean after generating the heavy artifacts.

Bootstrap validation details are retained locally in `private/validation/bootstrap-share.json` and `private/validation/bootstrap-fresh-clone.log`. Dependency installation and application builds were not repeated because bootstrap reproduces the previously validated source trees exactly.
# Claude Agent SDK validation (2026-11-06)

Installed and pinned `@anthropic-ai/claude-agent-sdk` 0.3.318. A tool-free SDK request authenticated with the root `.env` OAuth token in a temporary home/config directory, with no API key or cached login supplied, and returned the exact requested marker.

The live parallel runner smoke test passed for `haiku`, `sonnet`, and `opus`, resolving to `claude-haiku-5-5`, `claude-sonnet-5-5`, and `claude-opus-5-5`. Each used real coding tools to repair an independent tiny repository, executed its tests, and produced a captured submission that passed independent assertions with the original tests unchanged. Evidence is in `private/validation/claude-20261106T163624Z-a0bb373f/summary.json` and its referenced process logs.

A subsequent Haiku fixture also passed the complete evaluator handoff: private baseline/candidate/reference packet, live model review, judgment file, SDK metadata sidecar, schema validation, and scoreboard completion. Evidence is in `private/validation/claude-20261106T163758Z-8827174f/summary.json`. These are transport fixtures, not results on the three AspenAI benchmark tasks; no full project task was run.

All 22 Python tests and 4 Node adapter tests passed. Git ignore checks confirmed `.env` and installed SDK dependencies are excluded while `.env.example` and the package lock remain shareable. Local host execution was verified; a Claude SDK Docker image and isolated application services were not built by this check.

