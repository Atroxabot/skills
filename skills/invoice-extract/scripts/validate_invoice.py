#!/usr/bin/env python3
"""Validate extracted invoice data.

Reads invoice JSON in the shape described in references/schema.md and checks
it: line and tax arithmetic, totals, signs, currency decimals, dates and
payment terms, IBAN and BIC, tax ID formats, duplicates across a batch, and
bank details against a list of known vendors.

Usage:
    python3 validate_invoice.py invoice.json
    python3 validate_invoice.py batch/*.json --known-vendors vendors.json --csv out.csv
    python3 validate_invoice.py invoice.json --json        # machine-readable findings
    python3 validate_invoice.py --amount "1.234,56"        # how could this number be read?

Each input file may hold one invoice object or a list of them. Exit status is
1 if any check FAILs, else 0.

FAIL means the numbers or IDs are inconsistent: re-read the document before
blaming the supplier, since most failures are reading errors. WARN means
something needs a person's look. INFO is context.
"""

import argparse
import csv
import json
import math
import re
import sys
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# ISO 4217 minor units that differ from the usual 2.
MINOR_UNITS = {
    **{c: 0 for c in "BIF CLP DJF GNF ISK JPY KMF KRW PYG RWF UGX UYI VND VUV XAF XOF XPF".split()},
    **{c: 3 for c in "BHD IQD JOD KWD LYD OMR TND".split()},
}

# IBAN lengths by country, from the SWIFT IBAN registry.
IBAN_LENGTHS = {
    "AD": 24, "AE": 23, "AL": 28, "AT": 20, "AZ": 28, "BA": 20, "BE": 16, "BG": 22,
    "BH": 22, "BI": 27, "BR": 29, "BY": 28, "CH": 21, "CR": 22, "CY": 28, "CZ": 24,
    "DE": 22, "DJ": 27, "DK": 18, "DO": 28, "EE": 20, "EG": 29, "ES": 24, "FI": 18,
    "FK": 18, "FO": 18, "FR": 27, "GB": 22, "GE": 22, "GI": 23, "GL": 18, "GR": 27,
    "GT": 28, "HR": 21, "HU": 28, "IE": 22, "IL": 23, "IQ": 23, "IS": 26, "IT": 27,
    "JO": 30, "KW": 30, "KZ": 20, "LB": 28, "LC": 32, "LI": 21, "LT": 20, "LU": 20,
    "LV": 21, "LY": 25, "MC": 27, "MD": 24, "ME": 22, "MK": 19, "MN": 20, "MR": 27,
    "MT": 31, "MU": 30, "NI": 28, "NL": 18, "NO": 15, "OM": 23, "PK": 24, "PL": 28,
    "PS": 29, "PT": 25, "QA": 29, "RO": 24, "RS": 22, "RU": 33, "SA": 24, "SC": 31,
    "SD": 18, "SE": 24, "SI": 19, "SK": 24, "SM": 27, "SO": 23, "ST": 25, "SV": 28,
    "TL": 23, "TN": 24, "TR": 26, "UA": 29, "VA": 22, "VG": 24, "XK": 20, "YE": 30,
}

# VAT number formats (after the country prefix). A match means well-formed,
# not registered: VIES (EU) or HMRC (UK) confirm registration.
VAT_FORMATS = {
    "AT": r"U\d{8}", "BE": r"[01]\d{9}", "BG": r"\d{9,10}", "CY": r"\d{8}[A-Z]",
    "CZ": r"\d{8,10}", "DE": r"\d{9}", "DK": r"\d{8}", "EE": r"\d{9}", "EL": r"\d{9}",
    "ES": r"[A-Z0-9]\d{7}[A-Z0-9]", "FI": r"\d{8}", "FR": r"[A-HJ-NP-Z0-9]{2}\d{9}",
    "HR": r"\d{11}", "HU": r"\d{8}", "IE": r"\d{7}[A-W][A-IW]?|\d[A-Z+*]\d{5}[A-W]",
    "IT": r"\d{11}", "LT": r"\d{9}|\d{12}", "LU": r"\d{8}", "LV": r"\d{11}", "MT": r"\d{8}",
    "NL": r"\d{9}B\d{2}", "PL": r"\d{10}", "PT": r"\d{9}", "RO": r"\d{2,10}",
    "SE": r"\d{10}01", "SI": r"\d{8}", "SK": r"\d{10}",
    "GB": r"\d{9}|\d{12}|GD\d{3}|HA\d{3}", "XI": r"\d{9}|\d{12}|GD\d{3}|HA\d{3}",
    "CHE": r"\d{9}(MWST|TVA|IVA)?", "NO": r"\d{9}(MVA)?",
}

OTHER_ID_FORMATS = {
    "GSTIN": (r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]", "India GSTIN"),
    "T-NUMBER": (r"T\d{13}", "Japan qualified invoice registration number"),
    "EIN": (r"\d{9}", "US EIN"),
    "TRN": (r"\d{15}", "UAE TRN"),
}

LEGAL_SUFFIXES = set(
    "gmbh mbh ag kg ohg ug ltd limited inc incorporated llc llp plc co corp corporation company "
    "sa sas sarl sarlu srl spa bv nv ab oy oyj as asa aps kft sp zoo the pty".split()
)

LEVELS = ("FAIL", "WARN", "INFO")


class Report:
    def __init__(self, label):
        self.label = label
        self.findings = []

    def add(self, level, area, message):
        self.findings.append({"level": level, "area": area, "message": message})

    def worst(self):
        for level in LEVELS[:2]:
            if any(f["level"] == level for f in self.findings):
                return level
        return "OK"


# ---------- small helpers ----------

def get(obj, path, default=None):
    for part in path.split("."):
        if isinstance(obj, dict):
            obj = obj.get(part)
        elif isinstance(obj, list) and part.isdigit() and int(part) < len(obj):
            obj = obj[int(part)]
        else:
            return default
        if obj is None:
            return default
    return default if obj == "" else obj


CANONICAL = re.compile(r"^-?\d+(\.\d+)?$")


def dec(value, report, area):
    """Parse a canonical decimal string. Reports non-canonical input."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        report.add("FAIL", area, f"expected a decimal string, got {value!r}")
        return None
    if isinstance(value, float):
        report.add("WARN", area, f"{value!r} is a float; write amounts as strings to keep cents exact")
        value = repr(value)
    if isinstance(value, int):
        value = str(value)
    text = str(value).strip()
    if not CANONICAL.match(text):
        report.add("FAIL", area, f"{text!r} isn't a canonical decimal (use '1234.56': no thousands separators, '.' for decimals)")
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        report.add("FAIL", area, f"can't parse {text!r}")
        return None


def money(x, places):
    return x.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def fmt(x):
    return f"{x:,}" if x is not None else "?"


def tolerance(unit, count):
    """Allowed rounding drift: half a minor unit per rounded amount, at least one unit."""
    return unit * max(1, math.ceil(count * 0.5))


def norm_id(value):
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def norm_name(value):
    words = re.sub(r"[^a-z0-9 ]", " ", str(value).lower()).split()
    return " ".join(w for w in words if w not in LEGAL_SUFFIXES)


def parse_date(value, report, area):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        report.add("FAIL", area, f"{value!r} isn't an ISO date (YYYY-MM-DD)")
        return None


# ---------- identifiers ----------

def iban_ok(iban):
    """Return (ok, message)."""
    iban = norm_id(iban)
    if len(iban) < 5 or not iban[:2].isalpha() or not iban[2:4].isdigit():
        return False, f"{iban} doesn't look like an IBAN"
    country = iban[:2]
    expected = IBAN_LENGTHS.get(country)
    if expected and len(iban) != expected:
        return False, f"{iban} has {len(iban)} characters; {country} IBANs have {expected}"
    rearranged = iban[4:] + iban[:4]
    digits = "".join(str(int(ch, 36)) for ch in rearranged)
    if int(digits) % 97 != 1:
        return False, f"{iban} fails the mod-97 checksum: a character is misread or mistyped"
    if not expected:
        return True, f"{iban} passes the checksum (length not checked for {country})"
    return True, ""


def abn_ok(value):
    digits = [int(c) for c in re.sub(r"\D", "", str(value))]
    if len(digits) != 11:
        return False
    digits[0] -= 1
    weights = (10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19)
    return sum(d * w for d, w in zip(digits, weights)) % 89 == 0


def check_tax_id(entry, party, report):
    if isinstance(entry, str):
        entry = {"type": "", "value": entry}
    raw = entry.get("value") or ""
    kind = (entry.get("type") or "").upper()
    value = norm_id(raw)
    area = f"{party}.tax_ids"
    if not value or kind in ("COMPANY_REGISTRATION", "REGISTRATION_NUMBER"):
        return
    if kind == "ABN" or (kind in ("", "GST") and len(value) == 11 and value.isdigit()):
        if abn_ok(value):
            return
        if kind == "ABN":
            report.add("FAIL", area, f"ABN {raw} fails its checksum")
            return
    for key, (pattern, label) in OTHER_ID_FORMATS.items():
        if kind in (key, key.replace("-", "")) or (key == "T-NUMBER" and value.startswith("T") and kind in ("", "T-NUMBER", "REGISTRATION")):
            if not re.fullmatch(pattern, value):
                report.add("WARN", area, f"{raw} doesn't match the {label} format")
            return
    for prefix in sorted(VAT_FORMATS, key=len, reverse=True):
        if value.startswith(prefix):
            body = value[len(prefix):]
            if not re.fullmatch(VAT_FORMATS[prefix], body):
                report.add("WARN", area, f"{raw} doesn't match the {prefix} VAT number format (misread, or not a VAT number?)")
            return
    if value.startswith("GR"):
        report.add("WARN", area, f"{raw}: Greek VAT numbers use the prefix EL, not GR")
    elif kind in ("VAT", "UID", "MWST", "TVA", "IVA", "USTIDNR") and value[:2].isalpha():
        report.add("INFO", area, f"{raw}: no format rule for prefix {value[:2]}")


# ---------- checks ----------

PAYABLE = {"invoice", "credit_note"}
NOT_PAYABLE = {"proforma": "a pro-forma is not a tax invoice; pay the real invoice instead",
               "statement": "a statement lists other invoices; it isn't a new invoice",
               "quote": "a quote isn't payable",
               "order_confirmation": "an order confirmation isn't payable"}


def check_document_type(doc, report):
    kind = doc.get("document_type")
    if not kind:
        report.add("WARN", "document_type", "missing: classify the document before anyone pays it")
    elif kind in NOT_PAYABLE:
        report.add("WARN", "document_type", NOT_PAYABLE[kind])
    elif kind == "reminder":
        report.add("INFO", "document_type", "a reminder refers to an existing invoice; make sure it isn't processed twice")
    elif kind == "receipt":
        report.add("INFO", "document_type", "a receipt records a payment already made; it isn't payable")
    if kind in PAYABLE:
        for path in ("invoice_number", "issue_date", "currency", "supplier.name"):
            if get(doc, path) is None:
                report.add("WARN", path, "missing")
        if get(doc, "totals.gross") is None and get(doc, "totals.amount_due") is None:
            report.add("WARN", "totals", "no gross total or amount due")
    if kind == "credit_note" and not doc.get("original_invoice_number"):
        report.add("INFO", "original_invoice_number", "credit note doesn't name the invoice it corrects")


def check_currency(doc, report):
    cur = doc.get("currency")
    if cur and not re.fullmatch(r"[A-Z]{3}", str(cur)):
        report.add("WARN", "currency", f"{cur!r} isn't an ISO 4217 code (use EUR, USD, GBP...)")
    places = MINOR_UNITS.get(str(cur or "").upper(), 2)
    return places, Decimal(1).scaleb(-places)


def check_lines(doc, report, places, unit):
    lines = doc.get("line_items") or []
    incl = bool(doc.get("prices_include_tax"))
    amounts = []
    for i, line in enumerate(lines):
        area = f"line_items.{i}"
        qty = dec(line.get("quantity"), report, area + ".quantity")
        price = dec(line.get("unit_price"), report, area + ".unit_price")
        disc = dec(line.get("discount"), report, area + ".discount") or Decimal(0)
        net = dec(line.get("net_amount"), report, area + ".net_amount")
        gross = dec(line.get("gross_amount"), report, area + ".gross_amount")
        tax = dec(line.get("tax_amount"), report, area + ".tax_amount")
        rate = dec(line.get("tax_rate"), report, area + ".tax_rate")
        printed = (gross if gross is not None else net) if incl else net
        if printed is not None:
            amounts.append(printed)
        if qty is not None and price is not None and printed is not None:
            expected = money(qty * price - disc, places)
            if abs(expected - printed) > unit:
                hint = " (price per 100 or 1,000 units? missed discount?)" if expected != 0 and (printed / expected) in (Decimal("0.01"), Decimal("0.001")) else ""
                report.add("FAIL", area, f"{fmt(qty)} × {fmt(price)} − {fmt(disc)} = {fmt(expected)}, but the line shows {fmt(printed)}{hint}")
        if rate is not None and (rate < 0 or rate > 30):
            report.add("WARN", area + ".tax_rate", f"{rate}% is outside the range of any VAT or GST rate")
        if net is not None and rate is not None and tax is not None:
            expected = money(net * rate / 100, places)
            if abs(expected - tax) > unit:
                report.add("FAIL", area + ".tax_amount", f"{fmt(net)} at {rate}% is {fmt(expected)}, line shows {fmt(tax)}")
        if net is not None and tax is not None and gross is not None and abs(net + tax - gross) > unit:
            report.add("FAIL", area, f"net {fmt(net)} + tax {fmt(tax)} ≠ gross {fmt(gross)}")
    return amounts


def check_totals(doc, report, places, unit, line_amounts):
    t = doc.get("totals") or {}
    incl = bool(doc.get("prices_include_tax"))
    v = {k: dec(t.get(k), report, f"totals.{k}") for k in
         ("lines", "allowances", "charges", "net", "tax", "rounding", "gross", "prepaid", "amount_due")}
    n = len(line_amounts)
    for k, x in v.items():
        if x is not None and -x.as_tuple().exponent > places:
            report.add("WARN", f"totals.{k}", f"{x} has more decimals than {doc.get('currency') or 'the currency'} uses ({places})")

    line_sum = sum(line_amounts, Decimal(0)) if line_amounts else None
    if line_sum is not None and v["lines"] is not None and abs(line_sum - v["lines"]) > tolerance(unit, n):
        report.add("FAIL", "totals.lines", f"line items add up to {fmt(line_sum)}, subtotal shows {fmt(v['lines'])} (missed or misread line?)")
    base = v["lines"] if v["lines"] is not None else line_sum
    adj = (v["charges"] or 0) - (v["allowances"] or 0)
    target_key = "gross" if incl else "net"
    target = v[target_key]
    if incl and target is not None and v["rounding"]:
        target -= v["rounding"]
    if base is not None and target is not None:
        expected = base + adj
        if abs(expected - target) > tolerance(unit, n):
            report.add("FAIL", f"totals.{target_key}",
                       f"lines {fmt(base)} − allowances {fmt(v['allowances'] or 0)} + charges {fmt(v['charges'] or 0)} = {fmt(expected)}, "
                       f"but {target_key} shows {fmt(target)} (difference {fmt(target - expected)})")
    if v["net"] is not None and v["tax"] is not None and v["gross"] is not None:
        expected = v["net"] + v["tax"] + (v["rounding"] or 0)
        if abs(expected - v["gross"]) > unit:
            report.add("FAIL", "totals.gross", f"net {fmt(v['net'])} + tax {fmt(v['tax'])} + rounding {fmt(v['rounding'] or 0)} = {fmt(expected)}, but gross shows {fmt(v['gross'])}")
    if v["gross"] is not None and v["amount_due"] is not None:
        expected = v["gross"] - (v["prepaid"] or 0)
        if abs(expected - v["amount_due"]) > unit:
            report.add("FAIL", "totals.amount_due", f"gross {fmt(v['gross'])} − prepaid {fmt(v['prepaid'] or 0)} = {fmt(expected)}, but amount due shows {fmt(v['amount_due'])}")
    if v["rounding"] and abs(v["rounding"]) >= Decimal("0.5"):
        report.add("WARN", "totals.rounding", f"rounding of {v['rounding']} is larger than cash rounding ever is")
    return v


def check_tax_summary(doc, report, places, unit, totals):
    rows = doc.get("tax_summary") or []
    lines = doc.get("line_items") or []
    tax_sum, base_sum, complete = Decimal(0), Decimal(0), True
    for i, row in enumerate(rows):
        area = f"tax_summary.{i}"
        rate = dec(row.get("rate"), report, area + ".rate")
        base = dec(row.get("taxable_amount"), report, area + ".taxable_amount")
        tax = dec(row.get("tax_amount"), report, area + ".tax_amount")
        category = row.get("category")
        if tax is None or base is None:
            complete = False
        tax_sum += tax or 0
        base_sum += base or 0
        if rate is not None and (rate < 0 or rate > 30):
            report.add("WARN", area, f"{rate}% is outside the range of any VAT or GST rate")
        if rate == 0 and not category:
            report.add("WARN", area, "0% tax without a category: say whether it's zero-rated, exempt or reverse charge")
        if category in ("reverse_charge", "exempt", "zero", "out_of_scope") and tax:
            report.add("FAIL", area, f"category {category} but tax amount {fmt(tax)}")
        if category == "reverse_charge" and not any(get(t, "value") or isinstance(t, str) for t in get(doc, "buyer.tax_ids", []) or []):
            report.add("WARN", area, "reverse charge needs the buyer's VAT number on the invoice")
        if rate is not None and base is not None and tax is not None:
            count = sum(1 for ln in lines if str(ln.get("tax_rate")) == str(row.get("rate"))) or 1
            expected = money(base * rate / 100, places)
            if abs(expected - tax) > tolerance(unit, count):
                report.add("FAIL", area, f"{fmt(base)} at {rate}% is {fmt(expected)}, but tax shows {fmt(tax)}")
    if rows and complete:
        if totals["tax"] is not None and abs(tax_sum - totals["tax"]) > tolerance(unit, len(rows)):
            report.add("FAIL", "tax_summary", f"tax per rate adds up to {fmt(tax_sum)}, total tax shows {fmt(totals['tax'])}")
        if totals["net"] is not None and abs(base_sum - totals["net"]) > tolerance(unit, len(rows)):
            report.add("FAIL", "tax_summary", f"taxable amounts add up to {fmt(base_sum)}, net total shows {fmt(totals['net'])}")


def check_signs(doc, report, totals):
    kind = doc.get("document_type")
    values = [totals[k] for k in ("net", "tax", "gross", "amount_due") if totals.get(k)]
    if any(x > 0 for x in values) and any(x < 0 for x in values):
        report.add("FAIL", "totals", "totals mix positive and negative amounts")
    gross = totals.get("gross") if totals.get("gross") is not None else totals.get("amount_due")
    if gross is None:
        return
    if kind == "credit_note" and gross > 0:
        report.add("WARN", "totals", "credit note with a positive total: record credits as negative amounts")
    if kind == "invoice" and gross < 0:
        report.add("WARN", "totals", "invoice with a negative total: is it really a credit note?")


TERM_PATTERNS = [
    re.compile(r"\bnet\s*(\d{1,3})\b", re.I),
    re.compile(r"\b(\d{1,3})\s*(?:days?|tage[n]?|jours|d[ií]as|giorni|dagen|dagar|dage|dager|päivää|dni|dias)\b", re.I),
]
IMMEDIATE = re.compile(r"due on receipt|upon receipt|immediate|sofort|à réception|a reception|bei erhalt", re.I)


def check_dates(doc, report, today):
    issue = parse_date(doc.get("issue_date"), report, "issue_date")
    due = parse_date(doc.get("due_date"), report, "due_date")
    supply = parse_date(doc.get("supply_date"), report, "supply_date")
    if issue:
        if issue > today + timedelta(days=1):
            report.add("WARN", "issue_date", f"{issue} is in the future: misread date, or day and month swapped?")
        elif issue < today - timedelta(days=365):
            report.add("INFO", "issue_date", f"{issue} is over a year old: check it hasn't been paid already")
    if issue and due and due < issue:
        report.add("FAIL", "due_date", f"due {due} is before the issue date {issue} (day and month swapped?)")
    if issue and supply and supply > issue + timedelta(days=62):
        report.add("WARN", "supply_date", f"supply date {supply} is long after the issue date {issue}")
    terms = doc.get("payment_terms") or ""
    days = None
    if IMMEDIATE.search(terms):
        days = 0
    else:
        for pattern in TERM_PATTERNS:
            matches = pattern.findall(terms)
            if matches:
                days = int(matches[-1])
                break
    if re.search(r"end of (the )?month|\beom\b|fin de mois|monatsende", terms, re.I):
        days = None
        report.add("INFO", "payment_terms", f"'{terms}' counts from month end; due date not checked")
    if issue and days is not None:
        expected = issue + timedelta(days=days)
        if due and abs((due - expected).days) > 1:
            report.add("WARN", "due_date", f"terms '{terms}' from {issue} give {expected}, but the due date is {due}")
        elif not due:
            report.add("INFO", "due_date", f"not printed; terms '{terms}' give {expected}")


def check_bank(doc, report):
    bank = get(doc, "supplier.bank") or {}
    iban = bank.get("iban")
    bic = bank.get("bic")
    if iban:
        ok, msg = iban_ok(iban)
        if not ok:
            report.add("FAIL", "supplier.bank.iban", msg)
        elif msg:
            report.add("INFO", "supplier.bank.iban", msg)
        if ok:
            country = norm_id(iban)[:2]
            sup_country = (get(doc, "supplier.country") or "").upper()
            if sup_country and len(sup_country) == 2 and sup_country != country:
                report.add("INFO", "supplier.bank.iban", f"supplier is in {sup_country} but the account is in {country}: fine if known, a question if new")
            buyer_iban = get(doc, "buyer.bank.iban")
            if buyer_iban and norm_id(buyer_iban) == norm_id(iban):
                report.add("FAIL", "supplier.bank.iban", "supplier IBAN equals the buyer's IBAN: fields mixed up")
    if bic:
        b = norm_id(bic)
        if not re.fullmatch(r"[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?", b):
            report.add("FAIL", "supplier.bank.bic", f"{bic} isn't a valid BIC (8 or 11 characters)")
        elif iban and b[4:6] != norm_id(iban)[:2] and not (b[4:6] in ("FR", "MC") and norm_id(iban)[:2] in ("FR", "MC")):
            report.add("INFO", "supplier.bank.bic", f"BIC country {b[4:6]} differs from IBAN country {norm_id(iban)[:2]}")
    routing = bank.get("routing_number")
    if routing:
        r = re.sub(r"\D", "", str(routing))
        weights = (3, 7, 1) * 3
        if len(r) != 9 or sum(int(d) * w for d, w in zip(r, weights)) % 10:
            report.add("FAIL", "supplier.bank.routing_number", f"{routing} fails the ABA routing checksum")
    sort_code = bank.get("sort_code")
    if sort_code and not re.fullmatch(r"\d{6}", re.sub(r"[\s-]", "", str(sort_code))):
        report.add("WARN", "supplier.bank.sort_code", f"{sort_code} isn't six digits")


def check_ids(doc, report):
    for party in ("supplier", "buyer"):
        for entry in get(doc, f"{party}.tax_ids", []) or []:
            check_tax_id(entry, party, report)


def check_confidence(doc, report):
    conf = doc.get("_confidence") or {}
    evidence = doc.get("_evidence") or {}
    for path, level in conf.items():
        if level == "low":
            severity = "WARN" if ("bank" in path or path.startswith("totals")) else "INFO"
            report.add(severity, path, "low confidence: a person should check this field against the document")
    if doc.get("document_type") in PAYABLE:
        wanted = ["totals.gross", "issue_date", "invoice_number"]
        if get(doc, "supplier.bank.iban"):
            wanted.append("supplier.bank.iban")
        missing = [p for p in wanted if get(doc, p) is not None and p not in evidence]
        if missing:
            report.add("INFO", "_evidence", "no source text recorded for " + ", ".join(missing))


def supplier_key(doc):
    for entry in get(doc, "supplier.tax_ids", []) or []:
        value = entry.get("value") if isinstance(entry, dict) else entry
        if value:
            return "id:" + norm_id(value)
    name = get(doc, "supplier.name")
    return "name:" + norm_name(name) if name else None


def check_batch(docs, reports):
    seen_number, seen_amount = {}, {}
    for doc, report in zip(docs, reports):
        key = supplier_key(doc)
        if not key or doc.get("document_type") not in PAYABLE | {None}:
            continue
        number = doc.get("invoice_number")
        if number:
            k = (key, norm_id(number))
            if k in seen_number:
                report.add("FAIL", "duplicate", f"same supplier and invoice number as {seen_number[k]}")
            else:
                seen_number[k] = report.label
        gross = get(doc, "totals.gross") or get(doc, "totals.amount_due")
        issued = doc.get("issue_date")
        if gross and issued:
            k = (key, str(gross), str(issued))
            if k in seen_amount and seen_amount[k][1] != number:
                report.add("WARN", "duplicate", f"same supplier, amount and date as {seen_amount[k][0]} (different number: resubmitted?)")
            else:
                seen_amount.setdefault(k, (report.label, number))


def load_vendors(path):
    with open(path, encoding="utf-8") as fh:
        vendors = json.load(fh)
    for v in vendors:
        v["_ids"] = {norm_id(x) for x in v.get("tax_ids", []) if x}
        v["_name"] = norm_name(v.get("name", ""))
        v["_accounts"] = {norm_id(x) for x in v.get("ibans", []) + v.get("account_numbers", []) if x}
    return vendors


def check_vendor(doc, report, vendors):
    ids = {norm_id(e.get("value") if isinstance(e, dict) else e) for e in get(doc, "supplier.tax_ids", []) or []}
    name = norm_name(get(doc, "supplier.name") or "")
    match = next((v for v in vendors if ids & v["_ids"]), None) or next((v for v in vendors if name and v["_name"] == name), None)
    bank = get(doc, "supplier.bank") or {}
    accounts = {norm_id(x) for x in (bank.get("iban"), bank.get("account_number")) if x}
    if not match:
        report.add("WARN", "vendor", f"supplier '{get(doc, 'supplier.name')}' isn't in the known-vendors list: new vendors need their bank details verified")
        return
    unknown = accounts - match["_accounts"]
    if unknown and match["_accounts"]:
        report.add("FAIL", "vendor.bank",
                   f"bank account {', '.join(sorted(unknown))} isn't on file for {match.get('name')}. Hold payment and confirm the change by phone, "
                   "using a number already on file, not one from this invoice or its email")


# ---------- amount interpretation ----------

def interpret_amount(text):
    s = text.strip()
    neg = s.startswith("-") or s.endswith("-") or (s.startswith("(") and s.endswith(")")) or s.upper().endswith("CR")
    s = re.sub(r"[^\d.,'   ]", "", s).strip()
    s = re.sub(r"[   ']", "_", s)
    sign = "-" if neg else ""
    seps = [c for c in s if c in ".,"]
    if not seps:
        return [(sign + s.replace("_", ""), "no decimal separator")]
    if "." in seps and "," in seps:
        dec_sep = s[max(s.rfind("."), s.rfind(","))]
        other = "," if dec_sep == "." else "."
        whole, _, frac = s.replace("_", "").replace(other, "").rpartition(dec_sep)
        return [(f"{sign}{whole}.{frac}", f"'{dec_sep}' is the decimal separator")]
    sep = seps[0]
    if len(seps) > 1:
        return [(sign + s.replace("_", "").replace(sep, ""), f"repeated '{sep}' are thousands separators")]
    whole, _, frac = s.replace("_", "").partition(sep)
    if len(frac) != 3:
        return [(f"{sign}{whole}.{frac}", f"'{sep}' is the decimal separator ({len(frac)} digit{'s' if len(frac) != 1 else ''} after it)")]
    return [(f"{sign}{whole}{frac}", f"'{sep}' as thousands separator"),
            (f"{sign}{whole}.{frac}", f"'{sep}' as decimal separator (three-decimal currency, or a quantity)")]


# ---------- driver ----------

def validate(doc, label, today, vendors):
    report = Report(label)
    check_document_type(doc, report)
    places, unit = check_currency(doc, report)
    amounts = check_lines(doc, report, places, unit)
    totals = check_totals(doc, report, places, unit, amounts)
    check_tax_summary(doc, report, places, unit, totals)
    check_signs(doc, report, totals)
    check_dates(doc, report, today)
    check_bank(doc, report)
    check_ids(doc, report)
    check_confidence(doc, report)
    if vendors is not None and doc.get("document_type") in PAYABLE | {None}:
        check_vendor(doc, report, vendors)
    return report


def load(paths):
    docs, labels = [], []
    for path in paths:
        with (sys.stdin if path == "-" else open(path, encoding="utf-8")) as fh:
            data = json.load(fh)
        items = data if isinstance(data, list) else [data]
        for i, item in enumerate(items):
            docs.append(item)
            name = path if len(items) == 1 else f"{path}[{i}]"
            labels.append(f"{name} ({item.get('document_type') or '?'} {item.get('invoice_number') or ''})".replace(" )", ")"))
    return docs, labels


def write_csv(path, docs, reports):
    cols = ["source", "status", "document_type", "supplier_name", "supplier_tax_id", "invoice_number", "issue_date",
            "due_date", "currency", "net", "tax", "gross", "amount_due", "iban", "po_number", "payment_reference", "issues"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for doc, rep in zip(docs, reports):
            ids = get(doc, "supplier.tax_ids", []) or []
            first_id = (ids[0].get("value") if isinstance(ids[0], dict) else ids[0]) if ids else ""
            issues = "; ".join(f"{f['level']} {f['area']}: {f['message']}" for f in rep.findings if f["level"] != "INFO")
            w.writerow([rep.label, rep.worst(), doc.get("document_type"), get(doc, "supplier.name"), first_id,
                        doc.get("invoice_number"), doc.get("issue_date"), doc.get("due_date"), doc.get("currency"),
                        get(doc, "totals.net"), get(doc, "totals.tax"), get(doc, "totals.gross"), get(doc, "totals.amount_due"),
                        get(doc, "supplier.bank.iban"), doc.get("po_number"), doc.get("payment_reference"), issues])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="*", help="invoice JSON files ('-' for stdin)")
    ap.add_argument("--known-vendors", help="JSON list of vendors with verified bank details")
    ap.add_argument("--csv", help="write one row per invoice to this CSV file")
    ap.add_argument("--json", action="store_true", help="print findings as JSON")
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD) for date checks")
    ap.add_argument("--amount", help="show how a printed number could be read, then exit")
    args = ap.parse_args()

    if args.amount:
        for value, why in interpret_amount(args.amount):
            print(f"{value:>16}  {why}")
        return 0
    if not args.files:
        ap.error("give at least one invoice JSON file")

    today = date.fromisoformat(args.today) if args.today else date.today()
    vendors = load_vendors(args.known_vendors) if args.known_vendors else None
    docs, labels = load(args.files)
    reports = [validate(d, l, today, vendors) for d, l in zip(docs, labels)]
    check_batch(docs, reports)

    if args.csv:
        write_csv(args.csv, docs, reports)
    if args.json:
        print(json.dumps([{"source": r.label, "status": r.worst(), "findings": r.findings} for r in reports], indent=2, ensure_ascii=False))
    else:
        for r in reports:
            print(f"== {r.label}: {r.worst()}")
            for level in LEVELS:
                for f in r.findings:
                    if f["level"] == level:
                        print(f"  {level:<4}  {f['area']}: {f['message']}")
        counts = {lvl: sum(1 for r in reports if r.worst() == lvl) for lvl in ("OK", "WARN", "FAIL")}
        if len(reports) > 1:
            print(f"\n{len(reports)} documents: {counts['OK']} OK, {counts['WARN']} with warnings, {counts['FAIL']} failing")
    return 1 if any(r.worst() == "FAIL" for r in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
