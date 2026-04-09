package com.sachinmeier.jdivoiceandroid.dispatch

import com.sachinmeier.jdivoiceandroid.config.ActionType
import com.sachinmeier.jdivoiceandroid.config.AppConfig
import com.sachinmeier.jdivoiceandroid.config.CommandDefinition
import com.sachinmeier.jdivoiceandroid.config.PowerValue
import com.sachinmeier.jdivoiceandroid.config.Transport
import com.sachinmeier.jdivoiceandroid.lifx.LanLight
import com.sachinmeier.jdivoiceandroid.lifx.LifxHttpClient
import com.sachinmeier.jdivoiceandroid.lifx.LifxLanClient

data class DispatchOutcome(
    val details: String,
)

class CommandDispatcher(
    private val lanClient: LifxLanClient,
    private val httpClient: LifxHttpClient,
) {
    suspend fun dispatch(
        config: AppConfig,
        command: CommandDefinition,
    ): DispatchOutcome {
        return when (command.action.type) {
            ActionType.POWER -> dispatchPower(config, command)
            ActionType.SCENE -> dispatchScene(config, command)
        }
    }

    suspend fun listLanLights(config: AppConfig): List<LanLight> {
        return lanClient.listLights(
            timeoutMs = config.lifx.lanDiscoveryTimeoutMs,
            cacheTtlMs = config.lifx.lanCacheTtlMs,
        )
    }

    private suspend fun dispatchPower(
        config: AppConfig,
        command: CommandDefinition,
    ): DispatchOutcome {
        val action = command.action
        val transport = action.transport ?: config.lifx.defaultTransport
        return when (transport) {
            Transport.LAN -> {
                val lights = resolveLanTargets(config, action.target.orEmpty())
                val desiredPowerOn = when (action.value) {
                    PowerValue.ON -> true
                    PowerValue.OFF -> false
                    PowerValue.TOGGLE -> {
                        val anyOn = lights.any { lanClient.getPower(it) == true }
                        !anyOn
                    }

                    null -> error("Power value missing.")
                }
                lights.forEach { light ->
                    lanClient.setPower(light, desiredPowerOn, action.durationMs)
                }
                DispatchOutcome(
                    "Set ${lights.joinToString { it.label }} to ${if (desiredPowerOn) "on" else "off"} over LAN.",
                )
            }

            Transport.HTTP -> {
                val selector = action.selector ?: resolveHttpSelector(config, action.target.orEmpty())
                val desiredPowerOn = when (action.value) {
                    PowerValue.ON -> true
                    PowerValue.OFF -> false
                    PowerValue.TOGGLE -> error("HTTP toggle is not supported in this app.")
                    null -> error("Power value missing.")
                }
                httpClient.setPower(
                    baseUrl = config.lifx.httpBaseUrl,
                    token = config.lifx.httpToken,
                    selector = selector,
                    powerOn = desiredPowerOn,
                    durationMs = action.durationMs,
                )
                DispatchOutcome(
                    "Set selector `$selector` to ${if (desiredPowerOn) "on" else "off"} over HTTP.",
                )
            }
        }
    }

    private fun dispatchScene(
        config: AppConfig,
        command: CommandDefinition,
    ): DispatchOutcome {
        val sceneId = command.action.sceneId ?: error("Scene ID missing.")
        httpClient.activateScene(
            baseUrl = config.lifx.httpBaseUrl,
            token = config.lifx.httpToken,
            sceneId = sceneId,
            durationMs = command.action.durationMs,
        )
        return DispatchOutcome("Activated cloud scene `$sceneId`.")
    }

    private suspend fun resolveLanTargets(config: AppConfig, target: String): List<LanLight> {
        val discovered = listLanLights(config)
        if (target == "all") {
            return discovered
        }
        config.groups[target]?.let { members ->
            return members.map { alias ->
                val definition = config.lights.getValue(alias)
                discovered.firstOrNull { it.label == definition.label }
                    ?: error("LAN light `${definition.label}` is not currently discoverable.")
            }
        }

        val light = config.lights[target] ?: error("Unknown target `$target`.")
        return listOf(
            discovered.firstOrNull { it.label == light.label }
                ?: error("LAN light `${light.label}` is not currently discoverable."),
        )
    }

    private fun resolveHttpSelector(config: AppConfig, target: String): String {
        if (target == "all") {
            return "all"
        }
        val light = config.lights[target] ?: error("Unknown target `$target`.")
        return light.httpSelector ?: "label:${light.label}"
    }
}
