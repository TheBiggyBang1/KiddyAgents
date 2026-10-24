"""Canned agent answers for `kiddy run --fake` and the tests: an episode that fits its budget."""

from pydantic import BaseModel

from kiddy.state import Brief, FactCheck, Line, Review, Scene, Scores, Script, VisionCheck

LEARNING_GOAL = "In autumn the green fades, and the yellow and orange that were hiding come out."

BRIEF = Brief(
    topic="why leaves change color",
    angle="Fennel finds a yellow leaf and wonders where the green went",
    learning_goal=LEARNING_GOAL,
    format="story",
    mood="cozy",
    characters=["fennel", "olo", "glim"],
    target_minutes=3,
)


def scene(number: int, visual: str, characters: list[str], *lines: tuple[str, str]) -> Scene:
    return Scene(
        id=number, visual=visual, characters=characters, target_seconds=20,
        lines=[Line(speaker=speaker, text=text, emotion="warm") for speaker, text in lines],
    )


SCRIPT = Script(
    title="Where Did the Green Go?",
    logline="Fennel finds a yellow leaf, and with Olo and Glim learns why leaves change color.",
    learning_goal=LEARNING_GOAL,
    fact_claims=[
        LEARNING_GOAL,
        "Leaves are green because of chlorophyll, which helps trees make food from sunlight.",
        "In autumn, shorter days mean trees make less chlorophyll, so the green fades.",
        "Yellow and orange are in the leaf all summer, hidden by the green.",
        "Many trees make new red color in their leaves in autumn.",
    ],
    scenes=[
        scene(1, "Fennel holds up a bright yellow leaf under a tall maple in golden light",
              ["fennel"],
              ("narrator", "It was a cool autumn morning in Maple Wood. The air smelled like "
                           "apples, and the wind made the trees whisper."),
              ("narrator", "Fennel was out exploring with his tiny green backpack."),
              ("fennel", "Look! A yellow leaf! Yesterday it was green. Where did the green go?")),
        scene(2, "Fennel runs to Olo on a forest path, holding the yellow leaf up high",
              ["fennel", "olo"],
              ("fennel", "Olo! Olo! My leaf lost its green. Is it sick?"),
              ("olo", "No, Fennel. Your leaf is not sick. It is changing, like the season."),
              ("olo", "Let us find out why, together.")),
        scene(3, "Olo and Glim look at a big green leaf glowing in the sunshine",
              ["olo", "glim"],
              ("olo", "All summer, leaves are green because of a green helper. It is called "
                      "chlorophyll."),
              ("olo", "Can you say it with me? Chlor-o-phyll!"),
              ("glim", "Chlor-o-phyll! It helps the tree make food from sunshine!")),
        scene(4, "Olo and Fennel watch the sun set early over the trees, cool blue evening",
              ["olo", "fennel"],
              ("olo", "In autumn the days get shorter. There is less sunshine, and the nights "
                      "get cool."),
              ("fennel", "So the tree makes less green helper?"),
              ("olo", "Yes! Little by little, the green fades away. The tree gets ready for its "
                      "winter rest.")),
        scene(5, "Glim glows above a single leaf that is half green and half orange",
              ["glim"],
              ("glim", "And guess what was hiding under the green all summer long? Yellow and "
                       "orange!"),
              ("narrator", "The yellow and orange were there all along. The green was just "
                           "covering them up, like a blanket.")),
        scene(6, "Fennel laughs and peeks around a pile of yellow and orange leaves",
              ["fennel", "glim"],
              ("fennel", "Like a surprise under a blanket! Peekaboo, yellow! Peekaboo, orange!"),
              ("glim", "Can you say it too? Peekaboo, yellow! Peekaboo, orange!"),
              ("narrator", "Fennel laughed so hard that his fluffy tail wiggled.")),
        scene(7, "Olo smiles under a tree with bright red leaves, Fennel beside him",
              ["olo", "fennel"],
              ("olo", "Some leaves turn red, too. Many trees make that red color new each "
                      "autumn."),
              ("fennel", "So yellow and orange were hiding, and red is brand new!"),
              ("olo", "That's right, Fennel. You are a great leaf detective.")),
        scene(8, "Fennel, Olo and Glim wave goodbye under a tree of orange and yellow leaves",
              ["fennel", "olo", "glim"],
              ("narrator", "Let us remember what we learned today."),
              ("fennel", "In autumn the green fades away."),
              ("glim", "And the yellow and orange that were hiding come out to play!"),
              ("olo", "Can you find a yellow leaf on your next walk with a grown-up?"),
              ("narrator", "Bye for now, friends! See you next time in Maple Wood.")),
    ],
)

REVIEW = Review(
    fact_checks=[
        FactCheck(claim=claim, verdict="true", correction="") for claim in SCRIPT.fact_claims
    ],
    hard_fails=[],
    scores=Scores(age_fit=5, clarity=5, warmth=5, learning_value=5, drawability=5, originality=4),
    issues=[],
)

VISION = VisionCheck(
    matches_scene=True, characters_on_model=True, has_text=False, unsettling=False, problems=[]
)

ANSWERS: dict[type[BaseModel], BaseModel] = {
    Brief: BRIEF, Script: SCRIPT, Review: REVIEW, VisionCheck: VISION,
}


def answer[T: BaseModel](schema: type[T]) -> T:
    return ANSWERS[schema].model_copy(deep=True)
