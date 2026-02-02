from __future__ import annotations

import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Dict

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .calculations import calculate_all
from .constants import DEFAULT_MIN_WAGE, get_rules, save_rules
from .models import CalculationInput

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


def _require_auth(x_auth_token: str | None = Header(default=None)) -> str:
    if not x_auth_token or x_auth_token not in SESSIONS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nao autorizado")
    return SESSIONS[x_auth_token]


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/login")
def login(payload: dict) -> dict:
    credentials = _get_credentials()
    if payload.get("login") != credentials["login"] or payload.get("senha") != credentials["password"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais invalidas")
    token = secrets.token_urlsafe(24)
    SESSIONS[token] = credentials["login"]
    return {"token": token}


@app.post("/calculate")
def calculate(payload: CalculationInput, _user: str = Depends(_require_auth)) -> dict:
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
        salario_minimo=payload.salario_minimo,
    )

    # Include some context to help the UI explain assumptions
    result["assumptions"] = {
        "annual_expenses": annual_expenses["total"],
        "min_wage_used": payload.salario_minimo or DEFAULT_MIN_WAGE,
        "presumed_profit_rate": 0.32,
        "pis_rate": 0.0065,
        "cofins_rate": 0.03,
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
        salario_minimo=payload.salario_minimo,
    )

    now = datetime.now()
    empresa_dir = DATA_DIR / _slugify(nome_empresa)
    empresa_dir.mkdir(parents=True, exist_ok=True)
    file_id = now.strftime("%Y-%m-%d_%H%M%S")
    record = {
        "id": f"{_slugify(nome_empresa)}/{file_id}",
        "created_at": now.isoformat(),
        "nome_cliente": (payload.nome_cliente or "").strip(),
        "nome_empresa": nome_empresa,
        "input": payload.model_dump(),
        "output": result,
    }
    (empresa_dir / f"{file_id}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"id": record["id"]}


@app.get("/simulations")
def list_simulations(_user: str = Depends(_require_auth)) -> list[dict]:
    records: list[dict] = []
    for path in DATA_DIR.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            records.append(
                {
                    "id": payload.get("id"),
                    "created_at": payload.get("created_at"),
                    "nome_cliente": payload.get("nome_cliente"),
                    "nome_empresa": payload.get("nome_empresa"),
                }
            )
        except json.JSONDecodeError:
            continue
    records.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return records


@app.get("/simulations/{sim_id:path}")
def load_simulation(sim_id: str, _user: str = Depends(_require_auth)) -> dict:
    safe_id = sim_id.replace("..", "").strip("/")
    path = DATA_DIR / f"{safe_id}.json"
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulacao nao encontrada")
    return json.loads(path.read_text(encoding="utf-8"))


@app.delete("/simulations/{sim_id:path}")
def delete_simulation(sim_id: str, _user: str = Depends(_require_auth)) -> dict:
    safe_id = sim_id.replace("..", "").strip("/")
    path = DATA_DIR / f"{safe_id}.json"
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulacao nao encontrada")
    path.unlink()
    return {"status": "deleted"}


@app.get("/analysis")
def analysis(_user: str = Depends(_require_auth)) -> list[dict]:
    rows: list[dict] = []
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
    return rows


@app.get("/config")
def get_config(_user: str = Depends(_require_auth)) -> dict:
    return get_rules()


@app.put("/config")
def update_config(payload: dict, _user: str = Depends(_require_auth)) -> dict:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Formato invalido")
    save_rules(payload)
    return {"status": "updated"}
