# Error Codes

## HTTP Status Codes

### 400 Bad Request

Invalid request format or missing required fields.

```json
{
  "detail": {
    "status": "invalid_request",
    "message": "Missing required field: text"
  }
}
```

**Solution:** Check request body structure and required parameters.

### 401 Unauthorized

Invalid or missing API key.

```json
{
  "detail": {
    "status": "invalid_api_key",
    "message": "Invalid API key"
  }
}
```

**Solution:** Verify your `xi-api-key` header is set correctly.

### 403 Forbidden

Insufficient permissions or subscription tier.

```json
{
  "detail": {
    "status": "quota_exceeded",
    "message": "Character quota exceeded for current billing period"
  }
}
```

**Solution:** Upgrade subscription or wait for quota reset.

### 404 Not Found

Resource doesn't exist.

```json
{
  "detail": {
    "status": "voice_not_found",
    "message": "Voice not found"
  }
}
```

**Solution:** Check the resource ID (voice_id, agent_id, etc.).

### 422 Validation Error

Invalid parameters.

```json
{
  "detail": [
    {
      "loc": ["body", "model_id"],
      "msg": "Invalid model_id",
      "type": "value_error"
    }
  ]
}
```

**Solution:** Check parameter values against documentation.

### 429 Too Many Requests

Rate limit exceeded.

```json
{
  "detail": {
    "status": "rate_limit_exceeded",
    "message": "Rate limit exceeded. Please retry after 60 seconds."
  }
}
```

**Solution:** Implement exponential backoff and retry.

```python
import time
from elevenlabs.core import ApiError

def call_with_backoff(func, max_retries=5):
    for attempt in range(max_retries):
        try:
            return func()
        except ApiError as e:
            if e.status_code == 429:
                wait = min(2 ** attempt, 60)
                time.sleep(wait)
            else:
                raise
    raise Exception("Max retries exceeded")
```

### 500 Internal Server Error

Server-side error.

**Solution:** Retry with exponential backoff. If persistent, check [status.elevenlabs.io](https://status.elevenlabs.io).

## SDK Error Handling

### Python

```python
from elevenlabs import ElevenLabs
from elevenlabs.core import ApiError

client = ElevenLabs()

try:
    result = client.text_to_speech.convert(
        text="Hello",
        voice_id="JBFqnCBsd6RMkjVDRZzb"
    )
except ApiError as e:
    print(f"Status: {e.status_code}")
    print(f"Body: {e.body}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### JavaScript

```javascript
import { ElevenLabsClient } from "@elevenlabs/elevenlabs-js";

const client = new ElevenLabsClient();

try {
  const result = await client.textToSpeech.convert("JBFqnCBsd6RMkjVDRZzb", {
    text: "Hello",
  });
} catch (error) {
  if (error.statusCode) {
    console.error("API Error:", error.statusCode, error.body);
  } else {
    console.error("Unexpected error:", error);
  }
}
```
