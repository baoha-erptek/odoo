"""Drive P-INV-INITIAL-LOAD imports against a remote Odoo via XML-RPC.

Reads STAGING_BASE_URL / STAGING_DB / STAGING_ADMIN_LOGIN / STAGING_ADMIN_PASSWORD
from ``.env`` and runs the four ``base_import`` jobs in dependency order:

  1. ``01_product_categories.xlsx``  -> ``product.category``
  2. ``02_product_templates.xlsx``   -> ``product.template``
  3. ``03_initial_on_hand.xlsx``     -> ``stock.quant``   (then auto-Apply)
  4. ``04_reorder_rules.xlsx``       -> ``stock.warehouse.orderpoint``

After step 3 the script calls ``action_apply_inventory`` on the just-imported
quants to push ``inventory_quantity`` into real on-hand stock.

External-ID anchor: ``inv_initial_load.<slug>`` (set in the XLSX ``id`` column)
guarantees idempotent reruns -- a second invocation update-in-place via the
standard ``ir.model.data`` resolution and never duplicates rows.

Usage::

    python3 scripts/apply_inventory_to_staging.py \\
        --input-dir .0temp/import/inventory/<timestamp>/
    python3 scripts/apply_inventory_to_staging.py \\
        --input-dir .0temp/import/inventory/<timestamp>/ --dry-run
"""

from __future__ import annotations

import argparse
import itertools
import json
import logging
import mimetypes
import os
import sys
import uuid
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Final

import openpyxl
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
)
_logger = logging.getLogger('apply_inventory_to_staging')

XLSX_MIME: Final[str] = (
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)

# Ordered: each step depends on external IDs created by the previous step.
# Steps 3 + 4 require a template-extid -> product.product id rewrite because
# stock.quant.product_id and stock.warehouse.orderpoint.product_id are M2O
# to product.product (variant), while the XLSX uses product.template extids.
IMPORT_STEPS: Final[list[tuple[str, str]]] = [
    ('01_product_categories.xlsx', 'product.category'),
    ('02_product_templates.xlsx', 'product.template'),
    ('03_initial_on_hand.xlsx', 'stock.quant'),
    ('04_reorder_rules.xlsx', 'stock.warehouse.orderpoint'),
]

# Models whose product_id column needs template-extid -> product.product int
# rewrite before .load().
PRODUCT_VARIANT_MODELS: Final[frozenset[str]] = frozenset({
    'stock.quant', 'stock.warehouse.orderpoint',
})

IMPORT_OPTIONS: Final[dict[str, object]] = {
    'has_headers': True,
    'advanced': True,           # enable dotted '/' paths for related fields
    'keep_matches': False,
    'name_create_enabled_fields': {},
    'import_set_empty_fields': [],
    'import_skip_records': [],
    'fallback_values': {},
    'skip': 0,
    'limit': 2000,
    'encoding': 'utf-8',
    'separator': ',',
    'quoting': '"',
    'date_format': '',
    'datetime_format': '',
    'float_thousand_separator': ',',
    'float_decimal_separator': '.',
    'tracking_disable': True,
}


_RPC_ID = itertools.count(1)


class JsonRpcClient:
    """JSON-RPC + session-cookie client for Odoo.

    JSON-RPC is used for /jsonrpc business calls (None-tolerant).
    The cookie jar carries the /web/session/authenticate session so the
    standard ``/base_import/set_file`` multipart endpoint can be used to
    upload the raw XLSX bytes — same path the web UI takes.
    """

    def __init__(self, base_url: str, db: str) -> None:
        self.base_url = base_url
        self.endpoint = f'{base_url}/jsonrpc'
        self.db = db
        self.uid: int | None = None
        self.password: str | None = None
        self._cookies = CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookies),
        )

    def _call(self, service: str, method: str, args: list[Any]) -> Any:
        payload = {
            'jsonrpc': '2.0',
            'method': 'call',
            'id': next(_RPC_ID),
            'params': {'service': service, 'method': method, 'args': args},
        }
        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
        )
        with self._opener.open(req, timeout=120) as resp:
            body = json.loads(resp.read().decode('utf-8'))
        if 'error' in body:
            err = body['error']
            raise RuntimeError(
                f"JSON-RPC {service}.{method} error: "
                f"{err.get('data', {}).get('message') or err.get('message')}\n"
                f"{err.get('data', {}).get('debug', '')}"
            )
        return body.get('result')

    def login(self, login: str, password: str) -> int:
        # /jsonrpc common.login bootstraps the uid for execute_kw.
        uid = self._call('common', 'login', [self.db, login, password])
        if not uid:
            raise RuntimeError(f'Authentication failed for {login} @ {self.db}')
        self.uid = uid
        self.password = password
        # Session-cookie auth so /base_import/set_file accepts the multipart.
        session_payload = {
            'jsonrpc': '2.0',
            'method': 'call',
            'id': next(_RPC_ID),
            'params': {'db': self.db, 'login': login, 'password': password},
        }
        req = urllib.request.Request(
            f'{self.base_url}/web/session/authenticate',
            data=json.dumps(session_payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
        )
        with self._opener.open(req, timeout=60) as resp:
            session = json.loads(resp.read().decode('utf-8'))
        if 'error' in session:
            raise RuntimeError(
                f'/web/session/authenticate failed: {session["error"]}',
            )
        return uid

    def version(self) -> dict[str, Any]:
        return self._call('common', 'version', [])

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any],
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        assert self.uid is not None and self.password is not None
        return self._call('object', 'execute_kw', [
            self.db, self.uid, self.password,
            model, method, args, kwargs or {},
        ])

    def upload_import_file(self, import_id: int, xlsx_path: Path) -> dict[str, Any]:
        """POST the file to /base_import/set_file via multipart/form-data."""
        boundary = uuid.uuid4().hex
        mime = (mimetypes.guess_type(xlsx_path.name)[0]
                or 'application/octet-stream')
        body = (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="ufile"; filename="{xlsx_path.name}"\r\n'
            f'Content-Type: {mime}\r\n\r\n'
        ).encode('utf-8') + xlsx_path.read_bytes() + (
            f'\r\n--{boundary}--\r\n'
        ).encode('utf-8')
        url = f'{self.base_url}/base_import/set_file?id={import_id}'
        req = urllib.request.Request(
            url, data=body,
            headers={
                'Content-Type': f'multipart/form-data; boundary={boundary}',
            },
        )
        with self._opener.open(req, timeout=180) as resp:
            raw = resp.read().decode('utf-8')
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise RuntimeError(f'/base_import/set_file non-JSON response: {raw[:500]}')


def load_env(env_path: Path) -> dict[str, str]:
    """Tiny .env parser; ignores comments and blank lines."""
    out: dict[str, str] = {}
    for raw in env_path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        value = value.strip().strip('"').strip("'")
        out[key.strip()] = value
    return out


def read_headers(xlsx_path: Path) -> list[str]:
    """First-row column headers verbatim (already match Odoo field paths)."""
    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    ws = wb.active
    headers = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
    wb.close()
    return [str(h) for h in headers if h is not None]


def read_xlsx_rows(xlsx_path: Path) -> tuple[list[str], list[list[str]]]:
    """Parse XLSX into (header_row, data_rows-as-strings).

    ``model.load`` expects every cell stringified — booleans, numbers, etc.
    """
    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    ws = wb.active
    iterator = ws.iter_rows(values_only=True)
    raw_headers = next(iterator)
    headers = [str(h) for h in raw_headers if h is not None]
    rows: list[list[str]] = []
    for row in iterator:
        if not row or all(cell is None or cell == '' for cell in row):
            continue
        stringified: list[str] = []
        for cell in row[:len(headers)]:
            if cell is None:
                stringified.append('')
            elif isinstance(cell, bool):
                stringified.append('TRUE' if cell else 'FALSE')
            elif isinstance(cell, float):
                stringified.append(
                    f'{cell:.6f}'.rstrip('0').rstrip('.') if cell != int(cell)
                    else str(int(cell))
                )
            else:
                stringified.append(str(cell))
        rows.append(stringified)
    wb.close()
    return headers, rows


def resolve_template_extid_to_variant_id(
    client: JsonRpcClient,
    headers: list[str],
    rows: list[list[str]],
) -> tuple[list[str], list[list[str]]]:
    """Replace ``product_id/id`` column (holding template extids) with
    ``product_id`` column holding the int id of the corresponding variant
    (product.product) auto-created by product.template."""
    if 'product_id/id' not in headers:
        return headers, rows
    col = headers.index('product_id/id')
    extids = sorted({row[col] for row in rows if row[col]})
    _logger.info('  resolving %d template extids -> product.product ids', len(extids))

    # 1) extid (module.name) -> product.template id via ir.model.data.
    # complete_name is unstored in Odoo 19; split into (module, name) tuples.
    pairs = sorted({tuple(e.split('.', 1)) for e in extids if '.' in e})
    modules = sorted({m for m, _ in pairs})
    names = sorted({n for _, n in pairs})
    md_records = client.execute_kw(
        'ir.model.data', 'search_read',
        [[
            ('model', '=', 'product.template'),
            ('module', 'in', modules),
            ('name', 'in', names),
        ]],
        {'fields': ['module', 'name', 'res_id']},
    )
    extid_to_tmpl: dict[str, int] = {
        f"{r['module']}.{r['name']}": r['res_id'] for r in md_records
    }
    missing = set(extids) - set(extid_to_tmpl)
    if missing:
        raise RuntimeError(
            f'{len(missing)} template extid(s) not found on staging '
            f'(first 5: {sorted(missing)[:5]}). Run steps 1-2 first.'
        )

    # 2) template id -> product.product id (single-variant assumption per slice)
    tmpl_ids = list(extid_to_tmpl.values())
    variant_records = client.execute_kw(
        'product.product', 'search_read',
        [[('product_tmpl_id', 'in', tmpl_ids)]],
        {'fields': ['id', 'product_tmpl_id']},
    )
    tmpl_to_variant: dict[int, int] = {}
    for v in variant_records:
        tmpl_id = v['product_tmpl_id'][0] if isinstance(v['product_tmpl_id'], list) else v['product_tmpl_id']
        # First variant wins; single-variant templates by design.
        tmpl_to_variant.setdefault(tmpl_id, v['id'])
    missing_variants = set(tmpl_ids) - set(tmpl_to_variant)
    if missing_variants:
        raise RuntimeError(
            f'{len(missing_variants)} template(s) have no product.product variant '
            f'(first 5: {sorted(missing_variants)[:5]}).'
        )

    extid_to_variant: dict[str, int] = {
        extid: tmpl_to_variant[tmpl_id]
        for extid, tmpl_id in extid_to_tmpl.items()
    }

    # `product_id/.id` tells load() to treat the value as a raw DB id rather
    # than a name to search. Plain `product_id` would trigger name_search and
    # interpret integers as labels (Odoo 19: rows 101+ "No matching record
    # found for name '411'" trap).
    new_headers = list(headers)
    new_headers[col] = 'product_id/.id'
    new_rows = [
        [str(extid_to_variant[r[col]]) if i == col else r[i] for i in range(len(r))]
        for r in rows
    ]
    return new_headers, new_rows


def run_one_import(
    client: JsonRpcClient,
    xlsx_path: Path,
    res_model: str,
    dry_run: bool,
) -> list[int]:
    """Push one XLSX through ``model.load`` — the import primitive used
    internally by ``base_import``. Returns list of imported record IDs."""
    if not xlsx_path.exists():
        raise FileNotFoundError(xlsx_path)
    headers, rows = read_xlsx_rows(xlsx_path)
    if res_model in PRODUCT_VARIANT_MODELS and not dry_run:
        headers, rows = resolve_template_extid_to_variant_id(client, headers, rows)
    _logger.info('  headers: %s', headers)
    _logger.info('  data rows: %d', len(rows))

    if dry_run:
        _logger.info('  dry-run: skipping %s.load() call', res_model)
        return []

    # `load` is the canonical Odoo import API. It honours external IDs
    # ('id' column) for update-in-place semantics, resolves '/id' relations,
    # and runs in a single transaction per call.
    result = client.execute_kw(
        res_model, 'load',
        [headers, rows],
    )
    messages = result.get('messages') or []
    blocking = [m for m in messages if m.get('type') == 'error']
    if blocking:
        for m in blocking:
            _logger.error('  LOAD ERROR: %s', m)
        raise RuntimeError(f'{res_model}.load failed: {len(blocking)} error(s)')
    for m in messages:
        _logger.warning('  message: %s', m)
    ids = result.get('ids') or []
    _logger.info('  loaded %d rows into %s', len(ids), res_model)
    return list(ids)


def apply_inventory(client: JsonRpcClient, quant_ids: list[int]) -> None:
    """Materialise inventory_quantity into on-hand via action_apply_inventory."""
    if not quant_ids:
        _logger.warning('  no quant ids to apply')
        return
    _logger.info('  calling action_apply_inventory on %d quants', len(quant_ids))
    client.execute_kw('stock.quant', 'action_apply_inventory', [quant_ids])
    _logger.info('  action_apply_inventory OK')


def verify_post_import(client: JsonRpcClient) -> None:
    """Quick read-back: count templates, categories, orderpoints."""
    n_tmpl = client.execute_kw(
        'product.template', 'search_count',
        [[('default_code', '=like', '%-%-S%')]],
    )
    n_cat = client.execute_kw(
        'product.category', 'search_count', [[('id', '!=', False)]],
    )
    n_orderpoint = client.execute_kw(
        'stock.warehouse.orderpoint', 'search_count', [[('id', '!=', False)]],
    )
    _logger.info('Post-import counts:')
    _logger.info('  product.template (SIZE-anchored SKUs) : %d', n_tmpl)
    _logger.info('  product.category (total)              : %d', n_cat)
    _logger.info('  stock.warehouse.orderpoint (total)    : %d', n_orderpoint)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--input-dir', type=Path, required=True,
                   help='Directory containing the 4 XLSX files.')
    p.add_argument('--dry-run', action='store_true',
                   help='Only call parse_preview for each step; no writes.')
    p.add_argument('--env-file', type=Path,
                   default=Path('.env'),
                   help='.env path (default ./.env)')
    args = p.parse_args()

    env = load_env(args.env_file)
    overlay = {k: os.environ[k] for k in os.environ if k.startswith('STAGING_')}
    env.update(overlay)

    base_url = env['STAGING_BASE_URL'].rstrip('/')
    db = env['STAGING_DB']
    login = env['STAGING_ADMIN_LOGIN']
    pwd = env['STAGING_ADMIN_PASSWORD']

    _logger.info('Target: %s  db=%s  user=%s', base_url, db, login)
    client = JsonRpcClient(base_url, db)
    version = client.version()
    _logger.info('Server version: %s', version.get('server_version'))
    uid = client.login(login, pwd)
    _logger.info('Authenticated uid=%s', uid)

    for fname, res_model in IMPORT_STEPS:
        path = args.input_dir / fname
        _logger.info('--- Step: %s -> %s ---', fname, res_model)
        ids = run_one_import(client, path, res_model, args.dry_run)
        # Apply inventory inline so a later-step failure can't leave the
        # just-loaded quants with inventory_quantity but no real on-hand.
        if res_model == 'stock.quant' and not args.dry_run and ids:
            _logger.info('--- Apply inventory ---')
            apply_inventory(client, ids)

    if not args.dry_run:
        _logger.info('--- Verification ---')
        verify_post_import(client)

    _logger.info('Done.')


if __name__ == '__main__':
    main()
