package com.sachinmeier.jdivoiceandroid.ui

import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.sachinmeier.jdivoiceandroid.JdiVoiceApplication
import com.sachinmeier.jdivoiceandroid.databinding.ActivityConfigBinding

class ConfigActivity : AppCompatActivity() {
    private lateinit var binding: ActivityConfigBinding
    private val configRepository by lazy {
        (application as JdiVoiceApplication).appContainer.configRepository
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityConfigBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.configEditText.setText(configRepository.loadConfigText())
        binding.saveConfigButton.setOnClickListener {
            runCatching {
                configRepository.saveConfigText(binding.configEditText.text.toString())
            }.onSuccess {
                setResult(RESULT_OK)
                Toast.makeText(this, "Config saved.", Toast.LENGTH_SHORT).show()
                finish()
            }.onFailure { error ->
                Toast.makeText(this, error.message ?: "Unable to save config.", Toast.LENGTH_LONG).show()
            }
        }
        binding.resetConfigButton.setOnClickListener {
            runCatching {
                configRepository.restoreDefaultConfig()
                binding.configEditText.setText(configRepository.loadConfigText())
            }.onSuccess {
                Toast.makeText(this, "Default config restored.", Toast.LENGTH_SHORT).show()
            }.onFailure { error ->
                Toast.makeText(this, error.message ?: "Unable to restore default config.", Toast.LENGTH_LONG).show()
            }
        }
    }
}
