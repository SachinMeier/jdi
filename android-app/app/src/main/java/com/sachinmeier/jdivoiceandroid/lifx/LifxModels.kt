package com.sachinmeier.jdivoiceandroid.lifx

data class LanLight(
    val macAddress: String,
    val ipAddress: String,
    val label: String,
)

class LifxException(message: String, cause: Throwable? = null) : RuntimeException(message, cause)
