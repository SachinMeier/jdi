package com.sachinmeier.jdivoiceandroid.config

class ConfigException(message: String) : IllegalArgumentException(message)

object ConfigValidator {
    fun validate(config: AppConfig) {
        require(config.audio.sampleRateHz == 16_000) {
            "Audio sample rate must be 16000 Hz."
        }
        require(config.audio.frameSize > 0) {
            "Audio frameSize must be greater than zero."
        }
        require(config.audio.commandTimeoutMs > 0) {
            "Audio commandTimeoutMs must be greater than zero."
        }
        require(config.recognition.modelDownloadUrl.isNotBlank()) {
            "Recognition modelDownloadUrl may not be blank."
        }
        require(config.recognition.modelDirectoryName.isNotBlank()) {
            "Recognition modelDirectoryName may not be blank."
        }
        if (config.wakeWord.enabled) {
            require(config.wakeWord.phrases.isNotEmpty()) {
                "Wake-word mode requires at least one wake phrase."
            }
        }

        val normalizedSeen = mutableSetOf<String>()
        for ((alias, light) in config.lights) {
            require(alias.isNotBlank()) { "Light aliases may not be blank." }
            require(light.label.isNotBlank()) { "lights.$alias.label may not be blank." }
        }

        for ((groupAlias, groupMembers) in config.groups) {
            require(groupAlias.isNotBlank()) { "Group aliases may not be blank." }
            require(groupMembers.isNotEmpty()) { "groups.$groupAlias may not be empty." }
            for (member in groupMembers) {
                require(config.lights.containsKey(member)) {
                    "groups.$groupAlias references unknown light `$member`."
                }
            }
        }

        require(config.commands.isNotEmpty()) { "At least one command is required." }
        for (command in config.commands) {
            require(command.phrases.isNotEmpty()) { "Every command requires at least one phrase." }
            for (phrase in command.phrases) {
                val normalized = normalizePhrase(phrase)
                require(normalized.isNotBlank()) { "Command phrases may not be blank." }
                require(normalizedSeen.add(normalized)) {
                    "Duplicate normalized command phrase `$normalized`."
                }
            }
            validateAction(config, command.action)
        }
    }

    private fun validateAction(config: AppConfig, action: CommandAction) {
        require(action.durationMs >= 0) { "Command durationMs must be non-negative." }
        when (action.type) {
            ActionType.POWER -> {
                require(action.target != null || action.selector != null) {
                    "Power actions require target or selector."
                }
                require(action.value != null) { "Power actions require a value." }
                val transport = action.transport ?: config.lifx.defaultTransport
                if (transport == Transport.LAN) {
                    require(action.target != null) {
                        "LAN power actions require a target."
                    }
                    validateTarget(config, action.target)
                }
                if (transport == Transport.HTTP && action.target != null) {
                    validateTarget(config, action.target)
                }
            }

            ActionType.SCENE -> {
                require(action.sceneId?.isNotBlank() == true) {
                    "Scene actions require sceneId."
                }
            }
        }
    }

    private fun validateTarget(config: AppConfig, target: String) {
        if (target == "all") {
            return
        }
        require(config.lights.containsKey(target) || config.groups.containsKey(target)) {
            "Unknown target `$target`."
        }
    }
}
