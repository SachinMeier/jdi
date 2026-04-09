package com.sachinmeier.jdivoiceandroid

import android.content.Context
import com.sachinmeier.jdivoiceandroid.config.ConfigRepository
import com.sachinmeier.jdivoiceandroid.dispatch.CommandDispatcher
import com.sachinmeier.jdivoiceandroid.lifx.LifxHttpClient
import com.sachinmeier.jdivoiceandroid.lifx.LifxLanClient
import com.sachinmeier.jdivoiceandroid.model.ModelRepository
import okhttp3.OkHttpClient

class AppContainer(context: Context) {
    private val appContext = context.applicationContext
    private val httpClient = OkHttpClient()

    val configRepository = ConfigRepository(appContext)
    val modelRepository = ModelRepository(appContext, httpClient)
    val lifxLanClient = LifxLanClient()
    val lifxHttpClient = LifxHttpClient(httpClient)
    val commandDispatcher = CommandDispatcher(
        lanClient = lifxLanClient,
        httpClient = lifxHttpClient,
    )
}
