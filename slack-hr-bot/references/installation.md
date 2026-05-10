# Installation Guide

Complete setup instructions for the Slack HR Bot with ElevenLabs Agents.

## Prerequisites

- Node.js 18+ or Python 3.9+
- ElevenLabs API key with Conversational AI access
- Slack workspace with admin permissions to install apps

## Step 1: Create Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App** > **From scratch**
3. Name your app (e.g., "HR Assistant") and select your workspace

### Configure OAuth Scopes

Navigate to **OAuth & Permissions** and add these Bot Token Scopes:

| Scope | Purpose |
|-------|---------|
| `app_mentions:read` | Respond when mentioned |
| `chat:write` | Send messages |
| `commands` | Handle slash commands |
| `im:history` | Read DM history |
| `im:read` | Access DM channels |
| `im:write` | Send DMs |
| `users:read` | Get user information |
| `users:read.email` | Get user emails (for HR lookup) |

### Enable Socket Mode

1. Go to **Socket Mode** and enable it
2. Generate an App-Level Token with `connections:write` scope
3. Save the token as `SLACK_APP_TOKEN`

### Enable Events

Navigate to **Event Subscriptions** and subscribe to:

- `message.im` - Direct messages to bot
- `app_mention` - When bot is mentioned
- `app_home_opened` - App home tab opened

### Create Slash Commands

Go to **Slash Commands** and create:

| Command | Description |
|---------|-------------|
| `/hr` | Ask the HR assistant a question |
| `/pto` | Check PTO balance or request time off |
| `/benefits` | View your benefits information |
| `/policy` | Search company policies |

## Step 2: Install Dependencies

### JavaScript

```bash
mkdir hr-bot && cd hr-bot
npm init -y
npm install @slack/bolt @elevenlabs/elevenlabs-js dotenv express
```

### Python

```bash
mkdir hr-bot && cd hr-bot
python -m venv venv
source venv/bin/activate
pip install slack-bolt elevenlabs python-dotenv flask
```

## Step 3: Configure Environment

Create `.env` file:

```bash
# ElevenLabs
ELEVENLABS_API_KEY=your-elevenlabs-api-key
HR_AGENT_ID=your-agent-id

# Slack
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_APP_TOKEN=xapp-your-app-token

# HR System (your backend)
HR_API_URL=https://your-hr-system.com
HR_API_KEY=your-hr-api-key

# Optional
LOG_LEVEL=info
NODE_ENV=production
```

## Step 4: Create the HR Agent

### Using Python SDK

```python
from elevenlabs import ElevenLabs
import os
from dotenv import load_dotenv

load_dotenv()
client = ElevenLabs()

# Read prompt from file for easier maintenance
with open("prompts/hr_system_prompt.txt", "r") as f:
    system_prompt = f.read()

agent = client.conversational_ai.agents.create(
    name="HR Assistant - Slack",
    tags=["production", "slack", "hr"],
    conversation_config={
        "agent": {
            "first_message": "Hi! I'm your HR assistant. How can I help you today?",
            "language": "en",
            "prompt": {
                "prompt": system_prompt,
                "llm": "claude-sonnet-4-5",
                "temperature": 0.7,
                "tools": [...],  # See SKILL.md for full tools config
            }
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
        }
    }
)

print(f"HR_AGENT_ID={agent.agent_id}")
```

### Using CLI

```bash
# Initialize project
elevenlabs agents init

# Create from template
elevenlabs agents add "HR Assistant" --template customer-service

# Edit the generated config in agents.json, then push
elevenlabs agents push
```

## Step 5: Implement Webhooks

Create webhook endpoints for HR system integration:

```javascript
// src/webhooks.js
const express = require("express");
const router = express.Router();

// PTO Balance Check
router.post("/api/pto/balance", async (req, res) => {
  const { employee_id } = req.body.parameters;
  
  // Integrate with your HR system
  const balance = await hrSystem.getPtoBalance(employee_id);
  
  res.json({
    result: {
      vacation_days: balance.vacation,
      sick_days: balance.sick,
      personal_days: balance.personal,
      message: `You have ${balance.vacation} vacation days, ${balance.sick} sick days, and ${balance.personal} personal days remaining.`
    }
  });
});

// PTO Request Submission
router.post("/api/pto/request", async (req, res) => {
  const { employee_id, start_date, end_date, reason } = req.body.parameters;
  
  const request = await hrSystem.submitPtoRequest({
    employeeId: employee_id,
    startDate: start_date,
    endDate: end_date,
    reason: reason || "Time off request"
  });
  
  res.json({
    result: {
      request_id: request.id,
      status: request.status,
      message: `Your PTO request (${request.id}) from ${start_date} to ${end_date} has been submitted and is pending approval.`
    }
  });
});

// Policy Lookup
router.post("/api/policies/search", async (req, res) => {
  const { query } = req.body.parameters;
  
  const policies = await hrSystem.searchPolicies(query);
  
  res.json({
    result: {
      policies: policies.map(p => ({
        title: p.title,
        summary: p.summary,
        link: p.documentUrl
      })),
      message: policies.length > 0 
        ? `I found ${policies.length} relevant policies.`
        : "I couldn't find any policies matching your query."
    }
  });
});

module.exports = router;
```

## Step 6: Run the Bot

### Development

```bash
# JavaScript
node src/index.js

# Python
python src/main.py
```

### Production

```bash
# Using PM2
pm2 start src/index.js --name hr-bot

# Using systemd
sudo systemctl enable hr-bot
sudo systemctl start hr-bot
```

## Verification

1. **Test DM**: Send a direct message to your bot
2. **Test slash command**: Type `/hr What's the PTO policy?`
3. **Check logs**: Verify no errors in your application logs
4. **Monitor conversations**: Use ElevenLabs dashboard to review conversations

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Bot not responding | Check `SLACK_BOT_TOKEN` and Socket Mode connection |
| API errors | Verify `ELEVENLABS_API_KEY` has Conversational AI access |
| Webhook timeouts | Ensure webhook endpoints return within 20 seconds |
| Missing permissions | Re-install Slack app to workspace |

## Next Steps

- [Configure agent behavior](agent-configuration.md)
- [Set up HR system webhooks](webhooks.md)
- [Review security practices](security.md)
