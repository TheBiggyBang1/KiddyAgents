# KiddyAgent

A small team of AI agents that writes, illustrates, voices, edits and publishes kids' videos,
built on LangGraph. The full spec is in [BUILD_PROMPT.md](BUILD_PROMPT.md); channel settings and
characters are in [config/channel.yaml](config/channel.yaml).

## Quick start (PowerShell)

```powershell
uv sync
cd video; npm install; cd ..     # the Remotion project that renders the videos
uv run kiddy trace B --fake      # offline and free: placeholder pictures, silent voices
copy .env.example .env           # then add your keys (Anthropic, Groq, Cloudflare)
uv run kiddy trace A             # an alphabet tracing video for the letter A
uv run kiddy trace               # the next letter that hasn't been made yet
uv run kiddy list
uv run pytest
```

Alphabet tracing: Claude Haiku picks three words, Cloudflare paints them, Microsoft Edge voices
the lines, and Remotion (`video/`) draws the letters stroke by stroke and renders the video.
The stroke library is [src/kiddy/tracing/letters.json](src/kiddy/tracing/letters.json); preview
every letter with `cd video; npx remotion still src/index.ts LetterSheet sheet.png`.

Each episode lands in `output/episodes/<episode_id>/`. If a run stops, `uv run kiddy resume <episode_id>`
continues from the last finished step. `uv run kiddy run` still makes the older story videos.
