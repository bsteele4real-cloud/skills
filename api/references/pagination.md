# Pagination

List endpoints that return multiple items support pagination.

## Cursor-Based Pagination

Most endpoints use cursor-based pagination for efficient traversal.

### Request Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `page_size` | integer | Items per page (default varies by endpoint) |
| `cursor` | string | Cursor from previous response |

### Response Structure

```json
{
  "items": [...],
  "has_more": true,
  "next_cursor": "abc123"
}
```

### Python Example

```python
from elevenlabs import ElevenLabs

client = ElevenLabs()

# Get all voices with pagination
all_voices = []
cursor = None

while True:
    response = client.voices.get_all(
        page_size=100,
        cursor=cursor
    )
    all_voices.extend(response.voices)
    
    if not response.has_more:
        break
    cursor = response.next_cursor

print(f"Total voices: {len(all_voices)}")
```

### JavaScript Example

```javascript
import { ElevenLabsClient } from "@elevenlabs/elevenlabs-js";

const client = new ElevenLabsClient();

async function getAllVoices() {
  const allVoices = [];
  let cursor = undefined;

  while (true) {
    const response = await client.voices.getAll({
      pageSize: 100,
      cursor: cursor,
    });

    allVoices.push(...response.voices);

    if (!response.hasMore) break;
    cursor = response.nextCursor;
  }

  return allVoices;
}
```

## Endpoints with Pagination

| Endpoint | Default Page Size |
|----------|-------------------|
| `/voices` | 30 |
| `/convai/agents` | 30 |
| `/convai/conversations` | 30 |
| `/history` | 100 |
