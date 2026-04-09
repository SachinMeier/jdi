package com.sachinmeier.jdivoiceandroid.config

import android.content.Context
import kotlinx.serialization.json.Json
import java.io.File

class ConfigRepository(
    context: Context,
) {
    private val appContext = context.applicationContext
    private val json = Json {
        ignoreUnknownKeys = false
        prettyPrint = true
        encodeDefaults = true
    }

    private val configFile: File
        get() = File(appContext.filesDir, CONFIG_FILE_NAME)

    fun ensureConfigExists() {
        if (configFile.exists()) {
            return
        }
        val defaultConfig = appContext.assets.open(DEFAULT_CONFIG_ASSET).bufferedReader().use { it.readText() }
        configFile.writeText(defaultConfig, Charsets.UTF_8)
    }

    fun loadConfigText(): String {
        ensureConfigExists()
        return configFile.readText(Charsets.UTF_8)
    }

    fun loadConfig(): AppConfig {
        val config = json.decodeFromString<AppConfig>(loadConfigText())
        ConfigValidator.validate(config)
        return config
    }

    fun saveConfigText(rawJson: String) {
        val parsed = json.decodeFromString<AppConfig>(rawJson)
        ConfigValidator.validate(parsed)
        configFile.writeText(json.encodeToString(AppConfig.serializer(), parsed), Charsets.UTF_8)
    }

    fun restoreDefaultConfig() {
        val defaultConfig = appContext.assets.open(DEFAULT_CONFIG_ASSET).bufferedReader().use { it.readText() }
        saveConfigText(defaultConfig)
    }

    companion object {
        private const val CONFIG_FILE_NAME = "voice-config.json"
        private const val DEFAULT_CONFIG_ASSET = "default-config.json"
    }
}
