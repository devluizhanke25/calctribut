"""Constantes e carregamento das regras tributarias."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

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
CONFIG_PATH = BASE_DIR / "data" / "regras_tributarias.json"


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def get_rules() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return _deep_merge(DEFAULT_RULES, data)
        except json.JSONDecodeError:
            return DEFAULT_RULES
    return DEFAULT_RULES


def save_rules(data: Dict[str, Any]) -> None:
    merged = _deep_merge(DEFAULT_RULES, data)
    CONFIG_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
