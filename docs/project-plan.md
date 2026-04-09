# Project Plan

## Goal

Build a Raspberry Pi service that listens for a small fixed set of voice commands and maps them to LIFX light actions with low enough latency and enough reliability to be useful in a home.

## Scope

Included:

- Offline speech-to-text with Vosk.
- Exact phrase matching against a YAML command list.
- Local LIFX LAN control for light power and locally defined scenes.
- Optional LIFX HTTP API support for cloud scenes and selector-based power commands.
- Optional openWakeWord-based wake word gating.
- Optional GPIO push-to-talk button.
- A deployment README and a systemd service template.

Excluded from the initial build:

- Full natural-language understanding.
- Multi-user speaker identification gating.
- Hand-rolled LIFX binary packet generation.
- Kaldi acoustic-model fine-tuning workflow automation.

## Implementation Phases

1. Hardware and OS baseline
   - Pi 4 or Pi 5.
   - Raspberry Pi OS Lite 64-bit.
   - USB microphone or USB webcam microphone.
2. Voice stack
   - `sounddevice` captures 16 kHz mono PCM.
   - `openWakeWord` optionally gates command capture.
   - `Vosk` runs with a restricted grammar built from the configured command phrases.
   - Recognized transcripts are normalized and exact-matched.
3. Lighting stack
   - `lifxlan` handles local LAN discovery and direct power/color writes.
   - The official LIFX HTTP API handles scene activation and optional selector-based commands.
4. Operations
   - YAML config validates before startup.
   - CLI commands support config validation, light discovery, manual dispatch, and wake word verifier training.
   - `systemd` keeps the service alive.

## Acceptance Criteria

- `jdi validate-config` succeeds with a filled-out home config.
- `jdi list-audio-devices` finds at least one microphone.
- `jdi list-lights --transport lan` discovers the user’s bulbs on the same network.
- `jdi dispatch "turn all lights off"` executes a real command without using the microphone.
- In always-listening or wake-word mode, only configured phrases trigger actions.

## Reliability Strategy

- Start with push-to-talk or always-listening command testing before enabling wake word mode.
- Keep commands short and distinct.
- Use Vosk grammar restriction rather than open transcription.
- Prefer a dedicated USB microphone or conference mic over a far-away webcam mic.
- Add a wake word verifier model only after the base path works.
