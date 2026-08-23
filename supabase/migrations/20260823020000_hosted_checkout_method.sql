-- Adds HOSTED_CHECKOUT to collections.method / transactions.method: the
-- new default collection path (Merchant Portal "Request Collection" and
-- the customer-facing "Pay securely" payment-link flow both now always
-- redirect to Selcom's own hosted checkout page via create-order-minimal,
-- rather than Infinity asking the customer/merchant to pick a channel
-- like USSD_PUSH/STK_PUSH/SELCOM_PESA_PUSH/DYNAMIC_QR). Selcom's hosted
-- page shows whichever methods are enabled on the merchant's Selcom
-- account (card is confirmed NOT enabled — no exclusion logic needed
-- here or anywhere else).
--
-- The 4 old method values are untouched and remain fully valid — old
-- collections/transactions rows created before this change keep working
-- exactly as before; this is additive only.

alter table public.collections
  drop constraint collections_method_check;

alter table public.collections
  add constraint collections_method_check
  check (method in ('USSD_PUSH', 'STK_PUSH', 'SELCOM_PESA_PUSH', 'DYNAMIC_QR', 'HOSTED_CHECKOUT'));

alter table public.transactions
  drop constraint transactions_method_matches_type;

alter table public.transactions
  add constraint transactions_method_matches_type check (
    (type = 'collection'
      and method in ('USSD_PUSH', 'STK_PUSH', 'SELCOM_PESA_PUSH', 'DYNAMIC_QR', 'HOSTED_CHECKOUT')
      and collection_id is not null)
    or (type = 'disbursement'
      and method in ('SELCOM_PESA', 'MOBILE_MONEY', 'BANK_ACCOUNT')
      and disbursement_id is not null)
    or (type in ('fee', 'refund', 'reversal', 'adjustment')
      and method in (
        'USSD_PUSH', 'STK_PUSH', 'SELCOM_PESA_PUSH', 'DYNAMIC_QR', 'HOSTED_CHECKOUT',
        'SELCOM_PESA', 'MOBILE_MONEY', 'BANK_ACCOUNT', 'INTERNAL'
      ))
  );
