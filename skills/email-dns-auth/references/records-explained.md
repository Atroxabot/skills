# Email authentication records, explained

Each record: what it's for, its syntax, and the mistakes that break it. The specifications are RFC 7208 (SPF), RFC 6376 (DKIM), RFC 7489 (DMARC, being revised as "DMARCbis"), RFC 8461 (MTA-STS), RFC 8460 (TLS-RPT), RFC 7505 (null MX) and RFC 8058 (one-click unsubscribe). Mailbox-provider requirements come from Google's, Yahoo's and Microsoft's published sender guidelines.

## Contents

1. Envelope vs header: the two "from" addresses
2. SPF
3. DKIM
4. DMARC
5. Alignment in detail
6. The DMARC rollout plan
7. Bulk-sender requirements
8. MX and null MX
9. Reverse DNS (PTR)
10. MTA-STS and TLS-RPT
11. BIMI
12. ARC and forwarding
13. Reading an aggregate report by hand

## 1. Envelope vs header: the two "from" addresses

Every email has two senders:
- **Envelope sender** (MAIL FROM, shown afterwards as `Return-Path`): where bounces go. Recipients never see it. Sending services usually set it to their own domain so they can process bounces.
- **Header From**: the address shown in the mail client. This is what people trust, and what attackers forge.

SPF checks the envelope sender. DMARC protects the header From. Keeping the two straight explains most email authentication puzzles.

## 2. SPF

A TXT record on the domain listing the servers allowed to send mail with that domain as the envelope sender.

```
v=spf1 include:_spf.google.com include:sendgrid.net ip4:203.0.113.7 ~all
```

| Term | Meaning | Costs a DNS lookup? |
|---|---|---|
| `ip4:`, `ip6:` | An address or range | No |
| `include:domain` | Also allow whatever that domain's SPF allows | Yes, plus whatever it includes |
| `a`, `a:host` | The host's A/AAAA addresses | Yes |
| `mx`, `mx:domain` | The domain's MX servers | Yes (and more than 10 MX hosts is an error) |
| `exists:` | Advanced, macro-based | Yes |
| `ptr` | Deprecated; don't use | Yes |
| `redirect=domain` | Use that domain's record instead (only when there's no `all`) | Yes |
| `-all` / `~all` / `?all` / `+all` | What to say about everyone else: fail / softfail / neutral / pass | No |

Limits and traps:
- **10 DNS lookups in total**, counting nested includes. Over 10 is a permanent error and SPF fails for all mail. Each provider's include costs 1 to 4 lookups. Fix by removing services no longer used, or by moving a sender to a subdomain (`news.acme.io`) with its own record.
- **Two lookups that return nothing** (void lookups) is the most tolerated; more is a permanent error. Includes of retired services often cause this.
- **Only one SPF record** per name. Two `v=spf1` records make SPF fail outright. It's a common result of each service's setup guide saying "add this SPF record".
- **An include pointing to a domain without SPF** is a permanent error.
- **`+all` lets anyone send as you.** `?all` protects nothing.
- **`~all` vs `-all`**: with DMARC enforcing, the difference hardly matters, because DMARC decides. `~all` is the safer default while you're still finding senders. Don't present `~all` as a flaw.
- **Anything after `all` is ignored.**
- **Every TXT string is at most 255 characters.** Long records are split into several quoted strings in one record. Receivers join the strings without adding anything, so keep the space between two terms inside one of the strings (`"... include:a.com " "include:b.com ..."`), or the terms run together and the record breaks.
- **SPF applies to the exact name.** `acme.io`'s record says nothing about `mail.acme.io`. Subdomains that send mail, including bounce subdomains, need their own.
- **Forwarding breaks SPF.** A forwarded message arrives from the forwarder's server, not yours. DKIM survives forwarding, which is why DMARC should never rely on SPF alone.

## 3. DKIM

The sending service signs each message with a private key; the domain publishes the public key at `<selector>._domainkey.<domain>`.

```
s1._domainkey.acme.io  TXT  "v=DKIM1; k=rsa; p=MIIBIjANBgkqh..."
```

- The **selector** lets a domain have several keys (one per service, or old and new during rotation). The `s=` in a message's `DKIM-Signature` header names the one used; `d=` names the signing domain.
- Many services have you publish a **CNAME** to a key they host and rotate (`s1._domainkey.acme.io CNAME s1.domainkey.u123.wl.sendgrid.net`). Leave these as CNAMEs; copying today's key into a TXT record breaks when they rotate it.
- **Key size**: 2048-bit RSA is the norm. 1024 still works but is the minimum. Receivers reject keys under 1024.
- **An empty `p=`** means the key is revoked. That's correct for a retired selector.
- **`t=y`** marks a key as in testing; some receivers then treat signatures as absent. Remove it once things work.
- **Paste damage** is the usual breakage: a key split badly across strings, with a stray space, quote or line break, or truncated by a DNS form's character limit. The check script reports a key that won't decode.
- **`l=` in a signature** (body length limit) lets anyone append content to a signed message. Services that set it should be configured not to.
- **The signing domain can be anything.** A service signing with its own domain (`d=sendgrid.info`) passes DKIM but doesn't help DMARC. Custom DKIM, where the service signs as your domain, is the part that matters.

## 4. DMARC

A TXT record at `_dmarc.<domain>` saying what receivers should do with mail whose From domain isn't authenticated, and where to send reports.

```
_dmarc.acme.io  TXT  "v=DMARC1; p=quarantine; rua=mailto:dmarc@acme.io; adkim=r; aspf=r"
```

| Tag | Meaning |
|---|---|
| `v=DMARC1` | Required, and must come first |
| `p=` | Policy: `none` (report only), `quarantine` (spam folder), `reject` (bounce) |
| `sp=` | Policy for subdomains; defaults to `p` |
| `rua=` | Where to send daily aggregate reports (`mailto:` addresses, comma-separated) |
| `ruf=` | Where to send per-message failure reports; most large receivers don't send them |
| `adkim=`, `aspf=` | Alignment mode: `r` relaxed (default; same organizational domain) or `s` strict (exact match) |
| `pct=` | Apply the policy to only this percentage of failing mail. DMARCbis drops it in favor of `t=y` (testing), so use it only as a short ramp |
| `fo=` | Which failures trigger failure reports |
| `np=` | DMARCbis: policy for subdomains that don't exist |

Traps:
- **One record only**, at exactly `_dmarc.<domain>`. Two records means none applies.
- **Subdomains without their own record inherit** the organizational domain's record, using `sp=`.
- **Reports sent to another domain need permission from that domain.** If `acme.io` sends reports to `reports@dmarc-vendor.com`, the vendor must publish `acme.io._report._dmarc.dmarc-vendor.com TXT "v=DMARC1"`. Reporting services do this for you; a personal address at a different domain won't have it, and the reports silently never arrive.
- **`p=none` protects nothing.** It's the right first step and a bad final state.
- **`sp=none` under `p=reject`** leaves every subdomain open to spoofing.
- **Strict alignment** (`adkim=s`, `aspf=s`) breaks services that use a subdomain for bounces or signing. Relaxed is the usual choice.

## 5. Alignment in detail

DMARC passes if **either**:
- SPF passes, and the envelope sender's domain aligns with the From domain, **or**
- a DKIM signature passes, and its `d=` domain aligns with the From domain.

"Aligns" in relaxed mode means the same organizational domain: `em123.acme.io` aligns with `acme.io`; `acme.io` doesn't align with `acme.com` or `sendgrid.net`. The organizational domain is the registered domain: `acme.co.uk`, not `co.uk`. (The scripts use a built-in list of two-part suffixes; for an unusual suffix, check by hand.)

Per sending service, there are two ways to align:
1. **Custom DKIM**: the service signs with `d=yourdomain`. Works through forwarding. Always do this.
2. **Custom return path**: the service uses a bounce address on a subdomain of yours (`bounces@em123.acme.io`), with an SPF record on that subdomain (usually via a CNAME to the service). Nice to have.

A service that offers neither can't send DMARC-passing mail as your domain. Its options are to send from its own domain, or from a subdomain you hand over to it entirely.

## 6. The DMARC rollout plan

The goal is `p=reject` without losing legitimate mail.

1. **Publish `p=none` with `rua=`.** Nothing changes for delivery. Reports start arriving within a day or two.
2. **Watch reports for 2 to 4 weeks** (longer if some services send monthly, such as billing runs). List every source. For each legitimate one, set up aligned DKIM, and a custom return path where offered.
3. **When legitimate mail passes at about 98% or more**, move to `p=quarantine`. A short ramp (`pct=25`, then `50`, then `100`) is possible but optional.
4. **After another 2 to 4 weeks** with no legitimate failures, move to `p=reject`.
5. **Keep reading reports.** New tools get adopted without anyone telling IT; reports are how you find them.

Small domains with one or two well-understood senders (say, only Google Workspace) can move faster, once a sample message from each sender shows DMARC passing.

**Parked domains** (no mail at all) can go straight to the locked-down set:

```
@        TXT  "v=spf1 -all"
_dmarc   TXT  "v=DMARC1; p=reject;"
@        MX   0 .
```

Optionally, a wildcard `*._domainkey TXT "v=DKIM1; p="` revokes any DKIM key, so signatures with that domain can't validate.

## 7. Bulk-sender requirements

**Gmail and Yahoo** (from February 2024) and **Outlook.com, Hotmail and Live** (from May 2025) set rules for anyone sending them large volumes (Google's threshold is close to 5,000 messages a day to its users; once over, you're treated as a bulk sender permanently):

- SPF **and** DKIM for the sending domain
- DMARC published, `p=none` or stricter
- alignment: the From domain aligns with SPF or DKIM
- forward and reverse DNS for sending IPs
- TLS for transmission
- for marketing and subscribed mail: one-click unsubscribe (`List-Unsubscribe` with an https URL, plus `List-Unsubscribe-Post: List-Unsubscribe=One-Click`), honored within two days
- a spam complaint rate below 0.3% (aim under 0.1%) in Google Postmaster Tools

**All senders** to Gmail need at least SPF or DKIM, valid reverse DNS, TLS, and a low spam rate.

Failures show up as bounces or junking. Typical bounce texts: Gmail `550 5.7.26` (unauthenticated, or DMARC failed), Gmail `5.7.25` (no reverse DNS for the sending IP), Microsoft `550 5.7.515` (doesn't meet Outlook.com's requirements).

## 8. MX and null MX

MX records say where mail for the domain is delivered. A domain that sends but can't receive breaks replies and bounces, and some receivers distrust it. A domain that never receives mail should say so with a null MX (`0 .`, RFC 7505), so senders fail fast instead of retrying for days.

## 9. Reverse DNS (PTR)

The sending IP's reverse name should exist and resolve back to the same IP ("forward-confirmed"). Shared-IP services (Google, Microsoft, SendGrid and so on) handle this. It matters for self-hosted servers and dedicated IPs. Set PTR records with whoever owns the IP (the hosting provider), not in the domain's DNS.

## 10. MTA-STS and TLS-RPT

Both protect mail coming **to** the domain, not deliverability of mail sent from it.

- **MTA-STS** tells senders to deliver only over verified TLS to the listed MX hosts, which stops downgrade and interception attacks. It needs a TXT record (`_mta-sts.<domain>  "v=STSv1; id=20261015"`) and a policy file served over HTTPS at `https://mta-sts.<domain>/.well-known/mta-sts.txt`:
  ```
  version: STSv1
  mode: testing
  mx: aspmx.l.google.com
  mx: *.aspmx.l.google.com
  max_age: 604800
  ```
  Start with `mode: testing`, switch to `enforce` once TLS-RPT reports are clean, and change the `id` every time the policy changes. In enforce mode, an MX host missing from the policy will stop receiving mail from MTA-STS-aware senders.
- **TLS-RPT** (`_smtp._tls.<domain>  "v=TLSRPTv1; rua=mailto:tls-reports@acme.io"`) asks senders for daily reports of TLS delivery failures.

## 11. BIMI

Shows the brand logo next to authenticated mail in supporting clients. It requires DMARC at `quarantine` or `reject` (applied to 100% of mail), a square SVG logo in the SVG Tiny PS profile, and for Gmail and Apple Mail a Verified Mark Certificate or Common Mark Certificate. Record: `default._bimi.<domain>  TXT  "v=BIMI1; l=https://acme.io/logo.svg; a=https://acme.io/vmc.pem"`. It's a reward for strong authentication, not a deliverability fix.

## 12. ARC and forwarding

When a mailing list or forwarder changes a message (adding a footer or a subject tag), DKIM breaks; when it relays the message, SPF breaks. ARC lets the intermediary record the results it saw, and receivers that trust it can honor them. You don't publish anything for ARC. It's the reason a domain at `p=reject` can still have its mail survive well-run mailing lists, and the reason some forwarded mail still fails.

## 13. Reading an aggregate report by hand

Reports are XML, usually zipped or gzipped, one per receiver per day. The parts that matter:

```xml
<policy_published><domain>acme.io</domain><p>none</p>...</policy_published>
<record>
  <row>
    <source_ip>167.89.1.2</source_ip>
    <count>1240</count>
    <policy_evaluated>
      <disposition>none</disposition>   <!-- what the receiver did -->
      <dkim>fail</dkim>                 <!-- ALIGNED DKIM result -->
      <spf>fail</spf>                   <!-- ALIGNED SPF result -->
    </policy_evaluated>
  </row>
  <identifiers><header_from>acme.io</header_from></identifiers>
  <auth_results>                         <!-- raw results, alignment ignored -->
    <dkim><domain>sendgrid.info</domain><selector>smtpapi</selector><result>pass</result></dkim>
    <spf><domain>em4821.sendgrid.net</domain><result>pass</result></spf>
  </auth_results>
</record>
```

`policy_evaluated` holds the aligned results that DMARC used; `auth_results` holds the raw ones. "Raw pass, aligned fail", as here, is the signature of a legitimate service that isn't set up with custom DKIM yet. `scripts/summarize_dmarc.py` does this across many reports at once.
