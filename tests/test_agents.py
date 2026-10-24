import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool

from kiddy.graph import MAX_SCRIPT_ATTEMPTS, after_review
from kiddy.nodes.safety_reviewer import length_problems
from kiddy.nodes.scriptwriter import length_plan, revision_notes, tidy, word_budget
from kiddy.providers import fixtures
from kiddy.providers.llm import BadModelOutput
from kiddy.state import FactCheck, Issue, Review, Scores, Script

GOOD = Scores(age_fit=5, clarity=4, warmth=4, learning_value=4, drawability=4, originality=4)
NOTE = Issue(scene_id=3, problem="The rhyme is clumsy.", fix="Rhyme 'tree' with 'see'.")
MISLEADING = FactCheck(
    claim="Leaves change color because of rain.", verdict="misleading",
    correction="Leaves change color because shorter days make the green fade.",
)


def review(**changes) -> Review:
    return Review(fact_checks=[], hard_fails=[], scores=GOOD, issues=[]).model_copy(update=changes)


def test_review_passes_only_without_blockers_and_with_good_scores():
    assert review().passed
    assert not review(hard_fails=["unsafe stunt"]).passed
    assert not review(fact_checks=[MISLEADING]).passed  # a wrong fact is a hard fail
    assert not review(scores=GOOD.model_copy(update={"clarity": 1, "warmth": 2})).passed


def test_the_model_never_sees_the_passed_field():
    properties = convert_to_openai_tool(Review)["function"]["parameters"]["properties"]
    assert "passed" not in properties
    assert list(properties)[0] == "fact_checks"  # facts are checked before anything is scored


def test_blocked_script_goes_back_to_the_writer_then_to_a_human():
    blocked = review(hard_fails=["scary"])
    assert after_review({"review": blocked, "script_attempts": 1}) == "scriptwriter"
    assert after_review({"review": blocked, "script_attempts": MAX_SCRIPT_ATTEMPTS}) == "escalate"


def test_passed_script_with_notes_is_polished_while_tries_remain():
    noted = review(issues=[NOTE])
    assert after_review({"review": noted, "script_attempts": 1}) == "scriptwriter"
    assert after_review({"review": noted, "script_attempts": MAX_SCRIPT_ATTEMPTS}) == "art_director"
    assert after_review({"review": review(), "script_attempts": 1}) == "art_director"


def test_revision_notes_carry_blockers_facts_issues_and_human_notes():
    last = review(hard_fails=["unsafe things a child could copy"], fact_checks=[MISLEADING],
                  issues=[NOTE])
    notes = revision_notes({"review": last, "feedback": ["Make Glim sillier."]})
    assert notes == [
        "Hard fail: unsafe things a child could copy",
        "Wrong fact (misleading): Leaves change color because of rain. True version: "
        "Leaves change color because shorter days make the green fade.",
        "Scene 3: The rhyme is clumsy. Fix: Rhyme 'tree' with 'see'.",
        "Make Glim sillier.",
    ]


def test_length_is_counted_against_the_word_budget():
    script = fixtures.answer(Script)
    budget = word_budget(fixtures.BRIEF)
    assert length_problems(script, budget) == []  # the fake episode fits its own budget
    assert length_problems(script, budget * 2)[0].startswith("Too short:")
    assert length_problems(script, budget // 2)[0].startswith("Too long:")


def test_length_plan_splits_the_budget_into_scenes():
    assert length_plan(440) == {"total_words": 440, "scenes": 11, "words_per_scene": 40}
    assert length_plan(100)["scenes"] == 8  # never fewer than 8 pictures


def test_short_draft_gets_per_scene_notes():
    script = fixtures.answer(Script)
    script.scenes[1].lines = script.scenes[1].lines[:1]  # 10 words left in scene 2
    notes = revision_notes({"review": review(), "script": script, "brief": fixtures.BRIEF})
    assert "Scene 2 has 10 spoken words; give it about 41." in notes
    assert not any(note.startswith("Scene 1 ") for note in notes)  # 37 words is close enough


def test_tidy_maps_names_to_ids_and_renumbers_scenes(settings):
    script = fixtures.answer(Script)
    scene_count = len(script.scenes)
    script.scenes[0].lines[2].speaker = "Fennel"  # a name instead of an id
    script.scenes[0].characters = ["FENNEL", "a dragon"]  # unknown characters are dropped
    script.scenes[1].lines = []  # nothing to say: the scene goes

    tidied = tidy(script, settings)

    assert [scene.id for scene in tidied.scenes] == list(range(1, scene_count))
    assert tidied.scenes[0].lines[2].speaker == "fennel"
    assert tidied.scenes[0].characters == ["fennel"]


def test_tidy_rejects_a_script_with_nothing_to_say(settings):
    script = fixtures.answer(Script)
    for scene in script.scenes:
        scene.lines = []
    with pytest.raises(BadModelOutput):
        tidy(script, settings)
