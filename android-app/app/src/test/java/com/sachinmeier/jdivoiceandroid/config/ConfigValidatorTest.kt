package com.sachinmeier.jdivoiceandroid.config

import org.junit.Test

class ConfigValidatorTest {
    @Test(expected = IllegalArgumentException::class)
    fun rejectsDuplicateNormalizedCommandPhrases() {
        ConfigValidator.validate(
            AppConfig(
                lights = mapOf(
                    "bedroom" to LightDefinition(label = "Bedroom1"),
                ),
                commands = listOf(
                    CommandDefinition(
                        phrases = listOf("turn bedroom off"),
                        action = CommandAction(
                            type = ActionType.POWER,
                            target = "bedroom",
                            value = PowerValue.OFF,
                        ),
                    ),
                    CommandDefinition(
                        phrases = listOf("Turn bedroom off!!!"),
                        action = CommandAction(
                            type = ActionType.POWER,
                            target = "bedroom",
                            value = PowerValue.ON,
                        ),
                    ),
                ),
            ),
        )
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsUnknownGroupMember() {
        ConfigValidator.validate(
            AppConfig(
                lights = mapOf(
                    "bedroom" to LightDefinition(label = "Bedroom1"),
                ),
                groups = mapOf(
                    "common" to listOf("bedroom", "missing"),
                ),
                commands = listOf(
                    CommandDefinition(
                        phrases = listOf("toggle common"),
                        action = CommandAction(
                            type = ActionType.POWER,
                            target = "common",
                            value = PowerValue.TOGGLE,
                        ),
                    ),
                ),
            ),
        )
    }
}
