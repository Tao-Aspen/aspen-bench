import asyncio
import contextlib
import json
import math
import os
import re
import signal
import time
import uuid
from pathlib import Path

from .common import read_json, write_json


PLACEHOLDERS = {"prompt", "prompt_text", "workspace", "output", "task", "run_id"}


def load_command(path):
    config = read_json(path)
    argv = config.get("argv")
    if not isinstance(argv, list) or not argv or any(not isinstance(item, str) for item in argv):
        raise ValueError("Command config needs a nonempty argv array of strings")
    environment = config.get("env", {})
    if not isinstance(environment, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in environment.items()):
        raise ValueError("Command env must map strings to strings")
    timeout = config.get("timeout_seconds", 7200)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout_seconds must be positive")
    pass_env = config.get("pass_env", [])
    if not isinstance(pass_env, list):
        raise ValueError("pass_env must be an array")
    for key in pass_env:
        if not isinstance(key, str):
            raise ValueError("pass_env must list environment variable names")
    return config


def expand(value, replacements):
    pattern = r"\{(" + "|".join(sorted(PLACEHOLDERS)) + r")\}"
    return re.sub(pattern, lambda match: str(replacements[match[1]]), value)


async def stop_group(process):
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    await asyncio.sleep(0.2)
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    await process.wait()


async def execute(config, replacements, cwd, artifacts, image=None):
    artifacts.mkdir(parents=True, exist_ok=True)
    environment = {key: value for key, value in os.environ.items() if not key.startswith("ASPEN_BENCH_")}
    expanded = dict(replacements)
    container = None
    if image:
        expanded.update(prompt="/input/prompt.md", workspace="/workspace", output="/output/result.json")
    argv = [expand(item, expanded) for item in config["argv"]]
    additions = {key: expand(value, expanded) for key, value in config.get("env", {}).items()}
    additions.update(
        ASPEN_TASK_ID=expanded["task"], ASPEN_PROMPT_FILE=expanded["prompt"],
        ASPEN_WORKSPACE=expanded["workspace"], ASPEN_RESULT_FILE=expanded["output"],
    )
    if image:
        additions.setdefault("GIT_CONFIG_COUNT", "1")
        additions.setdefault("GIT_CONFIG_KEY_0", "safe.directory")
        additions.setdefault("GIT_CONFIG_VALUE_0", "/workspace")
        container = "aspen-candidate-" + uuid.uuid4().hex
        docker = ["docker", "run", "--rm", "--init", "--name", container,
                  "--mount", f"type=bind,src={Path(replacements['workspace']).resolve()},dst=/workspace",
                  "--mount", f"type=bind,src={Path(replacements['prompt']).resolve()},dst=/input/prompt.md,readonly",
                  "--mount", f"type=bind,src={Path(replacements['output']).parent.resolve()},dst=/output",
                  "--workdir", "/workspace"]
        for key in config.get("pass_env", []):
            if key in environment:
                docker.extend(["--env", key])
        for key, value in additions.items():
            docker.extend(["--env", f"{key}={value}"])
        argv = docker + [image] + argv
    else:
        environment.update(additions)
    started = time.monotonic()
    status = "launch_failed"
    returncode = None
    error = None
    process = None
    try:
        with (artifacts / "stdout.log").open("wb") as stdout, (artifacts / "stderr.log").open("wb") as stderr:
            process = await asyncio.create_subprocess_exec(*argv, cwd=cwd, env=environment, stdout=stdout, stderr=stderr, start_new_session=True)
            try:
                await asyncio.wait_for(process.wait(), timeout=config.get("timeout_seconds", 7200))
                returncode = process.returncode
                status = "completed" if returncode == 0 else "failed"
            except TimeoutError:
                status = "timeout"
            finally:
                await stop_group(process)
    except asyncio.CancelledError:
        status = "cancelled"
        raise
    except OSError as exception:
        error = str(exception)
    finally:
        if container and process is not None:
            cleanup = await asyncio.create_subprocess_exec("docker", "rm", "-f", container, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            await cleanup.wait()
        outcome = {"status": status, "returncode": returncode, "duration_seconds": round(time.monotonic() - started, 3), "error": error, "isolation": "docker" if image else "local-process", "image": image}
        write_json(artifacts / "process.json", outcome)
    return outcome
