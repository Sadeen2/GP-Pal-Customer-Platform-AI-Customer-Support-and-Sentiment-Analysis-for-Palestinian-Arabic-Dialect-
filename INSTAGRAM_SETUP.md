# Instagram Integration Notes

## New backend files
- `app/routes/instagram.py`
- `app/services/customer_identity_service.py`

## Updated backend files
- `app/main.py`: registers the Instagram router.
- `app/routes/predict.py`: manual agent replies now send back to Instagram when the conversation channel is `instagram`.
- `app/routes/whatsapp.py`: WhatsApp customer creation now uses the shared identity resolver.

## Environment variables
Add these to your `.env`:

```env
INSTAGRAM_VERIFY_TOKEN=pal_customer_verify
META_APP_SECRET=your_meta_app_secret
INSTAGRAM_ACCESS_TOKEN=your_page_or_ig_access_token
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_instagram_business_account_id
INSTAGRAM_GRAPH_VERSION=v21.0
INSTAGRAM_DEBUG_BODY=false
INSTAGRAM_VERBOSE_SEND=false
```

`INSTAGRAM_VERIFY_TOKEN` may be the same as `WHATSAPP_VERIFY_TOKEN`.

## Webhook endpoints
Use one of these callback URLs in Meta Developers:

```text
https://YOUR-DOMAIN/webhooks/instagram
https://YOUR-DOMAIN/api/instagram/webhook
```

The backend supports both GET verification and POST message receiving.

## Identity rule
The system always recognizes the same Instagram user by Instagram sender id.
For cross-channel matching, it links Instagram to an existing WhatsApp customer only when the customer sends a reliable identifier such as phone number or email. This avoids unsafe matching based only on name.
