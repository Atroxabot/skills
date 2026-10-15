#!/usr/bin/env python3
"""Check a domain's email authentication records.

Looks up MX, SPF, DMARC, DKIM (at given and common selectors), MTA-STS,
TLS-RPT and BIMI, evaluates them the way receiving mail servers do, and
reports problems ranked FAIL / WARN / INFO. Read-only: it never changes DNS.

Usage:
    python3 check_domain.py example.com
    python3 check_domain.py example.com --selector s1 --selector k1
    python3 check_domain.py example.com --ip 203.0.113.7     # is this sending IP allowed?
    python3 check_domain.py example.com --json

DNS is resolved with dnspython if installed, else `dig`, else DNS-over-HTTPS
(Cloudflare, then Google), so it works in sandboxes without a resolver.
"""

import argparse
import base64
import concurrent.futures
import ipaddress
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

TYPES = {"A": 1, "NS": 2, "CNAME": 5, "PTR": 12, "MX": 15, "TXT": 16, "AAAA": 28}

# Selectors used by common senders. Probing is best effort: many providers
# use per-account selectors, so "none found" doesn't mean "no DKIM".
COMMON_SELECTORS = [
    "google", "selector1", "selector2", "default", "dkim", "mail", "smtp", "k1", "k2", "k3",
    "s1", "s2", "s1024", "s2048", "hs1", "hs2", "mandrill", "mxvault", "zoho", "zmail",
    "fm1", "fm2", "fm3", "protonmail", "protonmail2", "protonmail3", "cm", "sig1", "pm",
    "everlytickey1", "everlytickey2", "mailjet", "sendgrid", "turbo-smtp", "key1", "key2",
    "dkim1", "dkim2", "mx", "email", "smtpapi", "krs",
]

# Two-label public suffixes, for a best-effort organizational domain.
MULTI_SUFFIXES = set(
    "co.uk org.uk ac.uk gov.uk ltd.uk plc.uk me.uk net.uk com.au net.au org.au edu.au gov.au "
    "co.nz org.nz net.nz co.jp ne.jp or.jp ac.jp com.br net.br org.br com.mx org.mx co.za org.za "
    "co.in net.in org.in co.il org.il com.sg com.hk com.tr com.cn net.cn org.cn co.kr or.kr "
    "com.tw com.ar com.co com.pe com.ph com.my com.vn co.id co.th com.ua com.pl com.es com.pt".split()
)

MX_PROVIDERS = [
    (r"\.google(mail)?\.com\.?$|^smtp\.google\.com", "Google Workspace"),
    (r"\.mail\.protection\.outlook\.com\.?$|\.outlook\.com\.?$", "Microsoft 365"),
    (r"\.zoho\.(com|eu|in|com\.au)\.?$", "Zoho Mail"),
    (r"\.messagingengine\.com\.?$", "Fastmail"),
    (r"\.protonmail\.ch\.?$", "Proton Mail"),
    (r"\.pphosted\.com\.?$", "Proofpoint"),
    (r"\.mimecast\.com\.?$", "Mimecast"),
    (r"\.barracudanetworks\.com\.?$", "Barracuda"),
    (r"\.icloud\.com\.?$", "iCloud Mail"),
    (r"\.secureserver\.net\.?$", "GoDaddy"),
    (r"\.ovh\.net\.?$", "OVH"),
    (r"\.yandex\.net\.?$", "Yandex"),
    (r"amazonaws\.com\.?$", "Amazon SES / WorkMail"),
]


def org_domain(domain):
    labels = domain.lower().rstrip(".").split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in MULTI_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


# ---------------- DNS ----------------

def split_txt(data):
    """Join the quoted character-strings of a TXT record."""
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', data)
    if not parts:
        return data
    return "".join(re.sub(r"\\(.)", r"\1", p) for p in parts)


class Resolver:
    def __init__(self, method="auto"):
        self.cache = {}
        self.errors = []
        self.method = method
        if method == "auto":
            try:
                import dns.resolver  # noqa: F401
                self.method = "dnspython"
            except ImportError:
                self.method = "dig" if shutil.which("dig") else "doh"

    def query(self, name, rtype):
        """Return (status, [answers]). Status: NOERROR, NXDOMAIN, SERVFAIL or ERROR."""
        key = (name.lower().rstrip("."), rtype)
        if key not in self.cache:
            try:
                self.cache[key] = getattr(self, "_" + self.method)(key[0], rtype)
            except Exception as exc:  # network trouble shouldn't kill the report
                self.errors.append(f"{key[0]} {rtype}: {exc}")
                self.cache[key] = ("ERROR", [])
        return self.cache[key]

    def _dnspython(self, name, rtype):
        import dns.resolver
        try:
            ans = dns.resolver.resolve(name, rtype, raise_on_no_answer=False)
        except dns.resolver.NXDOMAIN:
            return "NXDOMAIN", []
        except (dns.resolver.NoNameservers, dns.resolver.LifetimeTimeout):
            return "SERVFAIL", []
        out = []
        for r in ans:
            if rtype == "TXT":
                out.append(b"".join(r.strings).decode("utf-8", "replace"))
            elif rtype == "MX":
                out.append(f"{r.preference} {r.exchange.to_text()}")
            else:
                out.append(r.to_text())
        return "NOERROR", out

    def _dig(self, name, rtype):
        res = subprocess.run(["dig", "+noall", "+comments", "+answer", "+time=3", "+tries=2", name, rtype],
                             capture_output=True, text=True, timeout=20)
        m = re.search(r"status: (\w+)", res.stdout)
        status = m.group(1) if m else "ERROR"
        out = []
        for line in res.stdout.splitlines():
            if not line or line.startswith(";"):
                continue
            fields = line.split(None, 4)
            if len(fields) == 5 and fields[3] == rtype:
                out.append(split_txt(fields[4]) if rtype == "TXT" else fields[4])
        return status, out

    def _doh(self, name, rtype):
        last = None
        for url in ("https://cloudflare-dns.com/dns-query", "https://dns.google/resolve"):
            try:
                q = urllib.parse.urlencode({"name": name, "type": rtype})
                req = urllib.request.Request(f"{url}?{q}", headers={"accept": "application/dns-json"})
                with urllib.request.urlopen(req, timeout=10) as fh:
                    data = json.load(fh)
                status = {0: "NOERROR", 2: "SERVFAIL", 3: "NXDOMAIN"}.get(data.get("Status"), "ERROR")
                out = [split_txt(a["data"]) if rtype == "TXT" else a["data"]
                       for a in data.get("Answer", []) if a.get("type") == TYPES[rtype]]
                return status, out
            except Exception as exc:
                last = exc
        raise RuntimeError(f"DNS-over-HTTPS failed: {last}")


# ---------------- report ----------------

class Report:
    def __init__(self, domain):
        self.domain = domain
        self.items = []
        self.data = {}

    def add(self, level, area, message):
        self.items.append({"level": level, "area": area, "message": message})


# ---------------- SPF ----------------

MECHS = {"all", "include", "a", "mx", "ptr", "ip4", "ip6", "exists"}


def spf_records(resolver, domain):
    status, txts = resolver.query(domain, "TXT")
    return status, [t for t in txts if re.match(r"(?i)^v=spf1(\s|$)", t.strip())]


class SpfWalk:
    def __init__(self, resolver):
        self.r = resolver
        self.lookups = 0
        self.voids = 0
        self.errors = []
        self.warnings = []
        self.networks = []   # (network, path)
        self.unknown = []    # terms we can't evaluate offline (macros, exists, ptr)
        self.tree = []
        self.data_all = None

    def walk(self, domain, depth=0, path=()):
        if depth > 10:
            self.errors.append(f"include chain deeper than 10 at {domain} (loop?)")
            return
        status, recs = spf_records(self.r, domain)
        if not recs:
            if depth:
                self.errors.append(f"{' → '.join(path)} points to {domain}, which has no SPF record: receivers treat that as a permanent error")
                if status == "NXDOMAIN" or not self.r.query(domain, "TXT")[1]:
                    self.voids += 1
            return
        if len(recs) > 1:
            self.errors.append(f"{domain} has {len(recs)} SPF records; receivers treat more than one as a permanent error")
        record = recs[0]
        self.tree.append((depth, domain, record))
        terms = record.split()[1:]
        seen_all = False
        redirect = None
        for term in terms:
            if seen_all:
                self.warnings.append(f"'{term}' in {domain} comes after 'all' and is ignored")
                continue
            m = re.match(r"^([+\-~?]?)([a-zA-Z0-9]+)([:=/]?)(.*)$", term)
            if not m:
                self.errors.append(f"can't parse '{term}' in {domain}")
                continue
            qual, name, sep, arg = m.groups()
            name = name.lower()
            here = path + (domain,)
            if sep == "=":
                if name == "redirect":
                    redirect = arg
                elif name not in ("exp",):
                    self.warnings.append(f"unknown modifier '{term}' in {domain}")
                continue
            if name not in MECHS:
                self.errors.append(f"unknown mechanism '{term}' in {domain} (typo?) makes the whole record invalid")
                continue
            target = arg if sep == ":" else domain
            if "%{" in term:
                self.lookups += 1 if name in ("include", "a", "mx", "ptr", "exists") else 0
                self.unknown.append(f"{term} (macro, evaluated per message)")
                continue
            if name == "all":
                seen_all = True
                if qual in ("", "+"):
                    self.errors.append(f"'{term}' in {domain} authorizes every server on the internet to send as you")
                if depth == 0:
                    self.data_all = qual or "+"
            elif name == "include":
                self.lookups += 1
                self.walk(arg, depth + 1, here)
            elif name in ("a", "mx"):
                self.lookups += 1
                spec = target if sep == ":" else domain + ("/" + arg if sep == "/" else "")
                m2 = re.match(r"^([^/]*)(?:/(\d+))?(?://(\d+))?$", spec)
                if not m2:
                    self.errors.append(f"can't parse '{term}' in {domain}")
                    continue
                self._addresses(name, m2.group(1), (m2.group(2), m2.group(3)), here, term)
            elif name == "ptr":
                self.lookups += 1
                self.warnings.append(f"'ptr' in {domain} is deprecated (RFC 7208): slow, unreliable, and some receivers ignore it")
                self.unknown.append(term)
            elif name == "exists":
                self.lookups += 1
                self.unknown.append(term)
            elif name in ("ip4", "ip6"):
                try:
                    net = ipaddress.ip_network(arg, strict=False)
                    self.networks.append((net, " → ".join(here)))
                except ValueError:
                    self.errors.append(f"'{term}' in {domain} isn't a valid address or range")
        if redirect and not seen_all:
            self.lookups += 1
            self.walk(redirect, depth + 1, path + (domain,))
        elif redirect and seen_all:
            self.warnings.append(f"redirect= in {domain} is ignored because the record has 'all'")
        if depth == 0 and not seen_all and not redirect:
            self.warnings.append("SPF record has no 'all' and no redirect: unlisted servers get 'neutral', which protects nothing")

    def _addresses(self, kind, host, cidr, path, term):
        hosts = [host]
        if kind == "mx":
            status, mx = self.r.query(host, "MX")
            hosts = [m.split()[-1].rstrip(".") for m in mx if m.split()[-1] != "."]
            if len(hosts) > 10:
                self.errors.append(f"'{term}' expands to more than 10 MX hosts: permanent error")
            if not hosts:
                self.voids += 1
                return
        for h in hosts:
            found = False
            for rtype in ("A", "AAAA"):
                status, addrs = self.r.query(h, rtype)
                for a in addrs:
                    try:
                        bits = cidr[0] if rtype == "A" else cidr[1]
                        net = ipaddress.ip_network(f"{a}/{bits}" if bits else a, strict=False)
                        self.networks.append((net, " → ".join(path) + f" ({term} {h})"))
                        found = True
                    except ValueError:
                        pass
            if not found and kind == "a":
                self.voids += 1


def check_spf(r, domain, report, ip=None):
    status, recs = spf_records(r, domain)
    report.data["spf"] = recs
    if status == "NXDOMAIN":
        report.add("FAIL", "SPF", f"{domain} doesn't exist in DNS")
        return
    if not recs:
        if org_domain(domain) != domain:
            report.add("WARN", "SPF", "no SPF record on this subdomain: fine if it never sends mail, required if it does (including as a bounce domain)")
        else:
            report.add("FAIL", "SPF", "no SPF record. Receivers can't tell which servers may send as this domain")
        return
    walk = SpfWalk(r)
    walk.walk(domain)
    report.data["spf_tree"] = [{"depth": d, "domain": n, "record": rec} for d, n, rec in walk.tree]
    report.data["spf_lookups"] = walk.lookups
    for e in walk.errors:
        report.add("FAIL", "SPF", e)
    for w in walk.warnings:
        report.add("WARN", "SPF", w)
    if walk.lookups > 10:
        report.add("FAIL", "SPF", f"{walk.lookups} DNS lookups; the limit is 10, so receivers return a permanent error and SPF fails for all mail. Remove unused includes, or move a sender to a subdomain")
    elif walk.lookups >= 8:
        report.add("WARN", "SPF", f"{walk.lookups} of 10 DNS lookups used; one more provider include may break SPF")
    else:
        report.add("OK", "SPF", f"{walk.lookups} of 10 DNS lookups used")
    if walk.voids > 2:
        report.add("FAIL", "SPF", f"{walk.voids} lookups returned nothing; more than 2 is a permanent error")
    q = walk.data_all
    if q == "?":
        report.add("WARN", "SPF", "'?all' (neutral) gives no protection; use '~all' or '-all'")
    elif q in ("~", "-"):
        report.add("OK", "SPF", f"ends with '{q}all'")
    if ip:
        addr = ipaddress.ip_address(ip)
        hits = [p for net, p in walk.networks if addr.version == net.version and addr in net]
        if hits:
            report.add("OK", "SPF", f"{ip} is authorized via {hits[0]}")
        elif walk.unknown:
            report.add("WARN", "SPF", f"{ip} isn't in any listed range; can't evaluate {', '.join(walk.unknown[:3])} offline")
        else:
            report.add("FAIL", "SPF", f"{ip} is not authorized by this SPF record: mail from it fails SPF")


# ---------------- DMARC ----------------

DMARC_TAGS = {"v", "p", "sp", "np", "pct", "rua", "ruf", "adkim", "aspf", "fo", "rf", "ri", "t", "psd"}


def parse_tags(record):
    tags = {}
    for part in record.split(";"):
        if "=" in part:
            k, _, v = part.partition("=")
            tags[k.strip().lower()] = v.strip()
    return tags


def check_dmarc(r, domain, report):
    org = org_domain(domain)
    where = domain
    status, txts = r.query(f"_dmarc.{domain}", "TXT")
    recs = [t for t in txts if re.match(r"(?i)^v=DMARC1\s*(;|$)", t.strip())]
    if not recs and org != domain:
        where = org
        status, txts = r.query(f"_dmarc.{org}", "TXT")
        recs = [t for t in txts if re.match(r"(?i)^v=DMARC1\s*(;|$)", t.strip())]
    report.data["dmarc"] = recs
    if not recs:
        bad = [t for t in txts if "dmarc" in t.lower()]
        if bad:
            report.add("FAIL", "DMARC", f"record at _dmarc.{where} doesn't start with 'v=DMARC1': {bad[0]!r}")
        else:
            report.add("FAIL", "DMARC", "no DMARC record. Anyone can send mail showing this domain in From, and Gmail, Yahoo and Outlook require DMARC from bulk senders")
        return None
    if len(recs) > 1:
        report.add("FAIL", "DMARC", f"{len(recs)} DMARC records at _dmarc.{where}; receivers ignore all of them")
    tags = parse_tags(recs[0])
    sub_note = f" (inherited from {org}; sp= applies to subdomains)" if where != domain else ""
    unknown = set(tags) - DMARC_TAGS
    if unknown:
        report.add("WARN", "DMARC", f"unknown tags {', '.join(sorted(unknown))} (typo?)")
    p = tags.get("p", "").lower()
    policy = tags.get("sp", p).lower() if where != domain else p
    if p not in ("none", "quarantine", "reject"):
        report.add("FAIL", "DMARC", f"p= is missing or invalid ({tags.get('p')!r}); it must be none, quarantine or reject")
    elif policy == "none":
        report.add("WARN", "DMARC", f"policy is p=none{sub_note}: monitoring only, spoofed mail is still delivered. Fine as a first step while reading reports")
    else:
        report.add("OK", "DMARC", f"policy is {policy}{sub_note}")
    if p in ("quarantine", "reject") and tags.get("sp", "").lower() == "none":
        report.add("WARN", "DMARC", "sp=none leaves every subdomain spoofable even though the main domain is protected")
    pct = tags.get("pct")
    if pct and pct != "100":
        report.add("INFO", "DMARC", f"pct={pct}: the policy applies to only part of failing mail. The DMARC revision (DMARCbis) drops pct, so treat it as a ramp, not a permanent setting")
    if tags.get("t", "").lower() == "y":
        report.add("INFO", "DMARC", "t=y: testing mode (DMARCbis); receivers apply a weaker policy")
    rua = [u.strip() for u in tags.get("rua", "").split(",") if u.strip()]
    if not rua:
        report.add("WARN", "DMARC", "no rua= address, so no aggregate reports: you can't see who sends as your domain or what fails")
    for uri in rua:
        m = re.match(r"(?i)mailto:([^@!]+)@([^!]+)", uri)
        if not m:
            report.add("WARN", "DMARC", f"rua entry {uri!r} isn't a mailto: address")
            continue
        dest = m.group(2).lower()
        if org_domain(dest) != org_domain(where):
            name = f"{where}._report._dmarc.{dest}"
            _, auth = r.query(name, "TXT")
            if not any(a.lower().startswith("v=dmarc1") for a in auth):
                report.add("WARN", "DMARC", f"reports go to {dest}, which hasn't authorized them ({name} has no v=DMARC1 record), so receivers won't send them")
    if tags.get("ruf"):
        report.add("INFO", "DMARC", "ruf= (failure reports) is set; most large receivers don't send these, so don't rely on them")
    for t in ("adkim", "aspf"):
        if tags.get(t, "r").lower() == "s":
            report.add("INFO", "DMARC", f"{t}=s (strict): subdomains such as a bounce domain won't align; relaxed is the usual choice")
    report.data["dmarc_tags"] = tags
    return tags


# ---------------- DKIM ----------------

def der_rsa_bits(der):
    """Modulus size of an RSA key in SubjectPublicKeyInfo or PKCS#1 DER."""
    def read(buf, i):
        tag = buf[i]
        length = buf[i + 1]
        i += 2
        if length & 0x80:
            n = length & 0x7F
            length = int.from_bytes(buf[i:i + n], "big")
            i += n
        return tag, i, length

    def first_int(buf, i, end):
        while i < end:
            tag, start, length = read(buf, i)
            if tag == 0x02:
                body = buf[start:start + length].lstrip(b"\x00")
                return len(body) * 8 - (8 - body[0].bit_length()) if body else 0
            found = None
            if tag == 0x30:
                found = first_int(buf, start, start + length)
            elif tag == 0x03:  # BIT STRING: skip the unused-bits byte
                found = first_int(buf, start + 1, start + length)
            if found:
                return found
            i = start + length
        return None
    try:
        return first_int(der, 0, len(der))
    except (IndexError, ValueError):
        return None


def check_selector(r, domain, sel):
    status, txts = r.query(f"{sel}._domainkey.{domain}", "TXT")
    recs = [t for t in txts if "p=" in t]
    return sel, recs


def check_dkim(r, domain, selectors, report):
    _, probe = check_selector(r, domain, "zz-no-such-selector-7f3a")
    if probe:
        report.add("INFO", "DKIM", "every selector name answers with the same record (a wildcard), so probing can't find real keys; "
                   "take the selector from a sent message's DKIM-Signature header (s=) and re-run with --selector")
        wildcard = probe[0]
    else:
        wildcard = None
    found = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for sel, recs in pool.map(lambda s: check_selector(r, domain, s), selectors):
            for rec in recs:
                if rec != wildcard:
                    found.append((sel, rec))
    report.data["dkim"] = {s: rec for s, rec in found}
    if not found and wildcard:
        return
    if not found:
        report.add("WARN", "DKIM", f"no DKIM key at {len(selectors)} common selectors. That doesn't prove there is none: "
                   "find the real selector in a sent message's DKIM-Signature header (s=) and re-run with --selector")
        return
    for sel, rec in found:
        tags = parse_tags(rec)
        p = re.sub(r"\s", "", tags.get("p", ""))
        k = tags.get("k", "rsa").lower()
        name = f"{sel}._domainkey"
        if not p:
            report.add("INFO", "DKIM", f"{name}: key revoked (empty p=)")
            continue
        if tags.get("t", "").lower().startswith("y"):
            report.add("INFO", "DKIM", f"{name}: t=y testing mode; some receivers treat signatures as unsigned")
        if k == "ed25519":
            report.add("OK", "DKIM", f"{name}: Ed25519 key (sign with RSA too: not every receiver verifies Ed25519)")
            continue
        try:
            bits = der_rsa_bits(base64.b64decode(p + "=" * (-len(p) % 4)))
        except Exception:
            bits = None
        if not bits:
            report.add("FAIL", "DKIM", f"{name}: the public key doesn't decode (truncated or mangled when pasted into DNS?)")
        elif bits < 1024:
            report.add("FAIL", "DKIM", f"{name}: {bits}-bit RSA key; receivers reject keys under 1024 bits")
        elif bits < 2048:
            report.add("WARN", "DKIM", f"{name}: {bits}-bit RSA key works but is the minimum; rotate to 2048 when convenient")
        else:
            report.add("OK", "DKIM", f"{name}: {bits}-bit RSA key")


# ---------------- MX, MTA-STS, TLS-RPT, BIMI, PTR ----------------

def check_mx(r, domain, report):
    status, mx = r.query(domain, "MX")
    hosts = sorted((int(m.split()[0]), m.split()[1].rstrip(".")) for m in mx if len(m.split()) == 2)
    report.data["mx"] = hosts
    if any(h == "" or h == "." for _, h in hosts) or (len(hosts) == 1 and hosts[0][1] in ("", ".")):
        report.add("INFO", "MX", "null MX (RFC 7505): this domain declares it receives no mail")
        return hosts, True
    if not hosts:
        report.add("WARN", "MX", "no MX record: mail to this domain (replies, bounces) can't be delivered")
        return hosts, False
    providers = sorted({name for _, h in hosts for pat, name in MX_PROVIDERS if re.search(pat, h, re.I)})
    report.add("OK", "MX", ", ".join(h for _, h in hosts) + (f" ({', '.join(providers)})" if providers else ""))
    for _, h in hosts:
        if not r.query(h, "A")[1] and not r.query(h, "AAAA")[1]:
            report.add("FAIL", "MX", f"{h} has no address record: mail to it fails")
    return hosts, False


def mx_matches(pattern, host):
    pattern, host = pattern.lower().rstrip("."), host.lower().rstrip(".")
    if pattern.startswith("*."):
        return host.endswith(pattern[1:]) and host.count(".") == pattern.count(".")
    return host == pattern


def check_mta_sts(r, domain, hosts, report):
    _, txts = r.query(f"_mta-sts.{domain}", "TXT")
    rec = [t for t in txts if t.lower().startswith("v=stsv1")]
    _, tls = r.query(f"_smtp._tls.{domain}", "TXT")
    if not any(t.lower().startswith("v=tlsrptv1") for t in tls):
        report.add("INFO", "TLS-RPT", "no TLS reporting record (_smtp._tls); optional, but it tells you when encrypted delivery to you fails")
    if not rec:
        report.add("INFO", "MTA-STS", "not set up; optional, it stops attackers downgrading mail delivered to you to unencrypted")
        return
    url = f"https://mta-sts.{domain}/.well-known/mta-sts.txt"
    try:
        with urllib.request.urlopen(url, timeout=10) as fh:
            policy = fh.read(65536).decode("utf-8", "replace")
    except Exception as exc:
        report.add("FAIL", "MTA-STS", f"TXT record exists but the policy at {url} can't be fetched ({exc})")
        return
    fields = {}
    patterns = []
    for line in policy.splitlines():
        k, _, v = line.partition(":")
        if k.strip() == "mx":
            patterns.append(v.strip())
        elif k.strip():
            fields[k.strip()] = v.strip()
    mode = fields.get("mode")
    if mode == "enforce":
        missing = [h for _, h in hosts if not any(mx_matches(p, h) for p in patterns)]
        if missing:
            report.add("FAIL", "MTA-STS", f"mode enforce, but MX {', '.join(missing)} isn't listed in the policy: senders will refuse to deliver to it")
        else:
            report.add("OK", "MTA-STS", "mode enforce, all MX hosts covered")
    else:
        report.add("INFO", "MTA-STS", f"mode {mode or '?'} (not enforcing yet)")


def check_bimi(r, domain, dmarc, report):
    _, txts = r.query(f"default._bimi.{domain}", "TXT")
    rec = [t for t in txts if t.lower().startswith("v=bimi1")]
    if not rec:
        return
    tags = parse_tags(rec[0])
    if not dmarc or dmarc.get("p", "").lower() not in ("quarantine", "reject") or dmarc.get("pct", "100") != "100":
        report.add("WARN", "BIMI", "BIMI logo record exists but DMARC isn't at quarantine or reject with pct=100, so no mailbox will show the logo")
    elif not tags.get("a"):
        report.add("INFO", "BIMI", "no a= certificate (VMC or CMC): Gmail and Apple Mail won't show the logo without one")
    else:
        report.add("OK", "BIMI", "logo record and certificate present")


def check_ptr(r, ip, report):
    addr = ipaddress.ip_address(ip)
    _, names = r.query(addr.reverse_pointer, "PTR")
    if not names:
        report.add("FAIL", "PTR", f"{ip} has no reverse DNS name; Gmail and others reject or junk mail from such IPs")
        return
    name = names[0].rstrip(".")
    _, fwd = r.query(name, "A" if addr.version == 4 else "AAAA")
    if ip in fwd:
        report.add("OK", "PTR", f"{ip} ↔ {name} (forward-confirmed)")
    else:
        report.add("FAIL", "PTR", f"{ip} reverses to {name}, but {name} doesn't resolve back to {ip}")


# ---------------- driver ----------------

def run(domain, selectors, ip, method):
    r = Resolver(method)
    report = Report(domain)
    report.data["resolver"] = r.method
    if r.query(domain, "TXT")[0] == "NXDOMAIN" and not r.query(domain, "MX")[1]:
        report.add("FAIL", "DNS", f"{domain} doesn't exist in DNS (typo, or not registered?)")
        return report
    hosts, null_mx = check_mx(r, domain, report)
    check_spf(r, domain, report, ip)
    dmarc = check_dmarc(r, domain, report)
    check_dkim(r, domain, list(dict.fromkeys(selectors + COMMON_SELECTORS)), report)
    if not null_mx and hosts:
        check_mta_sts(r, domain, hosts, report)
    check_bimi(r, domain, dmarc, report)
    if ip:
        check_ptr(r, ip, report)
    if null_mx:
        spf = " ".join(report.data.get("spf", []))
        if spf.strip().lower() != "v=spf1 -all":
            report.add("WARN", "Parked", "domain receives no mail; if it sends none either, publish 'v=spf1 -all' and DMARC p=reject")
    if r.errors:
        report.add("WARN", "DNS", f"{len(r.errors)} lookups failed, so results may be incomplete (first: {r.errors[0]})")
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("domain")
    ap.add_argument("--selector", "-s", action="append", default=[], help="DKIM selector to check (repeatable)")
    ap.add_argument("--ip", help="a sending IP to test against SPF and reverse DNS")
    ap.add_argument("--resolver", default="auto", choices=["auto", "dnspython", "dig", "doh"])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    domain = args.domain.lower().strip().rstrip(".")
    domain = re.sub(r"^(https?://)?(www\.)?", "", domain).split("/")[0]
    if "@" in domain:
        domain = domain.split("@")[1]
    report = run(domain, args.selector, args.ip, args.resolver)
    if args.json:
        print(json.dumps({"domain": domain, "findings": report.items, "data": report.data}, indent=2, default=str))
    else:
        print(f"== {domain}  (DNS via {report.data['resolver']})")
        order = {"FAIL": 0, "WARN": 1, "OK": 2, "INFO": 3}
        for area in ("MX", "SPF", "DMARC", "DKIM", "MTA-STS", "TLS-RPT", "BIMI", "PTR", "Parked", "DNS"):
            for item in sorted((i for i in report.items if i["area"] == area), key=lambda i: order[i["level"]]):
                print(f"  {item['level']:<4}  {area:<8} {item['message']}")
        if report.data.get("spf_tree"):
            print("\nSPF tree:")
            for node in report.data["spf_tree"]:
                print(f"  {'  ' * node['depth']}{node['domain']}: {node['record']}")
        if report.data.get("dmarc"):
            print(f"\nDMARC: {report.data['dmarc'][0]}")
        fails = sum(1 for i in report.items if i["level"] == "FAIL")
        warns = sum(1 for i in report.items if i["level"] == "WARN")
        print(f"\n{fails} fail, {warns} warn")
    return 1 if any(i["level"] == "FAIL" for i in report.items) else 0


if __name__ == "__main__":
    sys.exit(main())
