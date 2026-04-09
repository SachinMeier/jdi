package com.sachinmeier.jdivoiceandroid.config

class CommandMatcher(commands: List<CommandDefinition>) {
    private val byPhrase = commands.flatMap { command ->
        command.phrases.map { phrase -> normalizePhrase(phrase) to command }
    }.toMap()

    val phrases: List<String> = byPhrase.keys.toList()

    fun match(transcript: String): MatchedCommand? {
        val normalized = normalizePhrase(transcript)
        val command = byPhrase[normalized] ?: return null
        return MatchedCommand(normalized, command)
    }
}

fun normalizePhrase(value: String): String {
    return value
        .trim()
        .lowercase()
        .replace(Regex("[^a-z0-9\\s]"), " ")
        .replace(Regex("\\s+"), " ")
        .trim()
}
