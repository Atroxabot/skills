---
name: invoice-extract
description: Extracts structured data from invoices, bills, receipts and credit notes (PDF, scan, photo, e-invoice XML or pasted text) into JSON or CSV, then checks it with a validator script instead of trusting the read. Checks line and tax arithmetic, totals, dates and payment terms, IBAN checksums, VAT and tax ID formats, currency decimals, duplicates across a batch, and changed bank details (the classic invoice fraud). Use whenever the user asks to extract, parse, read, digitize or capture an invoice or receipt, pull out line items, totals or VAT, prepare invoices for accounts payable, bookkeeping, an expense report or an accounting import, reconcile a batch of bills, or asks whether an invoice adds up or looks legitimate. Reports problems; never pays, approves or posts anything.
---

# Invoice extract

Turn invoices into data that an accounts-payable system or a bookkeeper can trust. The extraction itself is the easy half. The value is in the second half: proving the numbers add up, catching misreads, and flagging the invoices that should not be paid as-is.

Why this needs care: a model reading an invoice will produce a confident, tidy JSON even when it misread a digit, mixed up `1.234,56` and `1,234.56`, or took the statement total for the invoice total. A wrong number in accounts payable becomes a wrong payment. So every figure gets checked against the other figures on the page, by a script, before anyone relies on it.

## Workflow

### 1. Get the most authoritative source first

Invoices often carry the same data twice. Prefer the machine-readable copy, because it was generated from the supplier's books and has no reading errors.

1. **Embedded e-invoice XML.** Factur-X and ZUGFeRD PDFs (common in France and Germany) carry a full XML invoice as a PDF attachment. Run `pdfdetach -list file.pdf`; if it lists `factur-x.xml`, `zugferd-invoice.xml`, `xrechnung.xml` or similar, extract it with `pdfdetach -saveall -o <dir> file.pdf` and read that. A standalone `.xml` file may be UBL (Peppol, `<Invoice xmlns="urn:oasis:names:specification:ubl:...">`) or CII (`<rsm:CrossIndustryInvoice>`). See [references/regional-formats.md](references/regional-formats.md) for where the fields live.
2. **QR payment codes.** A Swiss QR-bill or an EPC (SEPA) QR code holds the IBAN, amount and reference in structured form. If you can decode it, it is the best source for payment fields, and the printed values should match it.
3. **PDF text layer.** `pdftotext -layout file.pdf -` keeps columns aligned, which matters for line-item tables. Check the output is real text and not empty: a scanned PDF has no text layer.
4. **The image.** For scans and photos, read the page image directly. Zoom into the totals block and the bank details, since those are where a misread costs the most.

If two sources disagree (the XML says 1,190.00 and the printed page says 1,109.00), report both. Don't silently pick one.

### 2. Decide what kind of document it is

Classify before extracting, because the type changes what the numbers mean and whether anything should be paid:

| Type | How to recognize it | Why it matters |
|---|---|---|
| Invoice | "Invoice", "Rechnung", "Facture", a number, a due date | Payable |
| Credit note | "Credit note", "Gutschrift", "Avoir", negative totals, refers to an original invoice | Reduces what is owed. Totals should be negative or marked as credits |
| Receipt | Already paid: "Paid", card details, cash register layout | Expense evidence, not payable. Prices usually include tax |
| Pro-forma | "Pro forma", "Proforma" | A quote dressed as an invoice. Not a tax invoice. Paying it and then the real invoice doubles the payment |
| Statement | A list of several invoices with a running balance | Not a new invoice. Extract the listed invoice numbers instead |
| Quote / order confirmation | "Quote", "Estimate", "Order confirmation" | Not payable |
| Reminder / dunning letter | "Reminder", "Mahnung", "overdue", may add fees | Refers to an existing invoice. Check it isn't processed twice |

If you can't tell, say so in the output rather than defaulting to "invoice".

### 3. Extract into the schema

Use the schema in [references/schema.md](references/schema.md). The rules that matter most:

- **Copy, don't infer.** Fill a field only from text on the document. A missing field is `null`. If you calculate a value (a missing net total from the line items), put it in the field and record `"derived"` in `_confidence` for that path, so nobody mistakes it for something the supplier stated.
- **Keep the evidence.** For every amount, date, ID and bank detail, put the exact source text in `_evidence` (for example `"totals.gross": "Gesamtbetrag 1.428,00 €"`). This lets a person check a figure in seconds, and it exposes normalization mistakes.
- **Amounts are decimal strings** in canonical form: `"1234.56"`, minus sign for negatives, no thousands separators. Never floats, because floats can't represent most cents exactly.
- **Normalize numbers by the document's convention, not yours.** `1.234,56` is German style; `1'234.56` is Swiss; `12,34,567.00` is Indian grouping. Work out the convention from the whole document (look at an amount that is unambiguous) before converting any number. [references/regional-formats.md](references/regional-formats.md) lists the conventions and the traps.
- **Dates are ISO 8601** (`2026-03-04`). `04/03/2026` is ambiguous; resolve it with the supplier's country, other dates on the page (a day above 12 settles the order), and the payment terms. If it stays ambiguous, mark the confidence `low` and say why.
- **Unreadable is a valid answer.** If a digit is smudged or cut off, don't guess. Mark the field `low` and say which character is unclear. A guessed IBAN digit sends money to the wrong place; a flagged one gets checked.
- **Tax lines are per rate.** Many invoices mix rates (standard plus reduced, or taxable plus exempt). Record each rate in `tax_summary`, including 0% lines with their reason (exempt, zero-rated, reverse charge), because the reason has accounting consequences.

### 4. Validate with the script

Save the JSON and run:

```
python3 scripts/validate_invoice.py invoice.json
python3 scripts/validate_invoice.py batch/*.json --known-vendors vendors.json --csv out.csv
```

It checks, with exact decimal arithmetic:
- each line: quantity × unit price − discount = line amount
- lines, document-level allowances and charges against the net total
- each tax rate: taxable amount × rate = tax, and the tax summary against the total tax
- net + tax = gross, and gross − prepaid = amount due
- signs are consistent (a credit note shouldn't mix positive and negative totals)
- decimals fit the currency (JPY has none, KWD has three)
- dates parse, the due date isn't before the issue date, and it matches the payment terms
- IBAN length and mod-97 checksum, BIC format, and whether the BIC country matches the IBAN
- VAT and tax ID formats for EU countries, the UK, Switzerland and Norway, plus the Australian ABN checksum
- across a batch: duplicate invoice numbers per supplier, and same supplier with the same amount and date
- with `--known-vendors`: bank details that differ from the ones on file

Tolerances follow real rounding practice. Suppliers round tax per line or per document, and both are legal, so the script allows a small difference that grows with the number of lines and reports anything beyond it.

**When a check fails, go back to the document before blaming the supplier.** Most failures are reading errors: a 3 read as 8, a missed discount line, a thousands separator read as a decimal point, a shipping charge left out. Fix the extraction and re-run. Only a failure that survives a careful re-read is a finding about the invoice. Then report it plainly ("the line items sum to 1,180.00 but the invoice states a net of 1,200.00; the difference matches nothing on the page").

A format check is not proof of existence. A well-formed VAT number may not be registered; confirm EU numbers in the VIES service and UK numbers with HMRC if it matters. A valid IBAN checksum means the number is internally consistent, not that it belongs to this supplier.

### 5. Flag what shouldn't be paid as-is

Some findings are about risk, not arithmetic. Report them in their own section so they aren't lost among rounding notes:

- **Changed or unfamiliar bank details.** This is the most expensive invoice fraud: a real supplier's invoice, or a convincing copy, with the attacker's account. If the IBAN differs from the one on file, or the invoice or its cover email announces "our bank details have changed", say the payment should be held until someone confirms the change by phone, using a number already on file and not one printed on the invoice or in the email. Don't treat new details as a correction to apply.
- **Duplicates.** The same supplier and invoice number seen before, or the same amount and date from the same supplier. Also a reminder or statement that repeats an invoice already in the batch.
- **Document type problems.** A pro-forma, quote or statement submitted as an invoice.
- **Mismatches between sources.** XML vs printed page, QR code vs printed IBAN or amount.
- **Weak signals**, labeled as weak: a round amount, a supplier name with no tax ID or address, a personal email domain, an invoice number far out of the supplier's usual sequence. These justify a look, not an accusation.

Never change a payment detail, approve, or post anything on your own. Report and let a person decide.

### 6. Output

Give the user:

1. **The data**: the JSON (or a CSV for a batch, via `--csv`), with `_evidence` and `_confidence` kept unless they asked for a clean export.
2. **The validation result**: one line per check that failed or warned, with the numbers. If everything passed, say so in one line.
3. **Hold or check before paying**: the risk findings from step 5, if any, at the top.
4. **Low-confidence fields**: what you couldn't read and what to look at.

Keep the narrative short. People processing invoices want the figures and the exceptions, not a description of the invoice.

For large batches, process each document separately and validate all of them together at the end, so the duplicate checks see the whole batch.

## References

- [references/schema.md](references/schema.md): the JSON schema, with field meanings and an example. Read before the first extraction.
- [references/regional-formats.md](references/regional-formats.md): number and date conventions, tax names and rules by region, e-invoice formats and where their fields live. Read when the invoice is foreign, tax-inclusive, reverse-charge, or an e-invoice.
- `scripts/validate_invoice.py`: the validator. Run it on every extraction. `--help` lists the options; `--amount "1.234,56"` shows how an ambiguous number could be read.
