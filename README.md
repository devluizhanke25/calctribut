# Estimativas PF x PJ Brasil Salomão

Simulador financeiro-tributário para comparar Pessoa Física (PF) vs Pessoa Jurídica (PJ) no regime de Lucro Presumido. A aplicação transforma a planilha de cálculo em uma experiência web moderna com backend em Python e frontend separado.

## Visão geral
- **Frontend**: HTML/CSS/JS puro com layout de dashboard, menu lateral, autenticação simples, histórico, análise, parâmetros e geração de PDF.
- **Backend**: FastAPI com cálculo financeiro, autenticação, persistência de simulações e endpoints para histórico/análise.
- **Regras**: parâmetros tributários em JSON (`backend/data/regras_tributarias.json`).
- **Persistência**: cada simulação salva gera um JSON em `data/simulacoes/<empresa>/<data>.json`.

## Estrutura de pastas
```
brmsalcalc/
  backend/
    __init__.py
    calculations.py
    constants.py
    main.py
    models.py
    requirements.txt
    data/
      regras_tributarias.json
  frontend/
    index.html
    styles.css
    app.js
    img/
      logo.png
  data/
    simulacoes/
  tests/
    test_calculos.py
  .env
  README.md
```

## Requisitos
- Python 3.10+
- Navegador moderno (Chrome/Edge/Firefox)

## Instalação
### 1) Backend
```powershell
cd "C:\Users\Luiz Nunes\Desktop\HANKE DIGITAL SOLUTIONS\brmsalcalc"
python -m venv .venv
.\.venv\Scripts\activate
pip install -r backend\requirements.txt
uvicorn backend.main:app --reload --port 8000
```

### 2) Frontend (obrigatório abrir via servidor)
O PDF só funciona corretamente quando o HTML é servido por HTTP (não use `file://`).

```powershell
cd "C:\Users\Luiz Nunes\Desktop\HANKE DIGITAL SOLUTIONS\brmsalcalc"
python -m http.server 5500
```

Acesse:
```
http://127.0.0.1:5500/frontend/index.html
```

## Login
As credenciais ficam no `.env`:
```
ADMIN_LOGIN=admin
ADMIN_PASSWORD=admin123
```

## Funcionalidades
- **Premissas**: entrada de dados financeiros + salvar simulação.
- **Pessoa Física**: cálculo de impostos e receita líquida.
- **Pessoa Jurídica**: cálculo completo Lucro Presumido.
- **Comparativo Final**: visão executiva + gráficos (barra/pizza) + parecer + download de PDF.
- **Histórico**: lista de simulações salvas (carregar / excluir).
- **Análise**: tabela consolidada de todas as simulações.
- **Parâmetros**: edição das regras tributárias em JSON.
- **Logout**: botão Sair no menu lateral.

## Regras tributárias (JSON)
Arquivo: `backend/data/regras_tributarias.json`

Exemplo:
```json
{
  "version": "2026-01",
  "pf": {
    "irpf_flat": 0.275,
    "inss_pf_rate": 0.20,
    "prolabore_inss_rate": 0.11
  },
  "pj": {
    "presumed_profit_rate": 0.32,
    "irpj_rate": 0.15,
    "irpj_additional_rate": 0.10,
    "irpj_additional_threshold": 240000,
    "csll_rate": 0.09,
    "pis_rate": 0.0065,
    "cofins_rate": 0.03,
    "cbs_rate": 0.009,
    "ibs_rate": 0.001,
    "inss_folha_rate": 0.20,
    "cbs_enabled": false,
    "ibs_enabled": false,
    "double_expense_in_pj": true
  }
}
```

## Testes
```powershell
pytest
```

## Fluxo de uso
1. Faça login.
2. Preencha premissas.
3. Clique em **Salvar simulação** para gravar JSON.
4. Consulte histórico e análise conforme necessário.
5. Baixe o PDF a partir do comparativo.

## Endpoints principais
- `POST /login` → retorna token.
- `POST /calculate` → calcula resultados (requer token).
- `POST /simulations` → salva simulação.
- `GET /simulations` → lista simulações.
- `GET /simulations/{id}` → carrega simulação.
- `DELETE /simulations/{id}` → exclui simulação.
- `GET /analysis` → dados consolidados.
- `GET /config` → regras tributárias atuais.
- `PUT /config` → atualiza regras tributárias.

## Observações
- A geração de PDF usa `html2pdf.js` via CDN.
- Se o backend for reiniciado, é necessário logar novamente (token em memória).
- Fórmulas estão alinhadas à planilha fornecida; ajustes em `backend/data/regras_tributarias.json`.

## Ajustes rápidos
- **Logo**: substitua `frontend/img/logo.png`.
- **Cores/tema**: edite `frontend/styles.css`.
- **Regras fiscais**: edite `backend/data/regras_tributarias.json`.

---

Qualquer dúvida ou melhoria, só pedir.
