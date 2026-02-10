from __future__ import annotations

import hashlib
import json
import os
from urllib.parse import quote
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from flask import Flask, jsonify, render_template, request

from backend.calculations import calculate_all
from backend.constants import DEFAULT_MIN_WAGE, get_rules, save_rules

BASE_DIR = Path(__file__).resolve().parent
# Use absolute paths to avoid cwd issues on Vercel.
app = Flask(
    __name__,
    static_folder=str(BASE_DIR / "static"),
    static_url_path="/static",
    template_folder=str(BASE_DIR / "templates"),
)
# Vercel filesystem is read-only except for /tmp.
if os.getenv("VERCEL") or os.getenv("VERCEL_ENV"):
    DATA_DIR = Path("/tmp") / "brmsalcalc" / "simulacoes"
else:
    DATA_DIR = BASE_DIR / "data" / "simulacoes"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _get_credentials() -> Dict[str, str]:
    env = {
        "ADMIN_LOGIN": os.getenv("ADMIN_LOGIN"),
        "ADMIN_PASSWORD": os.getenv("ADMIN_PASSWORD"),
    }
    if not env["ADMIN_LOGIN"] or not env["ADMIN_PASSWORD"]:
        env_path = BASE_DIR / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if not line or line.strip().startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() in ("ADMIN_LOGIN", "ADMIN_PASSWORD"):
                    env[key.strip()] = value.strip()
    return {
        "login": env.get("ADMIN_LOGIN") or "admin",
        "password": env.get("ADMIN_PASSWORD") or "admin123",
    }


def _make_token(login: str, password: str) -> str:
    raw = f"{login}:{password}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _kv_config() -> Optional[Dict[str, str]]:
    url = os.getenv("KV_REST_API_URL") or os.getenv("UPSTASH_REDIS_REST_URL")
    token = os.getenv("KV_REST_API_TOKEN") or os.getenv("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        return None
    return {"url": url.rstrip("/"), "token": token}


def _kv_request(command: str, *args: str, data: Optional[str] = None) -> Dict[str, Any]:
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


def _kv_set(key: str, value: str) -> None:
    _kv_request("set", key, data=value)


def _kv_get(key: str) -> Optional[str]:
    payload = _kv_request("get", key)
    return payload.get("result")


def _kv_del(key: str) -> None:
    _kv_request("del", key)


def _kv_zadd(key: str, score: float, member: str) -> None:
    _kv_request("zadd", key, str(score), member)


def _kv_zrem(key: str, member: str) -> None:
    _kv_request("zrem", key, member)


def _kv_zrange(key: str, start: int, stop: int, rev: bool = False) -> list[str]:
    args = [key, str(start), str(stop)]
    if rev:
        args.append("REV")
    payload = _kv_request("zrange", *args)
    return payload.get("result") or []


def _kv_mget(keys: list[str]) -> list[Optional[str]]:
    if not keys:
        return []
    payload = _kv_request("mget", *keys)
    return payload.get("result") or []


def _storage_use_kv() -> bool:
    return _kv_config() is not None


def _require_kv_if_vercel() -> Optional[tuple[Any, int]]:
    if os.getenv("VERCEL") or os.getenv("VERCEL_ENV"):
        if not _kv_config():
            return _json_error("KV nao configurado", 500)
    return None


def _slugify(value: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in value.strip())
    return "_".join(filter(None, safe.split("_"))).lower() or "empresa"


def _load_records() -> list[dict[str, Any]]:
    if _storage_use_kv():
        ids = _kv_zrange("sim:index", 0, -1, rev=True)
        keys = [f"sim:{sim_id}" for sim_id in ids]
        raw_items = _kv_mget(keys)
        records: list[dict[str, Any]] = []
        for raw in raw_items:
            if not raw:
                continue
            try:
                records.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return records

    records: list[dict[str, Any]] = []
    for path in DATA_DIR.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        records.append(payload)
    return records


def _save_record(record: dict[str, Any]) -> None:
    if _storage_use_kv():
        sim_id = record["id"]
        key = f"sim:{sim_id}"
        _kv_set(key, json.dumps(record, ensure_ascii=False, indent=2))
        created_at = record.get("created_at") or datetime.now().isoformat()
        score = datetime.fromisoformat(created_at).timestamp()
        _kv_zadd("sim:index", score, sim_id)
        return

    sim_id = record["id"]
    path = DATA_DIR / f"{sim_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_record(sim_id: str) -> Optional[dict[str, Any]]:
    if _storage_use_kv():
        key = f"sim:{sim_id}"
        raw = _kv_get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    path = DATA_DIR / f"{sim_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _delete_record(sim_id: str) -> None:
    if _storage_use_kv():
        key = f"sim:{sim_id}"
        _kv_del(key)
        _kv_zrem("sim:index", sim_id)
        return

    path = DATA_DIR / f"{sim_id}.json"
    if path.exists():
        path.unlink()


def _require_auth() -> Optional[str]:
    token = request.headers.get("X-Auth-Token")
    if not token:
        return None
    credentials = _get_credentials()
    expected = _make_token(credentials["login"], credentials["password"])
    if token != expected:
        return None
    return credentials["login"]


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
    token = _make_token(credentials["login"], credentials["password"])
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
    kv_guard = _require_kv_if_vercel()
    if kv_guard:
        return kv_guard

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
    file_id = now.strftime("%Y-%m-%d_%H%M%S")
    sim_id = f"{_slugify(nome_empresa)}/{file_id}"
    record = {
        "id": sim_id,
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
    _save_record(record)
    return jsonify({"id": record["id"]})


@app.get("/simulations")
def list_simulations() -> Any:
    if not _require_auth():
        return _json_error("Nao autorizado", 401)
    kv_guard = _require_kv_if_vercel()
    if kv_guard:
        return kv_guard

    records = []
    for payload in _load_records():
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
    kv_guard = _require_kv_if_vercel()
    if kv_guard:
        return kv_guard

    safe_id = sim_id.replace("..", "").strip("/")
    payload = _get_record(safe_id)
    if not payload:
        return _json_error("Simulacao nao encontrada", 404)
    return jsonify(payload)


@app.delete("/simulations/<path:sim_id>")
def delete_simulation(sim_id: str) -> Any:
    if not _require_auth():
        return _json_error("Nao autorizado", 401)
    kv_guard = _require_kv_if_vercel()
    if kv_guard:
        return kv_guard

    safe_id = sim_id.replace("..", "").strip("/")
    payload = _get_record(safe_id)
    if not payload:
        return _json_error("Simulacao nao encontrada", 404)
    _delete_record(safe_id)
    return jsonify({"status": "deleted"})


@app.get("/analysis")
def analysis() -> Any:
    if not _require_auth():
        return _json_error("Nao autorizado", 401)
    kv_guard = _require_kv_if_vercel()
    if kv_guard:
        return kv_guard

    rows: list[dict[str, Any]] = []
    for payload in _load_records():
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


@app.get("/simulations/")
def list_simulations_slash() -> Any:
    return list_simulations()


@app.get("/analysis/")
def analysis_slash() -> Any:
    return analysis()


@app.get("/config/")
def config_slash() -> Any:
    return get_config()


@app.get("/kv-health")
def kv_health() -> Any:
    config = _kv_config()
    if not config:
        return _json_error("KV nao configurado", 500)
    try:
        _kv_set("kv:health", "ok")
        value = _kv_get("kv:health")
        return jsonify({"status": "ok", "value": value})
    except Exception as exc:
        return _json_error(f"KV erro: {exc}", 500)
