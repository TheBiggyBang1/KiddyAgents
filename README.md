# KiddyAgent

A small team of AI agents that writes, illustrates, voices, edits and publishes kids' videos,
built on LangGraph. The full spec is in [BUILD_PROMPT.md](BUILD_PROMPT.md); channel settings and
characters are in [config/channel.yaml](config/channel.yaml).

## Quick start (PowerShell)

```powershell
uv sync
uv run kiddy run --fake          # offline and free: placeholder pictures, silent voices
copy .env.example .env           # then paste your free Groq key into .env
uv run kiddy run --topic "why do leaves change color?"
uv run kiddy list
uv run pytest
```

Each episode lands in `output/episodes/<episode_id>/`. If a run stops, `uv run kiddy resume <episode_id>`
continues from the last finished step.
