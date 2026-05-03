# n8n WAHA WhatsApp Quotation Bot

This folder is the WAHA replacement for the failed Evolution API setup.

It keeps the same collection-only conversation logic from `n8n-evolution/whatsapp-quotation-workflow.json` but changes the WhatsApp gateway adapter to WAHA:

- Webhook path: `whatsapp-quotation-waha`
- WAHA API URL from n8n: `http://172.17.0.1:3002`
- WAHA session: `default`
- API header: `X-Api-Key`
- Send text endpoint: `POST /api/sendText`

Existing folders are untouched:

- `n8n/` remains the Meta Cloud API version.
- `n8n-evolution/` remains the Evolution API attempt.

## Run

```bash
docker compose -f n8n-waha/docker-compose.waha.yml up -d
```

Open `http://localhost:3002/dashboard`, login with:

- Username: `admin`
- Password: `RAGM-WAHA-Dashboard-2026`
- API key: `B6D711FCDE4D4FD5936544120E713976`

Start the `default` session, configure webhook events for `message`, and scan the QR.

Webhook URL for WAHA session:

```text
http://172.17.0.1:5678/webhook/whatsapp-quotation-waha
```

Import `n8n-waha/whatsapp-quotation-workflow.json` into n8n and activate it.
