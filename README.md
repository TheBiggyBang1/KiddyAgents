# KiddyAgent

A small team of AI agents that writes, illustrates, voices, edits and publishes kids' videos,
built on LangGraph. The full spec is in [BUILD_PROMPT.md](BUILD_PROMPT.md); channel settings and
characters are in [config/channel.yaml](config/channel.yaml).

## Day to day: autopilot

You never write a topic. The showrunner invents each episode from the stem idea in
[config/channel.yaml](config/channel.yaml) (`concept`), rotating subjects and formats, and every
finished video waits for you:

```powershell
uv run kiddy autopilot --count 3   # invent and make 3 episodes, one after another
uv run kiddy review --open         # list what's waiting, and play the oldest
uv run kiddy approve <episode>     # uploads to YouTube, goes public at the next free time
uv run kiddy reject <episode> --notes "too much talking"   # the next episodes learn from it
uv run kiddy schedule              # what's on YouTube and when it goes public
```

YouTube setup (once): see [HOW_IT_WORKS.md](HOW_IT_WORKS.md), part 2. Save the OAuth client as
`secrets/client_secret.json`, then `uv run kiddy auth youtube` and sign in as the channel's account.

Formats: **puppet shows** (Fennel, Olo and Glim as React puppets with lip sync, in
`video/src/puppet/`) and **alphabet tracing** (about one in four episodes, until A-Z is done).

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
