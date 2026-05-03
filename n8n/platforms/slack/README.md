# Slack Integration Setup

## Prerequisites

1. A Slack workspace with admin access
2. n8n instance running and accessible
3. RAGM backend running with the generic integration endpoint

## Slack App Configuration

### 1. Create Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App**
2. Choose **From scratch**, name it (e.g., "RAGM Quotation Bot")
3. Select your workspace

### 2. Bot Token Scopes

Under **OAuth & Permissions**, add these Bot Token Scopes:
- `chat:write` — Send messages
- `files:write` — Upload quotation files
- `files:read` — Read uploaded files from users
- `im:history` — Read DM messages
- `im:write` — Open DMs

### 3. Event Subscriptions

Under **Event Subscriptions**:
- Enable events
- Set Request URL to your n8n webhook (e.g., `https://n8n.example.com/webhook/slack-quotation`)
- Subscribe to bot events: `message.im`

### 4. Install to Workspace

Install the app and copy the **Bot User OAuth Token** (`xoxb-...`).

## n8n Workflow Setup

1. Import `n8n/shared/core-quotation-subworkflow.json` as a sub-workflow
2. Create a Slack parent workflow that:
   - Receives Slack events via webhook
   - Collects BOQ + spec files from Slack messages
   - Downloads files using Slack API (`files.info` + private URL with token)
   - Calls the Core Sub-Workflow with:
     - `source_platform`: `"slack"`
     - `platform_reply_info`: `{"channel_id": "...", "user_id": "...", "bot_token": "xoxb-..."}`
3. Import `n8n/shared/callback-router.json` for delivery
4. Set `N8N_PIPELINE_CALLBACK_URL` in the backend to point to the callback router webhook

## platform_reply_info Format

```json
{
  "channel_id": "C01234ABCDE",
  "user_id": "U01234ABCDE",
  "bot_token": "xoxb-..."
}
```

The callback router uses `channel_id` to deliver the quotation DOCX back to the user.
