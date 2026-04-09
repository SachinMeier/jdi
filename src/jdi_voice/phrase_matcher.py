from __future__ import annotations

from dataclasses import dataclass

from .config import CommandBinding, normalize_phrase


@dataclass(frozen=True)
class PhraseMatch:
    transcript: str
    normalized_transcript: str
    command: CommandBinding


class ExactPhraseMatcher:
    """Maps normalized transcripts to a configured command."""

    def __init__(self, commands: tuple[CommandBinding, ...]) -> None:
        self._commands_by_phrase: dict[str, CommandBinding] = {}
        for command in commands:
            for phrase in command.phrases:
                normalized = normalize_phrase(phrase)
                if normalized in self._commands_by_phrase:
                    raise ValueError(f"Duplicate phrase `{normalized}`.")
                self._commands_by_phrase[normalized] = command

    @property
    def phrases(self) -> tuple[str, ...]:
        return tuple(self._commands_by_phrase.keys())

    def match(self, transcript: str) -> PhraseMatch | None:
        normalized = normalize_phrase(transcript)
        command = self._commands_by_phrase.get(normalized)
        if command is None:
            return None
        return PhraseMatch(
            transcript=transcript,
            normalized_transcript=normalized,
            command=command,
        )

