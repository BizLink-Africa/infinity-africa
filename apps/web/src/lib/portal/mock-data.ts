/**
 * Seed data for the merchant portal prototype — shaped exactly like what
 * apps/api's /v1 endpoints return (see types.ts), so lib/portal/api.ts can
 * be swapped from "read this array" to "fetch from FastAPI" without
 * touching any component. Values roughly match the Google Stitch mockups
 * this UI was built from.
 */

import { CollectionMethod, InvoiceStatus } from "@infinity/shared";

import type { ApiKey, Collection, Customer, Invoice, SupportTicket, Transaction } from "./types";

export const MOCK_MERCHANT_ID = "5c1f0b2a-0000-4000-8000-000000000001";

let idCounter = 1000;
function nextId(prefix: string): string {
  idCounter += 1;
  return `${prefix}-${idCounter}`;
}

export function mockInvoices(): Invoice[] {
  const items = (rows: [string, string, string][]): Invoice["items"] =>
    rows.map(([description, quantity, unit_price], index) => ({
      id: nextId("item"),
      description,
      quantity,
      unit_price,
      line_total: String(Number(quantity) * Number(unit_price)),
      sort_order: index,
    }));

  return [
    {
      id: nextId("inv"),
      merchant_id: MOCK_MERCHANT_ID,
      customer_id: null,
      invoice_number: "INV-1042",
      customer_name: "Juma Traders Ltd",
      customer_email: null,
      customer_phone: "+255712445310",
      due_date: "2026-08-10",
      currency: "TZS",
      subtotal: "120000.00",
      tax_amount: "0.00",
      discount_amount: "0.00",
      total_amount: "120000.00",
      amount_paid: "120000.00",
      status: InvoiceStatus.PAID,
      payment_link_id: null,
      notes: null,
      created_at: "2026-07-28T09:00:00Z",
      updated_at: "2026-08-10T09:00:00Z",
      items: items([["Wholesale delivery — 50kg bags", "1", "120000"]]),
    },
    {
      id: nextId("inv"),
      merchant_id: MOCK_MERCHANT_ID,
      customer_id: null,
      invoice_number: "INV-1041",
      customer_name: "Amani Store",
      customer_email: "amani@example.com",
      customer_phone: null,
      due_date: "2026-08-14",
      currency: "TZS",
      subtotal: "64500.00",
      tax_amount: "0.00",
      discount_amount: "0.00",
      total_amount: "64500.00",
      amount_paid: "0.00",
      status: InvoiceStatus.SENT,
      payment_link_id: null,
      notes: null,
      created_at: "2026-08-01T09:00:00Z",
      updated_at: "2026-08-01T09:00:00Z",
      items: items([["Monthly supply top-up", "1", "64500"]]),
    },
    {
      id: nextId("inv"),
      merchant_id: MOCK_MERCHANT_ID,
      customer_id: null,
      invoice_number: "INV-1040",
      customer_name: "Neema Salon",
      customer_email: null,
      customer_phone: "+255689552771",
      due_date: "2026-08-05",
      currency: "TZS",
      subtotal: "90000.00",
      tax_amount: "0.00",
      discount_amount: "0.00",
      total_amount: "90000.00",
      amount_paid: "45000.00",
      status: InvoiceStatus.PARTIALLY_PAID,
      payment_link_id: null,
      notes: null,
      created_at: "2026-07-25T09:00:00Z",
      updated_at: "2026-08-05T09:00:00Z",
      items: items([["Equipment deposit", "1", "90000"]]),
    },
    {
      id: nextId("inv"),
      merchant_id: MOCK_MERCHANT_ID,
      customer_id: null,
      invoice_number: "INV-1039",
      customer_name: "Baraka Textiles",
      customer_email: null,
      customer_phone: "+255745118062",
      due_date: "2026-07-28",
      currency: "TZS",
      subtotal: "145000.00",
      tax_amount: "0.00",
      discount_amount: "0.00",
      total_amount: "145000.00",
      amount_paid: "0.00",
      status: InvoiceStatus.OVERDUE,
      payment_link_id: null,
      notes: null,
      created_at: "2026-07-14T09:00:00Z",
      updated_at: "2026-07-28T09:00:00Z",
      items: items([["Fabric consignment", "1", "145000"]]),
    },
    {
      id: nextId("inv"),
      merchant_id: MOCK_MERCHANT_ID,
      customer_id: null,
      invoice_number: "INV-1038",
      customer_name: "Grace Mwakalinga",
      customer_email: null,
      customer_phone: "+255754221908",
      due_date: "2026-07-20",
      currency: "TZS",
      subtotal: "25000.00",
      tax_amount: "0.00",
      discount_amount: "0.00",
      total_amount: "25000.00",
      amount_paid: "0.00",
      status: InvoiceStatus.CANCELLED,
      payment_link_id: null,
      notes: null,
      created_at: "2026-07-10T09:00:00Z",
      updated_at: "2026-07-20T09:00:00Z",
      items: items([["Design consultation", "1", "25000"]]),
    },
    {
      id: nextId("inv"),
      merchant_id: MOCK_MERCHANT_ID,
      customer_id: null,
      invoice_number: "INV-1037",
      customer_name: "Kilimanjaro Cafe",
      customer_email: "orders@kilicafe.co.tz",
      customer_phone: null,
      due_date: "2026-08-20",
      currency: "TZS",
      subtotal: "58000.00",
      tax_amount: "0.00",
      discount_amount: "0.00",
      total_amount: "58000.00",
      amount_paid: "0.00",
      status: InvoiceStatus.DRAFT,
      payment_link_id: null,
      notes: null,
      created_at: "2026-08-13T09:00:00Z",
      updated_at: "2026-08-13T09:00:00Z",
      items: items([["Coffee beans — 20kg", "1", "58000"]]),
    },
  ];
}

export function mockCollections(): Collection[] {
  // Customer names aren't a field on the collections table (only
  // customer_phone/customer_id are) — the page component resolves a
  // display name by matching customer_phone against mockCustomers(),
  // exactly like a real page would need to join the two resources.
  const rows: Array<[CollectionMethod, string, string, Collection["status"], string]> = [
    [CollectionMethod.STK_PUSH, "85000.00", "+255754221908", "successful", "2026-08-13T10:00:00Z"],
    [CollectionMethod.USSD_PUSH, "420000.00", "+255712445310", "processing", "2026-08-13T08:00:00Z"],
    [CollectionMethod.SELCOM_PESA_PUSH, "150000.00", "+255767903214", "successful", "2026-08-12T14:00:00Z"],
    [CollectionMethod.STK_PUSH, "60000.00", "+255689552771", "failed", "2026-08-12T09:00:00Z"],
    [CollectionMethod.DYNAMIC_QR, "25000.00", "+255745118062", "successful", "2026-08-11T16:00:00Z"],
    [CollectionMethod.USSD_PUSH, "310000.00", "+255678340526", "processing", "2026-08-10T11:00:00Z"],
  ];

  return rows.map(([method, amount, phone, status, initiated_at]) => ({
    id: nextId("col"),
    merchant_id: MOCK_MERCHANT_ID,
    customer_id: null,
    payment_link_id: null,
    invoice_id: null,
    merchant_reference: null,
    method,
    amount,
    currency: "TZS",
    customer_phone: phone,
    status,
    provider: "mock_selcom",
    provider_reference: status === "processing" ? null : `MOCK-SELCOM-${nextId("").slice(-8).toUpperCase()}`,
    transaction_reference: `TXN-${nextId("").slice(-8).toUpperCase()}`,
    message: null,
    expires_at: null,
    initiated_at,
    completed_at: status === "processing" ? null : initiated_at,
    created_at: initiated_at,
    updated_at: initiated_at,
  }));
}

export function mockTransactions(): Transaction[] {
  const rows: Array<[Transaction["type"], string, string, string, Transaction["status"], string]> = [
    ["collection", "PLK-7X29QK", "M-Pesa", "480000.00", "successful", "2026-08-13T09:12:00Z"],
    ["disbursement", "TXN-88214", "CRDB Bank", "1200000.00", "successful", "2026-08-13T08:47:00Z"],
    ["fee", "FEE-30187", "Wallet", "8400.00", "successful", "2026-08-12T17:30:00Z"],
    ["collection", "INV-1042", "Tigo Pesa", "2150000.00", "pending", "2026-08-12T14:05:00Z"],
    ["collection", "PLK-4M18RT", "Airtel Money", "96000.00", "failed", "2026-08-11T19:22:00Z"],
    ["disbursement", "TXN-88109", "NMB Bank", "640000.00", "pending", "2026-08-11T11:58:00Z"],
    ["collection", "INV-1039", "Selcom Pesa", "720000.00", "successful", "2026-08-10T16:41:00Z"],
    ["fee", "FEE-30122", "Wallet", "14600.00", "failed", "2026-08-09T10:15:00Z"],
  ];

  return rows.map(([type, reference, method, gross_amount, status, created_at]) => ({
    id: nextId("txn"),
    merchant_id: MOCK_MERCHANT_ID,
    reference,
    provider_reference: null,
    type,
    method,
    collection_id: type === "collection" ? nextId("col") : null,
    disbursement_id: type === "disbursement" ? nextId("dis") : null,
    gross_amount,
    fee_amount: "0.00",
    net_amount: gross_amount,
    currency: "TZS",
    status,
    created_at,
  }));
}

export function mockCustomers(): Customer[] {
  return [
    { id: nextId("cus"), merchant_id: MOCK_MERCHANT_ID, name: "Grace Mwakalinga", phone: "+255754221908", email: null, total_spent: "1240000.00", last_transaction_at: "2026-08-13T00:00:00Z", status: "active", created_at: "2026-05-01T00:00:00Z" },
    { id: nextId("cus"), merchant_id: MOCK_MERCHANT_ID, name: "Juma Traders", phone: "+255712445310", email: null, total_spent: "4820000.00", last_transaction_at: "2026-08-13T00:00:00Z", status: "active", created_at: "2026-03-11T00:00:00Z" },
    { id: nextId("cus"), merchant_id: MOCK_MERCHANT_ID, name: "Amani Store", phone: "+255767903214", email: null, total_spent: "2150000.00", last_transaction_at: "2026-08-12T00:00:00Z", status: "active", created_at: "2026-04-22T00:00:00Z" },
    { id: nextId("cus"), merchant_id: MOCK_MERCHANT_ID, name: "Neema Salon", phone: "+255689552771", email: null, total_spent: "610000.00", last_transaction_at: "2026-08-12T00:00:00Z", status: "inactive", created_at: "2026-06-02T00:00:00Z" },
    { id: nextId("cus"), merchant_id: MOCK_MERCHANT_ID, name: "Baraka Mushi", phone: "+255745118062", email: null, total_spent: "340000.00", last_transaction_at: "2026-08-11T00:00:00Z", status: "active", created_at: "2026-07-01T00:00:00Z" },
    { id: nextId("cus"), merchant_id: MOCK_MERCHANT_ID, name: "Zainab Hassan", phone: "+255678340526", email: null, total_spent: "95000.00", last_transaction_at: "2026-07-02T00:00:00Z", status: "inactive", created_at: "2026-06-18T00:00:00Z" },
  ];
}

export function mockApiKeys(): ApiKey[] {
  return [];
}

export function mockSupportTickets(): SupportTicket[] {
  return [];
}
