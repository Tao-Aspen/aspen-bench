import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { credentials, positiveNumber, sdkEnvironment, successful } from '../adapters/claude.mjs';

test('dotenv OAuth wins over inherited credentials and is never shell evaluated', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'aspen-credentials-'));
  try {
    const file = join(directory, '.env');
    await writeFile(file, 'export CLAUDE_CODE_OAUTH_TOKEN="literal-$(example)"\n');
    assert.deepEqual(await credentials(file, { CLAUDE_CODE_OAUTH_TOKEN: 'old', ANTHROPIC_API_KEY: 'other' }), { name: 'CLAUDE_CODE_OAUTH_TOKEN', value: 'literal-$(example)' });
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test('missing credentials fail and environment API key works without dotenv', async () => {
  const missing = join(tmpdir(), 'aspen-nonexistent-file', '.env');
  await assert.rejects(credentials(missing, {}), /Set CLAUDE_CODE_OAUTH_TOKEN/);
  assert.deepEqual(await credentials(missing, { ANTHROPIC_API_KEY: 'example' }), { name: 'ANTHROPIC_API_KEY', value: 'example' });
});

test('SDK environment excludes other providers, auth sources, and user configuration', () => {
  const env = sdkEnvironment({ name: 'CLAUDE_CODE_OAUTH_TOKEN', value: 'example' }, '/isolated', {
    PATH: '/bin', HOME: '/real-home', ANTHROPIC_API_KEY: 'unwanted', ANTHROPIC_BASE_URL: 'https://unwanted',
    CLAUDE_CODE_USE_BEDROCK: '1', CLAUDE_CONFIG_DIR: '/real-config', GITHUB_TOKEN: 'unwanted',
  });
  assert.equal(env.CLAUDE_CODE_OAUTH_TOKEN, 'example');
  assert.equal(env.HOME, '/isolated');
  assert.equal(env.CLAUDE_CONFIG_DIR, '/isolated/.claude');
  for (const name of ['ANTHROPIC_API_KEY', 'ANTHROPIC_BASE_URL', 'CLAUDE_CODE_USE_BEDROCK', 'GITHUB_TOKEN']) assert.equal(env[name], undefined);
});

test('budget limits and SDK result errors cannot become successful attempts', () => {
  for (const value of ['0', '-1', 'NaN', 'Infinity']) assert.throws(() => positiveNumber(value, 'budget'));
  assert.throws(() => positiveNumber('1.5', 'turns', true));
  assert.equal(positiveNumber('0.5', 'budget'), 0.5);
  assert.equal(successful({ subtype: 'success', is_error: false }), true);
  for (const result of [undefined, { subtype: 'success', is_error: true }, { subtype: 'error_max_turns', is_error: false }]) assert.equal(successful(result), false);
});
