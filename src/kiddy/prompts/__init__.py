"""System prompts (one Markdown file per agent) and a helper to show data to the models."""

from functools import cache
from pathlib import Path

import yaml


@cache
def system_prompt(agent: str) -> str:
    return (Path(__file__).parent / f"{agent}.md").read_text(encoding="utf-8")


def as_yaml(data: dict) -> str:
    """YAML reads more naturally than JSON for the models, and costs fewer tokens."""
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)
