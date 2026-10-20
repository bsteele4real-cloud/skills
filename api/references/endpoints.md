# API Endpoints

Base URL: `https://api.elevenlabs.io/v1`

## Text-to-Speech

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/text-to-speech/{voice_id}` | Convert text to speech |
| POST | `/text-to-speech/{voice_id}/stream` | Stream audio as generated |
| POST | `/text-to-speech/{voice_id}/with-timestamps` | Get audio with word timestamps |

## Speech-to-Text

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/speech-to-text` | Transcribe audio file |
| POST | `/speech-to-text/stream` | Stream transcription |

## Voices

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/voices` | List all voices |
| GET | `/voices/{voice_id}` | Get voice details |
| POST | `/voices/add` | Add voice from samples |
| DELETE | `/voices/{voice_id}` | Delete a voice |
| POST | `/voices/{voice_id}/edit` | Edit voice settings |
| GET | `/voices/settings/default` | Get default voice settings |

## Voice Design

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/voice-generation/generate-voice` | Generate voice from description |
| POST | `/voice-generation/generate-voice/preview` | Preview generated voice |

## Sound Effects

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/sound-generation` | Generate sound effect from prompt |

## Audio Isolation

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/audio-isolation` | Remove background noise/music |
| POST | `/audio-isolation/stream` | Stream isolated audio |

## Conversational AI (Agents)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/convai/agents/create` | Create an agent |
| GET | `/convai/agents` | List agents |
| GET | `/convai/agents/{agent_id}` | Get agent details |
| PATCH | `/convai/agents/{agent_id}` | Update agent |
| DELETE | `/convai/agents/{agent_id}` | Delete agent |
| GET | `/convai/conversations/get-signed-url` | Get signed URL for client |

## User & Account

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/user` | Get user info and usage |
| GET | `/user/subscription` | Get subscription details |

## Common Request Headers

| Header | Required | Description |
|--------|----------|-------------|
| `xi-api-key` | Yes | Your ElevenLabs API key |
| `Content-Type` | Yes (POST) | `application/json` or `multipart/form-data` |
| `Accept` | No | Response format (e.g., `audio/mpeg`) |

## Common Response Headers

| Header | Description |
|--------|-------------|
| `x-character-count` | Characters consumed by request |
| `x-ratelimit-limit` | Rate limit ceiling |
| `x-ratelimit-remaining` | Remaining requests in window |
| `x-ratelimit-reset` | Window reset timestamp |
| `request-id` | Unique request identifier |
