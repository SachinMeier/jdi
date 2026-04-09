package com.sachinmeier.jdivoiceandroid.recognition

import com.sachinmeier.jdivoiceandroid.config.normalizePhrase
import org.json.JSONObject
import org.vosk.Model
import org.vosk.Recognizer

class VoskGrammarRecognizer(
    private val model: Model,
    private val sampleRateHz: Int,
    phrases: List<String>,
    private val detectPartialMatches: Boolean,
) {
    private val normalizedPhrases = phrases.map(::normalizePhrase).toSet()
    private val grammarJson = phrases.joinToString(
        prefix = "[",
        postfix = "]",
    ) { phrase -> JSONObject.quote(phrase) }

    fun newSession(): Session {
        val recognizer = Recognizer(model, sampleRateHz.toFloat(), grammarJson)
        return Session(recognizer, normalizedPhrases, detectPartialMatches)
    }

    class Session(
        private val recognizer: Recognizer,
        private val normalizedPhrases: Set<String>,
        private val detectPartialMatches: Boolean,
    ) : AutoCloseable {
        fun acceptAudio(buffer: ByteArray, length: Int): String? {
            if (recognizer.acceptWaveForm(buffer, length)) {
                return extractField(recognizer.result, "text")
                    ?.takeIf { normalizePhrase(it) in normalizedPhrases }
            }
            if (!detectPartialMatches) {
                return null
            }
            return extractField(recognizer.partialResult, "partial")
                ?.takeIf { normalizePhrase(it) in normalizedPhrases }
        }

        fun finalizeResult(): String? {
            return extractField(recognizer.finalResult, "text")
                ?.takeIf { normalizePhrase(it) in normalizedPhrases }
        }

        override fun close() {
            recognizer.close()
        }

        private fun extractField(rawJson: String, field: String): String? {
            return runCatching {
                JSONObject(rawJson).optString(field).trim()
            }.getOrNull()?.takeIf { it.isNotBlank() }
        }
    }
}
