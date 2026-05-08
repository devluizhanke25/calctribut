from __future__ import annotations

import secrets
from datetime import datetime
from pathlib import Path
from typing import Dict

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .calculations import calculate_all
from .constants import get_rules, save_rules
from .models import CalculationInput
from .storage import (
    authenticate_user,
    count_users,
    create_user as db_create_user,
    delete_simulation as db_delete_simulation,
    delete_user as db_delete_user,
    ensure_default_user,
    get_simulation as db_get_simulation,
    get_user as db_get_user,
    init_db,
    list_simulations as db_list_simulations,
    list_users as db_list_users,
    migrate_legacy_json_simulations,
    save_simulation as db_save_simulation,
    set_user_role as db_set_user_role,
    update_user_password as db_update_user_password,
)

app = FastAPI(title="Simulador Financeiro-Tributario")

# CORS liberado para facilitar o consumo pelo frontend local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "simulador.db"
init_db(DB_PATH)
migrate_legacy_json_simulations(DB_PATH, BASE_DIR / "data" / "simulacoes")

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


_bootstrap_creds = _get_credentials()
ensure_default_user(DB_PATH, _bootstrap_creds["login"], _bootstrap_creds["password"])
db_set_user_role(DB_PATH, _bootstrap_creds["login"], "admin")


def _slugify(value: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in value.strip())
    return "_".join(filter(None, safe.split("_"))).lower() or "empresa"


def _require_auth(x_auth_token: str | None = Header(default=None)) -> str:
    if not x_auth_token or x_auth_token not in SESSIONS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nao autorizado")
    return SESSIONS[x_auth_token]


def _is_admin(login_value: str) -> bool:
    user = db_get_user(DB_PATH, login_value)
    if not user:
        return False
    return str(user.get("role") or "analista") == "admin"


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/login")
def login(payload: dict) -> dict:
    login_value = str(payload.get("login") or "")
    password_value = str(payload.get("senha") or "")
    if not authenticate_user(DB_PATH, login_value, password_value):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais invalidas")
    token = secrets.token_urlsafe(24)
    SESSIONS[token] = login_value
    user = db_get_user(DB_PATH, login_value) or {}
    return {"token": token, "role": user.get("role", "analista")}


@app.post("/calculate")
def calculate(payload: CalculationInput, _user: str = Depends(_require_auth)) -> dict:
    rules = get_rules()
    annual_expenses = {
        "secretaria": payload.despesas_anuais.secretaria,
        "aluguel_condominio": payload.despesas_anuais.aluguel_condominio,
        "contador": payload.despesas_anuais.contador,
        "outras_despesas": payload.despesas_anuais.outras_despesas,
    }
    annual_expenses["total"] = (
        annual_expenses["secretaria"]
        + annual_expenses["aluguel_condominio"]
        + annual_expenses["contador"]
        + annual_expenses["outras_despesas"]
    )

    result = calculate_all(
        monthly_income=payload.rendimento_mensal,
        annual_expenses=annual_expenses,
        pro_labore_monthly=payload.pro_labore,
        iss_fixo=payload.iss_fixo,
    )

    # Include some context to help the UI explain assumptions
    result["assumptions"] = {
        "annual_expenses": annual_expenses["total"],
        "presumed_profit_regime": rules["pj"]["presumed_profit_regime"],
        "standard_irpj_presumed_rate": rules["pj"]["standard_irpj_presumed_rate"],
        "standard_csll_presumed_rate": rules["pj"]["standard_csll_presumed_rate"],
        "hospital_presumed_rate": rules["pj"]["hospital_presumed_rate"],
        "pis_rate": rules["pj"]["pis_rate"],
        "cofins_rate": rules["pj"]["cofins_rate"],
    }

    return result


@app.post("/simulations")
def save_simulation(payload: CalculationInput, _user: str = Depends(_require_auth)) -> dict:
    nome_empresa = (payload.nome_empresa or "").strip()
    if not nome_empresa:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome da empresa obrigatório")

    annual_expenses = {
        "secretaria": payload.despesas_anuais.secretaria,
        "aluguel_condominio": payload.despesas_anuais.aluguel_condominio,
        "contador": payload.despesas_anuais.contador,
        "outras_despesas": payload.despesas_anuais.outras_despesas,
    }
    annual_expenses["total"] = (
        annual_expenses["secretaria"]
        + annual_expenses["aluguel_condominio"]
        + annual_expenses["contador"]
        + annual_expenses["outras_despesas"]
    )

    result = calculate_all(
        monthly_income=payload.rendimento_mensal,
        annual_expenses=annual_expenses,
        pro_labore_monthly=payload.pro_labore,
        iss_fixo=payload.iss_fixo,
    )

    now = datetime.now()
    file_id = now.strftime("%Y-%m-%d_%H%M%S_%f")
    record = {
        "id": f"{_slugify(nome_empresa)}/{file_id}",
        "created_at": now.isoformat(),
        "nome_cliente": (payload.nome_cliente or "").strip(),
        "nome_empresa": nome_empresa,
        "input": payload.model_dump(),
        "output": result,
    }
    db_save_simulation(DB_PATH, record)
    return {"id": record["id"]}


@app.get("/simulations")
def list_simulations(_user: str = Depends(_require_auth)) -> list[dict]:
    records: list[dict] = []
    for payload in db_list_simulations(DB_PATH):
        records.append(
            {
                "id": payload.get("id"),
                "created_at": payload.get("created_at"),
                "nome_cliente": payload.get("nome_cliente"),
                "nome_empresa": payload.get("nome_empresa"),
            }
        )
    records.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return records


@app.get("/simulations/{sim_id:path}")
def load_simulation(sim_id: str, _user: str = Depends(_require_auth)) -> dict:
    safe_id = sim_id.replace("..", "").strip("/")
    payload = db_get_simulation(DB_PATH, safe_id)
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulacao nao encontrada")
    return payload


@app.delete("/simulations/{sim_id:path}")
def delete_simulation(sim_id: str, _user: str = Depends(_require_auth)) -> dict:
    safe_id = sim_id.replace("..", "").strip("/")
    payload = db_get_simulation(DB_PATH, safe_id)
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulacao nao encontrada")
    db_delete_simulation(DB_PATH, safe_id)
    return {"status": "deleted"}


@app.get("/analysis")
def analysis(_user: str = Depends(_require_auth)) -> list[dict]:
    rows: list[dict] = []
    for payload in db_list_simulations(DB_PATH):
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
    return rows


@app.get("/config")
def get_config(_user: str = Depends(_require_auth)) -> dict:
    if not _is_admin(_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")
    return get_rules()


@app.put("/config")
def update_config(payload: dict, _user: str = Depends(_require_auth)) -> dict:
    if not _is_admin(_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Formato invalido")
    save_rules(payload)
    return {"status": "updated"}


@app.get("/users")
def users_list(_user: str = Depends(_require_auth)) -> list[dict]:
    if not _is_admin(_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")
    return db_list_users(DB_PATH)


@app.post("/users")
def user_create(payload: dict, _user: str = Depends(_require_auth)) -> dict:
    if not _is_admin(_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")
    login_value = str(payload.get("login") or "").strip()
    senha = str(payload.get("senha") or "")
    if len(login_value) < 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Login deve ter ao menos 3 caracteres")
    if len(senha) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha deve ter ao menos 6 caracteres")
    role = str(payload.get("role") or "analista").strip().lower()
    if role not in ("admin", "analista"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Perfil invalido")
    if db_get_user(DB_PATH, login_value):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Usuario ja existe")
    db_create_user(DB_PATH, login_value, senha, role)
    return {"status": "created", "login": login_value, "role": role}


@app.put("/users/{login_value}")
def user_update(login_value: str, payload: dict, _user: str = Depends(_require_auth)) -> dict:
    if not _is_admin(_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")
    senha = str(payload.get("senha") or "")
    if len(senha) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha deve ter ao menos 6 caracteres")
    if not db_update_user_password(DB_PATH, login_value, senha):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado")
    return {"status": "updated", "login": login_value}


@app.delete("/users/{login_value}")
def user_delete(login_value: str, _user: str = Depends(_require_auth)) -> dict:
    if not _is_admin(_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")
    if _user == login_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nao e permitido excluir o proprio usuario logado",
        )
    if not db_get_user(DB_PATH, login_value):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado")
    if count_users(DB_PATH) <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nao e permitido remover o ultimo usuario")
    db_delete_user(DB_PATH, login_value)
    return {"status": "deleted", "login": login_value}
