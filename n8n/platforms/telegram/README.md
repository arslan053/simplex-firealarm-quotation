# Telegram Quotation Mini App

Layer 1 platform workflow for Telegram.

## Flow

1. User opens `@GenerateQuotationBot` or sends `/start`.
2. n8n receives the Telegram webhook at `/webhook/telegram-quotation-bot`.
3. Bot replies with a `Create Quotation` button.
4. Button opens the Telegram Mini App at `/webhook/telegram-mini-app`.
5. Mini App collects client, project, quotation details, BOQ, and Specs PDF.
6. Submit posts to `/webhook/telegram-mini-app-submit`.
7. The workflow uploads files and metadata to the existing RAGM generic quotation endpoint.
8. Existing pipeline callback router delivers the DOCX back via Telegram `sendDocument`.

## Environment Variables

The workflow reads these values from n8n container environment when present:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_MINI_APP_URL`
- `TELEGRAM_SUBMIT_URL`
- `RAGM_BACKEND_API_URL`
- `RAGM_TENANT_SLUG`
- `RAGM_LOGIN_EMAIL`
- `RAGM_LOGIN_PASSWORD`
- `N8N_PIPELINE_CALLBACK_URL`

Current defaults are set for the local deployment so the module can run immediately.

## Telegram Webhook

Set the Bot API webhook to:

```bash
https://n8n.amprosystem.com/webhook/telegram-quotation-bot
```

## Public URLs

- Mini App: `https://n8n.amprosystem.com/webhook/telegram-mini-app`
- Submit: `https://n8n.amprosystem.com/webhook/telegram-mini-app-submit`

## Notes

- The Mini App is served by n8n so no backend API changes are needed.
- The workflow uses native Node.js HTTP/HTTPS for binary multipart upload to avoid n8n Task Runner binary HTTP issues.
- Final delivery is handled by the shared callback router Telegram branch.
