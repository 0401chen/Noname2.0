from __future__ import annotations

import os
from pathlib import Path


def resolve_project_root() -> Path:
    """Locate the repository asset root without relying on editable installs.

    Local development usually imports modules from ``backend/src`` while a Docker
    image imports them from site-packages. Searching the current working directory
    and its parents keeps knowledge and evaluation assets available in both cases.
    ``REPLAY_PROJECT_ROOT`` remains an explicit deployment override.
    """

    configured = os.getenv("REPLAY_PROJECT_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()

    module_path = Path(__file__).resolve()
    candidates = [Path.cwd(), *Path.cwd().parents, module_path.parent, *module_path.parents]
    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        has_knowledge = (candidate / "knowledge" / "reviewed" / "core.json").exists()
        has_evaluation = (candidate / "evaluation" / "scenarios").exists()
        if has_knowledge or has_evaluation:
            return candidate

    return Path.cwd().resolve()


def knowledge_file() -> Path:
    return resolve_project_root() / "knowledge" / "reviewed" / "core.json"


def evaluation_results_dir() -> Path:
    return resolve_project_root() / "evaluation" / "results"
