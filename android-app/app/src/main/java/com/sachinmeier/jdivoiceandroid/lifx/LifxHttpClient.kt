package com.sachinmeier.jdivoiceandroid.lifx

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

class LifxHttpClient(
    private val httpClient: OkHttpClient,
) {
    fun setPower(
        baseUrl: String,
        token: String,
        selector: String,
        powerOn: Boolean,
        durationMs: Int,
    ) {
        require(token.isNotBlank()) { "LIFX HTTP token is missing." }
        val body = """{"power":"${if (powerOn) "on" else "off"}","duration":${durationMs / 1000.0}}"""
            .toRequestBody(JSON_MEDIA_TYPE)
        val request = Request.Builder()
            .url("${baseUrl.trimEnd('/')}/lights/${selector}/state")
            .header("Authorization", "Bearer $token")
            .put(body)
            .build()
        httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw LifxException("LIFX HTTP power request failed with HTTP ${response.code}.")
            }
        }
    }

    fun activateScene(
        baseUrl: String,
        token: String,
        sceneId: String,
        durationMs: Int,
    ) {
        require(token.isNotBlank()) { "LIFX HTTP token is missing." }
        val body = """{"duration":${durationMs / 1000.0}}""".toRequestBody(JSON_MEDIA_TYPE)
        val request = Request.Builder()
            .url("${baseUrl.trimEnd('/')}/scenes/scene_id:$sceneId/activate")
            .header("Authorization", "Bearer $token")
            .put(body)
            .build()
        httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw LifxException("LIFX scene activation failed with HTTP ${response.code}.")
            }
        }
    }

    companion object {
        private val JSON_MEDIA_TYPE = "application/json; charset=utf-8".toMediaType()
    }
}
