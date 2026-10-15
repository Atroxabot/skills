#!/usr/bin/env python3
"""Read the authentication story out of one email's headers.

Takes a saved message (.eml, or the text from Gmail's "Show original" /
Outlook's "View message source") and reports what the receiving server
decided for SPF, DKIM and DMARC, which domains were checked, whether they
align with the visible From address, the path the message took, and the
bulk-sender headers (List-Unsubscribe) that Gmail and Yahoo require.

Usage:
    python3 parse_headers.py message.eml
    pbpaste | python3 parse_headers.py
    python3 parse_headers.py message.eml --json

A sent message is the best evidence there is: DNS shows what a domain
publishes, headers show what actually happened to real mail.
"""

import argparse
import json
import os
import re
import sys
from email.parser import BytesHeaderParser
from email.utils import getaddresses, parsedate_to_datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_domain import org_domain  # noqa: E402

ESP_HINTS = [
    ("X-SG-EID", "SendGrid"), ("X-Mailgun-Sid", "Mailgun"), ("X-MC-User", "Mailchimp / Mandrill"),
    ("X-Mailchimp-Campaign", "Mailchimp"), ("X-SES-Outgoing", "Amazon SES"), ("X-PM-Message-Id", "Postmark"),
    ("X-HubSpot-Message-Id", "HubSpot"), ("X-Klaviyo-Msg-Id", "Klaviyo"), ("X-CSA-Complaints", "certified bulk sender"),
    ("X-Brevo-Message-Id", "Brevo"), ("X-Mailjet-Campaign", "Mailjet"), ("X-Zoho-Virus-Status", "Zoho"),
    ("X-Google-Smtp-Source", "Google"), ("X-MS-Exchange-Organization-AuthSource", "Microsoft 365"),
]


def domain_of(addr):
    addr = (addr or "").strip().strip("<>")
    return addr.rsplit("@", 1)[1].lower().rstrip(">. ") if "@" in addr else addr.lower()


def tags(value):
    out = {}
    for part in re.sub(r"\s+", " ", value).split(";"):
        k, sep, v = part.partition("=")
        if sep:
            out[k.strip().lower()] = v.strip()
    return out


def parse_auth_results(value):
    """Parse one Authentication-Results header into (authserv_id, [results])."""
    value = re.sub(r"\s+", " ", value)
    authserv, _, rest = value.partition(";")
    results = []
    for chunk in re.split(r";\s*(?=[a-z\-]+=)", rest):
        m = re.match(r"\s*([a-z\-]+)=([a-z]+)\b(.*)", chunk.strip(), re.I)
        if not m:
            continue
        method, result, props = m.groups()
        p = dict((k.lower(), v.strip('"')) for k, v in re.findall(r"([a-z]+\.[a-z\-]+)=(\"[^\"]*\"|[^\s;()]+)", props, re.I))
        reason = re.search(r"\(([^)]*)\)", props)
        results.append({"method": method.lower(), "result": result.lower(), "props": p,
                        "comment": reason.group(1) if reason else ""})
    return authserv.strip().split()[0] if authserv.strip() else "?", results


def aligned(a, b):
    if not a or not b:
        return None
    if a == b:
        return "strict"
    return "relaxed" if org_domain(a) == org_domain(b) else False


def analyze(raw):
    msg = BytesHeaderParser().parsebytes(raw)
    out = {"findings": []}

    def add(level, area, text):
        out["findings"].append({"level": level, "area": area, "message": text})

    froms = getaddresses(msg.get_all("From", []))
    from_domain = domain_of(froms[0][1]) if froms else None
    out["from"] = froms[0][1] if froms else None
    if len(froms) != 1:
        add("WARN", "From", f"{len(froms)} From addresses; DMARC needs exactly one")
    return_path = domain_of(msg.get("Return-Path", ""))
    out["return_path"] = msg.get("Return-Path")

    dkim_sigs = []
    for sig in msg.get_all("DKIM-Signature", []):
        t = tags(sig)
        dkim_sigs.append({"d": t.get("d", "").lower(), "s": t.get("s"), "a": t.get("a"),
                          "l": t.get("l"), "h": t.get("h", "")})
        if t.get("l"):
            add("WARN", "DKIM", f"signature from {t.get('d')} uses l= (body length limit): anyone can append content and keep the signature valid")
    out["dkim_signatures"] = dkim_sigs

    ar_headers = msg.get_all("Authentication-Results", [])
    if not ar_headers:
        add("WARN", "Auth", "no Authentication-Results header: this copy wasn't saved from the recipient's mailbox, or the receiver doesn't add one")
    parsed = [parse_auth_results(h) for h in ar_headers]
    out["authentication_results"] = [{"authserv_id": a, "results": r} for a, r in parsed]
    # The topmost header is added by the final receiving server; lower ones may
    # come from intermediate hops or be forged by the sender.
    verdict = {}
    if parsed:
        authserv, results = parsed[0]
        out["receiver"] = authserv
        for res in results:
            verdict.setdefault(res["method"], []).append(res)
        if len(parsed) > 1:
            add("INFO", "Auth", f"{len(parsed)} Authentication-Results headers; trusting the top one ({authserv}). Lower ones come from earlier hops or the sender")

    spf = (verdict.get("spf") or [None])[0]
    spf_domain = domain_of(spf["props"].get("smtp.mailfrom", "")) if spf else return_path
    if spf:
        line = f"{spf['result']} for {spf_domain or '?'}"
        level = "OK" if spf["result"] == "pass" else ("WARN" if spf["result"] in ("softfail", "neutral", "none") else "FAIL")
        add(level, "SPF", line + (f" ({spf['comment']})" if spf["comment"] else ""))
    spf_align = aligned(spf_domain, from_domain)
    if spf_domain and from_domain:
        if spf_align:
            add("OK", "SPF", f"envelope domain {spf_domain} aligns with From {from_domain} ({spf_align})")
        else:
            add("INFO", "SPF", f"envelope domain {spf_domain} doesn't align with From {from_domain}, so SPF can't satisfy DMARC; DKIM has to")

    dkim_results = verdict.get("dkim", [])
    dkim_pass_aligned = None
    for res in dkim_results:
        d = res["props"].get("header.d") or res["props"].get("header.i", "").lstrip("@").split("@")[-1]
        sel = res["props"].get("header.s", "?")
        al = aligned(d.lower(), from_domain) if d else None
        level = "OK" if res["result"] == "pass" else "FAIL"
        add(level, "DKIM", f"{res['result']} for d={d or '?'} s={sel}" + (f", aligned ({al})" if al else ", not aligned with From") +
            (f" ({res['comment']})" if res["comment"] and res["result"] != "pass" else ""))
        if res["result"] == "pass" and al:
            dkim_pass_aligned = d
    if not dkim_results and dkim_sigs:
        for sig in dkim_sigs:
            al = aligned(sig["d"], from_domain)
            add("INFO", "DKIM", f"signed by d={sig['d']} s={sig['s']} ({'aligned' if al else 'not aligned'}); no receiver verdict in the headers")
    if not dkim_sigs and not dkim_results:
        add("FAIL", "DKIM", "message isn't DKIM-signed: it depends on SPF alone, which breaks when mail is forwarded")
    elif dkim_sigs and not any(aligned(s["d"], from_domain) for s in dkim_sigs):
        add("WARN", "DKIM", f"no signature uses the From domain ({from_domain}): set up custom DKIM at the sending service so d= is your domain")

    dmarc = (verdict.get("dmarc") or [None])[0]
    if dmarc:
        level = "OK" if dmarc["result"] == "pass" else ("WARN" if dmarc["result"] in ("none", "bestguesspass") else "FAIL")
        add(level, "DMARC", f"{dmarc['result']} for {dmarc['props'].get('header.from', from_domain)}" + (f" ({dmarc['comment']})" if dmarc["comment"] else ""))
    elif from_domain:
        would = "pass" if ((spf and spf["result"] == "pass" and spf_align) or dkim_pass_aligned) else "fail"
        add("INFO", "DMARC", f"no receiver verdict; from the SPF and DKIM results it would {would}")
    for res in verdict.get("compauth", []):
        add("OK" if res["result"] == "pass" else "WARN", "Microsoft", f"compauth={res['result']} {res['comment']}".strip())
    arc = msg.get_all("ARC-Seal", [])
    if arc:
        add("INFO", "ARC", f"{len(arc)} ARC set(s), added by forwarders, mailing lists or the receiver itself to record earlier results")

    hops = []
    for rec in reversed(msg.get_all("Received", [])):
        flat = re.sub(r"\s+", " ", rec)
        frm = re.search(r"\bfrom (\S+)(?: \(([^)]*)\))?", flat)
        by = re.search(r"\bby (\S+)", flat)
        when = flat.rsplit(";", 1)[-1].strip() if ";" in flat else ""
        try:
            ts = parsedate_to_datetime(when)
        except (TypeError, ValueError, IndexError):
            ts = None
        ip = re.search(r"\[?((?:\d{1,3}\.){3}\d{1,3}|[0-9a-f]*:[0-9a-f:]+)\]?", frm.group(2) or "", re.I) if frm and frm.group(2) else None
        hops.append({"from": frm.group(1) if frm else None, "ip": ip.group(1) if ip else None,
                     "by": by.group(1) if by else None, "time": ts.isoformat() if ts else when})
        if ts and len(hops) > 1 and hops[-2].get("_ts"):
            delay = (ts - hops[-2]["_ts"]).total_seconds()
            hops[-1]["delay_s"] = delay
            if delay > 600:
                add("WARN", "Path", f"{int(delay // 60)} minutes between {hops[-2]['by']} and {hops[-1]['by']} (queued or throttled)")
        hops[-1]["_ts"] = ts
    for h in hops:
        h.pop("_ts", None)
    out["path"] = hops
    if hops:
        add("INFO", "Path", "Received headers below the receiver's own can be forged by the sender; trust only hops added by servers you know")

    unsub = msg.get("List-Unsubscribe")
    unsub_post = msg.get("List-Unsubscribe-Post")
    bulk = bool(msg.get("List-Id") or (msg.get("Precedence", "").lower() in ("bulk", "list")) or
                any(msg.get(h) for h, _ in ESP_HINTS[:12]))
    if unsub:
        if "https://" not in unsub:
            add("WARN", "Bulk", "List-Unsubscribe has no https link; one-click unsubscribe (RFC 8058) needs one")
        if not unsub_post or "one-click" not in unsub_post.lower():
            add("WARN", "Bulk", "List-Unsubscribe without 'List-Unsubscribe-Post: List-Unsubscribe=One-Click': Gmail and Yahoo require one-click unsubscribe for bulk marketing mail")
        else:
            add("OK", "Bulk", "one-click unsubscribe headers present")
    elif bulk:
        add("WARN", "Bulk", "looks like bulk or marketing mail but has no List-Unsubscribe header")
    services = [name for h, name in ESP_HINTS if msg.get(h)]
    if services:
        out["sending_service"] = services
        add("INFO", "Sender", "sent through " + ", ".join(dict.fromkeys(services)))
    for h in ("X-Spam-Status", "X-Spam-Score", "X-MS-Exchange-Organization-SCL", "X-Forefront-Antispam-Report"):
        if msg.get(h):
            value = re.sub(r"\s+", " ", msg.get(h))[:160]
            add("INFO", "Spam", f"{h}: {value}")
    out["from_domain"] = from_domain
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("file", nargs="?", help="message file (default: stdin)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    raw = open(args.file, "rb").read() if args.file else sys.stdin.buffer.read()
    out = analyze(raw.replace(b"\r\n", b"\n"))
    if args.json:
        print(json.dumps(out, indent=2, default=str))
        return 0
    print(f"== From {out.get('from')}  (receiver: {out.get('receiver', '?')})")
    order = ["FAIL", "WARN", "OK", "INFO"]
    for area in ("From", "Auth", "SPF", "DKIM", "DMARC", "Microsoft", "ARC", "Bulk", "Sender", "Spam", "Path"):
        for f in sorted((f for f in out["findings"] if f["area"] == area), key=lambda f: order.index(f["level"])):
            print(f"  {f['level']:<4}  {area:<9} {f['message']}")
    if out["path"]:
        print("\nPath (origin first):")
        for h in out["path"]:
            delay = f"  +{int(h['delay_s'])}s" if h.get("delay_s") is not None else ""
            print(f"  {h.get('from') or '?'} [{h.get('ip') or '-'}] → {h.get('by') or '?'}  {h.get('time')}{delay}")
    return 1 if any(f["level"] == "FAIL" for f in out["findings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
