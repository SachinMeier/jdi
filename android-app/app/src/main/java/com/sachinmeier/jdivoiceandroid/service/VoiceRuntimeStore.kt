package com.sachinmeier.jdivoiceandroid.service

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

data class VoiceServiceSnapshot(
    val serviceRunning: Boolean = false,
    val modelInstalled: Boolean = false,
    val listeningMode: String = "idle",
    val lastTranscript: String = "",
    val lastAction: String = "",
    val errorMessage: String? = null,
)

object VoiceRuntimeStore {
    private val mutableState = MutableStateFlow(VoiceServiceSnapshot())

    val state: StateFlow<VoiceServiceSnapshot> = mutableState

    fun update(transform: (VoiceServiceSnapshot) -> VoiceServiceSnapshot) {
        mutableState.value = transform(mutableState.value)
    }

    fun reset() {
        mutableState.value = VoiceServiceSnapshot()
    }
}
