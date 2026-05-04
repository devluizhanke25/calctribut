from pydantic import BaseModel, Field


class AnnualExpenses(BaseModel):
    secretaria: float = Field(0, ge=0)
    aluguel_condominio: float = Field(0, ge=0)
    contador: float = Field(0, ge=0)
    outras_despesas: float = Field(0, ge=0)


class CalculationInput(BaseModel):
    nome_cliente: str | None = None
    nome_empresa: str | None = None
    rendimento_mensal: float = Field(..., ge=0)
    despesas_anuais: AnnualExpenses
    pro_labore: float = Field(0, ge=0)
    iss_fixo: float = Field(0, ge=0)
