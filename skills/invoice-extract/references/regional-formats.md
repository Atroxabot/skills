# Regional formats, tax rules and e-invoices

What changes from country to country when reading an invoice, and where the traps are. Rates and mandates change; the ones here were current as of late 2026. When a rate matters to the outcome, say which rate you assumed and suggest checking it.

## Numbers

Work out the document's convention once, from an amount that can only be read one way (one with both separators, or with two digits after the last separator), and then apply it to every number.

| Convention | Example | Where |
|---|---|---|
| Comma thousands, point decimal | `1,234.56` | US, UK, Ireland, Australia, NZ, English Canada, Japan, China, Mexico, Israel |
| Point thousands, comma decimal | `1.234,56` | Germany, Austria, Netherlands, Belgium, Italy, Spain, Portugal, Denmark, Brazil, Indonesia, Turkey |
| Space thousands, comma decimal | `1 234,56` | France, Sweden, Norway, Finland, Poland, Czechia, Slovakia, Russia, French Canada. The space is often a narrow no-break space (U+202F) or no-break space (U+00A0), which some text extraction drops, giving `1234,56` |
| Apostrophe thousands, point decimal | `1'234.56` | Switzerland, Liechtenstein |
| Indian grouping | `12,34,567.89` | India (lakh = 1,00,000; crore = 1,00,00,000) |

Traps:
- **A lone separator with three digits after it** (`1,500` or `1.500`) is a thousands separator in one convention and a decimal in the other. It's also a real decimal for currencies with three minor digits (KWD, BHD, OMR, JOD, TND, IQD, LYD). Settle it from the rest of the document, never alone. `python3 scripts/validate_invoice.py --amount "1,500"` lists the readings.
- **Negative formats**: `-100.00`, `100.00-` (trailing minus, common in SAP output), `(100.00)`, `100.00 CR`, or a red number in the image. All mean negative.
- **Currency symbols** go before or after, with or without a space. `$` alone is ambiguous (USD, CAD, AUD, NZD, MXN, SGD, HKD...); use the supplier's address and any ISO code on the page.
- **OCR and text-layer errors**: a dropped decimal point turns `1,234.56` into `123456`; a `,` read as `.`; `O`/`0`, `l`/`1`, `S`/`5`, `B`/`8` confusions in IDs. The validator's arithmetic checks catch most of these.

## Dates

| Order | Example | Where |
|---|---|---|
| Day month year | `04.03.2026`, `04/03/2026`, `4-3-26` | Most of Europe, UK, Latin America, India, Australia, NZ |
| Month day year | `03/04/2026` | United States, and some Canadian and Philippine documents |
| Year month day | `2026-03-04`, `2026/03/04`, `2026年3月4日` | ISO, Sweden, Lithuania, Canada (often), China, Japan, Korea, Hungary (`2026.03.04.`) |

To resolve a slash date: a day above 12 anywhere on the page settles the order; the supplier's country is strong evidence; payment terms ("30 days") give a check against the due date. Japanese documents may use era years: Reiwa 1 = 2019, so Reiwa 8 (令和8年) = 2026. Thai documents may use the Buddhist era (subtract 543).

Month names appear in the local language: `März`, `mars`, `marzo`, `maart`, `marraskuu` (that one is November).

## Tax by region

### European Union (VAT)

- Every EU invoice must show the supplier's VAT number, and the buyer's for reverse-charge and intra-community supplies. Greece uses the prefix `EL`, not `GR`.
- **Reverse charge**: when a business in one EU country buys services from another, the supplier charges 0% and the buyer accounts for the VAT. The invoice says "Reverse charge", "Steuerschuldnerschaft des Leistungsempfängers", "Autoliquidation", "Inversione contabile" or similar. Category `reverse_charge`, tax `0`. It's correct, not a missing tax.
- **Intra-community supply of goods**: exempt (category `exempt` or, in e-invoices, `K`), with a note citing the exemption.
- **Small-business exemptions** let small suppliers charge no VAT (Germany's "Kleinunternehmer, § 19 UStG", France's "TVA non applicable, art. 293 B du CGI"). Tax `0` is legitimate; the invoice should say why.
- Rates change more often than people expect (Finland 25.5% from September 2024, Estonia 24% from July 2025, Romania 21% from August 2025). Don't flag a rate as wrong from memory; flag only a rate that disagrees with the invoice's own arithmetic.

E-invoicing mandates: Italy (SDI, FatturaPA XML) for years; Belgium B2B via Peppol from January 2026; Poland's KSeF phased in during 2026; France phasing in from September 2026; Germany requires businesses to be able to receive e-invoices since January 2025, with issuing phased in over 2027 and 2028. In these countries, a PDF may be a visual copy of the legally valid XML.

### United Kingdom

VAT at 20%, 5% or 0%; VAT numbers `GB` + 9 digits (or 12, or `GD`/`HA` + 3 for government and health bodies). Northern Ireland businesses trading goods with the EU use `XI`. UK domestic bank details are an account number (8 digits) and sort code (`12-34-56`); IBANs appear for international payments.

### Switzerland and Liechtenstein

VAT is MWST / TVA / IVA, at 8.1% standard, 2.6% reduced, 3.8% accommodation (since 2024). The UID is `CHE-123.456.789` followed by `MWST`, `TVA` or `IVA` when VAT-registered. Payment is by **QR-bill**: the QR code (it starts with `SPC`) contains the IBAN, amount, currency and reference. A QR-IBAN (institution ID 30000–31999 in positions 5–9) must be paid with the 27-digit QR reference. Cash rounding to 0.05 is common.

### Norway

VAT (MVA) 25% standard. Organization number 9 digits, followed by `MVA` when VAT-registered. Payments use a KID reference number.

### United States

No VAT. Sales tax is set by state and locality and often doesn't appear on B2B invoices (the buyer may owe use tax instead). The supplier's tax ID is the EIN (`12-3456789`), usually collected on a W-9 rather than printed. Bank details are an account number plus a 9-digit ABA routing number; wire instructions sometimes add a SWIFT code.

### Canada

GST 5% federally; provinces add PST (BC, SK, MB), QST (Quebec, 9.975%), or combine them into HST (13–15%, depending on the province). The GST/HST number is the 9-digit business number + `RT0001`.

### Australia and New Zealand

Australia: GST 10%. A "Tax invoice" heading and the supplier's ABN (11 digits, with a checksum the validator tests) are needed for the buyer to claim GST credits. New Zealand: GST 15%, GST number 8 or 9 digits.

### India

GST is split: CGST + SGST (equal halves) for sales within a state, or IGST for sales between states. Never both. The GSTIN is 15 characters: 2-digit state code, the 10-character PAN, an entity digit, `Z`, and a check character. Larger businesses issue e-invoices with an IRN (a 64-character hash) and a signed QR code. Amounts often use Indian grouping.

### Japan

Since October 2023, the qualified invoice system requires the supplier's registration number (`T` + 13 digits) and tax shown per rate (10% standard, 8% reduced for food). Dates may use era years.

### Middle East

UAE VAT 5%, with a 15-digit TRN. Saudi Arabia VAT 15%; ZATCA e-invoices carry a QR code with the seller name, VAT number, timestamp, total and VAT.

### Latin America

Invoices are government-registered XML; the printed PDF is a representation. Mexico: CFDI with a UUID ("folio fiscal") and the RFC tax IDs. Brazil: NF-e with a 44-digit access key and CNPJ tax IDs. Read the XML if you have it.

## E-invoice field locations

Both main formats implement the European standard EN 16931, so they hold the same data with different tag names.

| Field | UBL (Peppol, XRechnung-UBL) | CII (Factur-X, ZUGFeRD, XRechnung-CII) |
|---|---|---|
| Number | `cbc:ID` | `rsm:ExchangedDocument/ram:ID` |
| Type | root element `Invoice` or `CreditNote`; `cbc:InvoiceTypeCode` | `ram:TypeCode` |
| Issue date | `cbc:IssueDate` (`2026-03-04`) | `ram:IssueDateTime/udt:DateTimeString` with `format="102"` (`20260304`) |
| Due date | `cbc:DueDate` | `ram:SpecifiedTradePaymentTerms/ram:DueDateDateTime` |
| Currency | `cbc:DocumentCurrencyCode` | `ram:InvoiceCurrencyCode` |
| Seller | `cac:AccountingSupplierParty/cac:Party` | `ram:SellerTradeParty` |
| Seller VAT | `cac:PartyTaxScheme/cbc:CompanyID` | `ram:SpecifiedTaxRegistration/ram:ID` with `schemeID="VA"` |
| IBAN | `cac:PaymentMeans/cac:PayeeFinancialAccount/cbc:ID` | `ram:PayeePartyCreditorFinancialAccount/ram:IBANID` |
| Payment reference | `cac:PaymentMeans/cbc:PaymentID` | `ram:PaymentReference` |
| Lines | `cac:InvoiceLine` | `ram:IncludedSupplyChainTradeLineItem` |
| Line quantity, amount | `cbc:InvoicedQuantity`, `cbc:LineExtensionAmount` | `ram:BilledQuantity`, `ram:LineTotalAmount` |
| Unit price | `cac:Price/cbc:PriceAmount`, per `cbc:BaseQuantity` | `ram:NetPriceProductTradePrice/ram:ChargeAmount`, per `ram:BasisQuantity` |
| Tax per rate | `cac:TaxTotal/cac:TaxSubtotal` | `ram:ApplicableTradeTax` (header level) |
| Line total, net, tax, gross | `cac:LegalMonetaryTotal`: `LineExtensionAmount`, `TaxExclusiveAmount`, `TaxInclusiveAmount` (tax from `cac:TaxTotal/cbc:TaxAmount`) | `ram:SpecifiedTradeSettlementHeaderMonetarySummation`: `LineTotalAmount`, `TaxBasisTotalAmount`, `TaxTotalAmount`, `GrandTotalAmount` |
| Allowances, charges | `AllowanceTotalAmount`, `ChargeTotalAmount` | `AllowanceTotalAmount`, `ChargeTotalAmount` |
| Prepaid, rounding, due | `PrepaidAmount`, `PayableRoundingAmount`, `PayableAmount` | `TotalPrepaidAmount`, `RoundingAmount`, `DuePayableAmount` |

Traps:
- **Base quantity.** A price can be per 100 or per 1,000 units (`BaseQuantity` / `BasisQuantity`). Line amount = quantity × price ÷ base quantity.
- **Tax category codes** (UNCL 5305): `S` standard, `AA` reduced (some profiles), `Z` zero-rated, `E` exempt, `AE` reverse charge, `K` intra-community supply, `G` export outside the EU, `O` outside the scope of VAT, `L` and `M` Canary Islands and Ceuta/Melilla.
- **Type codes**: `380` commercial invoice, `381` credit note, `384` corrected invoice, `386` prepayment invoice, `389` self-billed invoice.
- **Profile.** Factur-X `MINIMUM` and `BASIC WL` profiles carry header totals but no line items; use the printed page for the lines.

## Payment QR codes

- **EPC QR / GiroCode** (SEPA credit transfer, common on German, Austrian, Dutch, Belgian and Finnish invoices): line 1 `BCD`, then version, character set, `SCT`, BIC, beneficiary name, IBAN, amount as `EUR123.45`, purpose code, structured reference, free text.
- **Swiss QR-bill**: starts with `SPC`; contains the IBAN, creditor, amount, currency, debtor, reference type (`QRR`, `SCOR` or `NON`) and reference.

If the QR content and the printed details disagree, report both. A tampered PDF sometimes changes the printed IBAN but not the QR code, or the reverse.
