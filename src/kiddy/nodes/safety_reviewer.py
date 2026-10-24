"""Safety reviewer: judges the script on its own, against the kid-safety rubric."""

from langgraph.runtime import Runtime

from kiddy.nodes.scriptwriter import word_budget
from kiddy.prompts import as_yaml, system_prompt
from kiddy.state import EpisodeState, Review, Script
from kiddy.store import save_json
from kiddy.studio import RunContext, get_studio

LENGTH_RANGE = (0.8, 1.25)  # share of the word budget a script may use


def safety_reviewer(state: EpisodeState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    script = state["script"]
    # The reviewer sees the script only, never the writer's prompt, so it judges independently.
    request = {"audience_age": studio.settings.audience_age, "script": script.model_dump()}
    review, tokens = studio.llm.structured(
        "safety_reviewer", Review, system_prompt("safety_reviewer"), as_yaml(request)
    )
    # Length is counted, not judged: models are bad at counting their own words.
    problems = length_problems(script, word_budget(state["brief"]))
    review = review.model_copy(update={"hard_fails": review.hard_fails + problems})
    save_json(studio.episode_dir(state["episode_id"]) / "review.json", review)
    return {"review": review, "tokens_used": tokens}


def length_problems(script: Script, budget: int) -> list[str]:
    words = script.spoken_words()
    low, high = (round(budget * share) for share in LENGTH_RANGE)
    if words < low:
        return [f"Too short: {words} spoken words, but the budget is {budget} (aim for "
                f"{low}-{high}). Add lines and scenes that deepen the same story."]
    if words > high:
        return [f"Too long: {words} spoken words, but the budget is {budget} (aim for "
                f"{low}-{high}). Trim lines without losing the story or the recap."]
    return []
