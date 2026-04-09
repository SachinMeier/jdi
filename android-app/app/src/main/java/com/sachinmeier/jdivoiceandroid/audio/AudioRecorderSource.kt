package com.sachinmeier.jdivoiceandroid.audio

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import com.sachinmeier.jdivoiceandroid.config.AudioConfig
import kotlin.math.max

class AudioRecorderSource(
    private val config: AudioConfig,
) {
    private var recorder: AudioRecord? = null

    @SuppressLint("MissingPermission")
    fun startIfNeeded() {
        if (recorder != null) {
            return
        }
        val minBuffer = AudioRecord.getMinBufferSize(
            config.sampleRateHz,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        val bufferSize = max(minBuffer, config.frameSize * 4)
        recorder = AudioRecord(
            MediaRecorder.AudioSource.VOICE_RECOGNITION,
            config.sampleRateHz,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            bufferSize,
        ).also { it.startRecording() }
    }

    fun read(target: ByteArray): Int {
        val activeRecorder = recorder ?: return 0
        return activeRecorder.read(target, 0, target.size, AudioRecord.READ_BLOCKING)
    }

    fun stop() {
        recorder?.run {
            stop()
            release()
        }
        recorder = null
    }
}
