-- Rename disbursements.status to its own uppercase DisbursementStatus
-- vocabulary (packages/shared/src/disbursement-status.ts,
-- apps/api/app/schemas/enums.py) — distinct from the lowercase
-- TransactionStatus values transactions.status keeps using unchanged:
-- pending/processing/successful/failed/reversed/cancelled ->
-- PENDING/PROCESSING/SUCCESS/FAILED/REVERSED. 'cancelled' (previously used
-- by reject_disbursement) folds into FAILED — a rejected disbursement never
-- had funds reserved, so there's nothing left to distinguish it from a
-- payout that failed outright.

update public.disbursements set status = 'FAILED' where status = 'cancelled';
update public.disbursements set status = 'SUCCESS' where status = 'successful';
update public.disbursements set status = upper(status) where status in ('pending', 'processing', 'failed', 'reversed');

alter table public.disbursements
  alter column status drop default;

alter table public.disbursements
  drop constraint disbursements_status_check;

alter table public.disbursements
  add constraint disbursements_status_check
  check (status in ('PENDING', 'PROCESSING', 'SUCCESS', 'FAILED', 'REVERSED'));

alter table public.disbursements
  alter column status set default 'PENDING';
