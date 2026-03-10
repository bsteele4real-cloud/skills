## Cursor Cloud specific instructions

### Overview

This is **ElevenLabs Skills** — a collection of Markdown-based AI coding assistant skill definitions following the [Agent Skills specification](https://agentskills.io/specification). There is no build system, CI/CD, linter, or automated test suite.

The only executable code is a Python speech-to-text transcription CLI at `openclaw/elevenlabs-transcribe/scripts/`.

### Services

| Component | Type | Notes |
|-----------|------|-------|
| Transcription script | Python CLI | Requires `ELEVENLABS_API_KEY`, `python3`, `ffmpeg` |
| ElevenLabs API | External SaaS | All functionality depends on a valid API key |

### Running the transcription script

The shell wrapper at `openclaw/elevenlabs-transcribe/scripts/transcribe.sh` auto-creates a `.venv` and installs pip dependencies on first run. You can also activate the venv manually:

```bash
source openclaw/elevenlabs-transcribe/scripts/.venv/bin/activate
python3 openclaw/elevenlabs-transcribe/scripts/transcribe.py <audio_file>
```

### Gotchas

- `python3.12-venv` apt package is needed to create the venv (not installed by default in the base image).
- The `transcribe.sh` wrapper handles venv setup automatically, but if you run `transcribe.py` directly you must activate the venv first.
- No linting, testing, or build commands exist in this repo. The skill definitions are pure Markdown.
