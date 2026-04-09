package com.sachinmeier.jdivoiceandroid

import android.app.Application

class JdiVoiceApplication : Application() {
    lateinit var appContainer: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        appContainer = AppContainer(this)
    }
}
