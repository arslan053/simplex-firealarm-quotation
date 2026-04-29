# Adding a New Messaging Platform Integration

## What Already Exists

The backend has a generic multipart endpoint that accepts file uploads from any platform:

**Endpoint:** `POST /api/integrations/generic/quotation/start`

It accepts:
- `boq_file` — BOQ document (xlsx/pdf) as file upload
- `spec_file` — Specification PDF as file upload
- `source_platform` — string identifier (e.g. "slack", "telegram")
- `platform_reply_info` — JSON string with platform-specific reply routing data (channel IDs, bot tokens, etc.)
- `client_data` — JSON string with client info (name, company_name, email, phone, address)
- `project_data` — JSON string (project_name, city, country, due_date)
- `quotation_config` — JSON string (service_option, margin_percent, payment_terms_text, subject)
- `boq_media_type` — "xlsx", "pdf", or "images"

**File:** `backend/app/modules/integrations/generic_router.py`

There is also a reusable n8n sub-workflow that handles login + upload:

**File:** `n8n/shared/core-quotation-subworkflow.json`

It takes: `tenant_slug`, `backend_url`, `credentials`, `source_platform`, `platform_reply_info`, `client_data`, `project_data`, `quotation_config`, `boq_media_type` + binary files (`boq_file`, `spec_file`).

And a callback router that delivers results back to the user on their platform:

**File:** `n8n/shared/callback-router.json`

It receives pipeline completion/failure callbacks from the backend, downloads the quotation DOCX, and routes delivery based on `source_platform`. It already has delivery branches for Slack and Telegram.

The callback payload from the backend looks like:
```json
{
  "status": "completed|failed",
  "source_platform": "slack",
  "platform_reply_info": { ... },
  "project_id": "...",
  "download_url": "...",
  "file_name": "quotation.docx"
}
```

## What You Need to Build

For the new platform, create an n8n workflow JSON file at `n8n/platforms/<platform-name>/workflow.json` that does:

1. **Receive messages** — Webhook trigger that receives incoming messages from the platform
2. **Conversation flow** — Collect from the user: BOQ file, spec file, and optionally client details, project details, quotation config (service option, margin, payment terms, subject)
3. **Download files** — Download the user's uploaded files from the platform's API into binary data
4. **Call the core sub-workflow** — Pass all collected data + binary files to `n8n/shared/core-quotation-subworkflow.json` via an Execute Workflow node
5. **Set `platform_reply_info`** — Include whatever the callback router needs to send the result back (channel IDs, chat IDs, bot tokens, etc.)

Also add a delivery branch in `n8n/shared/callback-router.json` if the platform is not already handled there.

## Reference

- See `n8n/README.md` for the full architecture diagram
- See `n8n/platforms/slack/README.md` and `n8n/platforms/telegram/README.md` for platform-specific setup examples
- The generic endpoint code is at `backend/app/modules/integrations/generic_router.py`
- The pipeline callback logic is at `backend/app/modules/pipeline/service.py` in `_notify_n8n_pipeline_callback`
