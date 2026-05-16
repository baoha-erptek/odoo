"""Fernet-at-rest encryption helpers for Etsy OAuth tokens (P1-10).

Single instance-wide Fernet key sourced from
`ir.config_parameter.etsy.oauth.fernet_key`. Lazy generation on first
encrypt() call, serialised with `pg_advisory_xact_lock` so two
concurrent first-use requests can never persist different keys.

Decision **D-P1-10-02** in `specs/005-etsy-api-channel/p1-10-plan.md`:
key stored in `ir.config_parameter` with system-only ACL (the gate
lives in `models/ir_config_parameter.py`). Rotation is out of scope
for P1-10.

Security model:
- Plaintext lives in memory only for the duration of encrypt/decrypt.
- Ciphertext (a Fernet token, base64 ASCII) lives in the
  `etsy.shop.etsy_oauth_*` columns (groups='base.group_system').
- The Fernet key itself lives in `ir_config_parameter` with the
  `_SENSITIVE_KEYS` gate enforced in the model override.
- Callers must already be inside a sudo()/system context — this
  module performs no ACL check of its own.

Signature note: encrypt/decrypt take an explicit `env` argument
because Odoo 19 dropped the implicit `Environment.envs` class
attribute. The previous (RED) test signature `encrypt(plaintext)`
was clarified during GREEN — the contract (encrypt→decrypt round
trip under a single instance key) is unchanged.
"""

import hashlib
import logging

from cryptography.fernet import Fernet

_logger = logging.getLogger(__name__)

_FERNET_KEY_ICP_NAME = 'etsy.oauth.fernet_key'


def _advisory_lock_key() -> int:
    """Deterministic 32-bit signed int derived from the ICP key name.

    `pg_advisory_xact_lock(bigint)` accepts a 64-bit int; we hash the
    name and pull the top 4 bytes, then interpret as signed so the
    value fits int4 too — Postgres is happy with either width.
    """
    digest = hashlib.sha256(_FERNET_KEY_ICP_NAME.encode('utf-8')).digest()
    return int.from_bytes(digest[:4], byteorder='big', signed=True)


def _read_key(env) -> bytes | None:
    """Read the Fernet key from ICP, returning None when unset/empty.

    Uses sudo() because the get_param override in
    `models/ir_config_parameter.py` blocks non-system reads. The
    `if not raw` check handles three identical-from-our-POV states:
    row missing, value NULL, value empty string.
    """
    icp = env['ir.config_parameter'].sudo()
    raw = icp.get_param(_FERNET_KEY_ICP_NAME, default='')
    if not raw:
        return None
    return raw.encode('ascii') if isinstance(raw, str) else raw


def _get_or_generate_key(env) -> bytes:
    """Read or lazy-generate the Fernet key. Concurrency-safe.

    Holds a transaction-scoped advisory lock so two simultaneous
    first-use requests serialize through key creation rather than
    both generating distinct keys (which would corrupt every token
    written by the loser).
    """
    # Serialise first-use across concurrent transactions. Released at
    # txn end (commit/rollback).
    env.cr.execute("SELECT pg_advisory_xact_lock(%s)", (_advisory_lock_key(),))
    # Re-read after acquiring the lock — another waiter may have
    # generated the key while we waited.
    key = _read_key(env)
    if key is not None:
        return key
    new_key = Fernet.generate_key()  # bytes, base64-ASCII Fernet key
    env['ir.config_parameter'].sudo().set_param(
        _FERNET_KEY_ICP_NAME, new_key.decode('ascii'),
    )
    # Force the ORM to send the INSERT/UPDATE to Postgres now —
    # callers reading the raw column via SQL on the same cursor
    # (audit tooling, drift verification, tests) would otherwise see
    # the pre-write value.
    env['ir.config_parameter'].flush_model(['key', 'value'])
    _logger.info(
        'Generated Fernet key for %r (one-time lazy init).',
        _FERNET_KEY_ICP_NAME,
    )
    return new_key


def _require_key(env) -> bytes:
    """Read the Fernet key; raise ValueError when missing (no generation)."""
    key = _read_key(env)
    if key is None:
        raise ValueError(
            f"Fernet key {_FERNET_KEY_ICP_NAME!r} is missing or empty; "
            "cannot decrypt ciphertext."
        )
    return key


def encrypt(plaintext: str, env) -> str:
    """Encrypt plaintext under the instance Fernet key.

    Returns a base64-ASCII Fernet token (e.g. `gAAAAA...`). Empty
    plaintext returns empty string (callers may rely on this no-op
    pattern when persisting nullable fields).
    """
    if not plaintext:
        return ''
    key = _get_or_generate_key(env)
    return Fernet(key).encrypt(plaintext.encode('utf-8')).decode('ascii')


def decrypt(ciphertext: str, env) -> str:
    """Decrypt a Fernet token to its plaintext.

    Raises `ValueError` if the key is missing/empty (operator must
    run the bootstrap first). Raises
    `cryptography.fernet.InvalidToken` if the ciphertext is malformed
    or was encrypted under a different key.
    """
    if not ciphertext:
        return ''
    key = _require_key(env)
    return Fernet(key).decrypt(ciphertext.encode('ascii')).decode('utf-8')
