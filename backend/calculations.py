from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict

from .constants import DEFAULT_MIN_WAGE, get_rules


@dataclass
class PFResult:
    rendimento_anual: float
    inss: float
    irpf: float
    iss: float
    total_tributos: float
    aliquota_efetiva: float
    receita_liquida: float
    renda_liquida: float
    total_despesas: float


@dataclass
class PJResult:
    base_presumida: float
    irpj: float
    irpj_adicional: float
    irpj_total: float
    csll: float
    irpj_csll: float
    pis: float
    cofins: float
    cbs: float
    ibs: float
    iss: float
    inss_folha: float
    total_impostos: float
    lucro_liquido: float
    dividendos: float
    irpf_m_percent: float
    impacto_pf: float
    aliquota_efetiva_final: float
    pro_labore_liquido: float


def _calc_irpj_additional(base_presumida_anual: float, threshold: float, rate: float) -> float:
    excedente = max(base_presumida_anual - threshold, 0.0)
    return excedente * rate


def calculate_pf(
    monthly_income: float,
    annual_expenses: float,
    iss_fixo: float,
    salario_minimo: float,
    secretaria_anual: float,
) -> PFResult:
    """Reproduz as formulas da planilha para Pessoa Fisica."""
    rules = get_rules()
    pf_rules = rules["pf"]

    annual_income = monthly_income * 12

    # INSS conforme planilha: (salario minimo * 20%) + (secretaria * 20%)
    inss = (salario_minimo * pf_rules["inss_pf_rate"]) + (secretaria_anual * pf_rules["inss_pf_rate"])

    total_despesas = annual_expenses + inss + iss_fixo
    renda_liquida = annual_income - total_despesas

    irpf = renda_liquida * pf_rules["irpf_flat"]
    total_tributos = irpf + iss_fixo + inss
    aliquota = (total_tributos / annual_income) if annual_income > 0 else 0.0

    receita_liquida = renda_liquida - total_tributos

    return PFResult(
        rendimento_anual=annual_income,
        inss=inss,
        irpf=irpf,
        iss=iss_fixo,
        total_tributos=total_tributos,
        aliquota_efetiva=aliquota,
        receita_liquida=receita_liquida,
        renda_liquida=renda_liquida,
        total_despesas=total_despesas,
    )


def calculate_pj(
    monthly_income: float,
    annual_expenses: Dict[str, float],
    pro_labore_monthly: float,
    iss_fixo: float,
) -> PJResult:
    rules = get_rules()
    pj_rules = rules["pj"]

    annual_income = monthly_income * 12

    base_presumida = annual_income * pj_rules["presumed_profit_rate"]
    irpj = base_presumida * pj_rules["irpj_rate"]
    irpj_adicional = _calc_irpj_additional(
        base_presumida, pj_rules["irpj_additional_threshold"], pj_rules["irpj_additional_rate"]
    )
    irpj_total = irpj + irpj_adicional
    csll = base_presumida * pj_rules["csll_rate"]
    irpj_csll = irpj_total + csll

    pis = annual_income * pj_rules["pis_rate"]
    cofins = annual_income * pj_rules["cofins_rate"]
    cbs = annual_income * pj_rules["cbs_rate"] if pj_rules.get("cbs_enabled") else 0.0
    ibs = annual_income * pj_rules["ibs_rate"] if pj_rules.get("ibs_enabled") else 0.0
    iss = iss_fixo

    # INSS folha pagamento conforme planilha: (secretaria + 0.2) * 20%
    secretaria_anual = annual_expenses.get("secretaria", 0.0)
    inss_folha = (secretaria_anual + pj_rules["inss_folha_rate"]) * pj_rules["inss_folha_rate"]

    total_impostos = (
        irpj_csll
        + pis
        + cofins
        + cbs
        + ibs
        + iss
        + inss_folha
    )

    pro_labore_anual = pro_labore_monthly * 12
    total_despesas = annual_expenses["total"] + pro_labore_anual

    if pj_rules.get("double_expense_in_pj"):
        lucro_liquido = annual_income - total_impostos - (2 * total_despesas)
    else:
        lucro_liquido = annual_income - total_impostos - total_despesas

    dividendos = lucro_liquido

    irpf_m_percent = (dividendos / 60000.0) - 10.0
    impacto_pf = dividendos * (irpf_m_percent / 100.0)
    pro_labore_liquido = pro_labore_anual - (pro_labore_anual * rules["pf"]["prolabore_inss_rate"])

    aliquota_final = (
        (total_impostos + impacto_pf) / annual_income
        if annual_income > 0
        else 0.0
    )

    return PJResult(
        base_presumida=base_presumida,
        irpj=irpj,
        irpj_adicional=irpj_adicional,
        irpj_total=irpj_total,
        csll=csll,
        irpj_csll=irpj_csll,
        pis=pis,
        cofins=cofins,
        cbs=cbs,
        ibs=ibs,
        iss=iss,
        inss_folha=inss_folha,
        total_impostos=total_impostos,
        lucro_liquido=lucro_liquido,
        dividendos=dividendos,
        irpf_m_percent=irpf_m_percent,
        impacto_pf=impacto_pf,
        aliquota_efetiva_final=aliquota_final,
        pro_labore_liquido=pro_labore_liquido,
    )


def calculate_all(
    monthly_income: float,
    annual_expenses: Dict[str, float],
    pro_labore_monthly: float,
    iss_fixo: float,
    salario_minimo: float,
) -> Dict[str, Dict[str, float]]:
    salario_minimo = salario_minimo or DEFAULT_MIN_WAGE

    pf = calculate_pf(
        monthly_income,
        annual_expenses["total"],
        iss_fixo,
        salario_minimo,
        annual_expenses.get("secretaria", 0.0),
    )
    pj = calculate_pj(monthly_income, annual_expenses, pro_labore_monthly, iss_fixo)

    comparativo = {
        "economia_tributaria": pf.total_tributos - (pj.total_impostos + pj.impacto_pf),
        "aliquota_pf": pf.aliquota_efetiva,
        "aliquota_pj_final": pj.aliquota_efetiva_final,
        "receita_liquida_pf": pf.receita_liquida,
        "lucro_liquido_pj": pj.lucro_liquido,
    }

    return {
        "pf": asdict(pf),
        "pj": asdict(pj),
        "comparativo": comparativo,
    }
