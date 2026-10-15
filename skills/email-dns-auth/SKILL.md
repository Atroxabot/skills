---
name: email-dns-auth
description: Checks and fixes a domain's email authentication, the DNS records (SPF, DKIM, DMARC, MX, MTA-STS, TLS-RPT, BIMI, reverse DNS) that decide whether mail sent as the domain is trusted, junked or rejected. Runs live DNS checks, reads message headers to see what really happened to a sent email, summarizes DMARC aggregate reports, and gives copy-paste DNS records plus a safe rollout order. Use when someone says their emails go to spam or bounce, sees errors like 550 5.7.26 or 5.7.515, asks to set up or check SPF, DKIM or DMARC, connect a sending service (Google Workspace, Microsoft 365, SendGrid, Mailchimp, HubSpot, Amazon SES, Postmark), meet the Gmail, Yahoo or Outlook bulk-sender requirements, stop others spoofing their domain, lock down a domain that sends no mail, or read DMARC reports. Technical infrastructure only; for writing email content use a writing skill.
---

# Email DNS authentication

Make sure mail sent as a domain is provably from that domain, and fix it when it isn't. When this is broken, the symptoms are vague: "our invoices land in spam", "Gmail bounced the newsletter", "someone sent phishing from our address". The causes are concrete and checkable: a missing or invalid record, a sending service that isn't aligned, an SPF record over its lookup limit.

The people asking are often not email engineers. Explain each problem in a sentence of plain language before the technical detail, and give exact records they can paste into their DNS provider.

## How it fits together (read this first)

A receiving server asks three questions about each message:

1. **SPF: was it sent from a server the domain allows?** The domain publishes a list of allowed servers. The check runs against the hidden envelope sender (Return-Path), not the From address people see.
2. **DKIM: is it signed by the domain, and unchanged?** The sending service signs the message; the domain publishes the public key. The signature names its own domain (`d=`), which can be any domain.
3. **DMARC: do those checks vouch for the From address people see?** DMARC passes only if SPF or DKIM passes **and** the domain it passed for matches the visible From domain. This matching is called **alignment**, and it's where most real problems are.

Alignment explains the most common confusion. A marketing tool sends as `news@acme.io`, but by default its envelope sender is something like `bounces@sendgrid.net` and it signs with `d=sendgrid.info`. SPF passes (for sendgrid.net) and DKIM passes (for sendgrid.info), yet DMARC fails, because neither is acme.io. Adding the tool's `include:` to acme.io's SPF record doesn't fix this, because SPF is checked against the tool's own bounce domain. The fix is the tool's "domain authentication" setup: custom DKIM so it signs as `d=acme.io`, and where offered a custom bounce domain such as `em123.acme.io`.

[references/records-explained.md](references/records-explained.md) covers each record's syntax, the limits and gotchas, and the rollout plan. Read it before writing any record.

## Workflow

### 1. Gather what you need

- **The domain**, and the exact From address that has the problem. Subdomains matter: `mail.acme.io` and `acme.io` have separate SPF records.
- **Every service that sends as the domain.** Usual suspects: the mailbox provider (Google Workspace, Microsoft 365), marketing (Mailchimp, HubSpot, Klaviyo), transactional (SendGrid, Postmark, SES, Mailgun), support desks (Zendesk, Freshdesk, Intercom), billing (Stripe, QuickBooks, Xero), CRM (Salesforce), website forms. Ask; people forget half of these. DMARC reports (step 5) find the rest.
- **A real message, if there's a delivery problem.** A sample is the best evidence there is: DNS shows what the domain publishes; the headers show what the receiver actually decided. In Gmail use "Show original"; in Outlook, "View message source". Save it as a `.eml` or paste it.
- **The exact bounce text**, if mail is rejected. It usually names the failed check. Gmail `550 5.7.26` means unauthenticated or failed DMARC. Gmail `5.7.25` means the sending IP has no reverse DNS. Microsoft `550 5.7.515` means the domain doesn't meet Outlook.com's authentication requirements for high-volume senders.

### 2. Check the published records

```
python3 scripts/check_domain.py acme.io
python3 scripts/check_domain.py acme.io --selector s1 --selector k2   # selectors from a real message's DKIM-Signature s=
python3 scripts/check_domain.py acme.io --ip 167.89.1.2               # a sending IP from the headers
```

It reports MX, SPF (with the include tree and the lookup count), DMARC (policy, reporting, and authorization for external report addresses), DKIM keys and their strength, MTA-STS, TLS-RPT, BIMI and reverse DNS. It works without a local resolver by falling back to DNS-over-HTTPS. It only reads DNS; it never changes anything.

Two things it can't see:
- **DKIM selectors are guesses.** It probes about 40 common names. "No key found" means "not at those names", not "no DKIM". The real selector is the `s=` in a sent message's `DKIM-Signature` header.
- **Alignment of each sending service.** DNS shows the policy, not what each service puts in the envelope and signature. Use a sample message from each service, or DMARC reports.

### 3. Check a real message

```
python3 scripts/parse_headers.py message.eml
```

It reads the receiving server's verdict (the topmost `Authentication-Results` header; lower ones can be forged or come from earlier hops), works out SPF and DKIM alignment with the From domain, lists DKIM signatures, traces the delivery path with delays, names the sending service, and checks the one-click unsubscribe headers bulk senders need.

Read the result as a story: which service sent it, what it passed for, why DMARC did or didn't pass, and the one change that would make it pass.

### 4. Diagnose and prioritize

Rank problems by what they break, in this order:

1. **Mail being rejected or junked now**: DMARC failing for a legitimate service, SPF over 10 lookups (a permanent error that fails SPF for all mail), multiple SPF records, a typo that invalidates a record, a DKIM key mangled when it was pasted in.
2. **Requirements about to bite**: Gmail and Yahoo (since February 2024) and Outlook.com (since May 2025) require bulk senders (roughly 5,000+ messages a day to their users) to have SPF and DKIM, a DMARC record of at least `p=none`, alignment through SPF or DKIM, reverse DNS on sending IPs, TLS, one-click unsubscribe on marketing mail (RFC 8058), and a spam complaint rate under 0.3%. Smaller senders need SPF or DKIM at minimum, and in practice should meet the same bar.
3. **Spoofing exposure**: no DMARC, or `p=none` long after the reports show everything legitimate passing, `sp=none`, parked domains with no records.
4. **Hardening**: 1024-bit DKIM keys, MTA-STS and TLS-RPT, BIMI.

Separate "broken" from "not best practice". A `~all` SPF record with an enforcing DMARC policy is fine; don't call it a problem.

### 5. Read DMARC reports before tightening

Before recommending `quarantine` or `reject`, know who sends as the domain. Aggregate reports (the XML files sent to the `rua=` address, often zipped) list every sending IP, its volume and whether it passed.

```
python3 scripts/summarize_dmarc.py reports/*.zip reports/*.xml.gz
python3 scripts/summarize_dmarc.py reports/ --resolve     # adds reverse DNS names to identify senders
```

It groups traffic by source, shows each source's volume and pass rate, labels the likely legitimate services that fail alignment, and estimates how much mail an enforcing policy would affect now. A source that fails but is a real service needs setting up. A source nobody recognizes, sending a domain's mail from consumer IP ranges, is spoofing; enforcement is what stops it. Forwarded mail (mailing lists, auto-forwards) often fails SPF but keeps DKIM; that's another reason to make sure every service signs with aligned DKIM.

### 6. Recommend changes

Give each change as an exact record and a reason:

| Type | Host / name | Value | Why |
|---|---|---|---|
| TXT | `@` | `v=spf1 include:_spf.google.com include:sendgrid.net ~all` | Replaces the two SPF records (only one is allowed) |

Rules for recommendations, with the reasons:

- **Never move straight to `p=reject`** on a domain that sends real mail. A reject policy bounces every unaligned message, including invoices and password resets from a service nobody remembered. Go `none` (with reports) → fix every legitimate source → `quarantine` → `reject`, watching reports at each step. The plan and timings are in [references/records-explained.md](references/records-explained.md).
- **One SPF record per name.** Merge; never add a second `v=spf1` record.
- **Don't "flatten" SPF** (replacing includes with IP lists) to dodge the lookup limit unless the user accepts the upkeep. Providers change their IPs, and a flattened record breaks silently. Prefer removing unused includes, or moving a sending service to a subdomain with its own SPF record.
- **Copy provider values from the provider's dashboard.** Selectors and CNAME targets are often specific to the account. [references/providers.md](references/providers.md) describes what each service's setup involves; the dashboard has the exact values.
- **Host names depend on the DNS provider.** Some want `_dmarc`, others `_dmarc.acme.io`, and some append the domain automatically, creating `_dmarc.acme.io.acme.io`. Say which form you're giving, and suggest re-running the check after publishing.
- **Parked domains** (owned, no mail): publish `v=spf1 -all`, `v=DMARC1; p=reject;`, and a null MX (`0 .`). Attackers prefer domains nobody watches.

### 7. Verify

After the user publishes changes, re-run `check_domain.py` (DNS changes can take from minutes to the record's TTL to show), then send a test message to a Gmail address and read its headers with `parse_headers.py`. Done means: DMARC passes on a real message from each sending service, not just that the records exist.

## Output

1. **Verdict in one or two sentences**, in plain language: what's wrong and what it's doing to their mail.
2. **Problems, most damaging first**, each with a one-line plain explanation and the technical detail.
3. **Records to publish or change**, as the table above, ready to paste.
4. **What to leave alone**: things that look odd but are fine, so nobody "fixes" them.
5. **Next steps**: the rollout stage they're at and when to move to the next one.

Keep jargon on a leash. "Your newsletter tool signs mail as itself, not as you, so Gmail can't confirm it's really from acme.io" lands better than "DKIM d= unaligned".

## References

- [references/records-explained.md](references/records-explained.md): each record's syntax, limits and traps; alignment; the DMARC rollout plan; parked domains; reading reports by hand.
- [references/providers.md](references/providers.md): what setting up common sending services involves, and how each one achieves alignment.
- `scripts/check_domain.py`: live DNS check of every record. `--json` for machine-readable output.
- `scripts/parse_headers.py`: what happened to a real message.
- `scripts/summarize_dmarc.py`: summarizes DMARC aggregate reports (`.xml`, `.xml.gz`, `.zip`).
