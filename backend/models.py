from pydantic import BaseModel, Field, field_validator


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
    salario_minimo: float = Field(0, ge=0)

    @field_validator("salario_minimo")
    @classmethod
    def validate_salario_minimo(cls, value: float) -> float:
        if value < 0:
            raise ValueError("salario_minimo nao pode ser negativo")
        return value
