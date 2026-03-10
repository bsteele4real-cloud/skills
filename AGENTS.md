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

### Claude Code via Vertex AI

Claude Code CLI is installed and configured to use GCP Vertex AI (`xi-playground` project). The Vertex env vars are in `~/.bashrc`. GCP Application Default Credentials are at `~/.config/gcloud/application_default_credentials.json` (from interactive `gcloud auth application-default login`).

**Critical:** Claude Code CLI hangs in headless/non-TTY shells (Ink framework requires raw mode on stdin). A wrapper at `~/bin/claude` uses `unbuffer` to provide a PTY. Ensure `~/bin` is first in `PATH` (already configured in `~/.bashrc`).

### Regenerating examples after skill changes

When skills in this repo are updated, the `elevenlabs/examples` repo should be regenerated:

```bash
git clone https://github.com/elevenlabs/examples.git /tmp/elevenlabs-examples
cd /tmp/elevenlabs-examples
pnpm install
pnpm generate            # runs scripts/generate-examples.sh which uses Claude Code
```

The script pulls latest skills via `pnpm dlx skills add elevenlabs/skills`, then runs Claude Code against each `PROMPT.md` to generate/verify examples. If changes are produced, create a PR on the examples repo.

### Gotchas

- `python3.12-venv` apt package is needed to create the venv (not installed by default in the base image).
- The `transcribe.sh` wrapper handles venv setup automatically, but if you run `transcribe.py` directly you must activate the venv first.
- No linting, testing, or build commands exist in this repo. The skill definitions are pure Markdown.
- If GCP ADC credentials expire, re-authenticate via Desktop pane: `gcloud auth application-default login`.
