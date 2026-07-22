"""Prompt registry — load, version, and store prompt templates.

All LLM prompt strings live in prompts/templates/ as YAML files.
This registry provides a single point of access so prompts are
never hardcoded in agent code.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"

_cache: dict[str, dict[str, Any]] = {}


def _load_template(name: str) -> dict[str, Any]:
    """Load a single template YAML file (with caching)."""
    if name in _cache:
        return _cache[name]

    path = TEMPLATES_DIR / f"{name}.yml"
    if not path.exists():
        path = TEMPLATES_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template '{name}' not found in {TEMPLATES_DIR}")

    with open(path) as f:
        template = yaml.safe_load(f)
    _cache[name] = template
    logger.debug(f"Loaded prompt template: {name}")
    return template


def get_prompt(name: str, **kwargs: Any) -> str:
    """Load a prompt template by name and format it with keyword args.

    Args:
        name: Template name (without .yml extension).
        **kwargs: Variables to substitute into the template.

    Returns:
        Formatted prompt string.

    Raises:
        FileNotFoundError: If the template doesn't exist.
        KeyError: If a required template variable is missing.
    """
    template = _load_template(name)
    system = template.get("system", "")
    user = template.get("user", "")
    full = f"{system}\n\n{user}" if system else user
    return full.format(**kwargs) if kwargs else full


def get_system_prompt(name: str, **kwargs: Any) -> str:
    """Get only the system prompt portion of a template."""
    template = _load_template(name)
    return template.get("system", "").format(**kwargs) if kwargs else template.get("system", "")


def get_user_prompt(name: str, **kwargs: Any) -> str:
    """Get only the user prompt portion of a template."""
    template = _load_template(name)
    return template.get("user", "").format(**kwargs) if kwargs else template.get("user", "")


def list_templates() -> list[str]:
    """List all available prompt templates."""
    return sorted(p.stem for p in TEMPLATES_DIR.glob("*.yml") if not p.name.startswith("_"))


def reload_all() -> None:
    """Clear cache and reload all templates (for hot-swapping)."""
    _cache.clear()
    logger.info("Prompt registry cache cleared — templates will reload on next access")
