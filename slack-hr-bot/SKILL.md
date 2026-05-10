---
name: slack-hr-bot
description: Build and deploy an HR assistant bot for Slack using ElevenLabs Conversational AI. Handles PTO requests, policy questions, benefits inquiries, and employee support.
license: MIT
compatibility: Requires ELEVENLABS_API_KEY, SLACK_BOT_TOKEN, and SLACK_SIGNING_SECRET.
metadata: {"openclaw": {"requires": {"env": ["ELEVENLABS_API_KEY", "SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET"]}, "primaryEnv": "ELEVENLABS_API_KEY"}}
---

# Slack HR Bot with ElevenLabs Agents

Build an intelligent HR assistant that integrates ElevenLabs Conversational AI with Slack for employee support.

> **Setup:** See [Installation Guide](references/installation.md) for complete setup instructions.

## Quick Start

### 1. Install Dependencies

```bash
npm install @slack/bolt @elevenlabs/elevenlabs-js dotenv express
```

### 2. Set Environment Variables

```bash
export ELEVENLABS_API_KEY="your-elevenlabs-key"
export SLACK_BOT_TOKEN="xoxb-your-bot-token"
export SLACK_SIGNING_SECRET="your-signing-secret"
export SLACK_APP_TOKEN="xapp-your-app-token"  # For Socket Mode
```

### 3. Create the HR Agent

```python
from elevenlabs import ElevenLabs

client = ElevenLabs()

hr_agent = client.conversational_ai.agents.create(
    name="HR Assistant",
    conversation_config={
        "agent": {
            "first_message": "Hi! I'm your HR assistant. I can help with PTO requests, benefits questions, company policies, and more. How can I help you today?",
            "language": "en",
            "prompt": {
                "prompt": """You are a friendly and professional HR assistant for the company.

Your responsibilities:
- Answer questions about company policies (PTO, remote work, dress code, etc.)
- Help employees submit and check PTO requests
- Provide information about benefits (health insurance, 401k, etc.)
- Guide employees through common HR processes
- Escalate complex issues to the HR team

Guidelines:
- Be empathetic and supportive
- Protect employee privacy - never share personal information
- For sensitive matters (harassment, discrimination), always escalate to HR
- Be clear about what you can and cannot do
- Use professional but friendly language""",
                "llm": "claude-sonnet-4-5",
                "temperature": 0.7,
                "tools": [
                    {
                        "type": "webhook",
                        "name": "check_pto_balance",
                        "description": "Check employee's PTO balance. Use when employee asks about remaining vacation days.",
                        "api_schema": {
                            "url": "{{HR_API_URL}}/api/pto/balance",
                            "method": "POST",
                            "request_body_schema": {
                                "type": "object",
                                "properties": {
                                    "employee_id": {"type": "string", "description": "Employee ID"}
                                },
                                "required": ["employee_id"]
                            }
                        }
                    },
                    {
                        "type": "webhook",
                        "name": "submit_pto_request",
                        "description": "Submit a PTO request. Use when employee wants to request time off.",
                        "api_schema": {
                            "url": "{{HR_API_URL}}/api/pto/request",
                            "method": "POST",
                            "request_body_schema": {
                                "type": "object",
                                "properties": {
                                    "employee_id": {"type": "string"},
                                    "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                                    "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                                    "reason": {"type": "string", "description": "Reason for PTO"}
                                },
                                "required": ["employee_id", "start_date", "end_date"]
                            }
                        }
                    },
                    {
                        "type": "webhook",
                        "name": "lookup_policy",
                        "description": "Look up company policy information. Use when employee asks about policies.",
                        "api_schema": {
                            "url": "{{HR_API_URL}}/api/policies/search",
                            "method": "POST",
                            "request_body_schema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "Policy topic to search for"}
                                },
                                "required": ["query"]
                            }
                        }
                    },
                    {
                        "type": "webhook",
                        "name": "get_benefits_info",
                        "description": "Get employee benefits information. Use when employee asks about benefits.",
                        "api_schema": {
                            "url": "{{HR_API_URL}}/api/benefits",
                            "method": "POST",
                            "request_body_schema": {
                                "type": "object",
                                "properties": {
                                    "employee_id": {"type": "string"},
                                    "benefit_type": {"type": "string", "enum": ["health", "dental", "vision", "401k", "life", "all"]}
                                },
                                "required": ["employee_id"]
                            }
                        }
                    },
                    {
                        "type": "webhook",
                        "name": "escalate_to_hr",
                        "description": "Escalate issue to HR team. Use for sensitive or complex matters.",
                        "api_schema": {
                            "url": "{{HR_API_URL}}/api/escalate",
                            "method": "POST",
                            "request_body_schema": {
                                "type": "object",
                                "properties": {
                                    "employee_id": {"type": "string"},
                                    "issue_type": {"type": "string", "enum": ["general", "sensitive", "urgent", "benefits", "payroll"]},
                                    "summary": {"type": "string", "description": "Brief summary of the issue"}
                                },
                                "required": ["employee_id", "issue_type", "summary"]
                            }
                        }
                    }
                ]
            }
        },
        "tts": {
            "voice_id": "EXAVITQu4vr4xnSDxMaL",
            "model_id": "eleven_flash_v2_5"
        },
        "conversation": {
            "text_only": True,
            "max_duration_seconds": 1800
        }
    },
    platform_settings={
        "guardrails": {
            "version": "1",
            "focus": {"is_enabled": True},
            "prompt_injection": {"is_enabled": True}
        },
        "privacy": {
            "conversation_history_redaction": {
                "enabled": True,
                "entities": ["email_address", "contact_number", "dob"]
            }
        }
    }
)

print(f"Created HR Agent: {hr_agent.agent_id}")
```

## Slack Integration

### Basic Slack Bot (JavaScript)

```javascript
const { App } = require("@slack/bolt");
const { ElevenLabsClient } = require("@elevenlabs/elevenlabs-js");

const app = new App({
  token: process.env.SLACK_BOT_TOKEN,
  signingSecret: process.env.SLACK_SIGNING_SECRET,
  socketMode: true,
  appToken: process.env.SLACK_APP_TOKEN,
});

const elevenlabs = new ElevenLabsClient();

// Store conversation sessions per user
const sessions = new Map();

// Handle direct messages to the bot
app.message(async ({ message, say }) => {
  if (message.channel_type !== "im") return;

  const userId = message.user;
  let session = sessions.get(userId);

  // Start new conversation if none exists
  if (!session) {
    session = await elevenlabs.conversationalAi.conversations.create({
      agentId: process.env.HR_AGENT_ID,
    });
    sessions.set(userId, session);
  }

  // Send message to agent and get response
  const response = await elevenlabs.conversationalAi.conversations.sendMessage({
    conversationId: session.conversationId,
    message: message.text,
  });

  await say(response.agentMessage);
});

// Handle /hr slash command
app.command("/hr", async ({ command, ack, respond }) => {
  await ack();

  const response = await elevenlabs.conversationalAi.conversations.create({
    agentId: process.env.HR_AGENT_ID,
    initialMessage: command.text,
  });

  await respond({
    text: response.agentMessage,
    response_type: "ephemeral",
  });
});

(async () => {
  await app.start();
  console.log("HR Bot is running!");
})();
```

### Interactive Components

```javascript
// Handle PTO request button clicks
app.action("submit_pto", async ({ body, ack, client }) => {
  await ack();

  await client.views.open({
    trigger_id: body.trigger_id,
    view: {
      type: "modal",
      callback_id: "pto_modal",
      title: { type: "plain_text", text: "Request Time Off" },
      blocks: [
        {
          type: "input",
          block_id: "start_date",
          element: {
            type: "datepicker",
            action_id: "start_date_input",
          },
          label: { type: "plain_text", text: "Start Date" },
        },
        {
          type: "input",
          block_id: "end_date",
          element: {
            type: "datepicker",
            action_id: "end_date_input",
          },
          label: { type: "plain_text", text: "End Date" },
        },
        {
          type: "input",
          block_id: "reason",
          element: {
            type: "plain_text_input",
            action_id: "reason_input",
            multiline: true,
          },
          label: { type: "plain_text", text: "Reason (optional)" },
          optional: true,
        },
      ],
      submit: { type: "plain_text", text: "Submit" },
    },
  });
});
```

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│   Slack     │────▶│   Slack Bot  │────▶│  ElevenLabs      │
│   Users     │◀────│   (Node.js)  │◀────│  HR Agent        │
└─────────────┘     └──────────────┘     └──────────────────┘
                           │                      │
                           ▼                      ▼
                    ┌──────────────┐     ┌──────────────────┐
                    │  HR System   │     │  Knowledge Base  │
                    │  Webhooks    │     │  (Policies/FAQ)  │
                    └──────────────┘     └──────────────────┘
```

## Features

| Feature | Description |
|---------|-------------|
| PTO Management | Check balance, submit requests, view history |
| Policy Lookup | Search company policies and procedures |
| Benefits Info | Health, dental, 401k, and other benefits |
| HR Escalation | Route complex issues to HR team |
| Privacy | Automatic PII redaction in logs |

## Configuration Options

See [Agent Configuration](references/agent-configuration.md) for all options.

### Key Settings

| Setting | Recommended | Description |
|---------|-------------|-------------|
| `llm` | `claude-sonnet-4-5` | Best for nuanced HR conversations |
| `temperature` | `0.7` | Balanced between helpful and consistent |
| `text_only` | `true` | Slack integration doesn't need voice |
| `guardrails.focus` | `enabled` | Keep agent on HR topics |

## Deployment

### Using PM2

```bash
npm install -g pm2
pm2 start src/index.js --name hr-bot
pm2 save
```

### Using Docker

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
CMD ["node", "src/index.js"]
```

```bash
docker build -t hr-bot .
docker run -d --env-file .env hr-bot
```

## References

- [Installation Guide](references/installation.md) - Complete setup instructions
- [Agent Configuration](references/agent-configuration.md) - All configuration options
- [Webhook Reference](references/webhooks.md) - HR system webhook implementation
- [Security & Privacy](references/security.md) - Security best practices
