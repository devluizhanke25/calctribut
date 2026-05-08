import app as flask_app_module
from backend.storage import ensure_default_user, init_db


def _auth_headers() -> dict[str, str]:
    creds = flask_app_module._get_credentials()
    token = flask_app_module._make_token(creds["login"], creds["password"])
    return {"X-Auth-Token": token}


def _payload() -> dict:
    return {
        "nome_cliente": "Cliente Teste",
        "nome_empresa": "Empresa Teste",
        "rendimento_mensal": 80000,
        "despesas_anuais": {
            "secretaria": 24000,
            "aluguel_condominio": 30000,
            "contador": 12000,
            "outras_despesas": 0,
        },
        "pro_labore": 1621,
        "iss_fixo": 1500,
    }


def test_save_simulation_idempotency_key_prevents_duplicate(tmp_path, monkeypatch):
    db_path = tmp_path / "simulador_test.db"
    init_db(db_path)
    creds = flask_app_module._get_credentials()
    ensure_default_user(db_path, creds["login"], creds["password"])
    monkeypatch.setattr(flask_app_module, "DB_PATH", db_path)

    client = flask_app_module.app.test_client()
    headers = _auth_headers() | {"Content-Type": "application/json", "X-Idempotency-Key": "same-click"}

    first = client.post("/simulations", json=_payload(), headers=headers)
    second = client.post("/simulations", json=_payload(), headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json["id"] == second.json["id"]
    assert second.json["deduplicated"] is True


def test_save_simulation_recent_duplicate_without_key_is_deduplicated(tmp_path, monkeypatch):
    db_path = tmp_path / "simulador_test.db"
    init_db(db_path)
    creds = flask_app_module._get_credentials()
    ensure_default_user(db_path, creds["login"], creds["password"])
    monkeypatch.setattr(flask_app_module, "DB_PATH", db_path)

    client = flask_app_module.app.test_client()
    headers = _auth_headers() | {"Content-Type": "application/json"}

    first = client.post("/simulations", json=_payload(), headers=headers)
    second = client.post("/simulations", json=_payload(), headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json["id"] == second.json["id"]
    assert second.json["deduplicated"] is True
