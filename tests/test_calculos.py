import pytest

from backend.calculations import calculate_all


def test_calculo_planilha_referencia():
    inputs = {
        "monthly_income": 80000,
        "annual_expenses": {
            "secretaria": 24000,
            "aluguel_condominio": 30000,
            "contador": 12000,
            "outras_despesas": 0,
        },
        "pro_labore_monthly": 1621,
        "iss_fixo": 1500,
        "salario_minimo": 1621,
    }
    inputs["annual_expenses"]["total"] = (
        inputs["annual_expenses"]["secretaria"]
        + inputs["annual_expenses"]["aluguel_condominio"]
        + inputs["annual_expenses"]["contador"]
        + inputs["annual_expenses"]["outras_despesas"]
    )

    result = calculate_all(**inputs)
    pf = result["pf"]
    pj = result["pj"]
    comp = result["comparativo"]

    assert pf["inss"] == pytest.approx(5124.2, rel=1e-6)
    assert pf["irpf"] == pytest.approx(244028.345, rel=1e-6)
    assert pf["total_tributos"] == pytest.approx(250652.545, rel=1e-6)
    assert pf["receita_liquida"] == pytest.approx(636723.255, rel=1e-6)
    assert pf["aliquota_efetiva"] == pytest.approx(0.2610964010416667, rel=1e-6)

    assert pj["base_presumida_irpj"] == pytest.approx(76800.0, rel=1e-6)
    assert pj["base_presumida_csll"] == pytest.approx(115200.0, rel=1e-6)
    assert pj["total_impostos"] == pytest.approx(63228.04, rel=1e-6)
    assert pj["lucro_liquido"] == pytest.approx(725867.96, rel=1e-6)
    assert pj["impacto_pf"] == pytest.approx(15227.253225760262, rel=1e-6)
    assert pj["aliquota_efetiva_final"] == pytest.approx(0.08172426377683362, rel=1e-6)

    assert comp["economia_tributaria"] == pytest.approx(172197.25177423976, rel=1e-6)


def test_calculo_regime_hospitalar(monkeypatch):
    def fake_rules():
        return {
            "pf": {
                "irpf_flat": 0.275,
                "inss_pf_rate": 0.20,
                "prolabore_inss_rate": 0.11,
            },
            "pj": {
                "presumed_profit_regime": "hospital",
                "standard_irpj_presumed_rate": 0.08,
                "standard_csll_presumed_rate": 0.12,
                "hospital_presumed_rate": 0.32,
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

    monkeypatch.setattr("backend.calculations.get_rules", fake_rules)

    inputs = {
        "monthly_income": 80000,
        "annual_expenses": {
            "secretaria": 24000,
            "aluguel_condominio": 30000,
            "contador": 12000,
            "outras_despesas": 0,
            "total": 66000,
        },
        "pro_labore_monthly": 1621,
        "iss_fixo": 1500,
        "salario_minimo": 1621,
    }

    result = calculate_all(**inputs)
    pj = result["pj"]

    assert pj["base_presumida_irpj"] == pytest.approx(307200.0, rel=1e-6)
    assert pj["base_presumida_csll"] == pytest.approx(307200.0, rel=1e-6)
    assert pj["irpj_total"] == pytest.approx(49080.0, rel=1e-6)
    assert pj["csll"] == pytest.approx(27648.0, rel=1e-6)
