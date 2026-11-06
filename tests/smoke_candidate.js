const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");

const prompt = fs.readFileSync(process.env.ASPEN_PROMPT_FILE, "utf8");
assert(prompt.length > 100);
assert(fs.existsSync("AGENTS.md"));
assert(fs.existsSync(".claude/CLAUDE.md"));
assert(fs.existsSync("AspenAI.sln"));
assert(!fs.existsSync("/private/references"));
assert(!fs.existsSync("/Users/taogroves/tools/aspen-bench/private"));
fs.writeFileSync("runner-smoke.txt", "Harness smoke test only. This is not a model solution.\n");
fs.writeFileSync(process.env.ASPEN_RESULT_FILE, JSON.stringify({ kind: "harness-smoke", task: process.env.ASPEN_TASK_ID }));
