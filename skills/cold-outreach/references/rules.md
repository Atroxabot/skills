# Outreach: benchmarks, deliverability, legal copy, DM limits (as of October 2026)

Read this for strategy, deliverability or compliance questions, or to check why a rule in SKILL.md exists. The vendor datasets (Instantly, Hunter, Belkins, Gong, Woodpecker) are correlational and come from companies that sell sending tools, so treat decimals as directional. **This is not legal advice.** Tell users with EU, German or Canadian recipients to check local rules.

## Benchmarks [Data]

| Source | Average reply rate | Notes |
|---|---|---|
| Instantly 2026 (2025 data) | 3.43% | Top quartile 5.5%+, top 10% 10.7%+ |
| Hunter 2026 (31M emails) | 4.5% per sequence | Sales 3%, marketing 6.2%, recruiting 7.5%, PR 13% |
| Belkins 2025 | 0.45% per email sent | Mostly agency campaigns |
| Woodpecker 2026 | 4.1% with no follow-ups; 8.3% with 3–5 steps | Campaign level |

- **The spread comes from what each study divides by:** per email or per contact, all replies or positive replies.
- **Working read:**
  - under 1% per email suggests a list or deliverability problem
  - 3–5% is average
  - 5–10% is good
  - 10%+ is top decile
- **Meetings booked:** about 0.5–2.5% of contacts.
- **Open rates are unreliable.** Apple Mail Privacy Protection accounts for about 49% of "opens." Judge emails on replies and meetings.
- **Executives reply less:** about 30% less likely than other contacts (Gong 2026).

## What moves replies [Data]

**Length**
- Best first touches come in under 80 words (Instantly).
- Executives: 50–100 words; replies drop sharply past 100 (Gong 2026).
- Hunter finds only a small gap by length.
- Working target: 50–100 words, under 80 for senior readers. Never cut the one detail that makes it relevant.

**Subject lines**
- 2–4 words open best (Belkins). 1–4 words for executives (Gong).
- Personalized subject lines: 7% replies against 3% (Belkins).
- "Quick question": 2.5% against 2.9% for other subjects (Hunter).

**Relevance and personalization**
- The top reasons decision makers give for ignoring cold email: too sales-focused (65%), irrelevant (61%), generic (48%) (Hunter survey).
- Two personalization details: 5.6% replies against 3.6% with none (Hunter).
- Hand-edited emails: 5.2% against 4.4% fully automated.
- 69% of US decision makers say AI-written emails bother them.

**List size**
- 21–50 recipients: 6.2% replies. 500+: 2.4%.
- 1–2 contacts per company: 5.1%. 3 or more: 3.5%.

**Buzzwords and ROI claims**
- ROI language cut success by about 15% (Gong 2021, 132K+ emails).
- Buzzwords, vague ROI claims and feature-led language "significantly reduce" executive replies (Gong 2026).

**The ask**
- Interest asks win at the cold stage (Gong, 304K emails).
- Specific time asks work later, once a deal is active.

**Tracking**
- No open or link tracking: 7.4% replies. With it: 4.4% (Hunter).

**Format**
- Plain text beats HTML and images (HubSpot).
- Custom domains: 5.2% replies against 2.5% for free email addresses.

**Timing** is a minor lever. Weekday mornings in the recipient's time zone, with Tuesday to Thursday slightly better. Hunter found no meaningful effect.

## Follow-ups [Data + Consensus]

- **Where replies come from:**
  - 42% come from follow-ups (Instantly).
  - Steps 2–6 bring 58.6% of replies, and step 3 drives 35.6% of meetings (Belkins).
- **How many:** three messages got 6.8% replies against 3.3% for one (Hunter).
- **Long sequences backfire.** Four or more emails reportedly more than triple unsubscribes and spam complaints (Belkins, earlier edition).
- **"Just checking in"** follow-ups reportedly cut meetings booked by about 14% (Saleshandy, via Woodpecker; secondhand).
- **Default:** 3–5 touches over 2–3 weeks. Each one adds something new, and they stop at the first reply.

## Deliverability [Official, verified 2026-10-14]

**Google and Yahoo**, for senders of about 5,000+ a day; the basics apply to everyone:
- SPF and DKIM
- DMARC, required for bulk senders
- a From domain aligned with SPF or DKIM
- TLS
- valid forward and reverse DNS
- one-click unsubscribe for marketing mail
- spam complaints under 0.3%; Google aims for under 0.1%
- Since November 2025, Gmail has ramped up enforcement and rejects non-compliant mail.

**Microsoft Outlook.com** (senders over 5,000 a day): SPF, DKIM and DMARC have been enforced since 2025-05-05. Non-compliant mail is rejected with "550 5.7.515."

**Volume** [Data/Consensus]:
- Practitioners keep each inbox to about 30–50 cold emails a day.
- New domains need warm-up.
- Cold email goes from secondary domains, never from the main company domain.

**Spam-trigger words** are mostly folklore. Complaint rates, authentication and engagement are what decide where mail lands. Still, avoid all-caps, "$$$" and the like, because they read as spam to people too.

**What this means for copy:** relevance, small lists and an easy "no" keep complaints down, and complaints decide whether any email arrives.

## Legal copy checklist [Official; practical, not legal advice]

| | US (CAN-SPAM) | UK (PECR + UK GDPR) | EU (GDPR + national law) | Canada (CASL) |
|---|---|---|---|---|
| **Cold B2B allowed?** | Yes, on an opt-out basis | Yes, to corporate addresses. Sole traders need consent. Legitimate interests applies to named people. | Varies by country. Germany is reported to require consent even for B2B. | Only with implied consent: the address was published, there's no "no unsolicited messages" statement, and the message is relevant to their role. |
| **Must include** | No misleading headers or subject lines; identify it as an ad; a valid postal address | Your identity; a valid opt-out address | Who you are and how to contact you; **where you got their data**, at the latest by the first message; their right to object | Your business name; a mailing address plus phone, email or web |
| **Opt-out** | Clear and conspicuous; honor within 10 business days | Honor it; the right to object is absolute | Right to object (Art. 21) | Clear and prominent; honor within 10 business days |

**Germany.** The Act Against Unfair Competition (UWG §7) treats advertising email sent without the recipient's prior express consent as an unacceptable nuisance, and German courts apply this to B2B email too. The narrow exception covers existing customers who bought similar products. So a cold sales email to a German business contact is risky even with a perfect footer. When the recipient is in Germany:
- say so plainly, and suggest the sender gets the consent question checked before emailing
- offer the LinkedIn route first: a connection note sent by hand, then a conversation, and email only once they've agreed to hear more
- still write the email if asked, with the full EU footer, and keep the warning in the notes

**In practice, every cold email footer has:**
1. a real name and company
2. a postal address (US and Canada)
3. a plain opt-out ("reply 'no' and I won't follow up")
4. for EU and UK recipients, where the address came from and a privacy-notice link

**Never** use a fake "Re:" or "Fwd:" on a first email, a deceptive subject line, or a fake referral.

**UK note:** the Data (Use and Access) Act 2025 is changing PECR, so recheck the ICO guidance.

## LinkedIn and X

- **LinkedIn automation is banned.** User Agreement s. 8.2 (effective 2025-11-03) prohibits bots and automated messaging or invitations, and accounts using them get restricted. Messages are sent by hand.

| LinkedIn message | Limit | Status |
|---|---|---|
| Connection note | 300 characters reported; 200 for free accounts per practitioners | Unverified; write **200 or fewer** |
| InMail | Subject about 200 characters, body about 2,000 | Secondhand; under about 400 characters reportedly performs better |
| Regular message | 8,000 characters | Secondhand |

- **Norms:**
  - no pitch in the connection note or the first DM
  - 2–4 lines that read like chat
  - 50.5% of decision makers prefer LinkedIn for vendor outreach (Hunter survey)
- **X DMs** from people the recipient doesn't follow go to message requests, and many accounts restrict DMs. Engage publicly first. Templated DMs get ignored or reported.

## Sources

Accessed October 2026.

**Deliverability**
- Google, email sender guidelines: https://support.google.com/a/answer/81126
- Google, sender guidelines FAQ (enforcement since November 2025): https://support.google.com/a/answer/14229414
- Yahoo Sender Hub, best practices: https://senders.yahooinc.com/best-practices/
- Microsoft, Outlook high-volume sender requirements (2025): https://techcommunity.microsoft.com/blog/outlook/strengthening-email-ecosystem-outlook%E2%80%99s-new-requirements-for-high%E2%80%90volume-senders/4399730

**Law**
- FTC, CAN-SPAM compliance guide: https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business
- ICO, electronic mail marketing (PECR): https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guide-to-pecr/electronic-and-telephone-marketing/electronic-mail-marketing/
- ICO, business-to-business marketing: https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/business-to-business-marketing/
- GDPR Art. 14: https://gdpr-info.eu/art-14-gdpr/
- Germany, UWG §7: https://www.gesetze-im-internet.de/uwg_2004/__7.html
- CASL, s. 10–11: https://laws-lois.justice.gc.ca/eng/acts/E-1.6/page-2.html

**LinkedIn**
- LinkedIn User Agreement (effective 2025-11-03): https://www.linkedin.com/legal/user-agreement

**Benchmarks**
- Instantly, 2026 benchmark report: https://instantly.ai/report-page
- Hunter, State of Email Outreach 2026: https://hunter.io/the-state-of-cold-email
- Hunter, cold email word count: https://hunter.io/blog/cold-email-word-count
- Belkins, sales follow-up statistics: https://belkins.io/blog/sales-follow-up-statistics
- Belkins, subject line statistics: https://belkins.io/blog/b2b-cold-email-subject-line-statistics
- Woodpecker, cold email statistics (updated 2026-06-23): https://woodpecker.co/blog/cold-email-statistics/
- Gong, do executives reply to cold email (2026-01-29): https://www.gong.io/blog/do-execs-really-reply-to-cold-email-here-s-what-the-data-says
- Gong, sales email statistics (updated 2026-03-06): https://www.gong.io/blog/sales-email-statistics
- HubSpot, plain text vs HTML (updated 2025-06-13): https://blog.hubspot.com/marketing/plain-text-vs-html-emails-data
- Gong Labs, interest CTA (304,174 emails): https://www.gong.io/resources/labs/this-surprising-cold-email-cta-will-help-you-book-a-lot-more-meetings/
