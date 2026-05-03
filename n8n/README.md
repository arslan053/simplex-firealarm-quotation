# n8n Integration Workflows

Multi-platform integration layer for the RAGM quotation pipeline.

## Architecture

```
                       ┌─────────────────┐
                       │  Messaging App   │
                       │ (Slack/Telegram) │
                       └────────┬────────┘
                                │
                    ┌───────────▼───────────┐
                    │  Platform Workflow     │  Layer 1: Platform-specific
                    │  (collects files,     │  message handling
                    │   extracts metadata)  │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │  Core Sub-Workflow     │  Layer 2: Reusable API
                    │  (login, upload,      │  orchestration
                    │   start pipeline)     │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │  RAGM Backend API     │
                    │  /api/integrations/   │
                    │  generic/quotation/   │
                    │  start                │
                    └───────────┬───────────┘
                                │ (pipeline callback)
                    ┌───────────▼───────────┐
                    │  Callback Router       │  Layer 3: Platform-agnostic
                    │  (routes delivery     │  callback dispatch
                    │   by source_platform) │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │  Platform Delivery    │
                    │  (Slack/Telegram API) │
                    └───────────────────────┘
```

## Directory Structure

```
n8n/
├── README.md                          # This file
├── shared/
│   ├── core-quotation-subworkflow.json  # Layer 2: reusable login + upload
│   └── callback-router.json             # Layer 3: platform-agnostic callback dispatch
├── platforms/
│   ├── slack/
│   │   └── README.md                    # Slack bot setup instructions
│   └── telegram/
│       └── README.md                    # Telegram bot setup (future)
└── archive/
    └── meta-cloud-api/                  # Original Meta Cloud API workflows
        ├── whatsapp-quotation-workflow.json
        └── whatsapp-flows/

n8n-waha/                              # WAHA WhatsApp gateway (standalone)
n8n-evolution/                         # Historical reference
```

## Key Concepts

### Generic Backend Endpoint

`POST /api/integrations/generic/quotation/start` (multipart form)

All new platforms use this endpoint. It accepts:
- `boq_file` — BOQ document (xlsx/pdf) as file upload
- `spec_file` — Specification PDF as file upload
- `source_platform` — Platform identifier (`slack`, `telegram`, etc.)
- `platform_reply_info` — JSON with platform-specific reply routing data
- `client_data`, `project_data`, `quotation_config` — JSON metadata

### Callback Payload

When the pipeline completes/fails, the backend sends a callback with:
```json
{
  "status": "completed|failed",
  "source_platform": "slack",
  "platform_reply_info": { "channel_id": "...", "bot_token": "..." },
  "project_id": "...",
  "download_url": "...",
  "file_name": "quotation.docx"
}
```

The callback router uses `source_platform` to route delivery.

### WAHA (WhatsApp) Isolation

The WAHA WhatsApp workflow in `n8n-waha/` remains standalone. It has its own dedicated callback webhook and does not use the generic endpoint or callback router.

## Adding a New Platform

1. Create a platform workflow in `n8n/platforms/<name>/`
2. The workflow should: receive messages, collect files, call the **Core Sub-Workflow**
3. Store `source_platform` and `platform_reply_info` (with routing data like channel IDs, bot tokens)
4. Add a delivery branch to the **Callback Router** for the new platform
5. Document setup in `n8n/platforms/<name>/README.md`
