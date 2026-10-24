"""Command line: `kiddy run`, `kiddy resume` and `kiddy list`."""

import os
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from kiddy.graph import build_graph, sqlite_checkpointer
from kiddy.settings import Settings
from kiddy.store import EpisodeStore, new_episode_id
from kiddy.studio import RunContext, studio_for

load_dotenv()
for stream in (sys.stdout, sys.stderr):
    stream.reconfigure(errors="replace")  # model text may hold characters old consoles can't show

app = typer.Typer(
    help="Kiddy: a small team of AI agents that makes kids' videos.",
    no_args_is_help=True, add_completion=False,
)
console = Console()


@app.command()
def run(
    topic: str = typer.Option("", help="What the episode is about. Empty: the showrunner picks."),
    fake: bool = typer.Option(
        False, "--fake", help="Fake every model and provider: offline and free."
    ),
) -> None:
    """Make a new episode, from idea to finished video."""
    ctx = RunContext(fake=fake)
    require_keys(ctx)
    episode_id = new_episode_id()
    studio_for(ctx).store.start(episode_id)
    drive(episode_id, {"episode_id": episode_id, "topic": topic}, ctx)


@app.command()
def resume(
    episode_id: str,
    fake: bool = typer.Option(False, "--fake", help="Use it if the episode started with --fake."),
) -> None:
    """Continue an episode from its last finished step. Finished pictures and voices are kept."""
    ctx = RunContext(fake=fake)
    require_keys(ctx)
    drive(episode_id, None, ctx)


@app.command("list")
def list_episodes(limit: int = typer.Option(20, help="How many recent episodes to show.")) -> None:
    """Show recent episodes and where each one stands."""
    table = Table("episode", "status", "title", "topic")
    for row in EpisodeStore(Path(RunContext().data_dir) / "kiddy.sqlite").recent(limit):
        table.add_row(row["id"], row["status"], row["title"] or "", row["topic"] or "")
    console.print(table)


def require_keys(ctx: RunContext) -> None:
    """Stop early, and kindly, when a real run has no Groq key."""
    if ctx.fake:
        return
    settings = Settings.load(Path(ctx.config_path))
    groq = any(m.model.startswith("groq:") for m in settings.llm.values())
    cloudflare = settings.providers.images == "cloudflare"
    missing = [
        *(["GROQ_API_KEY (free: https://console.groq.com/keys)"]
          if groq and not os.environ.get("GROQ_API_KEY") else []),
        *([f"{name} (free: Cloudflare dashboard > Workers AI)"
           for name in ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN")
           if cloudflare and not os.environ.get(name)]),
    ]
    if missing:
        console.print(f"[red]Missing in .env:[/] {', '.join(missing)}. Or try [bold]--fake[/].")
        raise typer.Exit(1)


def drive(episode_id: str, inputs: dict | None, ctx: RunContext) -> None:
    graph = build_graph(sqlite_checkpointer(Path(ctx.data_dir) / "checkpoints.sqlite"))
    config = {"configurable": {"thread_id": episode_id}, "max_concurrency": 4}
    resume_hint = f"uv run kiddy resume {episode_id}" + (" --fake" if ctx.fake else "")
    console.print(f"[bold]Episode {episode_id}[/]" + (" [dim](fake)[/]" if ctx.fake else ""))
    try:
        for update in graph.stream(inputs, config, context=ctx, stream_mode="updates"):
            for node, values in update.items():
                if node.startswith("__"):  # LangGraph's own bookkeeping, e.g. on resume
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

    final = graph.get_state(config).values
    folder = Path(ctx.output_dir) / "episodes" / episode_id
    if final.get("status") == "needs_human":
        console.print(
            f"\n[yellow]The script didn't pass review after {final.get('script_attempts')} tries."
            f"[/] The reasons are in {folder / 'review.json'}"
        )
    elif final.get("video_path"):
        console.print(f"\n[bold green]Video ready:[/] {final['video_path']}")
    console.print(f"Folder: {folder}\nModel tokens used: {final.get('tokens_used', 0):,}")


def describe(node: str, values: dict) -> str:
    """One short line about what an agent just produced."""
    if node == "images_done":
        return "every scene is painted"
    if "brief" in values:
        return f"topic: {values['brief'].topic}"
    if "script" in values:
        return f"\"{values['script'].title}\", {len(values['script'].scenes)} scenes"
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
    return values.get("status", "")
