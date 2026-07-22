#!/usr/bin/env python3
"""Reference implementation of the loader rules documented in
skills/config/SKILL.md (and README.md's "Configuration" section) against
the shapes in schemas/config.schema.json.

Usage: python3 scripts/check_config.py <path-to-config.json>

Exit codes:
  0 - file missing, or file is valid (unknown keys only warn)
  1 - malformed JSON, invalid model value, invalid worker name,
      out-of-range limits, or a malformed externalExecutors entry

Stdlib json only - no jsonschema dependency, so CI and contributors
never need a pip install to run this check.
"""
import json
import os
import sys

MODELS = {"haiku", "sonnet", "opus"}
WORKERS = {
    "sf-apex-worker", "sf-lwc-worker", "sf-test-worker", "sf-data-worker",
    "sf-debug-worker", "sf-metadata-worker", "sf-deploy-worker",
    "sf-mapper", "sf-reviewer",
}
TOP_KEYS = {"models", "limits", "deployWorker", "effort", "externalExecutors"}
MODELS_KEYS = {"default", "escalation", "workers"}
LIMITS_KEYS = {"maxConcurrent", "maxAttempts"}
DEPLOY_WORKER_KEYS = {"enabled"}
EXECUTOR_KEYS = {"enabled", "executable", "args", "timeoutSeconds"}


def fail(msg):
    print(f"config error: {msg}", file=sys.stderr)
    sys.exit(1)


def warn(msg):
    print(f"config warning: {msg}")


def check_models(models):
    if not isinstance(models, dict):
        return
    for key in models.keys() - MODELS_KEYS:
        warn(f"unknown key models.{key}")
    for key in ("default", "escalation"):
        if key in models and models[key] not in MODELS:
            fail(f"invalid model value at models.{key}")
    workers = models.get("workers")
    if isinstance(workers, dict):
        for name, value in workers.items():
            if name not in WORKERS:
                fail(f"invalid worker name at models.workers.{name}")
            if value not in MODELS:
                fail(f"invalid model value at models.workers.{name}")


def check_limits(limits):
    if not isinstance(limits, dict):
        return
    for key in limits.keys() - LIMITS_KEYS:
        warn(f"unknown key limits.{key}")
    mc = limits.get("maxConcurrent")
    if mc is not None and (not isinstance(mc, int) or isinstance(mc, bool) or not (1 <= mc <= 10)):
        fail("limits.maxConcurrent out of range (must be integer 1-10)")
    ma = limits.get("maxAttempts")
    if ma is not None and (not isinstance(ma, int) or isinstance(ma, bool) or not (1 <= ma <= 3)):
        fail("limits.maxAttempts out of range (must be integer 1-3)")


def check_executors(executors):
    if not isinstance(executors, dict):
        return
    for name, entry in executors.items():
        if not isinstance(entry, dict):
            fail(f"externalExecutors.{name} must be an object")
        for key in entry.keys() - EXECUTOR_KEYS:
            warn(f"unknown key externalExecutors.{name}.{key}")
        for required in ("enabled", "executable", "args"):
            if required not in entry:
                fail(f"externalExecutors.{name} missing required key '{required}'")
        if "args" in entry and not isinstance(entry["args"], list):
            fail(f"externalExecutors.{name}.args must be an array")


def main():
    if len(sys.argv) != 2:
        fail("usage: check_config.py <path-to-config.json>")
    path = sys.argv[1]
    if not os.path.exists(path):
        sys.exit(0)
    with open(path) as f:
        text = f.read()
    try:
        config = json.loads(text)
    except json.JSONDecodeError as e:
        fail(f"malformed JSON - {e}")
        return
    if not isinstance(config, dict):
        fail("top-level config must be a JSON object")
    for key in config.keys() - TOP_KEYS:
        warn(f"unknown top-level key '{key}'")
    check_models(config.get("models"))
    check_limits(config.get("limits"))
    if "deployWorker" in config and isinstance(config["deployWorker"], dict):
        for key in config["deployWorker"].keys() - DEPLOY_WORKER_KEYS:
            warn(f"unknown key deployWorker.{key}")
    check_executors(config.get("externalExecutors"))
    sys.exit(0)


if __name__ == "__main__":
    main()
