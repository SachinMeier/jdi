package com.sachinmeier.jdivoiceandroid.service

import com.sachinmeier.jdivoiceandroid.AppContainer
import com.sachinmeier.jdivoiceandroid.audio.AudioRecorderSource
import com.sachinmeier.jdivoiceandroid.config.AppConfig
import com.sachinmeier.jdivoiceandroid.config.CommandMatcher
import com.sachinmeier.jdivoiceandroid.config.ConfigException
import com.sachinmeier.jdivoiceandroid.config.normalizePhrase
import com.sachinmeier.jdivoiceandroid.recognition.VoskGrammarRecognizer
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.vosk.Model
import java.io.File
import kotlin.math.ceil

class VoiceEngine(
    private val appContainer: AppContainer,
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    @Volatile
    private var running = false

    @Volatile
    private var manualPressed = false

    @Volatile
    private var manualReleaseRequested = false

    private var loopJob: Job? = null
    private var config: AppConfig? = null
    private var matcher: CommandMatcher? = null
    private var model: Model? = null
    private var wakeRecognizer: VoskGrammarRecognizer? = null
    private var commandRecognizer: VoskGrammarRecognizer? = null
    private var wakeSession: VoskGrammarRecognizer.Session? = null
    private var commandSession: VoskGrammarRecognizer.Session? = null
    private var audioSource: AudioRecorderSource? = null
    private var commandMode: CommandMode = CommandMode.IDLE
    private var commandDeadlineMs: Long = 0L
    private var discardFramesRemaining: Int = 0

    suspend fun start() {
        if (running) {
            return
        }
        val loadedConfig = appContainer.configRepository.loadConfig()
        val modelDir = requireModelDirectory(loadedConfig)
        val loadedModel = Model(modelDir.absolutePath)
        val loadedMatcher = CommandMatcher(loadedConfig.commands)
        val loadedWakeRecognizer = loadedConfig.wakeWord.takeIf { it.enabled }?.let {
            VoskGrammarRecognizer(
                model = loadedModel,
                sampleRateHz = loadedConfig.audio.sampleRateHz,
                phrases = loadedConfig.wakeWord.phrases,
                detectPartialMatches = true,
            )
        }
        val loadedCommandRecognizer = VoskGrammarRecognizer(
            model = loadedModel,
            sampleRateHz = loadedConfig.audio.sampleRateHz,
            phrases = loadedMatcher.phrases,
            detectPartialMatches = false,
        )

        config = loadedConfig
        matcher = loadedMatcher
        model = loadedModel
        wakeRecognizer = loadedWakeRecognizer
        commandRecognizer = loadedCommandRecognizer
        wakeSession = loadedWakeRecognizer?.newSession()
        audioSource = AudioRecorderSource(loadedConfig.audio)
        commandMode = if (loadedConfig.wakeWord.enabled) CommandMode.WAKE_IDLE else CommandMode.IDLE
        running = true
        VoiceRuntimeStore.update {
            it.copy(
                serviceRunning = true,
                modelInstalled = true,
                listeningMode = if (loadedConfig.wakeWord.enabled) "wake" else "idle",
                errorMessage = null,
            )
        }
        loopJob = scope.launch { runLoop() }
    }

    suspend fun stop() {
        running = false
        loopJob?.cancelAndJoin()
        loopJob = null
        commandSession?.close()
        commandSession = null
        wakeSession?.close()
        wakeSession = null
        audioSource?.stop()
        audioSource = null
        model?.close()
        model = null
        wakeRecognizer = null
        commandRecognizer = null
        config = null
        matcher = null
        manualPressed = false
        manualReleaseRequested = false
        commandMode = CommandMode.IDLE
        VoiceRuntimeStore.update {
            it.copy(
                serviceRunning = false,
                listeningMode = "idle",
                errorMessage = null,
            )
        }
    }

    suspend fun reload() {
        stop()
        start()
    }

    fun onManualPress() {
        if (!running) {
            return
        }
        manualPressed = true
        manualReleaseRequested = false
        val currentConfig = config ?: return
        armCommandSession(CommandMode.MANUAL, currentConfig)
    }

    fun onManualRelease() {
        if (!running) {
            return
        }
        manualPressed = false
        manualReleaseRequested = true
    }

    private suspend fun runLoop() {
        val buffer = ByteArray((config?.audio?.frameSize ?: 1280) * 2)
        while (running) {
            val currentConfig = config ?: break
            if (!shouldCaptureAudio(currentConfig)) {
                audioSource?.stop()
                updateListeningMode(currentConfig)
                delay(50)
                continue
            }

            val source = audioSource ?: AudioRecorderSource(currentConfig.audio).also {
                audioSource = it
            }
            source.startIfNeeded()
            val bytesRead = source.read(buffer)
            if (bytesRead <= 0) {
                continue
            }

            when (commandMode) {
                CommandMode.MANUAL -> handleCommandAudio(currentConfig, buffer, bytesRead, fromWake = false)
                CommandMode.POST_WAKE -> handlePostWakeAudio(currentConfig, buffer, bytesRead)
                CommandMode.WAKE_IDLE -> handleWakeAudio(currentConfig, buffer, bytesRead)
                CommandMode.IDLE -> {
                    if (manualPressed) {
                        armCommandSession(CommandMode.MANUAL, currentConfig)
                    }
                }
            }
        }
    }

    private suspend fun handleWakeAudio(
        currentConfig: AppConfig,
        buffer: ByteArray,
        bytesRead: Int,
    ) {
        val wake = wakeSession?.acceptAudio(buffer, bytesRead) ?: return
        commandSession?.close()
        commandSession = null
        discardFramesRemaining = ceil(
            currentConfig.audio.postWakeDelayMs.toDouble() /
                ((currentConfig.audio.frameSize * 1000.0) / currentConfig.audio.sampleRateHz),
        ).toInt()
        armCommandSession(CommandMode.POST_WAKE, currentConfig)
        VoiceRuntimeStore.update {
            it.copy(listeningMode = "wake detected", errorMessage = null)
        }
        wakeSession?.close()
        wakeSession = wakeRecognizer?.newSession()
        if (normalizePhrase(wake).isBlank()) {
            updateListeningMode(currentConfig)
        }
    }

    private suspend fun handlePostWakeAudio(
        currentConfig: AppConfig,
        buffer: ByteArray,
        bytesRead: Int,
    ) {
        if (discardFramesRemaining > 0) {
            discardFramesRemaining -= 1
            return
        }
        handleCommandAudio(currentConfig, buffer, bytesRead, fromWake = true)
    }

    private suspend fun handleCommandAudio(
        currentConfig: AppConfig,
        buffer: ByteArray,
        bytesRead: Int,
        fromWake: Boolean,
    ) {
        val session = commandSession ?: return
        val transcript = session.acceptAudio(buffer, bytesRead)
        if (transcript != null) {
            dispatchTranscript(currentConfig, transcript)
            finishCommandSession(currentConfig)
            return
        }

        if (commandMode == CommandMode.MANUAL && manualReleaseRequested) {
            finalizeAndDispatch(currentConfig)
            return
        }

        if (System.currentTimeMillis() >= commandDeadlineMs) {
            finalizeAndDispatch(currentConfig)
            if (fromWake) {
                updateListeningMode(currentConfig)
            }
        }
    }

    private suspend fun finalizeAndDispatch(currentConfig: AppConfig) {
        val transcript = commandSession?.finalizeResult()
        if (!transcript.isNullOrBlank()) {
            dispatchTranscript(currentConfig, transcript)
        }
        finishCommandSession(currentConfig)
    }

    private suspend fun dispatchTranscript(currentConfig: AppConfig, transcript: String) {
        VoiceRuntimeStore.update {
            it.copy(lastTranscript = transcript, listeningMode = "executing", errorMessage = null)
        }
        val matched = matcher?.match(transcript)
        if (matched == null) {
            VoiceRuntimeStore.update {
                it.copy(errorMessage = "No configured command matched `$transcript`.")
            }
            return
        }

        val outcome = try {
            appContainer.commandDispatcher.dispatch(currentConfig, matched.command)
        } catch (error: Throwable) {
            VoiceRuntimeStore.update {
                it.copy(errorMessage = error.message ?: "Unknown dispatch failure.")
            }
            return
        }

        VoiceRuntimeStore.update {
            it.copy(lastAction = outcome.details, errorMessage = null)
        }
    }

    private fun armCommandSession(mode: CommandMode, currentConfig: AppConfig) {
        if (commandMode == mode && commandSession != null) {
            return
        }
        commandSession?.close()
        commandSession = commandRecognizer?.newSession()
        commandDeadlineMs = System.currentTimeMillis() + currentConfig.audio.commandTimeoutMs
        manualReleaseRequested = false
        commandMode = mode
        VoiceRuntimeStore.update {
            it.copy(
                listeningMode = when (mode) {
                    CommandMode.MANUAL -> "manual"
                    CommandMode.POST_WAKE -> "command"
                    CommandMode.WAKE_IDLE -> "wake"
                    CommandMode.IDLE -> "idle"
                },
                errorMessage = null,
            )
        }
    }

    private fun finishCommandSession(currentConfig: AppConfig) {
        commandSession?.close()
        commandSession = null
        manualReleaseRequested = false
        commandMode = if (currentConfig.wakeWord.enabled) CommandMode.WAKE_IDLE else CommandMode.IDLE
        updateListeningMode(currentConfig)
    }

    private fun updateListeningMode(currentConfig: AppConfig) {
        val nextMode = when {
            commandMode == CommandMode.MANUAL -> "manual"
            commandMode == CommandMode.POST_WAKE -> "command"
            currentConfig.wakeWord.enabled -> "wake"
            else -> "idle"
        }
        VoiceRuntimeStore.update { it.copy(listeningMode = nextMode) }
    }

    private fun shouldCaptureAudio(currentConfig: AppConfig): Boolean {
        return currentConfig.wakeWord.enabled ||
            manualPressed ||
            commandMode == CommandMode.MANUAL ||
            commandMode == CommandMode.POST_WAKE
    }

    private fun requireModelDirectory(currentConfig: AppConfig): File {
        return appContainer.modelRepository.modelDirectory(currentConfig.recognition)
            .takeIf { it.isDirectory }
            ?: throw ConfigException(
                "Offline model is missing. Download the model from the main screen before starting the service.",
            )
    }

    private enum class CommandMode {
        IDLE,
        WAKE_IDLE,
        MANUAL,
        POST_WAKE,
    }
}
