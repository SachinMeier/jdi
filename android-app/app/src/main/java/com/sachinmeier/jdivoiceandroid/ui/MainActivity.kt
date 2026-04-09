package com.sachinmeier.jdivoiceandroid.ui

import android.Manifest
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.view.MotionEvent
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.sachinmeier.jdivoiceandroid.JdiVoiceApplication
import com.sachinmeier.jdivoiceandroid.databinding.ActivityMainBinding
import com.sachinmeier.jdivoiceandroid.service.VoiceForegroundService
import com.sachinmeier.jdivoiceandroid.service.VoiceRuntimeStore
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding
    private val appContainer by lazy { (application as JdiVoiceApplication).appContainer }

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { permissions ->
        val denied = permissions.filterValues { granted -> !granted }.keys
        if (denied.isNotEmpty()) {
            Toast.makeText(this, "Missing permissions: ${denied.joinToString()}", Toast.LENGTH_LONG).show()
            return@registerForActivityResult
        }
        VoiceForegroundService.start(this)
    }

    private val configEditorLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult(),
    ) { result ->
        if (result.resultCode == RESULT_OK) {
            VoiceForegroundService.reloadConfig(this)
            refreshModelStatus()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.startServiceButton.setOnClickListener {
            requestRequiredPermissionsAndStart()
        }
        binding.stopServiceButton.setOnClickListener {
            VoiceForegroundService.stop(this)
        }
        binding.downloadModelButton.setOnClickListener {
            downloadModel()
        }
        binding.configButton.setOnClickListener {
            configEditorLauncher.launch(Intent(this, ConfigActivity::class.java))
        }
        binding.batteryButton.setOnClickListener {
            requestBatteryOptimizationExemption()
        }
        binding.holdToTalkButton.setOnTouchListener { _, event ->
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> VoiceForegroundService.manualPress(this)
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> VoiceForegroundService.manualRelease(this)
            }
            true
        }

        lifecycleScope.launch {
            repeatOnLifecycle(androidx.lifecycle.Lifecycle.State.STARTED) {
                VoiceRuntimeStore.state.collect { snapshot ->
                    binding.serviceStatusText.text =
                        "Service: ${if (snapshot.serviceRunning) "running" else "stopped"}"
                    binding.listeningModeText.text = "Listening mode: ${snapshot.listeningMode}"
                    binding.lastTranscriptText.text = "Last transcript: ${snapshot.lastTranscript.ifBlank { "none" }}"
                    binding.lastActionText.text = "Last action: ${snapshot.lastAction.ifBlank { "none" }}"
                    binding.errorText.text = snapshot.errorMessage.orEmpty()
                    binding.errorText.visibility =
                        if (snapshot.errorMessage.isNullOrBlank()) android.view.View.GONE else android.view.View.VISIBLE
                    binding.holdToTalkButton.isEnabled = snapshot.serviceRunning
                }
            }
        }

        refreshModelStatus()
    }

    private fun requestRequiredPermissionsAndStart() {
        val permissions = mutableListOf(Manifest.permission.RECORD_AUDIO)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions += Manifest.permission.POST_NOTIFICATIONS
        }
        permissionLauncher.launch(permissions.toTypedArray())
    }

    private fun downloadModel() {
        lifecycleScope.launch {
            binding.downloadModelButton.isEnabled = false
            try {
                val config = appContainer.configRepository.loadConfig()
                appContainer.modelRepository.ensureModelDownloaded(config.recognition) { bytesRead, totalBytes ->
                    runOnUiThread {
                        binding.modelStatusText.text = if (totalBytes != null) {
                            "Model: downloading ${(bytesRead * 100 / totalBytes).coerceIn(0, 100)}%"
                        } else {
                            "Model: downloading ${bytesRead / 1024} KB"
                        }
                    }
                }
                refreshModelStatus()
                VoiceRuntimeStore.update { it.copy(modelInstalled = true, errorMessage = null) }
                Toast.makeText(this@MainActivity, "Offline model installed.", Toast.LENGTH_SHORT).show()
            } catch (error: Throwable) {
                binding.modelStatusText.text = "Model: download failed"
                binding.errorText.text = error.message
                binding.errorText.visibility = android.view.View.VISIBLE
            } finally {
                binding.downloadModelButton.isEnabled = true
            }
        }
    }

    private fun refreshModelStatus() {
        runCatching {
            val config = appContainer.configRepository.loadConfig()
            val installed = appContainer.modelRepository.isModelInstalled(config.recognition)
            binding.modelStatusText.text = if (installed) "Model: installed" else "Model: missing"
            if (installed) {
                binding.errorText.visibility = android.view.View.GONE
                VoiceRuntimeStore.update { it.copy(modelInstalled = true) }
            } else {
                VoiceRuntimeStore.update { it.copy(modelInstalled = false) }
            }
        }.onFailure { error ->
            binding.modelStatusText.text = "Model: config error"
            binding.errorText.text = error.message
            binding.errorText.visibility = android.view.View.VISIBLE
        }
    }

    private fun requestBatteryOptimizationExemption() {
        val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
        if (powerManager.isIgnoringBatteryOptimizations(packageName)) {
            Toast.makeText(this, "Battery optimization already disabled for this app.", Toast.LENGTH_SHORT).show()
            return
        }
        startActivity(
            Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                data = Uri.parse("package:$packageName")
            },
        )
    }
}
