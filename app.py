from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from flask import Flask, Response, jsonify, render_template, request, send_from_directory

from backend.calculations import calculate_all
from backend.constants import get_rules, save_rules
from backend.storage import (
    authenticate_user,
    count_users,
    create_user as db_create_user,
    delete_simulation as db_delete_simulation,
    delete_user as db_delete_user,
    ensure_default_user,
    get_idempotency as db_get_idempotency,
    get_simulation as db_get_simulation,
    get_user as db_get_user,
    init_db,
    list_simulations as db_list_simulations,
    list_users as db_list_users,
    migrate_legacy_json_simulations,
    save_simulation as db_save_simulation,
    set_user_role as db_set_user_role,
    set_idempotency as db_set_idempotency,
    update_user_password as db_update_user_password,
)

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
# Use absolute paths to avoid cwd issues on Vercel.
app = Flask(
    __name__,
    static_folder=str(BASE_DIR / "static"),
    static_url_path="/static",
    template_folder=str(FRONTEND_DIR),
)
# Vercel filesystem is read-only except for /tmp.
if os.getenv("VERCEL") or os.getenv("VERCEL_ENV"):
    DB_PATH = Path("/tmp") / "brmsalcalc" / "simulador.db"
else:
    DB_PATH = BASE_DIR / "data" / "simulador.db"
init_db(DB_PATH)
migrate_legacy_json_simulations(DB_PATH, BASE_DIR / "data" / "simulacoes")
TOKEN_SALT = os.getenv("TOKEN_SALT", "brmsalcalc-token-salt")


@app.after_request
def add_cors_headers(response: Response) -> Response:
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Auth-Token, X-Idempotency-Key"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


def _get_credentials_with_source() -> tuple[Dict[str, str], str]:
    def _normalize_env_credential(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in ("'", '"'):
            cleaned = cleaned[1:-1].strip()
        return cleaned

    env = {
        "ADMIN_LOGIN": _normalize_env_credential(os.getenv("ADMIN_LOGIN")),
        "ADMIN_PASSWORD": _normalize_env_credential(os.getenv("ADMIN_PASSWORD")),
    }
    source = "env"
    if not env["ADMIN_LOGIN"] or not env["ADMIN_PASSWORD"]:
        env_path = BASE_DIR / ".env"
        if env_path.exists():
            source = ".env"
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if not line or line.strip().startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() in ("ADMIN_LOGIN", "ADMIN_PASSWORD"):
                    env[key.strip()] = _normalize_env_credential(value)
    creds = {
        "login": env.get("ADMIN_LOGIN") or "admin",
        "password": env.get("ADMIN_PASSWORD") or "admin123",
    }
    if creds["login"] == "admin" and creds["password"] == "admin123":
        source = "defaults"
    return creds, source


def _get_credentials() -> Dict[str, str]:
    creds, _ = _get_credentials_with_source()
    return creds


_bootstrap_creds = _get_credentials()
ensure_default_user(DB_PATH, _bootstrap_creds["login"], _bootstrap_creds["password"])
db_set_user_role(DB_PATH, _bootstrap_creds["login"], "admin")


def _make_token(login: str, password: str) -> str:
    _ = password
    signature = hashlib.sha256(f"{login}:{TOKEN_SALT}".encode("utf-8")).hexdigest()
    return f"{login}.{signature}"


def _slugify(value: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in value.strip())
    return "_".join(filter(None, safe.split("_"))).lower() or "empresa"


def _stable_json_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _idempotency_get(user: str, idem_key: str) -> Optional[str]:
    if not idem_key:
        return None
    return db_get_idempotency(DB_PATH, user, idem_key)


def _idempotency_set(user: str, idem_key: str, sim_id: str) -> None:
    if not idem_key:
        return
    db_set_idempotency(DB_PATH, user, idem_key, sim_id)


def _find_duplicate_same_date(parsed: dict[str, Any], target_date: datetime) -> Optional[dict[str, Any]]:
    candidate_input = {
        "nome_cliente": (parsed.get("nome_cliente") or "").strip(),
        "nome_empresa": (parsed.get("nome_empresa") or "").strip(),
        "rendimento_mensal": parsed.get("rendimento_mensal"),
        "pro_labore": parsed.get("pro_labore"),
        "iss_fixo": parsed.get("iss_fixo"),
        "despesas_anuais": {
            "secretaria": parsed["annual_expenses"]["secretaria"],
            "aluguel_condominio": parsed["annual_expenses"]["aluguel_condominio"],
            "contador": parsed["annual_expenses"]["contador"],
            "outras_despesas": parsed["annual_expenses"]["outras_despesas"],
        },
    }
    candidate_hash = _stable_json_hash(candidate_input)
    target_day = target_date.date()
    for record in _load_records():
        created_at_raw = record.get("created_at")
        if not created_at_raw:
            continue
        try:
            created_at = datetime.fromisoformat(created_at_raw)
        except ValueError:
            continue
        if created_at.date() != target_day:
            continue
        record_input = record.get("input") or {}
        if not isinstance(record_input, dict):
            continue
        record_hash = _stable_json_hash(
            {
                "nome_cliente": (record_input.get("nome_cliente") or "").strip(),
                "nome_empresa": (record_input.get("nome_empresa") or "").strip(),
                "rendimento_mensal": record_input.get("rendimento_mensal"),
                "pro_labore": record_input.get("pro_labore"),
                "iss_fixo": record_input.get("iss_fixo"),
                "despesas_anuais": record_input.get("despesas_anuais") or {},
            }
        )
        if record_hash == candidate_hash:
            return record
    return None


def _load_records() -> list[dict[str, Any]]:
    return db_list_simulations(DB_PATH)


def _save_record(record: dict[str, Any]) -> None:
    db_save_simulation(DB_PATH, record)


def _get_record(sim_id: str) -> Optional[dict[str, Any]]:
    return db_get_simulation(DB_PATH, sim_id)


def _delete_record(sim_id: str) -> None:
    db_delete_simulation(DB_PATH, sim_id)


def _require_auth() -> Optional[dict[str, str]]:
    token = request.headers.get("X-Auth-Token")
    if not token:
        return None
    if "." not in token:
        return None
    login, signature = token.split(".", 1)
    if not login or not signature:
        return None
    expected_signature = hashlib.sha256(f"{login}:{TOKEN_SALT}".encode("utf-8")).hexdigest()
    if not secrets.compare_digest(signature, expected_signature):
        return None
    user = db_get_user(DB_PATH, login)
    if not user:
        return None
    return {"login": str(user["login"]), "role": str(user.get("role") or "analista")}


def _require_admin() -> Optional[dict[str, str]]:
    user = _require_auth()
    if not user:
        return None
    if user.get("role") != "admin":
        return None
    return user


def _json_error(message: str, status_code: int) -> tuple[Any, int]:
    return jsonify({"detail": message}), status_code


@app.get("/styles.css")
def frontend_styles() -> Any:
    return send_from_directory(FRONTEND_DIR, "styles.css")


@app.get("/app.js")
def frontend_app_js() -> Any:
    app_js = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8-sig")
    app_js = app_js.replace('const API_BASE = "http://127.0.0.1:8000";', 'const API_BASE = "";')
    return Response(app_js, mimetype="application/javascript")


@app.get("/img/<path:filename>")
def frontend_img(filename: str) -> Any:
    return send_from_directory(FRONTEND_DIR / "img", filename)


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
    payload_login = str(payload.get("login") or "")
    payload_senha = str(payload.get("senha") or "")
    if not authenticate_user(DB_PATH, payload_login, payload_senha):
        return _json_error("Credenciais invalidas", 401)
    token = _make_token(payload_login, payload_senha)
    user = db_get_user(DB_PATH, payload_login) or {}
    return jsonify({"token": token, "role": user.get("role", "analista")})


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

    rules = get_rules()
    result = calculate_all(
        monthly_income=parsed["rendimento_mensal"],
        annual_expenses=parsed["annual_expenses"],
        pro_labore_monthly=parsed["pro_labore"],
        iss_fixo=parsed["iss_fixo"],
    )

    result["assumptions"] = {
        "annual_expenses": parsed["annual_expenses"]["total"],
        "presumed_profit_regime": rules["pj"]["presumed_profit_regime"],
        "standard_irpj_presumed_rate": rules["pj"]["standard_irpj_presumed_rate"],
        "standard_csll_presumed_rate": rules["pj"]["standard_csll_presumed_rate"],
        "hospital_presumed_rate": rules["pj"]["hospital_presumed_rate"],
        "pis_rate": rules["pj"]["pis_rate"],
        "cofins_rate": rules["pj"]["cofins_rate"],
    }

    return jsonify(result)


@app.post("/simulations")
def save_simulation() -> Any:
    auth_ctx = _require_auth()
    auth_user = auth_ctx["login"] if auth_ctx else None
    if not auth_user:
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
        return _json_error("Nome da empresa obrigatorio", 400)

    idempotency_key = (request.headers.get("X-Idempotency-Key") or "").strip()
    if idempotency_key:
        existing_id = _idempotency_get(auth_user, idempotency_key)
        if existing_id:
            existing_record = _get_record(existing_id)
            if existing_record:
                return jsonify({"id": existing_id, "deduplicated": True})

    duplicate_record = _find_duplicate_same_date(parsed, target_date=datetime.now())
    if duplicate_record and duplicate_record.get("id"):
        dedup_id = str(duplicate_record["id"])
        if idempotency_key:
            _idempotency_set(auth_user, idempotency_key, dedup_id)
        return jsonify(
            {
                "detail": "Registro ja inserido com os mesmos dados na data de hoje.",
                "id": dedup_id,
                "duplicate": True,
            }
        ), 409

    result = calculate_all(
        monthly_income=parsed["rendimento_mensal"],
        annual_expenses=parsed["annual_expenses"],
        pro_labore_monthly=parsed["pro_labore"],
        iss_fixo=parsed["iss_fixo"],
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
        },
        "output": result,
    }
    _save_record(record)
    if idempotency_key:
        _idempotency_set(auth_user, idempotency_key, record["id"])
    return jsonify({"id": record["id"]})



@app.get("/simulations")
def list_simulations() -> Any:
    if not _require_auth():
        return _json_error("Nao autorizado", 401)

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

    safe_id = sim_id.replace("..", "").strip("/")
    payload = _get_record(safe_id)
    if not payload:
        return _json_error("Simulacao nao encontrada", 404)
    return jsonify(payload)


@app.delete("/simulations/<path:sim_id>")
def delete_simulation(sim_id: str) -> Any:
    if not _require_auth():
        return _json_error("Nao autorizado", 401)

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
    auth_user = _require_auth()
    if not auth_user:
        return _json_error("Nao autorizado", 401)
    if auth_user["role"] != "admin":
        return _json_error("Acesso restrito a administradores", 403)
    return jsonify(get_rules())


@app.put("/config")
def update_config() -> Any:
    auth_user = _require_auth()
    if not auth_user:
        return _json_error("Nao autorizado", 401)
    if auth_user["role"] != "admin":
        return _json_error("Acesso restrito a administradores", 403)

    payload = _get_payload()
    if not isinstance(payload, dict):
        return _json_error("Formato invalido", 400)
    save_rules(payload)
    return jsonify({"status": "updated"})


@app.get("/users")
def list_users() -> Any:
    auth_user = _require_auth()
    if not auth_user:
        return _json_error("Nao autorizado", 401)
    if auth_user["role"] != "admin":
        return _json_error("Acesso restrito a administradores", 403)
    return jsonify(db_list_users(DB_PATH))


@app.post("/users")
def create_user() -> Any:
    auth_user = _require_auth()
    if not auth_user:
        return _json_error("Nao autorizado", 401)
    if auth_user["role"] != "admin":
        return _json_error("Acesso restrito a administradores", 403)
    payload = _get_payload()
    if payload is None:
        return _json_error("Payload invalido", 400)
    login = str(payload.get("login") or "").strip()
    senha = str(payload.get("senha") or "")
    if len(login) < 3:
        return _json_error("Login deve ter ao menos 3 caracteres", 400)
    if len(senha) < 6:
        return _json_error("Senha deve ter ao menos 6 caracteres", 400)
    role = str(payload.get("role") or "analista").strip().lower()
    if role not in ("admin", "analista"):
        return _json_error("Perfil invalido", 400)
    if db_get_user(DB_PATH, login):
        return _json_error("Usuario ja existe", 409)
    db_create_user(DB_PATH, login, senha, role)
    return jsonify({"status": "created", "login": login, "role": role})


@app.put("/users/<login>")
def update_user(login: str) -> Any:
    auth_user = _require_auth()
    if not auth_user:
        return _json_error("Nao autorizado", 401)
    if auth_user["role"] != "admin":
        return _json_error("Acesso restrito a administradores", 403)
    payload = _get_payload()
    if payload is None:
        return _json_error("Payload invalido", 400)
    senha = str(payload.get("senha") or "")
    if len(senha) < 6:
        return _json_error("Senha deve ter ao menos 6 caracteres", 400)
    if not db_update_user_password(DB_PATH, login, senha):
        return _json_error("Usuario nao encontrado", 404)
    return jsonify({"status": "updated", "login": login})


@app.delete("/users/<login>")
def delete_user(login: str) -> Any:
    auth_user = _require_auth()
    if not auth_user:
        return _json_error("Nao autorizado", 401)
    if auth_user["role"] != "admin":
        return _json_error("Acesso restrito a administradores", 403)
    if auth_user["login"] == login:
        return _json_error("Nao e permitido excluir o proprio usuario logado", 400)
    user = db_get_user(DB_PATH, login)
    if not user:
        return _json_error("Usuario nao encontrado", 404)
    if count_users(DB_PATH) <= 1:
        return _json_error("Nao e permitido remover o ultimo usuario", 400)
    db_delete_user(DB_PATH, login)
    return jsonify({"status": "deleted", "login": login})


@app.get("/simulations/")
def list_simulations_slash() -> Any:
    return list_simulations()


@app.get("/analysis/")
def analysis_slash() -> Any:
    return analysis()


@app.get("/config/")
def config_slash() -> Any:
    return get_config()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
