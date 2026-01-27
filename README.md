![LOGO](/logo.png)

# ElevenLabs Skills

Agent skills for [ElevenLabs](https://elevenlabs.io) developer products. These skills follow the [Agent Skills specification](https://agentskills.io/specification) and can be used with any compatible AI coding assistant.

## Installation

```bash
npx skills add elevenlabs/skills
```

### Using with specific agents

**Claude Code:**
```bash
# Clone and reference the skills directory
git clone https://github.com/elevenlabs/skills.git
claude --plugin-dir ./skills
```

**Cursor:**
```bash
# Clone and copy skills to Cursor's skills directory
git clone https://github.com/elevenlabs/skills.git
cp -r skills/* ~/.cursor/skills/
```

**Other agents:**

These skills follow the [Agent Skills specification](https://agentskills.io/specification). Clone this repository and copy the skill directories to your agent's skills folder.

## Available Skills

| Skill | Description |
|-------|-------------|
| [text-to-speech](./text-to-speech) | Convert text to lifelike speech using ElevenLabs' AI voices |
| [speech-to-text](./speech-to-text) | Transcribe audio files to text with timestamps |
| [setup-api-key](./setup-api-key) | Guide through obtaining and configuring an ElevenLabs API key |

## Configuration

All skills require an ElevenLabs API key. Set it as an environment variable:

```bash
export ELEVENLABS_API_KEY="your-api-key"
```

Get your API key from the `setup-api-key` skill or use the [ElevenLabs dashboard](https://elevenlabs.io/app/developers/api-keys).

## SDK Support

Most skills include examples for:

- **Python** - `elevenlabs` package
- **JavaScript/TypeScript** - `@elevenlabs/elevenlabs-js`
- **cURL** - Direct REST API calls

## License

MIT
