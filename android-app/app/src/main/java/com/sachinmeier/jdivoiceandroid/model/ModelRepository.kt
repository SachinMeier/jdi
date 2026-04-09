package com.sachinmeier.jdivoiceandroid.model

import android.content.Context
import com.sachinmeier.jdivoiceandroid.config.RecognitionConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipInputStream

class ModelRepository(
    context: Context,
    private val httpClient: OkHttpClient,
) {
    private val appContext = context.applicationContext

    fun modelDirectory(config: RecognitionConfig): File {
        return File(File(appContext.filesDir, "models"), config.modelDirectoryName)
    }

    fun isModelInstalled(config: RecognitionConfig): Boolean {
        return modelDirectory(config).isDirectory
    }

    suspend fun ensureModelDownloaded(
        config: RecognitionConfig,
        onProgress: (bytesRead: Long, totalBytes: Long?) -> Unit = { _, _ -> },
    ): File = withContext(Dispatchers.IO) {
        val modelDir = modelDirectory(config)
        if (modelDir.isDirectory) {
            return@withContext modelDir
        }

        modelDir.parentFile?.mkdirs()
        val tempZip = File(appContext.cacheDir, "vosk-model.zip")
        val request = Request.Builder()
            .url(config.modelDownloadUrl)
            .build()

        httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                error("Model download failed with HTTP ${response.code}.")
            }
            val body = response.body ?: error("Model download returned an empty body.")
            val totalBytes = body.contentLength().takeIf { it > 0 }
            body.byteStream().use { input ->
                FileOutputStream(tempZip).use { output ->
                    val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                    var bytesReadTotal = 0L
                    while (true) {
                        val read = input.read(buffer)
                        if (read < 0) {
                            break
                        }
                        output.write(buffer, 0, read)
                        bytesReadTotal += read
                        onProgress(bytesReadTotal, totalBytes)
                    }
                }
            }
        }

        ZipInputStream(tempZip.inputStream().buffered()).use { zip ->
            while (true) {
                val entry = zip.nextEntry ?: break
                val output = File(modelDir.parentFile, entry.name)
                if (entry.isDirectory) {
                    output.mkdirs()
                } else {
                    output.parentFile?.mkdirs()
                    FileOutputStream(output).use { fileOut ->
                        zip.copyTo(fileOut)
                    }
                }
                zip.closeEntry()
            }
        }

        tempZip.delete()
        modelDir
    }
}
