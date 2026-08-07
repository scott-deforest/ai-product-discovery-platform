# Supplier Invoice Processing Workflow

## Purpose

This document describes the accounts-payable process for Northstar Manufacturing.
The finance team receives supplier invoices, verifies them against purchasing
records, routes exceptions for review, and schedules approved payments.

## Team and Volume

- Four accounts-payable analysts process approximately 2,200 invoices each month.
- About 70% of invoices arrive as PDF attachments in a shared email inbox.
- The remainder arrive through a supplier portal or as scanned paper documents.
- Month-end volume is approximately 40% higher than the weekly average.
- The team aims to enter complete invoices within three business days.

## Current Workflow

### 1. Invoice intake

An analyst opens each message, saves the attachment, and checks that the supplier
name, invoice number, invoice date, purchase-order number, currency, subtotal, tax,
and total are present. Invoices use many layouts, and some contain handwritten
notes or low-quality scans. Missing information is requested from the supplier by
email.

### 2. Data entry and validation

The analyst enters invoice fields into the enterprise resource planning system.
Supplier records and purchase orders are searched manually. The analyst also
checks whether the invoice number may already exist. Formatting differences such
as spaces, punctuation, or leading zeros make duplicate searches inconsistent.

### 3. Three-way match

Purchase-order invoices are compared with the purchase order and receiving record.
Invoices within the approved quantity and price tolerances proceed. Approximately
18% require review because a receiving record is missing, the price differs, the
quantity exceeds the order, or the purchase-order number is invalid.

### 4. Exception handling

The analyst emails the buyer or receiving department with a description of the
exception. Supporting details are copied from the invoice and ERP system. Replies
often arrive without all required information, and analysts send follow-up
messages. Exception ownership is tracked in a shared spreadsheet.

### 5. Approval and payment scheduling

Non-purchase-order invoices and exceptions require approval according to amount
and cost center. The ERP system records the final approval and schedules payment.
No automated recommendation may release a payment or change supplier banking
details.

## Current Challenges

- Analysts repeatedly transcribe common fields from invoices into the ERP system.
- Low-quality scans and inconsistent supplier layouts cause entry errors.
- Duplicate checks depend on exact formatting and individual analyst judgment.
- Exception messages are assembled manually from several systems.
- Shared-spreadsheet tracking provides limited visibility into aging exceptions.
- Month-end backlogs increase late-payment risk and reduce discount capture.

## Available Data

The company retains two years of invoice images, extracted ERP fields, purchase
orders, receiving records, exception codes, approval history, and payment dates.
Historical corrections are recorded, but the reason for a correction is often in
free-text notes. Supplier tax identifiers and banking information are restricted
financial data. Approximately 8% of archived scans are too poor for reliable text
extraction without manual review.

## Desired Outcomes

Finance wants to reduce manual entry, detect likely duplicates earlier, shorten
exception-resolution time, and improve visibility into bottlenecks. An initial
pilot should focus on one invoice channel and demonstrate measurable improvement
within one quarter.

## Constraints

- A finance employee must verify extracted fields before an invoice is posted.
- Existing approval limits and segregation-of-duties controls cannot be bypassed.
- Supplier banking changes require the established independent verification process.
- Low-confidence extraction must be routed to manual review.
- The solution must preserve an audit trail linking suggestions to source records.
