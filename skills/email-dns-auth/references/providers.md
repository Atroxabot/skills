# Sending services: what setup involves

How common services authenticate mail sent as your domain, and what makes them align for DMARC. **Always take the exact record values from the service's own dashboard.** Selectors, CNAME targets and account IDs are often specific to the account, and providers change their formats. This page tells you what to look for and what "done" means. It doesn't replace the values.

For every service, "done" means a real message from it shows `dkim=pass` with `header.d=` your domain (or a subdomain of it), and `dmarc=pass`. Check with `scripts/parse_headers.py`.

## Mailbox providers

### Google Workspace
- **SPF**: `include:_spf.google.com` (one lookup).
- **DKIM**: generated in the Admin console (Apps → Google Workspace → Gmail → Authenticate email). Default selector `google`; choose 2048-bit. Publish the TXT record it shows, then click **Start authentication**. Until you do, Google signs with a default `d=*.gappssmtp.com` domain that doesn't align.
- **Alignment**: the envelope sender is your own domain, so SPF aligns; DKIM aligns once authentication is started.
- Sending through Workspace from another domain alias needs DKIM set up for that domain too.

### Microsoft 365
- **SPF**: `include:spf.protection.outlook.com`.
- **DKIM**: two CNAME records, `selector1._domainkey` and `selector2._domainkey`, pointing at targets in Microsoft's domain. Microsoft changed the target format in 2025, so copy the exact values from the Defender portal (Email & collaboration → Policies → Email authentication settings → DKIM), then enable signing there. Until you do, Microsoft signs with `d=<tenant>.onmicrosoft.com`, which doesn't align with your domain.
- **Alignment**: SPF aligns for mail sent from mailboxes; DKIM aligns once custom signing is enabled.

### Zoho Mail, Fastmail, Proton Mail
Each provides an SPF include and DKIM records (TXT or CNAME) in its domain setup page. Fastmail uses selectors `fm1`, `fm2`, `fm3`; Proton uses `protonmail`, `protonmail2`, `protonmail3`. Same rule: done when DKIM signs as your domain.

## Transactional services

### SendGrid (Twilio)
- **Setup**: Settings → Sender Authentication → Authenticate Your Domain. With "automated security" on (the default), it gives three CNAMEs: a return-path subdomain (`em1234.acme.io`) and two DKIM selectors (`s1._domainkey`, `s2._domainkey`).
- **Alignment**: both DKIM and SPF (through the `em` subdomain). With automated security you don't need `include:sendgrid.net` in your root SPF record; adding it only costs lookups.

### Amazon SES
- **DKIM**: Easy DKIM gives three CNAMEs, `<token>._domainkey` → `<token>.dkim.amazonses.com`.
- **Return path**: configure a custom MAIL FROM domain (a subdomain such as `mail.acme.io`) with an MX record pointing at SES's feedback endpoint for your region, and an SPF record `v=spf1 include:amazonses.com ~all` on that subdomain.
- **Alignment**: DKIM through Easy DKIM; SPF only with the custom MAIL FROM domain. Without it, the envelope sender is `amazonses.com`.

### Postmark
- **DKIM**: a TXT record at a dated selector (like `20260101pm._domainkey`).
- **Return path**: a CNAME such as `pm-bounces.acme.io` → `pm.mtasv.net`.
- **Alignment**: both, once both records are verified in the dashboard.

### Mailgun
- Often set up on a subdomain (`mg.acme.io`), which then needs its own SPF (`include:mailgun.org`) and a DKIM TXT record at the selector shown in Mailgun's DNS records page.
- Mail sent "from" the root domain while using an `mg.` sending domain aligns in relaxed mode, since `mg.acme.io` and `acme.io` share an organizational domain.

## Marketing and CRM

### Mailchimp
- **DKIM**: "Authenticate domain" gives CNAMEs (`k2._domainkey` → `dkim2.mcsv.net` and `k3._domainkey` → `dkim3.mcsv.net`; older accounts used `k1`).
- **SPF**: Mailchimp uses its own envelope domain, so SPF never aligns, and adding Mailchimp's include to your SPF doesn't help DMARC. DKIM carries alignment alone.
- Mailchimp Transactional (formerly Mandrill) is set up separately, with the selector `mandrill`.

### HubSpot
- **Setup**: Settings → Domains & URLs → Email sending domains. Gives DKIM CNAMEs (`hs1-<id>._domainkey`, `hs2-<id>._domainkey`) and an SPF include specific to the account.
- **Alignment**: DKIM, once the domain is connected.

### Klaviyo
- **Setup**: a "branded sending domain", usually a subdomain (`send.acme.io`), set up with CNAMEs Klaviyo provides.
- **Alignment**: DKIM and SPF on the subdomain, relaxed-aligned with the root. Without a branded domain, Klaviyo signs as itself and DMARC fails for your From address.

### Salesforce
- **DKIM**: create keys in Setup → DKIM Keys; publish the two CNAMEs it shows, then activate the key.
- **SPF**: `include:_spf.salesforce.com` (two lookups: the include, and the `exists:` inside it).
- Marketing Cloud and Pardot (Account Engagement) are separate products with separate setup.

## Support and other tools

### Zendesk
- **SPF**: `include:mail.zendesk.com`.
- **DKIM**: CNAMEs `zendesk1._domainkey` and `zendesk2._domainkey` pointing to Zendesk; enable "digital signatures" in the admin center.

### Freshdesk, Intercom, Help Scout
Each has a "custom email domain" or "DKIM" page giving CNAME records. The usual trap: support replies go out signed as the vendor until this is done, and quarantine or reject policies send them to spam.

### Billing and accounting (Stripe, QuickBooks, Xero, Chargebee)
These often send receipts or invoices "from" your address. Most either support custom DKIM for a verified domain, or send from their own domain with your address as Reply-To. A tool that sends as your domain without either fails DMARC; change it to send from its own domain, or don't enforce until it's resolved.

### Website forms and apps
Contact forms and app servers that send through their own server rarely align. Route them through the mailbox provider or a transactional service with custom DKIM, instead of adding the web host's IP to SPF and hoping.

## When a service can't align

If a service offers no custom DKIM and no custom return path:
- have it send from its own domain, with your address as Reply-To, or
- give it a dedicated subdomain (`notify.acme.io`) and set `sp=` (or that subdomain's own `_dmarc` record) to allow for it while it's being replaced, or
- replace the service.

Don't hold the whole domain at `p=none` for one stubborn tool.
