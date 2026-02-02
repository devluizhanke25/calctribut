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

    assert pj["total_impostos"] == pytest.approx(121788.04, rel=1e-6)
    assert pj["lucro_liquido"] == pytest.approx(667307.96, rel=1e-6)
    assert pj["impacto_pf"] == pytest.approx(7485.856246560268, rel=1e-6)
    assert pj["aliquota_efetiva_final"] == pytest.approx(0.13466030859016695, rel=1e-6)

    assert comp["economia_tributaria"] == pytest.approx(121378.64875343977, rel=1e-6)
