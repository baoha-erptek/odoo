"""Shared XML-RPC session helper for UAT fixtures.

Reuses the pattern from scripts/e2e_product_listing.py without importing it
(that script has its own argparse + Excel coupling we don't want here).
"""
from __future__ import annotations

import logging
import os
import sys
import xmlrpc.client
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = REPO_ROOT / ".env"

log = logging.getLogger("uat.xmlrpc")


def _load_env_file() -> dict[str, str]:
    out: dict[str, str] = {}
    if not ENV_FILE.exists():
        return out
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip("'").strip('"')
        out[k.strip()] = v
    return out


_ENV = _load_env_file()


def env(key: str, fallback: str = "") -> str:
    return os.environ.get(key) or _ENV.get(key) or fallback


@dataclass
class StagingConfig:
    base_url: str
    db: str
    login: str
    password: str


@dataclass
class XmlrpcSession:
    cfg: StagingConfig
    uid: int
    common: xmlrpc.client.ServerProxy
    models: xmlrpc.client.ServerProxy

    def call(self, model: str, method: str, args: list, kwargs: dict | None = None) -> Any:
        return self.models.execute_kw(
            self.cfg.db, self.uid, self.cfg.password,
            model, method, args, kwargs or {},
        )


def connect(
    base_url: str | None = None,
    db: str | None = None,
    login: str | None = None,
    password: str | None = None,
) -> XmlrpcSession:
    cfg = StagingConfig(
        base_url=(base_url or env("STAGING_BASE_URL", "https://odoo.hatafax.com")).rstrip("/"),
        db=db or env("STAGING_DB", "esty_odoo19"),
        login=login or env("STAGING_ADMIN_LOGIN", "admin"),
        password=password or env("STAGING_ADMIN_PASSWORD"),
    )
    if not cfg.password:
        raise SystemExit(
            "Missing admin password. Set STAGING_ADMIN_PASSWORD in .env or env. "
            f"(login={cfg.login!r}, db={cfg.db!r})"
        )
    common = xmlrpc.client.ServerProxy(f"{cfg.base_url}/xmlrpc/2/common", allow_none=True)
    models = xmlrpc.client.ServerProxy(f"{cfg.base_url}/xmlrpc/2/object", allow_none=True)
    uid = common.authenticate(cfg.db, cfg.login, cfg.password, {})
    if not uid:
        raise SystemExit(
            f"Auth failed for {cfg.login!r} on {cfg.base_url}/{cfg.db}. "
            "Check STAGING_ADMIN_LOGIN + STAGING_ADMIN_PASSWORD."
        )
    log.info("XMLRPC authenticated: uid=%s base=%s db=%s", uid, cfg.base_url, cfg.db)
    return XmlrpcSession(cfg=cfg, uid=uid, common=common, models=models)
