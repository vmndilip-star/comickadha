#!/usr/bin/env python3
"""Fails if a secret is about to be committed. Standard library only.

    python scripts/check_secrets.py            scan every tracked file
    python scripts/check_secrets.py --staged   scan what is staged (the pre-commit hook runs this)

It blocks .env files (except .env.example) and anything that looks like an API key or private key.
Put real keys in .env (gitignored); .env.example keeps placeholders such as `your-key-here`.
A line containing `secrets-ok` is skipped, for the rare false positive.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import PurePosixPath

# Vendor key shapes: checked in every file.
KEY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Anthropic key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}|\bgithub_pat_[A-Za-z0-9_]{40,}")),
    ("Meta LLM key", re.compile(r"\bLLM_\d{8,}_[A-Za-z0-9_\-]{12,}")),
    ("Private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]

# NAME_API_KEY=value style assignments: only in env and config files, so code is not flagged.
ASSIGNMENT = re.compile(
    r"\b[A-Z][A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD)\b\s*[:=]\s*[\"']?"
    r"(?!your-|<|\$\{|example|changeme|placeholder)([A-Za-z0-9_\-./+=]{16,})"
)
CONFIG_SUFFIXES = {".env", ".ini", ".cfg", ".toml", ".yml", ".yaml", ".json", ".conf"}
CONFIG_NAMES = {"Dockerfile", "docker-compose.yml", ".env.example"}

SKIP_NAMES = {"package-lock.json", "uv.lock", "check_secrets.py", "test_check_secrets.py"}
MAX_BYTES = 2_000_000


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], check=True, capture_output=True).stdout


def is_env_file(path: str) -> bool:
    name = PurePosixPath(path).name
    return (name == ".env" or name.startswith(".env.")) and name != ".env.example"


def is_config(path: str) -> bool:
    p = PurePosixPath(path)
    return p.name in CONFIG_NAMES or p.suffix in CONFIG_SUFFIXES or p.name.startswith(".env")


def mask(value: str) -> str:
    """Never print a whole secret: show just enough to find it."""
    return value[:4] + "..."


def scan(path: str, data: bytes) -> list[str]:
    if PurePosixPath(path).name in SKIP_NAMES or len(data) > MAX_BYTES or b"\x00" in data[:8192]:
        return []
    text = data.decode("utf-8", errors="replace")
    problems = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if "secrets-ok" in line:
            continue
        found = next(((kind, m) for kind, p in KEY_PATTERNS if (m := p.search(line))), None)
        if found:
            kind, m = found
            problems.append(f"{path}:{lineno}: looks like a secret: {kind} ({mask(m.group(0))})")
        elif is_config(path) and (m := ASSIGNMENT.search(line)):
            problems.append(f"{path}:{lineno}: a secret value is assigned here ({mask(m.group(1))})")
    return problems


def main(argv: list[str]) -> int:
    staged = "--staged" in argv
    if staged:
        names = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").decode().split("\0")
    else:
        names = git("ls-files", "-z").decode().split("\0")
    names = [n for n in names if n]

    problems = [f"{n}: .env files must never be committed (keep secrets in the gitignored .env)" for n in names if is_env_file(n)]
    for name in names:
        if is_env_file(name):
            continue
        try:
            data = git("show", f":{name}") if staged else open(name, "rb").read()
        except (OSError, subprocess.CalledProcessError):
            continue
        problems += scan(name, data)

    if problems:
        print("Secret check failed:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        print("Move real keys to .env (gitignored) and use placeholders like your-key-here.", file=sys.stderr)
        return 1
    print(f"Secret check passed ({len(names)} {'staged' if staged else 'tracked'} files).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
