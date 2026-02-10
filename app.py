from __future__ import annotations

import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from flask import Flask, jsonify, render_template, request

from backend.calculations import calculate_all
from backend.constants import DEFAULT_MIN_WAGE, get_rules, save_rules

app = Flask(__name__, static_folder="public", static_url_path="/static")

BASE_DIR = Path(__file__).resolve().parent
# Vercel filesystem is read-only except for /tmp.
if os.getenv("VERCEL") or os.getenv("VERCEL_ENV"):
    DATA_DIR = Path("/tmp") / "brmsalcalc" / "simulacoes"
else:
    DATA_DIR = BASE_DIR / "data" / "simulacoes"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SESSIONS: Dict[str, str] = {}


def _load_env() -> Dict[str, str]:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return {}
    data: Dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _get_credentials() -> Dict[str, str]:
    env = _load_env()
    return {
        "login": env.get("ADMIN_LOGIN", "admin"),
        "password": env.get("ADMIN_PASSWORD", "admin123"),
    }


def _slugify(value: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in value.strip())
    return "_".join(filter(None, safe.split("_"))).lower() or "empresa"


def _require_auth() -> Optional[str]:
    token = request.headers.get("X-Auth-Token")
    if not token or token not in SESSIONS:
        return None
    return SESSIONS[token]


def _json_error(message: str, status_code: int) -> tuple[Any, int]:
    return jsonify({"detail": message}), status_code


def _to_float(value: Any, field_name: str, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} invalido")
    if number < 0:
        raise ValueError(f"{field_name} nao pode ser negativo")
    return number


def _get_payload() -> Optional[Dict[str, Any]]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None
    return payload


def _parse_calculation_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    despesas_raw = payload.get("despesas_anuais") or {}
    if not isinstance(despesas_raw, dict):
        raise ValueError("despesas_anuais invalido")

    rendimento_mensal = payload.get("rendimento_mensal")
    if rendimento_mensal is None:
        raise ValueError("rendimento_mensal obrigatorio")

    annual_expenses = {
        "secretaria": _to_float(despesas_raw.get("secretaria"), "secretaria"),
        "aluguel_condominio": _to_float(despesas_raw.get("aluguel_condominio"), "aluguel_condominio"),
        "contador": _to_float(despesas_raw.get("contador"), "contador"),
        "outras_despesas": _to_float(despesas_raw.get("outras_despesas"), "outras_despesas"),
    }
    annual_expenses["total"] = (
        annual_expenses["secretaria"]
        + annual_expenses["aluguel_condominio"]
        + annual_expenses["contador"]
        + annual_expenses["outras_despesas"]
    )

    return {
        "nome_cliente": payload.get("nome_cliente"),
        "nome_empresa": payload.get("nome_empresa"),
        "rendimento_mensal": _to_float(rendimento_mensal, "rendimento_mensal"),
        "pro_labore": _to_float(payload.get("pro_labore"), "pro_labore"),
        "iss_fixo": _to_float(payload.get("iss_fixo"), "iss_fixo"),
        "salario_minimo": _to_float(payload.get("salario_minimo"), "salario_minimo"),
        "annual_expenses": annual_expenses,
    }


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.get("/health")
def health_check() -> Any:
    return jsonify({"status": "ok"})


@app.post("/login")
def login() -> Any:
    payload = _get_payload()
    if payload is None:
        return _json_error("Payload invalido", 400)
    credentials = _get_credentials()
    if payload.get("login") != credentials["login"] or payload.get("senha") != credentials["password"]:
        return _json_error("Credenciais invalidas", 401)
    token = secrets.token_urlsafe(24)
    SESSIONS[token] = credentials["login"]
    return jsonify({"token": token})


@app.post("/calculate")
def calculate() -> Any:
    if not _require_auth():
        return _json_error("Nao autorizado", 401)

    payload = _get_payload()
    if payload is None:
        return _json_error("Payload invalido", 400)
    try:
        parsed = _parse_calculation_payload(payload)
    except ValueError as exc:
        return _json_error(str(exc), 400)

    result = calculate_all(
        monthly_income=parsed["rendimento_mensal"],
        annual_expenses=parsed["annual_expenses"],
        pro_labore_monthly=parsed["pro_labore"],
        iss_fixo=parsed["iss_fixo"],
        salario_minimo=parsed["salario_minimo"] or DEFAULT_MIN_WAGE,
    )

    result["assumptions"] = {
        "annual_expenses": parsed["annual_expenses"]["total"],
        "min_wage_used": parsed["salario_minimo"] or DEFAULT_MIN_WAGE,
        "presumed_profit_rate": 0.32,
        "pis_rate": 0.0065,
        "cofins_rate": 0.03,
    }

    return jsonify(result)


@app.post("/simulations")
def save_simulation() -> Any:
    if not _require_auth():
        return _json_error("Nao autorizado", 401)

    payload = _get_payload()
    if payload is None:
        return _json_error("Payload invalido", 400)
    try:
        parsed = _parse_calculation_payload(payload)
    except ValueError as exc:
        return _json_error(str(exc), 400)

    nome_empresa = (parsed.get("nome_empresa") or "").strip()
    if not nome_empresa:
        return _json_error("Nome da empresa obrigatório", 400)

    result = calculate_all(
        monthly_income=parsed["rendimento_mensal"],
        annual_expenses=parsed["annual_expenses"],
        pro_labore_monthly=parsed["pro_labore"],
        iss_fixo=parsed["iss_fixo"],
        salario_minimo=parsed["salario_minimo"] or DEFAULT_MIN_WAGE,
    )

    now = datetime.now()
    empresa_dir = DATA_DIR / _slugify(nome_empresa)
    empresa_dir.mkdir(parents=True, exist_ok=True)
    file_id = now.strftime("%Y-%m-%d_%H%M%S")
    record = {
        "id": f"{_slugify(nome_empresa)}/{file_id}",
        "created_at": now.isoformat(),
        "nome_cliente": (parsed.get("nome_cliente") or "").strip(),
        "nome_empresa": nome_empresa,
        "input": {
            "nome_cliente": parsed.get("nome_cliente"),
            "nome_empresa": parsed.get("nome_empresa"),
            "rendimento_mensal": parsed.get("rendimento_mensal"),
            "despesas_anuais": {
                "secretaria": parsed["annual_expenses"]["secretaria"],
                "aluguel_condominio": parsed["annual_expenses"]["aluguel_condominio"],
                "contador": parsed["annual_expenses"]["contador"],
                "outras_despesas": parsed["annual_expenses"]["outras_despesas"],
            },
            "pro_labore": parsed.get("pro_labore"),
            "iss_fixo": parsed.get("iss_fixo"),
            "salario_minimo": parsed.get("salario_minimo"),
        },
        "output": result,
    }
    (empresa_dir / f"{file_id}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return jsonify({"id": record["id"]})


@app.get("/simulations")
def list_simulations() -> Any:
    if not _require_auth():
        return _json_error("Nao autorizado", 401)

    records: list[dict[str, Any]] = []
    for path in DATA_DIR.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        records.append(
            {
                "id": payload.get("id"),
                "created_at": payload.get("created_at"),
                "nome_cliente": payload.get("nome_cliente"),
                "nome_empresa": payload.get("nome_empresa"),
            }
        )
    records.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return jsonify(records)


@app.get("/simulations/<path:sim_id>")
def load_simulation(sim_id: str) -> Any:
    if not _require_auth():
        return _json_error("Nao autorizado", 401)

    safe_id = sim_id.replace("..", "").strip("/")
    path = DATA_DIR / f"{safe_id}.json"
    if not path.exists():
        return _json_error("Simulacao nao encontrada", 404)
    return jsonify(json.loads(path.read_text(encoding="utf-8")))


@app.delete("/simulations/<path:sim_id>")
def delete_simulation(sim_id: str) -> Any:
    if not _require_auth():
        return _json_error("Nao autorizado", 401)

    safe_id = sim_id.replace("..", "").strip("/")
    path = DATA_DIR / f"{safe_id}.json"
    if not path.exists():
        return _json_error("Simulacao nao encontrada", 404)
    path.unlink()
    return jsonify({"status": "deleted"})


@app.get("/analysis")
def analysis() -> Any:
    if not _require_auth():
        return _json_error("Nao autorizado", 401)

    rows: list[dict[str, Any]] = []
    for path in DATA_DIR.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        output = payload.get("output", {})
        pf = output.get("pf", {})
        pj = output.get("pj", {})
        comparativo = output.get("comparativo", {})
        rows.append(
            {
                "created_at": payload.get("created_at"),
                "nome_empresa": payload.get("nome_empresa"),
                "nome_cliente": payload.get("nome_cliente"),
                "rendimento_anual": pf.get("rendimento_anual"),
                "total_tributos_pf": pf.get("total_tributos"),
                "total_impostos_pj": pj.get("total_impostos"),
                "impacto_pf": pj.get("impacto_pf"),
                "aliquota_pf": pf.get("aliquota_efetiva"),
                "aliquota_pj_final": pj.get("aliquota_efetiva_final"),
                "economia_tributaria": comparativo.get("economia_tributaria"),
            }
        )
    rows.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return jsonify(rows)


@app.get("/config")
def get_config() -> Any:
    if not _require_auth():
        return _json_error("Nao autorizado", 401)
    return jsonify(get_rules())


@app.put("/config")
def update_config() -> Any:
    if not _require_auth():
        return _json_error("Nao autorizado", 401)

    payload = _get_payload()
    if not isinstance(payload, dict):
        return _json_error("Formato invalido", 400)
    save_rules(payload)
    return jsonify({"status": "updated"})
