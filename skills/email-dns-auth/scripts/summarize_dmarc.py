#!/usr/bin/env python3
"""Summarize DMARC aggregate (rua) reports.

Reads report files (.xml, .xml.gz, .gz, .zip) or directories of them and
groups traffic by sending source: volume, aligned DKIM and SPF pass rates,
what receivers did, and a label for what the source probably is. Ends with
how much mail an enforcing policy would affect today.

Usage:
    python3 summarize_dmarc.py reports/
    python3 summarize_dmarc.py a.zip b.xml.gz --resolve    # reverse DNS for each source IP
    python3 summarize_dmarc.py reports/ --json

Labels are heuristics. "Legitimate, not aligned" means the source passes
DKIM or SPF for some other domain (usually a sending service missing custom
DKIM). "Unknown, failing" is either spoofing or a service nobody has
identified yet; check the names before calling it an attack.
"""

import argparse
import gzip
import io
import ipaddress
import json
import os
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from xml.etree import ElementTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_domain import Resolver, org_domain  # noqa: E402

SERVICE_HINTS = {
    "google.com": "Google", "googlemail.com": "Google", "gappssmtp.com": "Google Workspace (default DKIM)",
    "outlook.com": "Microsoft", "onmicrosoft.com": "Microsoft 365 (default DKIM)", "sendgrid.net": "SendGrid",
    "sendgrid.info": "SendGrid", "amazonses.com": "Amazon SES", "mcsv.net": "Mailchimp", "mcdlv.net": "Mailchimp",
    "mandrillapp.com": "Mailchimp Transactional", "mailgun.org": "Mailgun", "mailgun.net": "Mailgun",
    "mtasv.net": "Postmark", "hubspotemail.net": "HubSpot", "hubspot.com": "HubSpot", "zendesk.com": "Zendesk",
    "salesforce.com": "Salesforce", "exacttarget.com": "Salesforce Marketing Cloud", "klaviyomail.com": "Klaviyo",
    "freshdesk.com": "Freshdesk", "intercom-mail.com": "Intercom", "stripe.com": "Stripe", "zoho.com": "Zoho",
    "sparkpostmail.com": "SparkPost", "brevo.com": "Brevo", "sendinblue.com": "Brevo", "mailjet.com": "Mailjet",
    "constantcontact.com": "Constant Contact", "createsend.com": "Campaign Monitor", "shopify.com": "Shopify",
}


def iter_xml(paths):
    for path in paths:
        if os.path.isdir(path):
            names = sorted(os.listdir(path))
            yield from iter_xml([os.path.join(path, n) for n in names if not n.startswith(".")])
            continue
        with open(path, "rb") as fh:
            data = fh.read()
        try:
            if data[:2] == b"\x1f\x8b":
                yield path, gzip.decompress(data)
            elif data[:2] == b"PK":
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    for name in zf.namelist():
                        if name.lower().endswith(".xml"):
                            yield f"{path}:{name}", zf.read(name)
            else:
                yield path, data
        except (OSError, zipfile.BadZipFile) as exc:
            print(f"skipping {path}: {exc}", file=sys.stderr)


def text(node, path, default=""):
    found = node.find(path)
    return (found.text or "").strip() if found is not None and found.text else default


def strip_ns(root):
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def parse(paths):
    reports, rows = [], []
    for name, blob in iter_xml(paths):
        try:
            root = strip_ns(ElementTree.fromstring(blob))
        except ElementTree.ParseError as exc:
            print(f"skipping {name}: not valid XML ({exc})", file=sys.stderr)
            continue
        meta = {
            "file": name,
            "org": text(root, "report_metadata/org_name", "?"),
            "begin": text(root, "report_metadata/date_range/begin"),
            "end": text(root, "report_metadata/date_range/end"),
            "domain": text(root, "policy_published/domain"),
            "p": text(root, "policy_published/p"),
        }
        reports.append(meta)
        for rec in root.findall("record"):
            dkim_raw = [(text(d, "domain").lower(), text(d, "selector"), text(d, "result")) for d in rec.findall("auth_results/dkim")]
            spf_raw = [(text(s, "domain").lower(), text(s, "result")) for s in rec.findall("auth_results/spf")]
            rows.append({
                "ip": text(rec, "row/source_ip"),
                "count": int(text(rec, "row/count", "0") or 0),
                "disposition": text(rec, "row/policy_evaluated/disposition", "none"),
                "dkim": text(rec, "row/policy_evaluated/dkim"),
                "spf": text(rec, "row/policy_evaluated/spf"),
                "reasons": [text(r, "type") for r in rec.findall("row/policy_evaluated/reason")],
                "header_from": text(rec, "identifiers/header_from").lower(),
                "dkim_raw": dkim_raw,
                "spf_raw": spf_raw,
                "reporter": meta["org"],
            })
    return reports, rows


def service_for(domains):
    for d in domains:
        org = org_domain(d) if d else ""
        if org in SERVICE_HINTS:
            return SERVICE_HINTS[org]
    return None


def source_key(row, names):
    name = names.get(row["ip"])
    if name:
        return org_domain(name), name
    try:
        net = ipaddress.ip_network(row["ip"] + ("/24" if ":" not in row["ip"] else "/48"), strict=False)
        return str(net), None
    except ValueError:
        return row["ip"], None


def summarize(rows, names):
    groups = defaultdict(lambda: {"count": 0, "pass": 0, "dkim_aligned": 0, "spf_aligned": 0, "ips": set(),
                                  "raw_domains": defaultdict(int), "dispositions": defaultdict(int),
                                  "from": defaultdict(int), "forwarded": 0, "sample_name": None})
    for row in rows:
        key, name = source_key(row, names)
        g = groups[key]
        n = row["count"]
        g["count"] += n
        g["ips"].add(row["ip"])
        g["sample_name"] = g["sample_name"] or name
        g["from"][row["header_from"]] += n
        g["dispositions"][row["disposition"]] += n
        if row["dkim"] == "pass" or row["spf"] == "pass":
            g["pass"] += n
        if row["dkim"] == "pass":
            g["dkim_aligned"] += n
        if row["spf"] == "pass":
            g["spf_aligned"] += n
        for d, _, result in row["dkim_raw"]:
            if result == "pass" and d:
                g["raw_domains"]["dkim:" + d] += n
        for d, result in row["spf_raw"]:
            if result == "pass" and d:
                g["raw_domains"]["spf:" + d] += n
        if any(r in ("forwarded", "mailing_list", "trusted_forwarder", "local_policy") for r in row["reasons"]):
            g["forwarded"] += n
    out = []
    for key, g in groups.items():
        raw = [k.split(":", 1)[1] for k in sorted(g["raw_domains"], key=g["raw_domains"].get, reverse=True)]
        service = service_for(raw + [g["sample_name"] or ""])
        rate = g["pass"] / g["count"] if g["count"] else 0
        if rate >= 0.98:
            label = "passing"
        elif g["forwarded"] >= g["count"] / 2:
            label = "forwarded / mailing list"
        elif raw and not g["dkim_aligned"]:
            label = "legitimate, not aligned" if service or len(g["ips"]) > 1 else "authenticates as another domain"
        elif rate > 0.5:
            label = "mostly passing (some failures)"
        else:
            label = "unknown, failing"
        out.append({
            "source": g["sample_name"] or key, "group": key, "service": service, "label": label,
            "messages": g["count"], "pass_rate": round(rate, 4),
            "dkim_aligned_rate": round(g["dkim_aligned"] / g["count"], 4) if g["count"] else 0,
            "spf_aligned_rate": round(g["spf_aligned"] / g["count"], 4) if g["count"] else 0,
            "ips": sorted(g["ips"])[:10], "ip_count": len(g["ips"]),
            "authenticates_as": raw[:4], "dispositions": dict(g["dispositions"]), "header_from": dict(g["from"]),
        })
    return sorted(out, key=lambda s: -s["messages"])


def fmt_ts(ts):
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return "?"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="+", help="report files or directories")
    ap.add_argument("--resolve", action="store_true", help="look up reverse DNS for each source IP (slower)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    reports, rows = parse(args.paths)
    if not rows:
        print("no DMARC records found in the given files", file=sys.stderr)
        return 1
    names = {}
    if args.resolve:
        r = Resolver()
        for ip in sorted({row["ip"] for row in rows}):
            try:
                _, ptr = r.query(ipaddress.ip_address(ip).reverse_pointer, "PTR")
                if ptr:
                    names[ip] = ptr[0].rstrip(".")
            except ValueError:
                pass
    sources = summarize(rows, names)
    total = sum(s["messages"] for s in sources)
    failing = sum(round(s["messages"] * (1 - s["pass_rate"])) for s in sources)
    legit_failing = sum(round(s["messages"] * (1 - s["pass_rate"])) for s in sources
                        if s["label"] in ("legitimate, not aligned", "mostly passing (some failures)", "forwarded / mailing list"))
    domains = sorted({r["domain"] for r in reports if r["domain"]})
    policies = sorted({r["p"] for r in reports if r["p"]})
    begin = min((r["begin"] for r in reports if r["begin"]), default=None)
    end = max((r["end"] for r in reports if r["end"]), default=None)

    if args.json:
        print(json.dumps({"domains": domains, "policies": policies, "reports": len(reports), "period": [fmt_ts(begin), fmt_ts(end)],
                          "messages": total, "failing": failing, "sources": sources}, indent=2))
        return 0

    reporters = sorted({r["org"] for r in reports})
    print(f"== {', '.join(domains) or '?'}  policy p={'/'.join(policies) or '?'}  {fmt_ts(begin)} to {fmt_ts(end)}")
    print(f"   {len(reports)} reports from {', '.join(reporters[:6])}{' …' if len(reporters) > 6 else ''}")
    print(f"   {total:,} messages, {total - failing:,} passing DMARC ({(total - failing) / total:.1%})\n")
    print(f"{'messages':>9}  {'pass':>6}  {'dkim✓':>6}  {'spf✓':>6}  {'label':<30} source")
    for s in sources:
        svc = f" [{s['service']}]" if s["service"] else ""
        print(f"{s['messages']:>9,}  {s['pass_rate']:>6.0%}  {s['dkim_aligned_rate']:>6.0%}  {s['spf_aligned_rate']:>6.0%}  "
              f"{s['label']:<30} {s['source']}{svc} ({s['ip_count']} IP{'s' if s['ip_count'] != 1 else ''})")
        if s["label"] not in ("passing",) and s["authenticates_as"]:
            print(f"{'':>36}authenticates as: {', '.join(s['authenticates_as'])}")
    print()
    print(f"An enforcing policy would act on about {failing:,} messages ({failing / total:.1%}).")
    if legit_failing:
        print(f"About {legit_failing:,} of those look legitimate: set up aligned DKIM for those sources before tightening the policy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
