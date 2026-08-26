"""An in-memory stand-in for the supabase-py client, covering the subset of
the fluent query builder app/services and app/routers actually use:
select/insert/update/delete, .eq()/.is_()/.in_(), .order(), .range(),
.maybe_single(), count="exact". Good enough to exercise real router/service
code end-to-end in tests without a real Supabase project.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal


class _Result:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class _FakeQuery:
    def __init__(self, table: "_FakeTable", op: str, payload=None):
        self._table = table
        self._op = op
        self._payload = payload
        self._filters: list[tuple[str, str, object]] = []
        self._order_col: str | None = None
        self._order_desc = False
        self._range_start: int | None = None
        self._range_end: int | None = None
        self._limit: int | None = None
        self._single: str | None = None

    def eq(self, column, value):
        self._filters.append(("eq", column, value))
        return self

    def neq(self, column, value):
        self._filters.append(("neq", column, value))
        return self

    def is_(self, column, value):
        self._filters.append(("is", column, value))
        return self

    def in_(self, column, values):
        self._filters.append(("in", column, list(values)))
        return self

    def gte(self, column, value):
        self._filters.append(("gte", column, value))
        return self

    def gt(self, column, value):
        self._filters.append(("gt", column, value))
        return self

    def lte(self, column, value):
        self._filters.append(("lte", column, value))
        return self

    def lt(self, column, value):
        self._filters.append(("lt", column, value))
        return self

    def order(self, column, desc=False):
        self._order_col = column
        self._order_desc = desc
        return self

    def range(self, start, end):
        self._range_start = start
        self._range_end = end
        return self

    def limit(self, count):
        self._limit = count
        return self

    def maybe_single(self):
        self._single = "maybe_single"
        return self

    def single(self):
        self._single = "single"
        return self

    @staticmethod
    def _compare(row_value, value):
        """Numeric comparison when possible (amounts stored as numeric
        strings), else lexicographic (ISO8601 timestamps sort correctly as
        strings). Returns -1/0/1, or None if row_value is missing."""
        if row_value is None:
            return None
        try:
            a, b = float(row_value), float(value)
        except (TypeError, ValueError):
            a, b = str(row_value), str(value)
        return -1 if a < b else (1 if a > b else 0)

    def _matches(self, row: dict) -> bool:
        for kind, column, value in self._filters:
            if kind == "eq" and str(row.get(column)) != str(value):
                return False
            if kind == "neq" and str(row.get(column)) == str(value):
                return False
            if kind == "is" and value == "null" and row.get(column) is not None:
                return False
            if kind == "in" and str(row.get(column)) not in [str(v) for v in value]:
                return False
            if kind in ("gte", "gt", "lte", "lt"):
                cmp = self._compare(row.get(column), value)
                if cmp is None:
                    return False
                if kind == "gte" and cmp < 0:
                    return False
                if kind == "gt" and cmp <= 0:
                    return False
                if kind == "lte" and cmp > 0:
                    return False
                if kind == "lt" and cmp >= 0:
                    return False
        return True

    def execute(self) -> _Result:
        if self._op == "select":
            rows = [row for row in self._table.rows if self._matches(row)]
            if self._order_col:
                rows = sorted(
                    rows, key=lambda r: r.get(self._order_col) or "", reverse=self._order_desc
                )
            total = len(rows)
            if self._range_start is not None:
                rows = rows[self._range_start : self._range_end + 1]
            elif self._limit is not None:
                rows = rows[: self._limit]
            if self._single:
                return _Result(dict(rows[0]) if rows else None)
            return _Result([dict(r) for r in rows], count=total)

        if self._op == "insert":
            payloads = self._payload if isinstance(self._payload, list) else [self._payload]
            return _Result([self._table.insert(p) for p in payloads])

        if self._op == "update":
            matched = [row for row in self._table.rows if self._matches(row)]
            for row in matched:
                row.update(self._payload)
                row["updated_at"] = datetime.now(timezone.utc).isoformat()
            return _Result([dict(r) for r in matched])

        if self._op == "delete":
            matched = [row for row in self._table.rows if self._matches(row)]
            self._table.rows = [row for row in self._table.rows if row not in matched]
            return _Result([dict(r) for r in matched])

        raise NotImplementedError(self._op)


class _FakeTable:
    def __init__(self, name: str):
        self.name = name
        self.rows: list[dict] = []

    def insert(self, payload: dict) -> dict:
        row = dict(payload)
        row.setdefault("id", str(uuid.uuid4()))
        now = datetime.now(timezone.utc).isoformat()
        row.setdefault("created_at", now)
        row.setdefault("updated_at", now)
        if self.name == "invoice_items":
            # Mirrors invoice_items.line_total, a Postgres
            # `generated always as (quantity * unit_price) stored` column —
            # never supplied by the caller, always derived.
            row["line_total"] = str(Decimal(str(row["quantity"])) * Decimal(str(row["unit_price"])))
        self.rows.append(row)
        return row


class _FakeTableHandle:
    def __init__(self, table: _FakeTable):
        self._table = table

    def select(self, columns: str = "*", count: str | None = None) -> _FakeQuery:
        return _FakeQuery(self._table, "select")

    def insert(self, payload) -> _FakeQuery:
        return _FakeQuery(self._table, "insert", payload)

    def update(self, payload: dict) -> _FakeQuery:
        return _FakeQuery(self._table, "update", payload)

    def delete(self) -> _FakeQuery:
        return _FakeQuery(self._table, "delete")


class _FakeRpcCall:
    def __init__(self, client: "FakeSupabaseClient", fn_name: str, params: dict):
        self._client = client
        self._fn_name = fn_name
        self._params = params

    def execute(self) -> _Result:
        if self._fn_name == "post_ledger_entries":
            return self._client._post_ledger_entries(self._params.get("p_entries") or [])
        raise NotImplementedError(self._fn_name)


class _FakeStorageBucket:
    """In-memory stand-in for a supabase-py storage bucket proxy — covers
    .upload()/.create_signed_url(), the only two calls app/services/
    onboarding.py makes."""

    def __init__(self, objects: dict[str, bytes], bucket_id: str):
        self._objects = objects
        self._bucket_id = bucket_id

    def upload(self, path: str, file, file_options=None):
        self._objects[f"{self._bucket_id}/{path}"] = file
        return {"path": path, "fullPath": f"{self._bucket_id}/{path}"}

    def create_signed_url(self, path: str, expires_in: int, options=None) -> dict:
        url = f"https://fake.storage.test/{self._bucket_id}/{path}?expires_in={expires_in}"
        return {"signedURL": url, "signedUrl": url}


class _FakeStorage:
    def __init__(self, objects: dict[str, bytes]):
        self._objects = objects

    def from_(self, bucket_id: str) -> _FakeStorageBucket:
        return _FakeStorageBucket(self._objects, bucket_id)


class _FakeAuthAdminUser:
    """Mirrors the subset of supabase-py's gotrue User object
    app/services/admin_directory.py actually reads: .email and
    .user_metadata (for "full_name")."""

    def __init__(self, user_id: str, *, email: str | None, full_name: str | None):
        self.id = user_id
        self.email = email
        self.user_metadata = {"full_name": full_name} if full_name else {}


class _FakeGetUserResult:
    def __init__(self, user: _FakeAuthAdminUser):
        self.user = user


class _FakeGenerateLinkProperties:
    def __init__(self, action_link: str):
        self.action_link = action_link


class _FakeGenerateLinkResult:
    def __init__(self, user: _FakeAuthAdminUser, action_link: str):
        self.user = user
        self.properties = _FakeGenerateLinkProperties(action_link)


class _FakeAuthAdmin:
    def __init__(self):
        self._users: dict[str, _FakeAuthAdminUser] = {}

    def seed_user(self, user_id: str, *, email: str | None = None, full_name: str | None = None) -> None:
        self._users[str(user_id)] = _FakeAuthAdminUser(str(user_id), email=email, full_name=full_name)

    def get_user_by_id(self, user_id: str) -> _FakeGetUserResult:
        user = self._users.get(str(user_id))
        if user is None:
            # Mirrors a real Supabase Auth admin 404 — services/admin_directory.py
            # catches this (and anything else) and degrades to None/None.
            raise Exception(f"User {user_id} not found")  # noqa: TRY002
        return _FakeGetUserResult(user)

    def invite_user_by_email(self, email: str, options: dict | None = None) -> _FakeGetUserResult:
        """Mirrors the real Supabase Auth admin API closely enough for
        app/routers/merchant_portal.py::create_my_merchant_user: rejects an
        email already used by a seeded/invited user (real Supabase Auth
        errors on a duplicate email the same way), otherwise creates a new
        user with user_metadata.full_name from options["data"]["full_name"].
        """
        if any(user.email == email for user in self._users.values()):
            raise Exception(f"A user with email {email} already exists")  # noqa: TRY002
        user_id = str(uuid.uuid4())
        full_name = ((options or {}).get("data") or {}).get("full_name")
        self.seed_user(user_id, email=email, full_name=full_name)
        return _FakeGetUserResult(self._users[user_id])

    def generate_link(self, params: dict) -> "_FakeGenerateLinkResult":
        """Mirrors supabase_auth's admin generate_link closely enough for
        app/services/email.py's staff-invite and password-reset flows:
        never sends Supabase's own email (that's the whole point of using
        it over invite_user_by_email/reset_password_for_email), just
        returns an action_link. type="invite" creates a new user (same
        duplicate-email rejection as invite_user_by_email above);
        type="recovery" requires an *existing* user and raises if none
        matches — the real API's behavior, which
        send_password_reset_email relies on to silently no-op for an
        unregistered email (account enumeration prevention)."""
        link_type = params.get("type")
        email = params["email"]
        options = params.get("options") or {}
        redirect_to = options.get("redirect_to", "")
        token = uuid.uuid4().hex

        if link_type == "invite":
            if any(user.email == email for user in self._users.values()):
                raise Exception(f"A user with email {email} already exists")  # noqa: TRY002
            user_id = str(uuid.uuid4())
            full_name = (options.get("data") or {}).get("full_name")
            self.seed_user(user_id, email=email, full_name=full_name)
            user = self._users[user_id]
        elif link_type == "recovery":
            user = next((u for u in self._users.values() if u.email == email), None)
            if user is None:
                raise Exception(f"User {email} not found")  # noqa: TRY002
        else:
            raise NotImplementedError(f"generate_link type={link_type}")

        action_link = f"https://fake.supabase.test/auth/v1/verify?type={link_type}&token={token}&redirect_to={redirect_to}"
        return _FakeGenerateLinkResult(user, action_link)


class _FakeAuth:
    def __init__(self):
        self.admin = _FakeAuthAdmin()


class FakeSupabaseClient:
    def __init__(self):
        self._tables: dict[str, _FakeTable] = {}
        self._storage_objects: dict[str, bytes] = {}
        self.storage = _FakeStorage(self._storage_objects)
        self.auth = _FakeAuth()

    def table(self, name: str) -> _FakeTableHandle:
        if name not in self._tables:
            self._tables[name] = _FakeTable(name)
        return _FakeTableHandle(self._tables[name])

    def seed(self, table: str, row: dict) -> dict:
        """Directly insert a row, bypassing the query builder — for test setup."""
        return self.table(table)._table.insert(row)

    def seed_auth_user(self, user_id, *, email: str | None = None, full_name: str | None = None) -> None:
        self.auth.admin.seed_user(str(user_id), email=email, full_name=full_name)

    def rpc(self, fn_name: str, params: dict | None = None) -> _FakeRpcCall:
        return _FakeRpcCall(self, fn_name, params or {})

    def _post_ledger_entries(self, entries: list[dict]) -> _Result:
        """Mirrors supabase/migrations/20260814130002_post_ledger_entries_function.sql,
        20260814140001_post_ledger_entries_balance_check.sql, and
        20260828020000_post_ledger_entries_balance_snapshot.sql: inserts
        each entry (with its own balance_before/after snapshot) and updates
        its account's cached balance, using the same asset/expense-vs-
        liability/equity/revenue sign convention, and rejects the *whole*
        batch — nothing inserted, nothing updated — if it would take a
        merchant_wallet balance negative.

        Two-phase (validate every resulting balance, and capture each
        entry's before/after snapshot, before mutating anything) to mirror
        the real function's atomicity: a Postgres exception partway through
        rolls back the entire transaction, not just the entry that tripped
        it. Entries are walked in order so an account touched twice in the
        same batch sees the first entry's effect reflected in the second's
        balance_before — exactly like the real function's sequential loop.
        """
        accounts_table = self.table("ledger_accounts")._table

        running_balances: dict[str, Decimal] = {}
        snapshots: list[tuple[Decimal | None, Decimal | None]] = []
        for entry in entries:
            account = next((a for a in accounts_table.rows if a["id"] == entry["ledger_account_id"]), None)
            if account is None:
                snapshots.append((None, None))
                continue
            account_id = account["id"]
            current = running_balances.get(account_id, Decimal(str(account.get("balance") or "0")))
            amount = Decimal(str(entry["amount"]))
            increases_on_debit = account.get("account_type") in ("asset", "expense")
            is_debit = entry["direction"] == "debit"
            delta = amount if (is_debit == increases_on_debit) else -amount
            new_balance = current + delta
            if account.get("purpose") == "merchant_wallet" and new_balance < 0:
                raise Exception(  # noqa: TRY002 - mirrors a raw postgrest/Postgres error, see services/ledger.py
                    f"INSUFFICIENT_BALANCE: wallet {account_id} balance {current} "
                    f"cannot cover a {entry['direction']} of {amount} (would be {new_balance})"
                )
            running_balances[account_id] = new_balance
            snapshots.append((current, new_balance))

        entries_table = self.table("ledger_entries")._table
        inserted = []
        for entry, (balance_before, balance_after) in zip(entries, snapshots, strict=True):
            payload = dict(entry)
            payload["balance_before"] = str(balance_before) if balance_before is not None else None
            payload["balance_after"] = str(balance_after) if balance_after is not None else None
            row = entries_table.insert(payload)
            account = next((a for a in accounts_table.rows if a["id"] == entry["ledger_account_id"]), None)
            if account is not None and account["id"] in running_balances:
                account["balance"] = str(running_balances[account["id"]])
            inserted.append(row)

        return _Result(inserted)
