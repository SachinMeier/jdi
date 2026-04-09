from jdi_voice.config import CommandAction, CommandBinding
from jdi_voice.phrase_matcher import ExactPhraseMatcher


def test_phrase_matcher_normalizes_input() -> None:
    matcher = ExactPhraseMatcher(
        (
            CommandBinding(
                phrases=("Turn bedroom lights on",),
                action=CommandAction(type="power", target="bedroom", value="on"),
            ),
        )
    )

    match = matcher.match("turn bedroom lights on!!!")

    assert match is not None
    assert match.normalized_transcript == "turn bedroom lights on"
    assert match.command.action.target == "bedroom"

