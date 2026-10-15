# Invoice JSON schema

One JSON object per document. `scripts/validate_invoice.py` reads exactly this shape. Fields you can't find on the document are `null` (or left out); empty strings are treated the same as missing.

All amounts are decimal **strings** in canonical form: digits, an optional leading `-`, and `.` as the decimal point. `"1234.56"`, never `1234.56` (a float) and never `"1.234,56"`. Rates are percentages as strings: `"19"`, `"7.7"`, `"0"`.

## Fields

```json
{
  "document_type": "invoice",
  "invoice_number": "RE-2026-0412",
  "original_invoice_number": null,
  "issue_date": "2026-03-04",
  "supply_date": "2026-02-28",
  "due_date": "2026-04-03",
  "payment_terms": "30 days net",
  "currency": "EUR",
  "prices_include_tax": false,
  "po_number": "PO-7781",
  "payment_reference": "RF18539007547034",

  "supplier": {
    "name": "Holzwerk Brandt GmbH",
    "address": "Lindenstr. 12, 10969 Berlin, DE",
    "country": "DE",
    "tax_ids": [{"type": "VAT", "value": "DE123456789"}],
    "email": "rechnung@holzwerk-brandt.de",
    "phone": "+49 30 1234567",
    "bank": {
      "iban": "DE89370400440532013000",
      "bic": "COBADEFFXXX",
      "account_number": null,
      "routing_number": null,
      "sort_code": null,
      "account_name": "Holzwerk Brandt GmbH"
    }
  },
  "buyer": {
    "name": "Atelier Nord AB",
    "address": "Storgatan 3, 111 51 Stockholm, SE",
    "country": "SE",
    "tax_ids": [{"type": "VAT", "value": "SE556677889901"}]
  },

  "line_items": [
    {
      "description": "Oak shelf, 120 cm",
      "quantity": "4",
      "unit": "pcs",
      "unit_price": "250.00",
      "discount": "0",
      "tax_rate": "19",
      "net_amount": "1000.00",
      "tax_amount": null,
      "gross_amount": null
    }
  ],

  "tax_summary": [
    {"rate": "19", "category": "standard", "taxable_amount": "1200.00", "tax_amount": "228.00"}
  ],

  "totals": {
    "lines": "1200.00",
    "allowances": "0",
    "charges": "0",
    "net": "1200.00",
    "tax": "228.00",
    "rounding": "0",
    "gross": "1428.00",
    "prepaid": "0",
    "amount_due": "1428.00"
  },

  "notes": "Reverse charge does not apply.",

  "_evidence": {
    "totals.gross": "Gesamtbetrag 1.428,00 €",
    "supplier.bank.iban": "IBAN DE89 3704 0044 0532 0130 00",
    "issue_date": "Rechnungsdatum: 04.03.2026"
  },
  "_confidence": {
    "totals.lines": "derived",
    "supply_date": "medium"
  },
  "_source": {"file": "RE-2026-0412.pdf", "method": "pdf-text", "pages": 1}
}
```

## Field notes

**document_type**: one of `invoice`, `credit_note`, `receipt`, `proforma`, `statement`, `quote`, `order_confirmation`, `reminder`, `other`. See the table in SKILL.md.

**original_invoice_number**: for credit notes and reminders, the invoice they refer to.

**issue_date / supply_date / due_date**: the invoice date, the date goods or services were delivered (the tax point in many countries), and the payment deadline. Supply date is often labeled "delivery date", "Leistungsdatum", "date of supply" or given as a period; for a period, use the last day and put the full period in `notes`.

**payment_terms**: verbatim, such as "Net 30", "14 Tage netto", "2% 10, net 30", "Due on receipt". The validator compares a "N days" term with the dates.

**prices_include_tax**: `true` when the line prices already include tax, as on most receipts and consumer invoices. The validator then checks lines against gross rather than net.

**payment_reference**: the reference the payer must quote, such as a structured creditor reference (`RF...`), a Belgian structured communication (`+++123/4567/89012+++`), a Norwegian KID, a Finnish reference number, or a Swiss QR reference. Copy it exactly; banks match payments with it.

**tax_ids**: a list, because suppliers often print several (VAT number plus company registration number). `type` is what the document calls it: `VAT`, `GST`, `ABN`, `EIN`, `UID`, `MWST`, `TVA`, `GSTIN`, `TRN`, `T-number` (Japan), `company_registration`. Keep the country prefix as printed.

**bank**: whatever is printed. US invoices use account and routing numbers, UK domestic invoices use account number and sort code, most of the rest of the world uses IBAN and BIC.

**line_items**:
- `quantity` and `unit_price` as printed. Unit prices may have more decimals than the currency (`"0.0425"`); keep them.
- `discount` is the line discount as an amount. If the document shows a percentage, compute the amount, keep the percentage in `_evidence`, and mark the discount `derived`.
- `net_amount` is the line total before tax (or `gross_amount` when `prices_include_tax` is true). Use the printed value, not your own multiplication; the validator compares the two.

**tax_summary**: one entry per rate. `category` is `standard`, `reduced`, `zero`, `exempt`, `reverse_charge`, `out_of_scope` or `other`. A 0% line needs its category, because "zero-rated", "exempt" and "reverse charge" are treated differently in the buyer's accounts. If the invoice prints only a single tax total, make one entry and leave `taxable_amount` as the net.

**totals**:
- `lines`: sum of line amounts, if printed ("Subtotal").
- `allowances`: document-level discounts, as a positive number.
- `charges`: document-level additions such as shipping or handling, when they aren't line items.
- `net` = lines − allowances + charges.
- `tax`: total tax.
- `rounding`: cash rounding, used in some countries (Switzerland to 0.05, Sweden and Denmark on cash payments).
- `gross` = net + tax + rounding.
- `prepaid`: deposits or payments already made.
- `amount_due` = gross − prepaid.

For a credit note, use negative amounts throughout, even if the document prints them as positive under a "Credit" heading. Say in `notes` that you flipped the sign.

**_evidence**: keys are dotted paths (`line_items.0.net_amount`, `supplier.bank.iban`). Values are the exact text from the document, including its original formatting. Cover at least every total, date, ID and bank field.

**_confidence**: keys are dotted paths; values are `high`, `medium`, `low` or `derived`. Leave out fields that are `high`; list only the exceptions. Use `low` when a character was unclear, `medium` when you resolved an ambiguity (a date order, a number convention) from context, and `derived` when the value isn't printed and you calculated it.

**_source**: where the data came from: `xml` (embedded or standalone e-invoice), `qr`, `pdf-text`, `image`, or `text` (pasted).

## Known-vendors file

The validator's `--known-vendors` option takes a JSON list of vendors with the bank details already verified:

```json
[
  {"name": "Holzwerk Brandt GmbH", "tax_ids": ["DE123456789"], "ibans": ["DE89370400440532013000"]},
  {"name": "Northwind Traders", "tax_ids": [], "ibans": ["GB82WEST12345698765432"], "account_numbers": []}
]
```

It matches an invoice to a vendor by tax ID first, then by normalized name, and reports any IBAN or account number not in the list.
