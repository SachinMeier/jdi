package com.sachinmeier.jdivoiceandroid.config

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class CommandMatcherTest {
    @Test
    fun matchesNormalizedPhrase() {
        val matcher = CommandMatcher(
            listOf(
                CommandDefinition(
                    phrases = listOf("Turn Bedroom Off"),
                    action = CommandAction(
                        type = ActionType.POWER,
                        target = "bedroom",
                        value = PowerValue.OFF,
                    ),
                ),
            ),
        )

        val result = matcher.match("turn bedroom off!!!")

        assertNotNull(result)
        assertEquals("turn bedroom off", result?.normalizedPhrase)
    }

    @Test
    fun returnsNullForUnknownPhrase() {
        val matcher = CommandMatcher(
            listOf(
                CommandDefinition(
                    phrases = listOf("turn foyer on"),
                    action = CommandAction(
                        type = ActionType.POWER,
                        target = "foyer",
                        value = PowerValue.ON,
                    ),
                ),
            ),
        )

        assertNull(matcher.match("turn kitchen on"))
    }
}
