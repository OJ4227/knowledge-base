#!/usr/bin/env python3
"""Inject shared project state when Claude Code starts or compacts a session."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


MAX_DOCUMENT_CHARS = 4_000
CONTEXT_DOCUMENTS = (
    "HANDOVER.md",
    "meta/ongoing-discussions.md",
)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    sections = [git_context(repo_root)]
    sections.extend(document_context(repo_root, path) for path in CONTEXT_DOCUMENTS)

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": "\n\n".join(sections),
                }
            }
        )
    )


def git_context(repo_root: Path) -> str:
    branch = run_git(repo_root, "branch", "--show-current") or "(detached HEAD)"
    status = run_git(repo_root, "status", "--short") or "(clean)"
    recent = run_git(repo_root, "log", "-3", "--oneline") or "(no commits)"
    return (
        "Shared repository context loaded at session start.\n"
        f"Branch: {branch}\n"
        f"Working tree:\n{status}\n"
        f"Recent commits:\n{recent}"
    )


def document_context(repo_root: Path, relative_path: str) -> str:
    path = repo_root / relative_path
    if not path.exists():
        return f"{relative_path}: missing"

    content = path.read_text(encoding="utf-8")
    if len(content) > MAX_DOCUMENT_CHARS:
        content = (
            content[:MAX_DOCUMENT_CHARS]
            + f"\n\n[Truncated; read the complete {relative_path} before relying on it.]"
        )
    return f"--- {relative_path} ---\n{content}"


def run_git(repo_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        capture_output=True,
        check=False,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


if __name__ == "__main__":
    main()
