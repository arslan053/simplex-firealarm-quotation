# Email Integration Setup

Layer 1 email workflow for RAGM quotation intake.

## Flow

1. Gmail IMAP receives a new email.
2. If the normalized subject is exactly `quotation`, n8n replies with the form link.
3. The user completes the n8n form and uploads BOQ + specification files in the form.
4. The workflow maps the form data to the shared Core Sub-Workflow input and starts the quotation pipeline.
5. The shared callback router routes `source_platform: "email"` and sends the generated DOCX back as an email attachment.

## Gmail Credentials Needed

Create these n8n credentials:

### Gmail IMAP

- Credential type: IMAP
- Host: `imap.gmail.com`
- Port: `993`
- SSL/TLS: enabled
- User: full Gmail address
- Password: Gmail App Password

### Gmail SMTP

- Credential type: SMTP
- Host: `smtp.gmail.com`
- Port: `465`
- SSL/TLS: enabled
- User: full Gmail address
- Password: Gmail App Password

Gmail must have IMAP enabled. The Gmail account must use a Google App Password, not the normal account password.

## n8n Setup

1. Import `n8n/platforms/email/workflow.json`.
2. Assign the `Gmail IMAP` credential to the IMAP trigger.
3. Assign the `Gmail SMTP` credential to both send-email nodes.
4. In the workflow, replace visible placeholder From values:
   `RAGM Quotations <your-gmail-address@gmail.com>`
5. Confirm the public n8n URL in `Parse Quotation Email` is correct. Default is `https://n8n.amprosystem.com`.
6. Publish/activate the workflow.

## Form Fields

The form collects the same structured fields as Slack:

- Client: client name, company name, email, phone, address
- Project: project name, city, country, due date
- Quotation config: service option, margin percent, payment terms, subject
- Files: BOQ file and Specification PDF

Files must be uploaded in the form. Email attachments are intentionally ignored.

## platform_reply_info

The email workflow passes:

```json
{
  "email": "sender@example.com",
  "from_name": "Client Name",
  "smtp_from": "RAGM Quotations <your-gmail-address@gmail.com>"
}
```

The callback router uses `email` to send the result back.
