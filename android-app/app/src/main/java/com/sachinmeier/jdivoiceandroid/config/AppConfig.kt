package com.sachinmeier.jdivoiceandroid.config

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class AppConfig(
    val audio: AudioConfig = AudioConfig(),
    val recognition: RecognitionConfig = RecognitionConfig(),
    val wakeWord: WakeWordConfig = WakeWordConfig(),
    val lifx: LifxConfig = LifxConfig(),
    val lights: Map<String, LightDefinition> = emptyMap(),
    val groups: Map<String, List<String>> = emptyMap(),
    val commands: List<CommandDefinition> = emptyList(),
)

@Serializable
data class AudioConfig(
    val sampleRateHz: Int = 16_000,
    val frameSize: Int = 1_280,
    val commandTimeoutMs: Long = 4_000,
    val postWakeDelayMs: Long = 300,
)

@Serializable
data class RecognitionConfig(
    val modelDownloadUrl: String = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
    val modelDirectoryName: String = "vosk-model-small-en-us-0.15",
)

@Serializable
data class WakeWordConfig(
    val enabled: Boolean = true,
    val phrases: List<String> = listOf("hey jarvis"),
    val debounceMs: Long = 1_200,
)

@Serializable
data class LifxConfig(
    val defaultTransport: Transport = Transport.LAN,
    val httpToken: String = "",
    val httpBaseUrl: String = "https://api.lifx.com/v1",
    val lanDiscoveryTimeoutMs: Int = 1_200,
    val lanCacheTtlMs: Long = 30_000,
)

@Serializable
data class LightDefinition(
    val label: String,
    val httpSelector: String? = null,
)

@Serializable
data class CommandDefinition(
    val phrases: List<String>,
    val action: CommandAction,
    val description: String = "",
)

@Serializable
data class CommandAction(
    val type: ActionType,
    val target: String? = null,
    val value: PowerValue? = null,
    val transport: Transport? = null,
    val selector: String? = null,
    val sceneId: String? = null,
    val durationMs: Int = 250,
)

@Serializable
enum class ActionType {
    @SerialName("power")
    POWER,

    @SerialName("scene")
    SCENE,
}

@Serializable
enum class PowerValue {
    @SerialName("on")
    ON,

    @SerialName("off")
    OFF,

    @SerialName("toggle")
    TOGGLE,
}

@Serializable
enum class Transport {
    @SerialName("lan")
    LAN,

    @SerialName("http")
    HTTP,
}

data class MatchedCommand(
    val normalizedPhrase: String,
    val command: CommandDefinition,
)
