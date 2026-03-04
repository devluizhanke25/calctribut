"""Constantes e carregamento das regras tributarias."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict
from urllib.parse import quote

import requests

DEFAULT_MIN_WAGE = 1621.00

DEFAULT_RULES: Dict[str, Any] = {
    "version": "2026-01",
    "pf": {
        "irpf_flat": 0.275,
        "inss_pf_rate": 0.20,
        "prolabore_inss_rate": 0.11,
    },
    "pj": {
        "presumed_profit_rate": 0.32,
        "irpj_rate": 0.15,
        "irpj_additional_rate": 0.10,
        "irpj_additional_threshold": 240000,
        "csll_rate": 0.09,
        "pis_rate": 0.0065,
        "cofins_rate": 0.03,
        "cbs_rate": 0.009,
        "ibs_rate": 0.001,
        "inss_folha_rate": 0.20,
        "cbs_enabled": False,
        "ibs_enabled": False,
        "double_expense_in_pj": True,
    },
}

BASE_DIR = Path(__file__).resolve().parent
if os.getenv("VERCEL") or os.getenv("VERCEL_ENV"):
    CONFIG_PATH = Path("/tmp") / "brmsalcalc" / "regras_tributarias.json"
else:
    CONFIG_PATH = BASE_DIR / "data" / "regras_tributarias.json"
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
RULES_KV_KEY = "config:rules"


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _kv_config() -> Dict[str, str] | None:
    url = os.getenv("KV_REST_API_URL") or os.getenv("UPSTASH_REDIS_REST_URL")
    token = os.getenv("KV_REST_API_TOKEN") or os.getenv("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        return None
    return {"url": url.rstrip("/"), "token": token}


def _kv_request(command: str, *args: str, data: str | None = None) -> Dict[str, Any]:
    config = _kv_config()
    if not config:
        raise RuntimeError("KV nao configurado")
    path = "/".join([command.lower(), *[quote(str(arg), safe="") for arg in args]])
    url = f"{config['url']}/{path}"
    headers = {"Authorization": f"Bearer {config['token']}"}
    if data is None:
        response = requests.get(url, headers=headers, timeout=10)
    else:
        response = requests.post(url, headers=headers, data=data.encode("utf-8"), timeout=10)
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return payload


def _load_overrides() -> Dict[str, Any]:
    if _kv_config():
        payload = _kv_request("get", RULES_KV_KEY)
        raw = payload.get("result")
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def get_rules() -> Dict[str, Any]:
    return _deep_merge(DEFAULT_RULES, _load_overrides())


def save_rules(data: Dict[str, Any]) -> None:
    merged = _deep_merge(DEFAULT_RULES, data)
    if _kv_config():
        _kv_request("set", RULES_KV_KEY, data=json.dumps(merged, ensure_ascii=False, indent=2))
        return
    CONFIG_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
