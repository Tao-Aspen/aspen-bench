# Aspen Bench

Ten project-scale coding tasks are registered. The first three are implemented with full historical AspenAI repositories, human-style task prompts, private merged references, and weighted evaluator rubrics. Tasks 4-10 are reserved and cannot be run yet.

The runner uses Python 3.12+ and Git, with no Python package dependencies. Candidate and evaluator model integrations are supplied as commands. An optional pinned Claude Agent SDK adapter is included; live model calls happen only when you explicitly invoke it or its smoke check.

See [VALIDATION.md](VALIDATION.md) for the completed setup checks and their limits.

## Build after cloning

The Git repository contains only the runner, task specifications, tests, and a small frozen instruction snapshot. Full AspenAI histories, workspaces, reference code, patches, and run results are generated locally and ignored by Git.

From a fresh clone, with Python 3.12+ and Git installed:

```sh
python3 bootstrap.py --source ~/repos/AspenAI
```

This builds and verifies tasks 1, 2, and 3 by default. To start with a subset, add `--tasks 1`; running it later with `--tasks 1 2 3` verifies the existing task and builds the missing ones. The equivalent orchestrator command is `python3 orchestrator.py bootstrap --source ~/repos/AspenAI --tasks 1 2 3`.

The source checkout can be on any branch and have uncommitted changes. Bootstrap reads its Git history without switching branches, modifying files, or running repository hooks. It must contain the complete history through the commit pinned in `catalog.json`, including all selected PR commits. If history is missing, fetch main in that checkout first; for a shallow clone, fetch with `--unshallow`. Bootstrap itself makes no network requests and needs no Linear access, GitHub token, Docker daemon, model credentials, or package installation.

The tool reconstructs complete historical repositories and merged references, including the scoped PR patches. It overlays the exact original AGENTS.md and CLAUDE.md files from `dataset/instructions/`, so newer local instructions cannot change the benchmark. It checks the resulting source tree IDs against `dataset/manifest.json`, verifies file checksums and Git integrity, and checks that solution commits are absent from candidate history. Rebuilt overlay commit IDs and bundle bytes may vary with creation time; source trees and copied instructions must match the original benchmark.

New artifacts are built and verified in an ignored staging directory before being moved into place. Subsequent invocations verify and reuse completed tasks without overwriting inspection workspaces or runs. An incomplete set of existing outputs produces an error listing what to move aside before retrying. A force-killed build may leave an ignored `.bootstrap-*` staging directory; it can be removed after ensuring no bootstrap process is using it. Concurrent bootstrap invocations for the same benchmark are rejected.

This creates source repositories, not installed dependencies or running application services. Use the historical toolchain and service requirements below when executing agents. Original Linear research exports, old run results, and validation logs are archival evidence and are not required or regenerated; task provenance and PR scope are already included in the shareable specifications.

## Share through Git

Commit the benchmark directory normally. The included `.gitignore` excludes `private/`, `workspaces/`, `runs/`, generated bundles/manifests, staging directories, and Python caches. Keep `dataset/` tracked: its small instruction files and manifest are the inputs that make reconstruction independent of the original machine. No Git LFS or large-file hosting is required. Recipients need their own AspenAI checkout with the pinned history and run the bootstrap command above.

The task specifications and copied instructions contain internal AspenAI information; choose the repository's visibility accordingly. If generated files were already committed in a separate repository, `.gitignore` does not remove those existing Git objects or tracked files.

## Run candidates

```sh
cd ~/tools/aspen-bench
python3 orchestrator.py list
python3 orchestrator.py run --tasks 1 2 3 --jobs 3 \
  --candidate-command 'python3 /absolute/path/to/agent.py --prompt {prompt} --workspace {workspace}'
```

The command runs once per selected task, concurrently up to `--jobs`, with the task's fresh repository as its working directory. It must wait until the candidate is finished; do not detach the SDK session or background the real agent. Each attempt has its own full repository and Git object database. Neither the original AspenAI checkout nor the inspection workspaces are modified by a run.

`--candidate-command` is parsed as an argument vector, with normal shell-style quoting but no shell execution. Pipes, redirection, and shell substitutions are not evaluated. If you need a complex invocation, put it in your adapter. For exact argument handling, use `--candidate-config path/to/config.json` instead; start from [examples/candidate.json](examples/candidate.json).

Supported placeholders in command arguments and configured environment values:

| Placeholder | Value |
| --- | --- |
| `{prompt}` | Absolute path to the task prompt document |
| `{prompt_text}` | Full prompt text as one argument, for a CLI accepting text |
| `{workspace}` | Absolute path to this candidate's repository |
| `{output}` | Optional candidate report path; required JSON judgment path for evaluators |
| `{task}` | Stable task ID |
| `{run_id}` | Unique run ID |

Adapters also receive `ASPEN_PROMPT_FILE`, `ASPEN_WORKSPACE`, `ASPEN_RESULT_FILE`, and `ASPEN_TASK_ID`. Candidate output JSON is optional: the source tree is the submitted work. Stdout/stderr and process outcomes are captured separately. Candidate timeouts default to two hours; use `--candidate-timeout` with command mode, or `timeout_seconds` in JSON config. Model budgets and SDK permissions belong in the supplied adapter/config.

For an Agent SDK adapter, read the prompt document, set the SDK's working directory to the supplied workspace, start a fresh session, wait for all agent work, and exit with its completion status. Let the SDK read the copied repository instructions normally. No SDK dependency or vendor-specific behavior is assumed here.

## Claude Agent SDK

Install the optional adapter dependencies using Node 22.22.3 or later:

```sh
cd ~/tools/aspen-bench
npm ci --ignore-scripts
```

Put `CLAUDE_CODE_OAUTH_TOKEN=...` in the benchmark root `.env`, or export it in your environment. An `ANTHROPIC_API_KEY` is also supported. The adapter reads `.env` itself without evaluating shell expressions. Values in that file override the same environment variables, and an OAuth token takes precedence over an API key. Use `--env-file /path/to/file` to select another file. `.env` files and `node_modules` are ignored by Git; `.env.example` contains only an empty placeholder.

Check authentication and the complete integration with small disposable tasks:

```sh
python3 check_claude.py
```

This makes live calls using the `haiku`, `sonnet`, and `opus` aliases in parallel, verifies source edits and submission capture, then uses the first model to check the evaluator JSON handoff. Each SDK session has a $1 estimated-cost limit and a 150-second timeout. Use `--models haiku` for a smaller check, or pass exact model IDs. Logs and summaries go under `private/validation/claude-*`. These fixtures are not benchmark tasks or model performance scores. Subscription limits still apply, and SDK dollar estimates are not a billing statement.

Run the real first three tasks with a model ID verified on this machine:

```sh
python3 orchestrator.py run --tasks 1 2 3 --jobs 3 \
  --candidate-command "node '$PWD/adapters/claude.mjs' --model claude-opus-5-5 --prompt '{prompt}' --workspace '{workspace}' --output '{output}'"
```

Replace the model ID to compare models. The adapter records the requested and resolved model, SDK version, limits, usage, result, and tool transcript. It defaults to 200 turns and a 7,100-second SDK timeout, within the runner's 7,200-second timeout. Add `--max-turns`, `--max-budget-usd`, or `--timeout-seconds` inside the command to change those limits; increase `--candidate-timeout` outside the command when increasing the SDK timeout. Budget, turn-limit, authentication, and SDK errors produce nonzero exits so partial work is not mislabeled as a completed attempt.

The adapter uses the Claude Code system prompt and project settings, loads repository CLAUDE.md, and instructs the agent to follow AGENTS.md. Each session has an isolated temporary home/configuration directory, no resumed conversation, and no inherited user settings, API-key alternatives, provider overrides, or MCP connections. Only the selected credential and a small toolchain environment are forwarded. Credentials are omitted from adapter metadata and redacted from its output. Session state is removed when the adapter exits normally.

This command uses host mode with unattended tool permissions. It has the filesystem access described under Isolation and services below. For isolated comparisons, put the adapter and its npm dependencies in your candidate image and pass the credential through `pass_env`; the host `.env` is not mounted into containers. The adapter does not install AspenAI dependencies or provision SQL/Azurite services.

To use Claude as the evaluator, add `--evaluator` to the adapter command and supply it through `--evaluator-command` or `--evaluator-config`. For example, after a candidate run:

```sh
python3 orchestrator.py evaluate --run runs/RUN_ID --tasks 1 2 3 --jobs 3 \
  --evaluator-timeout 7200 \
  --evaluator-command "node '$PWD/adapters/claude.mjs' --evaluator --model claude-opus-5-5 --prompt '{prompt}' --workspace '{workspace}' --output '{output}'"
```

Evaluator mode preserves the model's judgment JSON for the runner to validate and writes SDK metadata beside it as `judgment.json.sdk.json`. Choose evaluator models and budgets consistently across comparisons.

## Run the evaluator

```sh
python3 orchestrator.py evaluate \
  --run runs/RUN_ID --tasks 1 2 3 --jobs 3 \
  --evaluator-command 'python3 /absolute/path/to/judge.py --prompt {prompt} --workspace {workspace} --output {output}'
```

Alternatively pass `--evaluator-command` or `--evaluator-config` to `run` to evaluate automatically once all candidates finish. Evaluation starts only after every candidate process has stopped. The evaluator needs file-reading and command-running capabilities, and must write the JSON format in [EVALUATOR.md](EVALUATOR.md) to `{output}`. Each evaluation receives disposable baseline, candidate, and reference copies. Repeating evaluation makes a new numbered packet and preserves earlier judgments.

Each task has twelve criteria totaling 100 points. The evaluator assigns levels 0-4 with evidence; the runner validates the response and computes the weighted score. It rejects missing/duplicate criteria, invalid levels, missing evidence, and full credit on blocked checks. An invalid or missing judgment remains an evaluation failure, not a score of zero. The scoreboard gives an overall mean only when every selected task has a valid judgment. It is written to `runs/RUN_ID/scoreboard.json` and reflects the latest selected evaluation batch; older individual judgments remain in their packets.

Timeouts and nonzero candidate exits preserve partial source for review. Launch failures and interrupted attempts are not scored. An interrupted attempt retains its workspace and logs but is not automatically resumed. A fresh run starts every task from the frozen baseline.

## Isolation and services

Local mode launches ordinary host processes. Separate directories and clean Git history prevent accidental reference exposure, but they are **not a filesystem security boundary**: a host agent with unrestricted file access can read sibling tasks or private references. Use the Docker option for serious comparisons:

```sh
python3 orchestrator.py run --tasks 1 2 3 --jobs 3 \
  --candidate-image your-agent-image:fixed-version \
  --candidate-config path/to/container-candidate.json
```

The image must contain your agent adapter and the desired toolchains. The runner mounts only that attempt's repository at `/workspace`, its prompt read-only at `/input/prompt.md`, and its report directory at `/output`. It does not mount the benchmark root, reference solutions, source checkout, host home, or Docker socket. Placeholders use container paths automatically. Each candidate gets its own container and process namespace. The container is removed after completion or timeout, and subprocess groups are terminated when a run is interrupted. Evaluators run on the host with access to their private packets.

Container configuration may list `pass_env` names for required model credentials; explicit `env` values are passed too. Host mode inherits the caller's environment. Keep reference-repository credentials and Linear/GitHub integrations unavailable to candidates so they cannot retrieve the finished implementation externally. Docker networking is available for model APIs and package restore; this runner does not provide a network allowlist. A fixed image digest and fixed model settings improve repeatability.

Existing application configuration points at conventional local SQL, Azurite, and application ports. **Do not let parallel attempts share a mutable seeded database or storage account.** For integration tests, provision separate disposable services per candidate inside its sandbox or through your adapter, and supply that historical checkout's connection settings. The runner does not rewrite historical application configuration or silently start production-connected applications. Unit tests and compilation can run without those services. Use a dedicated database/storage namespace for each evaluator packet as well. Never run the paid Bot.Prompts suite or real telephony/CRM/AI integration tests.

The starting SDK pins are .NET 10 for tasks 1 and 3 and .NET 8 with roll-forward for task 2. Task 3's frontend pins Node 22.22.3 and npm 10.9.8. Honor each snapshot's own `global.json`, package files, and lockfiles; the copied current instructions can mention newer tooling than an older baseline. Baseline build observations, including inherited/environment failures, are saved under `private/validation/`.

## Dataset layout and historical boundaries

| Task | Starting main commit | Reference main commit | Starting files |
| --- | --- | --- | ---: |
| 01 Prompt management | `b0b2ad333a1a5422377a534afe7055bf278e0a50` | `7bbbd53f3aae622a03c39537c4193873303e754d` | 3,736 |
| 02 Blind transfer | `d9ce1d18585bad56fe7e797678a261527635ccdc` | `2ee1e253e700cab276787ea1ce6dadaf4142378b` | 3,580 |
| 03 Outbound calling | `2dbc29827b91df67b912442e545f032ad16e7cad` | `44bd24123c48ee94f8ebaed85691d88ab35daf30` | 4,579 |

- `orchestrator.py`: root CLI and evaluator orchestration entry point.
- `catalog.json`: stable registry for all ten ideas, with availability states.
- `tasks/TASK/prompt.md`: the human-style request; no evaluation framing or answer links.
- `tasks/TASK/rubric.json`, `source.json`, `ledger.json`: private-to-the-evaluator task specification and provenance. Do not mount these task folders into candidate sandboxes.
- `tasks/TASK/baseline.bundle`: self-contained Git bundle containing only the starting commit's ancestors and the instruction-overlay commit. There are no remotes, shared object alternates, or future solution commits in candidate clones.
- `tasks/TASK/snapshot.json`: frozen tree IDs, checksums, instruction hashes, and file manifests.
- `workspaces/TASK/`: complete initial repositories for your inspection. Runs always clone their own fresh copies from the bundle.
- `bootstrap.py`: reconstruct and verify the heavy local artifacts from an AspenAI checkout.
- `dataset/instructions/`, `dataset/manifest.json`: shareable frozen instruction inputs and expected source tree IDs from the original benchmark.
- `private/instructions/`: local copy of the packaged AGENTS.md and CLAUDE.md files, including `.claude/CLAUDE.md`. No other uncommitted source changes are copied.
- `private/sources/`: frozen completed Linear issue details and PR links.
- `private/history.git`: private merged main history used to reconstruct snapshots.
- `private/references/TASK/`: full real reference code, individual merged PR patches, and scope ledger.
- `runs/RUN_ID/TASK/`: candidate workspace, prompt, logs, frozen submission, patch, and evaluation packets.

The baseline is immediately before the first linked project implementation merge, not a stripped-down exercise repository. Existing prototypes and prerequisite systems remain. References for tasks 1 and 2 are frozen at project completion; task 3 includes the completed slices of its source projects through the final selected merged follow-up. Its unfinished neighboring features are excluded explicitly.

The real projects were interleaved with other work. Reference code is therefore a real merged application, **not a clean answer patch that can be applied wholesale to the baseline**. The ledger contains 99, 49, and 65 project/supporting PRs respectively, with unrelated linked changes marked out of scope. The evaluator must use the human request and rubric to select relevant behavior and accept implementations adapted to the earlier architecture. This is a semantic implementation benchmark, not a source-text matching exercise.

Submission capture uses the filesystem, not the candidate's commit history or Git configuration. It includes new ignored source files as well as tracked modifications and deletions. Common generated directories such as `node_modules`, `bin`, `obj`, test reports, and `.git` are excluded unless the directory contains baseline-tracked source; the exclusion list is recorded. Symlinks are preserved without reading their targets. Treat evaluator packet code as untrusted and inspect it before executing tests.

## Verify and maintain

```sh
python3 -m unittest discover -s tests -v
python3 orchestrator.py verify --tasks 1 2 3
```

Verification checks every starting file, bundle checksums, instruction copies, reference manifests, Git integrity, and the absence of reference commits from candidate history. Use `bootstrap.py --source /path/to/AspenAI` to reconstruct snapshots after cloning the lightweight benchmark repository. `prepare` remains a low-level dataset-authoring command requiring prepopulated `private/instructions`; use bootstrap for distribution because it validates the packaged pins, stages output, and supports repeat invocations.

No frontier-model results or difficulty calibration are claimed yet. Pilot runs should test prompt clarity, evaluator agreement, and whether high-performing solutions separate meaningfully across the twelve criteria.
