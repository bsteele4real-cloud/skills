---
name: api
description: Core ElevenLabs API setup and usage. Use for client initialization, authentication, error handling, rate limits, and general API patterns across all ElevenLabs services.
license: MIT
compatibility: Requires internet access and an ElevenLabs API key (ELEVENLABS_API_KEY).
metadata: {"openclaw": {"requires": {"env": ["ELEVENLABS_API_KEY"]}, "primaryEnv": "ELEVENLABS_API_KEY"}}
---

# ElevenLabs API

Core API client setup, authentication, and common patterns for all ElevenLabs services.

> **Need an API key?** Use the `setup-api-key` skill for guided setup.

## Quick Start

### Python

```python
from elevenlabs import ElevenLabs

# Uses ELEVENLABS_API_KEY environment variable
client = ElevenLabs()

# Or pass directly
client = ElevenLabs(api_key="your-api-key")
```

### JavaScript

```javascript
import { ElevenLabsClient } from "@elevenlabs/elevenlabs-js";

// Uses ELEVENLABS_API_KEY environment variable
const client = new ElevenLabsClient();

// Or pass directly
const client = new ElevenLabsClient({ apiKey: "your-api-key" });
```

> **Important:** Use `@elevenlabs/elevenlabs-js`. The old `elevenlabs` npm package is deprecated.

### cURL

```bash
curl -X GET "https://api.elevenlabs.io/v1/user" \
  -H "xi-api-key: $ELEVENLABS_API_KEY"
```

## Installation

### Python

```bash
pip install elevenlabs
```

### JavaScript / TypeScript

```bash
npm install @elevenlabs/elevenlabs-js
```

## API Endpoints

Base URL: `https://api.elevenlabs.io/v1`

| Service | Endpoint | Description |
|---------|----------|-------------|
| Text-to-Speech | `/text-to-speech/{voice_id}` | Convert text to audio |
| Speech-to-Text | `/speech-to-text` | Transcribe audio to text |
| Voices | `/voices` | List and manage voices |
| Voice Design | `/voice-generation/generate-voice` | Create voices from prompts |
| Sound Effects | `/sound-generation` | Generate sound effects |
| Audio Isolation | `/audio-isolation` | Remove background noise |
| Agents | `/convai/agents` | Conversational AI agents |
| User | `/user` | Account info and usage |

See [API Reference](references/endpoints.md) for complete endpoint documentation.

## Authentication

All requests require the `xi-api-key` header:

```bash
curl -H "xi-api-key: $ELEVENLABS_API_KEY" https://api.elevenlabs.io/v1/user
```

SDKs handle this automatically when configured:

```python
# Python - reads from ELEVENLABS_API_KEY env var
client = ElevenLabs()

# JavaScript - reads from ELEVENLABS_API_KEY env var
const client = new ElevenLabsClient();
```

## Error Handling

### Python

```python
from elevenlabs import ElevenLabs
from elevenlabs.core import ApiError

client = ElevenLabs()

try:
    audio = client.text_to_speech.convert(
        text="Hello",
        voice_id="invalid-id"
    )
except ApiError as e:
    print(f"Status: {e.status_code}")
    print(f"Error: {e.body}")
```

### JavaScript

```javascript
import { ElevenLabsClient } from "@elevenlabs/elevenlabs-js";

const client = new ElevenLabsClient();

try {
  const audio = await client.textToSpeech.convert("invalid-id", {
    text: "Hello",
  });
} catch (error) {
  console.error("Status:", error.statusCode);
  console.error("Error:", error.body);
}
```

### Common Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| 400 | Bad request | Check request body and parameters |
| 401 | Unauthorized | Invalid or missing API key |
| 403 | Forbidden | Insufficient permissions or subscription tier |
| 404 | Not found | Resource doesn't exist (voice_id, agent_id, etc.) |
| 422 | Validation error | Invalid parameters (check voice_id, model_id) |
| 429 | Rate limited | Too many requests, implement backoff |
| 500 | Server error | Retry with exponential backoff |

## Rate Limits

Rate limits depend on your subscription tier. Monitor via response headers:

| Header | Description |
|--------|-------------|
| `x-ratelimit-limit` | Max requests per time window |
| `x-ratelimit-remaining` | Remaining requests in window |
| `x-ratelimit-reset` | Unix timestamp when window resets |

### Handling Rate Limits

```python
import time
from elevenlabs import ElevenLabs
from elevenlabs.core import ApiError

client = ElevenLabs()

def call_with_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except ApiError as e:
            if e.status_code == 429 and attempt < max_retries - 1:
                wait = 2 ** attempt
                time.sleep(wait)
            else:
                raise
```

## Usage Tracking

Monitor character/credit usage via the `/user` endpoint:

```python
user = client.user.get()
subscription = user.subscription

print(f"Characters used: {subscription.character_count}")
print(f"Character limit: {subscription.character_limit}")
print(f"Tier: {subscription.tier}")
```

For per-request tracking, access response headers:

```python
response = client.text_to_speech.convert.with_raw_response(
    text="Hello!",
    voice_id="JBFqnCBsd6RMkjVDRZzb",
    model_id="eleven_multilingual_v2"
)
audio = response.parse()
print(f"Characters: {response.headers.get('x-character-count')}")
print(f"Request ID: {response.headers.get('request-id')}")
```

## Async Support

### Python

```python
import asyncio
from elevenlabs import AsyncElevenLabs

async def main():
    client = AsyncElevenLabs()
    audio = await client.text_to_speech.convert(
        text="Hello!",
        voice_id="JBFqnCBsd6RMkjVDRZzb"
    )

asyncio.run(main())
```

### JavaScript

```javascript
import { ElevenLabsClient } from "@elevenlabs/elevenlabs-js";

const client = new ElevenLabsClient();

// All methods are async by default
const audio = await client.textToSpeech.convert("JBFqnCBsd6RMkjVDRZzb", {
  text: "Hello!",
});
```

## Timeouts and Retries

### Python

```python
from elevenlabs import ElevenLabs

client = ElevenLabs(
    timeout=30.0,  # Request timeout in seconds
    max_retries=3  # Auto-retry on transient errors
)
```

### JavaScript

```javascript
import { ElevenLabsClient } from "@elevenlabs/elevenlabs-js";

const client = new ElevenLabsClient({
  timeout: 30000, // Timeout in milliseconds
  maxRetries: 3,
});
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ELEVENLABS_API_KEY` | Your ElevenLabs API key | Yes |
| `ELEVENLABS_BASE_URL` | Custom API base URL | No |

## References

- [API Endpoints](references/endpoints.md) - Complete endpoint reference
- [Error Codes](references/errors.md) - Detailed error documentation
- [Pagination](references/pagination.md) - Handling paginated responses
