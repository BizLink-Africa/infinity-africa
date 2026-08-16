-- Real RLS policies, replacing the placeholders left as comments when each
-- table was created. Strategy, applied consistently below:
--
--   * SUPER_ADMIN (platform_admins membership) can read everything, and
--     write to platform-internal tables. Wrapped as `(select ...)` so
--     Postgres can evaluate the no-argument check once per statement
--     instead of once per row (see the Supabase RLS performance guide).
--   * MERCHANT_ADMIN and MERCHANT_STAFF ("merchant users") get equal access
--     to their own merchant's day-to-day business data (rule: "merchant
--     users can only access their own merchant's data"). Team management
--     (merchant_users) and the merchant profile itself (merchants) are
--     reserved for MERCHANT_ADMIN — the one deliberate ADMIN vs STAFF split.
--   * DEVELOPER is scoped to exactly what was asked of it: manage the
--     merchant's api_keys. It gets no access to customers/invoices/etc.
--   * Money-movement records that a trusted backend process writes
--     (collections, disbursements, transactions, webhook_events) are
--     read-only for merchant users via RLS — all writes to those tables
--     happen through apps/api using the service_role key, which bypasses
--     RLS entirely.
--   * settlement_accounts, ledger_accounts, ledger_entries, audit_logs are
--     platform-internal: no merchant policy at all, super admin only.
--   * payment_links and invoices additionally get a public (anon) SELECT
--     policy scoped to exactly the "valid"/"payable" rows a customer needs
--     to complete a checkout — nothing else on those tables, and no public
--     policy at all on any other table.

-- ---------------------------------------------------------------------------
-- platform_admins (self-view policy already added when the table was created)
-- ---------------------------------------------------------------------------

create policy "super admins can view the admin roster"
  on public.platform_admins for select
  using ((select public.current_user_is_super_admin()));

-- ---------------------------------------------------------------------------
-- merchants
-- ---------------------------------------------------------------------------

create policy "super admins can view all merchants"
  on public.merchants for select
  using ((select public.current_user_is_super_admin()));

create policy "super admins can update any merchant"
  on public.merchants for update
  using ((select public.current_user_is_super_admin()));

create policy "merchant members can view their own merchant"
  on public.merchants for select
  using (public.current_user_has_merchant_access(id));

create policy "merchant admins can update their own merchant"
  on public.merchants for update
  using (public.current_user_merchant_role(id) = 'MERCHANT_ADMIN');

-- No insert/delete policy: onboarding and offboarding a merchant go through
-- apps/api (service_role), not a direct client write.

-- ---------------------------------------------------------------------------
-- merchant_users
-- ---------------------------------------------------------------------------

create policy "super admins can manage all merchant memberships"
  on public.merchant_users for all
  using ((select public.current_user_is_super_admin()))
  with check ((select public.current_user_is_super_admin()));

create policy "users can view their own memberships"
  on public.merchant_users for select
  using (user_id = auth.uid());

create policy "merchant admins can manage their team"
  on public.merchant_users for all
  using (public.current_user_merchant_role(merchant_id) = 'MERCHANT_ADMIN')
  with check (public.current_user_merchant_role(merchant_id) = 'MERCHANT_ADMIN');

-- ---------------------------------------------------------------------------
-- customers (MERCHANT_ADMIN + MERCHANT_STAFF only — not DEVELOPER)
-- ---------------------------------------------------------------------------

create policy "super admins can view all customers"
  on public.customers for select
  using ((select public.current_user_is_super_admin()));

create policy "merchant admins and staff can manage their own customers"
  on public.customers for all
  using (public.current_user_merchant_role(merchant_id) in ('MERCHANT_ADMIN', 'MERCHANT_STAFF'))
  with check (public.current_user_merchant_role(merchant_id) in ('MERCHANT_ADMIN', 'MERCHANT_STAFF'));

-- ---------------------------------------------------------------------------
-- api_keys (MERCHANT_ADMIN + DEVELOPER — this is the DEVELOPER role's scope)
-- ---------------------------------------------------------------------------

create policy "super admins can view all api keys"
  on public.api_keys for select
  using ((select public.current_user_is_super_admin()));

create policy "merchant admins and developers can manage their api keys"
  on public.api_keys for all
  using (public.current_user_merchant_role(merchant_id) in ('MERCHANT_ADMIN', 'DEVELOPER'))
  with check (public.current_user_merchant_role(merchant_id) in ('MERCHANT_ADMIN', 'DEVELOPER'));

-- ---------------------------------------------------------------------------
-- settlement_accounts (platform-internal)
-- ---------------------------------------------------------------------------

create policy "super admins can manage settlement accounts"
  on public.settlement_accounts for all
  using ((select public.current_user_is_super_admin()))
  with check ((select public.current_user_is_super_admin()));

-- ---------------------------------------------------------------------------
-- payment_links (merchant CRUD + public read of active, unexpired links)
-- ---------------------------------------------------------------------------

create policy "super admins can view all payment links"
  on public.payment_links for select
  using ((select public.current_user_is_super_admin()));

create policy "merchant admins and staff can manage their payment links"
  on public.payment_links for all
  using (public.current_user_merchant_role(merchant_id) in ('MERCHANT_ADMIN', 'MERCHANT_STAFF'))
  with check (public.current_user_merchant_role(merchant_id) in ('MERCHANT_ADMIN', 'MERCHANT_STAFF'));

create policy "anyone can view a valid payment link"
  on public.payment_links for select
  using (status = 'ACTIVE' and (expires_at is null or expires_at > now()));

-- ---------------------------------------------------------------------------
-- invoices (merchant CRUD + public read of payable invoices)
-- ---------------------------------------------------------------------------

create policy "super admins can view all invoices"
  on public.invoices for select
  using ((select public.current_user_is_super_admin()));

create policy "merchant admins and staff can manage their invoices"
  on public.invoices for all
  using (public.current_user_merchant_role(merchant_id) in ('MERCHANT_ADMIN', 'MERCHANT_STAFF'))
  with check (public.current_user_merchant_role(merchant_id) in ('MERCHANT_ADMIN', 'MERCHANT_STAFF'));

create policy "anyone can view a payable invoice"
  on public.invoices for select
  using (status in ('SENT', 'PARTIALLY_PAID', 'OVERDUE'));

-- ---------------------------------------------------------------------------
-- invoice_items (mirrors invoices — access follows the parent invoice)
-- ---------------------------------------------------------------------------

create policy "super admins can view all invoice items"
  on public.invoice_items for select
  using ((select public.current_user_is_super_admin()));

create policy "merchant admins and staff can manage items on their invoices"
  on public.invoice_items for all
  using (
    invoice_id in (
      select id from public.invoices
      where public.current_user_merchant_role(merchant_id) in ('MERCHANT_ADMIN', 'MERCHANT_STAFF')
    )
  )
  with check (
    invoice_id in (
      select id from public.invoices
      where public.current_user_merchant_role(merchant_id) in ('MERCHANT_ADMIN', 'MERCHANT_STAFF')
    )
  );

create policy "anyone can view items of a payable invoice"
  on public.invoice_items for select
  using (
    invoice_id in (select id from public.invoices where status in ('SENT', 'PARTIALLY_PAID', 'OVERDUE'))
  );

-- ---------------------------------------------------------------------------
-- collections (read-only for merchant users — provider pushes are recorded
-- by apps/api via service_role, not written directly by a client)
-- ---------------------------------------------------------------------------

create policy "super admins can view all collections"
  on public.collections for select
  using ((select public.current_user_is_super_admin()));

create policy "merchant admins and staff can view their own collections"
  on public.collections for select
  using (public.current_user_merchant_role(merchant_id) in ('MERCHANT_ADMIN', 'MERCHANT_STAFF'));

-- ---------------------------------------------------------------------------
-- disbursements (read-only for merchant users, same reasoning as collections)
-- ---------------------------------------------------------------------------

create policy "super admins can view all disbursements"
  on public.disbursements for select
  using ((select public.current_user_is_super_admin()));

create policy "merchant admins and staff can view their own disbursements"
  on public.disbursements for select
  using (public.current_user_merchant_role(merchant_id) in ('MERCHANT_ADMIN', 'MERCHANT_STAFF'));

-- ---------------------------------------------------------------------------
-- transactions (read-only ledger view for merchant users)
-- ---------------------------------------------------------------------------

create policy "super admins can view all transactions"
  on public.transactions for select
  using ((select public.current_user_is_super_admin()));

create policy "merchant admins and staff can view their own transactions"
  on public.transactions for select
  using (public.current_user_merchant_role(merchant_id) in ('MERCHANT_ADMIN', 'MERCHANT_STAFF'));

-- ---------------------------------------------------------------------------
-- ledger_accounts / ledger_entries (platform-internal accounting)
-- ---------------------------------------------------------------------------

create policy "super admins can manage ledger accounts"
  on public.ledger_accounts for all
  using ((select public.current_user_is_super_admin()))
  with check ((select public.current_user_is_super_admin()));

create policy "super admins can view ledger entries"
  on public.ledger_entries for select
  using ((select public.current_user_is_super_admin()));

-- No insert policy for ledger_entries either: every row is written by
-- apps/api via service_role as part of posting a transaction, never by a
-- super admin's own client session.

-- ---------------------------------------------------------------------------
-- webhook_events (read-only delivery log for merchant users)
-- ---------------------------------------------------------------------------

create policy "super admins can view all webhook events"
  on public.webhook_events for select
  using ((select public.current_user_is_super_admin()));

create policy "merchant admins and staff can view their own webhook events"
  on public.webhook_events for select
  using (public.current_user_merchant_role(merchant_id) in ('MERCHANT_ADMIN', 'MERCHANT_STAFF'));

-- ---------------------------------------------------------------------------
-- audit_logs (platform-internal)
-- ---------------------------------------------------------------------------

create policy "super admins can view audit logs"
  on public.audit_logs for select
  using ((select public.current_user_is_super_admin()));
