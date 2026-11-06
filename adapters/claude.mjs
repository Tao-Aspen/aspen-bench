import { query } from '@anthropic-ai/claude-agent-sdk';
import { readFile, writeFile, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseArgs, parseEnv } from 'node:util';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');

export function positiveNumber(value, name, integer = false) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0 || (integer && !Number.isInteger(number))) {
    throw new Error(`${name} must be a positive ${integer ? 'integer' : 'number'}`);
  }
  return number;
}

export async function credentials(envFile, inherited = process.env) {
  let fromFile = {};
  try {
    fromFile = parseEnv(await readFile(envFile, 'utf8'));
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  const available = { ...inherited, ...fromFile };
  const name = available.CLAUDE_CODE_OAUTH_TOKEN?.trim()
    ? 'CLAUDE_CODE_OAUTH_TOKEN' : 'ANTHROPIC_API_KEY';
  const value = available[name]?.trim();
  if (!value) throw new Error('Set CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY in the benchmark .env or environment');
  return { name, value };
}

export function sdkEnvironment(authentication, home, inherited = process.env) {
  const names = ['PATH', 'TMPDIR', 'LANG', 'LC_ALL', 'SYSTEMROOT', 'DOTNET_ROOT', 'DOTNET_ROOT_ARM64', 'NUGET_PACKAGES'];
  const environment = Object.fromEntries(names.filter(name => inherited[name]).map(name => [name, inherited[name]]));
  return {
    ...environment,
    HOME: home,
    CLAUDE_CONFIG_DIR: join(home, '.claude'),
    CLAUDE_AGENT_SDK_CLIENT_APP: 'aspen-bench/1.0.0',
    [authentication.name]: authentication.value,
    GIT_CONFIG_COUNT: '1',
    GIT_CONFIG_KEY_0: 'safe.directory',
    GIT_CONFIG_VALUE_0: process.env.ASPEN_WORKSPACE || process.cwd(),
  };
}

export function successful(result) {
  return result?.subtype === 'success' && result.is_error === false;
}

export async function main(args = process.argv.slice(2)) {
  const { values } = parseArgs({ args, options: {
    prompt: { type: 'string', default: process.env.ASPEN_PROMPT_FILE },
    workspace: { type: 'string', default: process.env.ASPEN_WORKSPACE },
    output: { type: 'string', default: process.env.ASPEN_RESULT_FILE },
    model: { type: 'string', default: 'sonnet' },
    'env-file': { type: 'string', default: join(root, '.env') },
    'max-turns': { type: 'string', default: '200' },
    'max-budget-usd': { type: 'string' },
    'timeout-seconds': { type: 'string', default: '7100' },
    tools: { type: 'string' },
    evaluator: { type: 'boolean', default: false },
  } });
  if (!values.prompt || !values.workspace) throw new Error('--prompt and --workspace are required');
  if (values.evaluator && !values.output) throw new Error('--output is required for evaluators');
  const maxTurns = positiveNumber(values['max-turns'], '--max-turns', true);
  const timeout = positiveNumber(values['timeout-seconds'], '--timeout-seconds');
  const maxBudgetUsd = values['max-budget-usd'] === undefined ? undefined : positiveNumber(values['max-budget-usd'], '--max-budget-usd');
  const authentication = await credentials(values['env-file']);
  const redact = value => String(value).replaceAll(authentication.value, '[REDACTED]');
  const prompt = await readFile(resolve(values.prompt), 'utf8');
  const home = await mkdtemp(join(tmpdir(), 'aspen-claude-'));
  const abortController = new AbortController();
  const timer = setTimeout(() => abortController.abort(), timeout * 1000);
  const interrupt = () => abortController.abort();
  process.once('SIGTERM', interrupt);
  process.once('SIGINT', interrupt);
  const sdkPackage = JSON.parse(await readFile(join(root, 'node_modules/@anthropic-ai/claude-agent-sdk/package.json'), 'utf8'));
  const metadata = { sdk_version: sdkPackage.version, requested_model: values.model, authentication: authentication.name, max_turns: maxTurns, max_budget_usd: maxBudgetUsd ?? null, timeout_seconds: timeout, setting_sources: ['project'] };
  let result;
  let stderr = '';
  try {
    console.log(JSON.stringify({ type: 'adapter', ...metadata }));
    for await (const message of query({ prompt, options: {
      cwd: resolve(values.workspace),
      env: sdkEnvironment(authentication, home),
      model: values.model,
      systemPrompt: { type: 'preset', preset: 'claude_code', append: 'Follow the repository AGENTS.md instructions, including nested AGENTS.md files for the areas you change.' },
      settingSources: ['project'],
      strictMcpConfig: true,
      mcpServers: {},
      persistSession: false,
      permissionMode: 'bypassPermissions',
      allowDangerouslySkipPermissions: true,
      tools: values.tools === undefined ? { type: 'preset', preset: 'claude_code' } : values.tools.split(',').filter(Boolean),
      maxTurns,
      maxBudgetUsd,
      abortController,
      stderr: text => { stderr = (stderr + text).slice(-65536); },
    } })) {
      console.log(redact(JSON.stringify(message)));
      if (message.type === 'system' && message.subtype === 'init') metadata.resolved_model = message.model;
      if (message.type === 'result') result = message;
    }
    if (!result) throw new Error('Claude SDK exited without a result');
    if (values.output) {
      const reportPath = values.evaluator ? `${resolve(values.output)}.sdk.json` : resolve(values.output);
      await writeFile(reportPath, redact(JSON.stringify({ ...metadata, ...result }, null, 2)) + '\n');
    }
    if (!successful(result)) return 1;
    if (values.evaluator) JSON.parse(await readFile(resolve(values.output), 'utf8'));
    return 0;
  } catch (error) {
    console.error(redact(error instanceof Error ? error.message : error));
    return 1;
  } finally {
    if (stderr) console.error(redact(stderr));
    clearTimeout(timer);
    process.removeListener('SIGTERM', interrupt);
    process.removeListener('SIGINT', interrupt);
    await rm(home, { recursive: true, force: true });
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try {
    process.exitCode = await main();
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}
