# Voice Tuning

## The Practical Truth

If your command set is small, the biggest gains will not come from full speech-model fine-tuning. They will come from:

- Better microphone placement.
- Short, distinct phrases.
- Vosk grammar restriction.
- Lower room noise.
- Push-to-talk or a tuned wake word threshold.

That is why this project starts there first.

## What You Can Tune

### 1. Vosk Runtime Vocabulary Restriction

This project already does it.

- Every configured command phrase becomes part of the Vosk grammar.
- Vosk then works as a constrained command recognizer instead of a general dictation engine.
- For a home-control use case, this is the most important accuracy lever.

### 2. Custom Wake Word Verifier for Your Voice

This is the easiest voice-specific training path in the repo.

openWakeWord supports custom verifier models that act as a second-stage speaker-specific filter. The project includes:

```bash
jdi train-wakeword-verifier \
  --model-name hey_jarvis.onnx \
  --positive data/wakeword/positive/*.wav \
  --negative data/wakeword/negative/*.wav \
  --output runtime/hey_jarvis_verifier.pkl
```

Recommended data:

- At least 3 positive clips of you saying the wake phrase.
- At least 10 seconds of negative clips with your voice but not the wake phrase.
- A little room noise in both sets, recorded where the Pi will actually live.

This improves wake word precision for your voice. It does not directly improve the transcription of the command after the wake word.

### 3. Deeper Vosk Adaptation

Vosk documents three heavier adaptation paths beyond runtime vocabulary restriction:

- Offline language-model updates from domain text.
- Dictionary/graph updates for some larger models.
- Acoustic-model fine-tuning with roughly an hour of labeled data.

That is real work. It means Kaldi tooling, transcription data, and an offline training workflow. For this project, I would only do it if:

- the restricted-grammar setup still misrecognizes you often,
- you have already improved the microphone,
- and you are willing to maintain a separate speech-model training pipeline.

## My Recommendation

1. Get the base system working with push-to-talk.
2. Add always-listening restricted-grammar recognition.
3. Add wake word mode.
4. Only then train a custom wake word verifier.
5. Treat Vosk acoustic fine-tuning as a later research project, not the first weekend task.
