"""Command line. Day to day: `kiddy autopilot`, `kiddy review`, then `kiddy approve` or `reject`."""

import os
import string
import sys
from datetime import datetime
from pathlib import Path

import typer
from dotenv import load_dotenv
from langgraph.types import Command
from rich.console import Console
from rich.table import Table

from kiddy import youtube
from kiddy.approval import publish as publish_episode
from kiddy.checkpoints import sqlite_checkpointer
from kiddy.graph import build_graph
from kiddy.puppet.graph import build_puppet_graph
from kiddy.settings import Settings
from kiddy.showrunner import letters_done, next_idea
from kiddy.state import QAReport
from kiddy.store import UPLOADED, EpisodeStore, new_episode_id
from kiddy.studio import RunContext, studio_for
from kiddy.tracing.graph import build_tracing_graph

load_dotenv()
for stream in (sys.stdout, sys.stderr):
    stream.reconfigure(errors="replace")  # model text may hold characters old consoles can't show

app = typer.Typer(
    help="Kiddy: a small team of AI agents that makes kids' videos.",
    no_args_is_help=True, add_completion=False,
)
console = Console()

FAKE = typer.Option(False, "--fake", help="Fake every model and provider: offline and free.")
CONFIG = typer.Option("config/channel.yaml", "--config", help="Channel settings to use.")
KEYS = {"groq": "GROQ_API_KEY (free: https://console.groq.com/keys)",
        "anthropic": "ANTHROPIC_API_KEY (https://console.anthropic.com/settings/keys)"}
AGENTS = {
    "puppet": ["puppet_writer", "safety_reviewer"],
    "tracing": ["letter_planner"],
    "story": ["default", "scriptwriter", "safety_reviewer"],
}
GRAPHS = {"puppet": build_puppet_graph, "tracing": build_tracing_graph, "story": build_graph}


@app.command()
def autopilot(
    count: int = typer.Option(1, help="How many episodes to make, one after another."),
    fake: bool = FAKE,
    config: str = CONFIG,
) -> None:
    """Invent and make episodes on its own. Each one waits for your approval."""
    ctx = RunContext(fake=fake, config_path=config)
    require_keys(ctx, ["episode_planner", *AGENTS["puppet"], *AGENTS["tracing"]])
    studio = studio_for(ctx)
    made = 0
    for _ in range(count + 3):  # a few spare tries for shows the reviewer discards
        if made == count:
            break
        idea, tokens = next_idea(studio)
        console.print(f"\n[bold magenta]Showrunner:[/] {idea.format}, {idea.subject}: "
                      f"[bold]{idea.topic}[/]. {idea.why}")
        if idea.format == "tracing":
            episode_id = f"{new_episode_id()}-{idea.letter}"
            studio.store.start(episode_id, format="tracing", subject=idea.subject,
                               topic=idea.topic, learning_goal=idea.learning_goal)
            drive(episode_id, {"episode_id": episode_id, "letter": idea.letter,
                               "tokens_used": tokens}, ctx, "tracing")
        else:
            episode_id = f"{new_episode_id()}-show"
            studio.store.start(episode_id, format="puppet", subject=idea.subject,
                               topic=idea.topic, learning_goal=idea.learning_goal)
            drive(episode_id, {"episode_id": episode_id, "idea": idea, "tokens_used": tokens},
                  ctx, "puppet")
        made += studio.store.get(episode_id)["status"] == "awaiting_approval"
    console.print(f"\n[bold]{made} new episode(s) waiting for you.[/] See them with "
                  "[bold]uv run kiddy review[/]")


@app.command()
def review(open_next: bool = typer.Option(False, "--open", help="Play the oldest one.")) -> None:
    """List the videos waiting for your approval."""
    store = EpisodeStore(Path(RunContext().data_dir) / "kiddy.sqlite")
    waiting = [row for row in reversed(store.recent(200)) if row["status"] == "awaiting_approval"]
    if not waiting:
        console.print("Nothing is waiting. Make some with [bold]uv run kiddy autopilot[/]")
        return
    table = Table("episode", "format", "title", "warnings", "video")
    for row in waiting:
        folder = Path(RunContext().output_dir) / "episodes" / row["id"]
        report = folder / "qa_report.json"
        failed = [c.name for c in QAReport.model_validate_json(report.read_text("utf-8")).checks
                  if not c.ok] if report.exists() else []
        table.add_row(row["id"], row["format"], row["title"] or row["topic"],
                      "\n".join(failed) or "none", str(folder / "video.mp4"))
    console.print(table)
    console.print("Approve with [bold]uv run kiddy approve <episode>[/], or "
                  "[bold]uv run kiddy reject <episode> --notes \"what to change\"[/]")
    if open_next:
        os.startfile(Path(RunContext().output_dir) / "episodes" / waiting[0]["id"] / "video.mp4")


@app.command()
def approve(episode_id: str, config: str = CONFIG) -> None:
    """Approve a finished video. With youtube.upload on, it goes to YouTube right away."""
    row = episode_row(episode_id)
    ctx = RunContext(fake=bool(row["fake"]), config_path=config)
    require_youtube(ctx)
    drive(episode_id, Command(resume={"approved": True}), ctx, kind_of(row))


@app.command()
def reject(
    episode_id: str,
    notes: str = typer.Option("", help="What you didn't like. The next episodes learn from it."),
    config: str = CONFIG,
) -> None:
    """Reject a finished video, with notes for the next episodes."""
    row = episode_row(episode_id)
    ctx = RunContext(fake=bool(row["fake"]), config_path=config)
    drive(episode_id, Command(resume={"approved": False, "notes": notes}), ctx, kind_of(row))


@app.command()
def auth(service: str = typer.Argument("youtube", help="What to sign in to: youtube.")) -> None:
    """Sign in to YouTube once. Your browser opens: pick the kids' channel."""
    if service != "youtube":
        console.print(f"[red]Only youtube can be signed in to, not {service!r}.[/]")
        raise typer.Exit(1)
    secrets = Path(RunContext().secrets_dir)
    if not (secrets / youtube.CLIENT_FILE).exists():
        console.print(f"[red]Missing {secrets / youtube.CLIENT_FILE}.[/] Download the Desktop app "
                      "OAuth client from Google Cloud (HOW_IT_WORKS.md, part 2) and save it there.")
        raise typer.Exit(1)
    token = youtube.sign_in(secrets)
    channel = youtube.YouTubeClient(secrets).channel_title()
    console.print(f"Signed in to the channel [bold]{channel}[/]. Saved {token}.\n"
                  "Wrong channel? Run this again and pick the other one.")


@app.command()
def publish(episode_id: str, config: str = CONFIG) -> None:
    """Upload an approved episode now, or finish an upload that stopped."""
    row = episode_row(episode_id)
    if row["status"] not in ("approved", *UPLOADED):
        console.print(f"[red]{episode_id} is {row['status']}.[/] Only approved videos go to "
                      f"YouTube: [bold]uv run kiddy approve {episode_id}[/]")
        raise typer.Exit(1)
    ctx = RunContext(fake=bool(row["fake"]), config_path=config)
    require_youtube(ctx)
    try:
        done = publish_episode(studio_for(ctx), episode_id)
    except (youtube.YouTubeError, RuntimeError) as error:
        console.print(f"[red]Stopped:[/] {error}")
        raise typer.Exit(1) from error
    console.print(describe("publisher", {"youtube": done.model_dump()}))


@app.command()
def schedule() -> None:
    """Show what's on YouTube and when each video goes public."""
    store = EpisodeStore(Path(RunContext().data_dir) / "kiddy.sqlite")
    uploaded = sorted((row for row in store.recent(500) if row["youtube_video_id"]),
                      key=lambda row: row["publish_at"] or "")
    if not uploaded:
        console.print("Nothing is on YouTube yet. Approved videos upload by themselves.")
        return
    table = Table("episode", "title", "goes public", "link")
    now = datetime.now().astimezone()
    for row in uploaded:
        when = datetime.fromisoformat(row["publish_at"]) if row["publish_at"] else None
        shown = ("private" if when is None else "public now" if when <= now
                 else f"{when:%a %d %b %H:%M}")
        table.add_row(row["id"], row["title"] or row["topic"], shown,
                      f"https://youtu.be/{row['youtube_video_id']}")
    console.print(table)


@app.command()
def trace(
    letter: str = typer.Argument("", help="The letter to teach. Empty: the next one not made yet."),
    fake: bool = FAKE,
    config: str = CONFIG,
) -> None:
    """Make an alphabet tracing video for one letter, by hand."""
    ctx = RunContext(fake=fake, config_path=config)
    store = studio_for(ctx).store
    done = letters_done(store.recent(500))
    letter = (letter or next((c for c in string.ascii_uppercase if c not in done), "A")).upper()
    if letter not in string.ascii_uppercase:
        console.print(f"[red]{letter!r} isn't a letter from A to Z.[/]")
        raise typer.Exit(1)
    require_keys(ctx, AGENTS["tracing"])
    episode_id = f"{new_episode_id()}-{letter}"
    store.start(episode_id, format="tracing", topic=f"letter {letter}")
    drive(episode_id, {"episode_id": episode_id, "letter": letter}, ctx, "tracing")


@app.command()
def run(
    topic: str = typer.Option("", help="What the episode is about. Empty: the showrunner picks."),
    fake: bool = FAKE,
    config: str = CONFIG,
) -> None:
    """Make an older-style story episode (painted stills)."""
    ctx = RunContext(fake=fake, config_path=config)
    require_keys(ctx, AGENTS["story"])
    episode_id = new_episode_id()
    studio_for(ctx).store.start(episode_id, format="story")
    drive(episode_id, {"episode_id": episode_id, "topic": topic}, ctx, "story")


@app.command()
def resume(
    episode_id: str,
    fake: bool = typer.Option(False, "--fake", help="Use it if the episode started with --fake."),
    config: str = CONFIG,
) -> None:
    """Continue an episode from its last finished step. Finished pictures and voices are kept."""
    ctx = RunContext(fake=fake, config_path=config)
    kind = kind_of(episode_row(episode_id))
    require_keys(ctx, AGENTS[kind])
    drive(episode_id, None, ctx, kind)


@app.command("list")
def list_episodes(limit: int = typer.Option(20, help="How many recent episodes to show.")) -> None:
    """Show recent episodes and where each one stands."""
    table = Table("episode", "format", "status", "subject", "title")
    for row in EpisodeStore(Path(RunContext().data_dir) / "kiddy.sqlite").recent(limit):
        table.add_row(row["id"], row["format"] or "", row["status"], row["subject"] or "",
                      row["title"] or row["topic"] or "")
    console.print(table)


def episode_row(episode_id: str) -> dict:
    row = EpisodeStore(Path(RunContext().data_dir) / "kiddy.sqlite").get(episode_id)
    if row is None:
        console.print(f"[red]No episode {episode_id}.[/] See them with [bold]uv run kiddy list[/]")
        raise typer.Exit(1)
    return row


def kind_of(row: dict) -> str:
    """Which production line an episode belongs to."""
    return row["format"] if row["format"] in ("puppet", "tracing") else "story"


def require_youtube(ctx: RunContext) -> None:
    """Stop before approving when the upload that follows can't sign in."""
    if ctx.fake or not Settings.load(Path(ctx.config_path)).youtube.upload:
        return
    if not (Path(ctx.secrets_dir) / youtube.TOKEN_FILE).exists():
        console.print("[red]Not signed in to YouTube yet.[/] Run [bold]uv run kiddy auth youtube[/]"
                      " once, then approve again. (Or set youtube.upload: false in the config.)")
        raise typer.Exit(1)


def require_keys(ctx: RunContext, agents: list[str]) -> None:
    """Stop early, and kindly, when a real run is missing a key it will need."""
    if ctx.fake:
        return
    settings = Settings.load(Path(ctx.config_path))
    if settings.vision_check:
        agents = [*agents, "vision_check"]
    providers = {settings.model_for(agent).model.split(":")[0] for agent in agents}
    if settings.providers.tts == "groq":
        providers.add("groq")
    missing = [KEYS[p] for p in sorted(providers)
               if p in KEYS and not os.environ.get(KEYS[p].split()[0])]
    if settings.providers.images == "cloudflare":
        missing += [f"{name} (free: Cloudflare dashboard > Workers AI)"
                    for name in ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN")
                    if not os.environ.get(name)]
    if missing:
        console.print(f"[red]Missing in .env:[/] {', '.join(missing)}. Or try [bold]--fake[/].")
        raise typer.Exit(1)


def drive(episode_id: str, inputs: dict | Command | None, ctx: RunContext, kind: str) -> None:
    checkpointer = sqlite_checkpointer(Path(ctx.data_dir) / "checkpoints.sqlite")
    graph = GRAPHS[kind](checkpointer)
    config = {"configurable": {"thread_id": episode_id}, "max_concurrency": 4}
    resume_hint = f"uv run kiddy resume {episode_id}" + (" --fake" if ctx.fake else "")
    console.print(f"[bold]Episode {episode_id}[/]" + (" [dim](fake)[/]" if ctx.fake else ""))
    if ctx.fake and isinstance(inputs, dict):  # a new fake episode: it must never reach YouTube
        studio_for(ctx).store.update(episode_id, fake="yes")
    try:
        for update in graph.stream(inputs, config, context=ctx, stream_mode="updates"):
            for node, values in update.items():
                if node.startswith("__"):  # LangGraph's own bookkeeping: resumes, interrupts
                    continue
                console.print(f"  [green]done[/]  {node:<17} {describe(node, values or {})}")
    except KeyboardInterrupt:
        console.print(f"\nStopped. Continue later with: [bold]{resume_hint}[/]")
        raise typer.Exit(130) from None
    except Exception as error:
        console.print(
            f"\n[red]Stopped:[/] {error}\nFix it, then continue with: [bold]{resume_hint}[/]"
        )
        raise typer.Exit(1) from error

    snapshot = graph.get_state(config)
    final = snapshot.values
    folder = Path(ctx.output_dir) / "episodes" / episode_id
    if "approval" in snapshot.next:
        console.print(f"[bold yellow]Waiting for your approval:[/] {final.get('video_path')}")
    elif final.get("status") in ("approved", "rejected", "discarded", "needs_human", *UPLOADED):
        console.print(f"[bold]{final['status'].capitalize()}.[/]")
    console.print(f"Folder: {folder}\nModel tokens used: {final.get('tokens_used', 0):,}")


def describe(node: str, values: dict) -> str:
    """One short line about what an agent just produced."""
    if node in ("images_done", "pictures_done", "paint_cards"):
        return "pictures ready" if node != "paint_cards" else "painting the cards"
    if "plan" in values:
        return "words: " + ", ".join(idea.word for idea in values["plan"].words)
    if "cards" in values:
        card = values["cards"][0]
        return f"card {card.index}: {card.description}" + (
            f" [yellow]flagged: {card.flagged}[/]" if card.flagged else "")
    if "pictures" in values:
        picture = values["pictures"][0]
        return f"word {picture.index}" + (f" [yellow]flagged: {picture.flagged}[/]"
                                          if picture.flagged else "")
    if "lines" in values:
        seconds = sum(line.duration_s for line in values["lines"])
        return f"{len(values['lines'])} lines, {seconds:.0f} s of speech"
    if "props_path" in values:
        return values["props_path"]
    if "brief" in values:
        return f"topic: {values['brief'].topic}"
    if "script" in values:
        script = values["script"]
        return f"\"{script.title}\", {len(script.scenes)} scenes, {script.spoken_words()} words" \
            if hasattr(script, "spoken_words") else f"\"{script.title}\""
    if "review" in values:
        review = values["review"]
        blockers = len(review.hard_fails) + len(review.wrong_facts)
        verdict = "passed" if review.passed else f"blocked ({blockers} blockers)"
        notes = f", {len(review.issues)} notes" if review.issues else ""
        return f"{verdict}{notes}, average score {review.scores.average():.1f}"
    if "art_plan" in values:
        return f"{len(values['art_plan'].prompts)} picture prompts"
    if "images" in values:
        image = values["images"][0]
        return f"scene {image.scene_id}" + (f" [yellow]flagged: {image.flagged}[/]"
                                            if image.flagged else "")
    if "audio" in values:
        clip = values["audio"][0]
        return f"scene {clip.scene_id}, {clip.duration_s:.1f} s"
    if "video_path" in values:
        return values["video_path"]
    if "thumbnail_path" in values:
        return values["thumbnail_path"]
    if "metadata" in values:
        return f"title: {values['metadata'].title}"
    if "qa" in values:
        failed = [check.name for check in values["qa"].checks if not check.ok]
        return "all checks passed" if not failed else "failed: " + ", ".join(failed)
    if "youtube" in values:
        done = values["youtube"]
        when = (f"goes public {datetime.fromisoformat(done['publish_at']):%a %d %b %H:%M}"
                if done["publish_at"] else "private")
        warnings = "".join(f"\n        [yellow]not done: {w}[/]" for w in done["warnings"])
        return f"https://youtu.be/{done['video_id']}, {when}{warnings}"
    return values.get("status", "")
