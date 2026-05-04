const API_BASE = "http://127.0.0.1:8000";
const API_URL = `${API_BASE}/calculate`;

const defaults = {
  nome_cliente: "",
  nome_empresa: "",
  rendimento_mensal: 0,
  pro_labore: 0,
  iss_fixo: 0,
  secretaria: 0,
  aluguel_condominio: 0,
  contador: 0,
  outras_despesas: 0,
};

const state = { ...defaults };
let debounceTimer = null;
let lastResult = null;

const statusLoading = document.getElementById("status-loading");
const statusError = document.getElementById("status-error");
const statusIndicator = document.getElementById("status-indicator");
const saveAlert = document.getElementById("save-alert");
let isSavingSimulation = false;

const inputs = document.querySelectorAll(".money-input");
const nameInput = document.getElementById("nome_cliente");
const companyInput = document.getElementById("nome_empresa");
const loginOverlay = document.getElementById("login-overlay");
const loginButton = document.getElementById("login-btn");
const loginUser = document.getElementById("login-user");
const loginPass = document.getElementById("login-pass");
const loginError = document.getElementById("login-error");
const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebar-toggle");
const appShell = document.querySelector(".app-shell");
const sidebarBackdrop = document.getElementById("sidebar-backdrop");
const sidebarClose = document.getElementById("sidebar-close");
const logoutButton = document.getElementById("logout-btn");
const configForm = document.getElementById("config-form");
const configRefresh = document.getElementById("config-refresh");
const configSave = document.getElementById("config-save");
const configLockInput = document.getElementById("config-lock");
const configVersionInput = document.getElementById("config-version");
const configPfIrpfFlatInput = document.getElementById("config-pf-irpf-flat");
const configPfInssPfRateInput = document.getElementById("config-pf-inss-pf-rate");
const configPfProlaboreInssRateInput = document.getElementById("config-pf-prolabore-inss-rate");
const configRegimeStandard = document.getElementById("config-regime-standard");
const configRegimeHospital = document.getElementById("config-regime-hospital");
const configPjStandardIrpjPresumedRateInput = document.getElementById("config-pj-standard-irpj-presumed-rate");
const configPjStandardCsllPresumedRateInput = document.getElementById("config-pj-standard-csll-presumed-rate");
const configPjHospitalPresumedRateInput = document.getElementById("config-pj-hospital-presumed-rate");
const configPjIrpjRateInput = document.getElementById("config-pj-irpj-rate");
const configPjIrpjAdditionalRateInput = document.getElementById("config-pj-irpj-additional-rate");
const configPjIrpjAdditionalThresholdInput = document.getElementById("config-pj-irpj-additional-threshold");
const configPjCsllRateInput = document.getElementById("config-pj-csll-rate");
const configPjPisRateInput = document.getElementById("config-pj-pis-rate");
const configPjCofinsRateInput = document.getElementById("config-pj-cofins-rate");
const configPjCbsRateInput = document.getElementById("config-pj-cbs-rate");
const configPjIbsRateInput = document.getElementById("config-pj-ibs-rate");
const configPjInssFolhaRateInput = document.getElementById("config-pj-inss-folha-rate");
const configPjCbsEnabledInput = document.getElementById("config-pj-cbs-enabled");
const configPjIbsEnabledInput = document.getElementById("config-pj-ibs-enabled");
const configPjDoubleExpenseInput = document.getElementById("config-pj-double-expense-in-pj");
const presumedRegimeStandard = document.getElementById("presumed_regime_standard");
const presumedRegimeHospital = document.getElementById("presumed_regime_hospital");
let currentConfig = null;
let configSaveTimer = null;
const PRESUMED_REGIMES = {
  standard: {
    standard_irpj_presumed_rate: 0.08,
    standard_csll_presumed_rate: 0.12,
    hospital_presumed_rate: 0.32,
  },
  hospital: {
    standard_irpj_presumed_rate: 0.08,
    standard_csll_presumed_rate: 0.12,
    hospital_presumed_rate: 0.32,
  },
};
const DEFAULT_CONFIG = {
  version: "2026-01",
  pf: {
    irpf_flat: 0.275,
    inss_pf_rate: 0.2,
    prolabore_inss_rate: 0.11,
  },
  pj: {
    presumed_profit_regime: "standard",
    standard_irpj_presumed_rate: 0.08,
    standard_csll_presumed_rate: 0.12,
    hospital_presumed_rate: 0.32,
    irpj_rate: 0.15,
    irpj_additional_rate: 0.1,
    irpj_additional_threshold: 240000,
    csll_rate: 0.09,
    pis_rate: 0.0065,
    cofins_rate: 0.03,
    cbs_rate: 0.009,
    ibs_rate: 0.001,
    inss_folha_rate: 0.2,
    cbs_enabled: false,
    ibs_enabled: false,
    double_expense_in_pj: true,
  },
};
const consolidatedMap = {
  "cons-rendimento": () => formatCurrency(state.rendimento_mensal),
  "cons-prolabore": () => formatCurrency(state.pro_labore),
  "cons-iss": () => formatCurrency(state.iss_fixo),
  "cons-despesas": () =>
    formatCurrency(state.secretaria + state.aluguel_condominio + state.contador + state.outras_despesas),
  "cons-pf-rendimento": (d) => formatCurrency(d.pf.rendimento_anual),
  "cons-pf-inss": (d) => formatCurrency(d.pf.inss),
  "cons-pf-irpf": (d) => formatCurrency(d.pf.irpf),
  "cons-pf-total": (d) => formatCurrency(d.pf.total_tributos),
  "cons-pf-aliquota": (d) => formatPercent(d.pf.aliquota_efetiva),
  "cons-pf-receita": (d) => formatCurrency(d.pf.receita_liquida),
  "cons-pj-irpj": (d) => formatCurrency(d.pj.irpj_total),
  "cons-pj-csll": (d) => formatCurrency(d.pj.csll),
  "cons-pj-pis": (d) => formatCurrency(d.pj.pis),
  "cons-pj-cofins": (d) => formatCurrency(d.pj.cofins),
  "cons-pj-iss": (d) => formatCurrency(d.pj.iss),
  "cons-pj-total": (d) => formatCurrency(d.pj.total_impostos),
  "cons-pj-lucro": (d) => formatCurrency(d.pj.lucro_liquido),
  "cons-pj-dividendos": (d) => formatCurrency(d.pj.dividendos),
  "cons-pj-impacto": (d) => formatCurrency(d.pj.impacto_pf),
  "cons-pj-aliquota": (d) => formatPercent(d.pj.aliquota_efetiva_final),
  "cons-comp-economia": (d) => formatCurrency(d.comparativo.economia_tributaria),
  "cons-comp-aliquota-pf": (d) => formatPercent(d.comparativo.aliquota_pf),
  "cons-comp-aliquota-pj": (d) => formatPercent(d.comparativo.aliquota_pj_final),
  "cons-comp-receita-pf": (d) => formatCurrency(d.comparativo.receita_liquida_pf),
  "cons-comp-lucro-pj": (d) => formatCurrency(d.comparativo.lucro_liquido_pj),
};

const fieldMap = {
  nome_cliente: "nome_cliente",
  nome_empresa: "nome_empresa",
  rendimento_mensal: "rendimento_mensal",
  pro_labore: "pro_labore",
  iss_fixo: "iss_fixo",
  secretaria: "secretaria",
  aluguel_condominio: "aluguel_condominio",
  contador: "contador",
  outras_despesas: "outras_despesas",
};

const outputMap = {
  "pf-rendimento": (data) => data.pf.rendimento_anual,
  "cmp-pf-rendimento": (data) => data.pf.rendimento_anual,
  "pf-inss": (data) => data.pf.inss,
  "cmp-pf-inss": (data) => data.pf.inss,
  "pf-irpf": (data) => data.pf.irpf,
  "cmp-pf-irpf": (data) => data.pf.irpf,
  "pf-total-tributos": (data) => data.pf.total_tributos,
  "cmp-pf-total-tributos": (data) => data.pf.total_tributos,
  "pf-aliquota": (data) => data.pf.aliquota_efetiva,
  "cmp-pf-aliquota": (data) => data.pf.aliquota_efetiva,
  "pf-receita": (data) => data.pf.receita_liquida,
  "cmp-pf-receita": (data) => data.pf.receita_liquida,
  "pj-irpj": (data) => data.pj.irpj_total,
  "cmp-pj-irpj": (data) => data.pj.irpj_total,
  "pj-csll": (data) => data.pj.csll,
  "cmp-pj-csll": (data) => data.pj.csll,
  "cmp-pj-inss-folha": (data) => data.pj.inss_folha,
  "cmp-pj-impacto-pf-irpf": (data) => data.pj.impacto_pf,
  "pj-pis": (data) => data.pj.pis,
  "cmp-pj-pis": (data) => data.pj.pis,
  "pj-cofins": (data) => data.pj.cofins,
  "cmp-pj-cofins": (data) => data.pj.cofins,
  "pj-iss": (data) => data.pj.iss,
  "cmp-pj-iss": (data) => data.pj.iss,
  "pj-total-impostos": (data) => data.pj.total_impostos,
  "cmp-pj-total-impostos": (data) => data.pj.total_impostos,
  "pj-lucro": (data) => data.pj.lucro_liquido,
  "cmp-pj-lucro": (data) => data.pj.lucro_liquido,
  "pj-dividendos": (data) => data.pj.dividendos,
  "cmp-pj-dividendos": (data) => data.pj.dividendos,
  "pj-impacto-pf": (data) => data.pj.impacto_pf,
  "cmp-pj-impacto-pf": (data) => data.pj.impacto_pf,
  "pj-aliquota-final": (data) => data.pj.aliquota_efetiva_final,
  "cmp-pj-aliquota-final": (data) => data.pj.aliquota_efetiva_final,
  "comp-economia": (data) => data.comparativo.economia_tributaria,
  "comp-aliquota-pf": (data) => data.comparativo.aliquota_pf,
  "comp-aliquota-pj": (data) => data.comparativo.aliquota_pj_final,
  "comp-receita-pf": (data) => data.comparativo.receita_liquida_pf,
  "comp-lucro-pj": (data) => data.comparativo.lucro_liquido_pj,
};

function formatCurrency(value) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(value);
}

function formatPercent(value) {
  return `${(value * 100).toFixed(2)}%`;
}

function percentInputValue(value) {
  return (Number(value) * 100).toFixed(2).replace(/\.00$/, "");
}

function parseNumberInput(input, label, { percent = false } = {}) {
  const raw = input?.value?.trim()?.replace(",", ".");
  const number = Number(raw);
  if (!Number.isFinite(number) || number < 0) {
    throw new Error(`${label} inválido`);
  }
  return percent ? number / 100 : number;
}

function mergeConfig(config) {
  return {
    version: config?.version || DEFAULT_CONFIG.version,
    pf: {
      ...DEFAULT_CONFIG.pf,
      ...(config?.pf || {}),
    },
    pj: {
      ...DEFAULT_CONFIG.pj,
      ...(config?.pj || {}),
    },
  };
}

function setConfigLocked(locked) {
  if (!configForm) return;
  const fields = configForm.querySelectorAll("input, select, textarea, button");
  fields.forEach((field) => {
    if (field === configLockInput) {
      field.disabled = false;
      return;
    }
    if (field.type === "checkbox" || field.type === "radio" || field.tagName === "BUTTON" || field.tagName === "SELECT") {
      field.disabled = locked;
      return;
    }
    field.readOnly = locked;
  });
  if (configSave) {
    configSave.disabled = locked;
  }
}

function getToken() {
  return localStorage.getItem("auth_token");
}

function setToken(token) {
  localStorage.setItem("auth_token", token);
}

async function authFetch(url, options = {}) {
  const token = getToken();
  if (!token) {
    loginOverlay.classList.remove("hidden");
    throw new Error("Sem autenticação");
  }
  const headers = options.headers || {};
  const response = await fetch(url, {
    ...options,
    headers: {
      ...headers,
      "X-Auth-Token": token || "",
    },
  });
  if (response.status === 401) {
    localStorage.removeItem("auth_token");
    loginOverlay.classList.remove("hidden");
    throw new Error("Não autorizado");
  }
  return response;
}

function parseInput(value) {
  if (!value) return 0;
  const normalized = value
    .replace(/\./g, "")
    .replace(",", ".")
    .replace(/[^0-9.]/g, "");
  return Number(normalized) || 0;
}

function setInputValue(id, value) {
  const input = document.getElementById(id);
  if (input) {
    input.value = formatCurrency(value);
  }
}

function setError(id, message) {
  const error = document.getElementById(`${id}_error`);
  const input = document.getElementById(id);
  if (error) {
    error.textContent = message || "";
  }
  if (input) {
    input.classList.toggle("error", Boolean(message));
  }
}

function updateResumo() {
  document.getElementById("resumo-rendimento").textContent = formatCurrency(state.rendimento_mensal * 12);
  document.getElementById("resumo-despesas").textContent = formatCurrency(
    state.secretaria + state.aluguel_condominio + state.contador + state.outras_despesas
  );
  document.getElementById("resumo-prolabore").textContent = formatCurrency(state.pro_labore * 12);
}

function updateCharts(pfRate, pjRate) {
  const pfBar = document.getElementById("bar-pf");
  const pjBar = document.getElementById("bar-pj");
  if (!pfBar || !pjBar) return;
  const maxRate = Math.max(pfRate, pjRate, 0.01);
  pfBar.style.setProperty("--value", `${(pfRate / maxRate) * 100}%`);
  pjBar.style.setProperty("--value", `${(pjRate / maxRate) * 100}%`);
}

function updateExtraCharts(data) {
  const totalTributosPf = data.pf.total_tributos;
  const totalImpostosPj = data.pj.total_impostos;
  const impactoPf = data.pj.impacto_pf;

  const maxValue = Math.max(totalTributosPf, totalImpostosPj, impactoPf, 1);
  const barPf = document.getElementById("bar-tributos-pf");
  const barPj = document.getElementById("bar-impostos-pj");
  const barImpacto = document.getElementById("bar-impacto-pf");
  if (barPf && barPj && barImpacto) {
    barPf.style.setProperty("--value", `${(totalTributosPf / maxValue) * 100}%`);
    barPj.style.setProperty("--value", `${(totalImpostosPj / maxValue) * 100}%`);
    barImpacto.style.setProperty("--value", `${(impactoPf / maxValue) * 100}%`);
  }

  const pie = document.getElementById("pie-pj");
  const totalPj = totalImpostosPj + impactoPf;
  if (pie && totalPj > 0) {
    const pctPj = (totalImpostosPj / totalPj) * 360;
    pie.style.background = `conic-gradient(#111111 0deg ${pctPj}deg, #d0d0d0 ${pctPj}deg 360deg)`;
  }

}

async function calculate() {
  if (!getToken()) {
    loginOverlay.classList.remove("hidden");
    statusError.textContent = "Faça login para calcular.";
    statusError.classList.remove("hidden");
    return;
  }
  statusLoading.classList.remove("hidden");
  statusError.classList.add("hidden");
  statusIndicator.textContent = "Atualizando simulação";

  const payload = {
    nome_cliente: state.nome_cliente,
    nome_empresa: state.nome_empresa,
    rendimento_mensal: state.rendimento_mensal,
    despesas_anuais: {
      secretaria: state.secretaria,
      aluguel_condominio: state.aluguel_condominio,
      contador: state.contador,
      outras_despesas: state.outras_despesas,
    },
    pro_labore: state.pro_labore,
    iss_fixo: state.iss_fixo,
  };

  try {
    const response = await authFetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error("Falha no cálculo");
    }

    const data = await response.json();
    lastResult = data;

    Object.entries(outputMap).forEach(([id, selector]) => {
      const value = selector(data);
      const element = document.getElementById(id);
      if (!element) return;
      if (id.includes("aliquota")) {
        element.textContent = formatPercent(value);
      } else {
        element.textContent = formatCurrency(value);
      }
    });

    updateCharts(data.comparativo.aliquota_pf, data.comparativo.aliquota_pj_final);
    updateExtraCharts(data);
    updateConsolidated(data);
    return data;
  } catch (error) {
    if (error.message === "Não autorizado" || error.message === "Sem autenticação") {
      statusError.textContent = "Sessão expirada. Faça login novamente.";
    } else {
      statusError.textContent = "Não foi possível calcular. Verifique o backend.";
    }
    statusError.classList.remove("hidden");
    return null;
  } finally {
    statusLoading.classList.add("hidden");
    statusIndicator.textContent = "Simulação atualizada";
  }
}

function scheduleCalculation() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    updateResumo();
    calculate();
  }, 350);
}

function handleInput(event) {
  const id = event.target.id;
  const rawValue = parseInput(event.target.value);

  if (rawValue < 0) {
    setError(id, "Valor não pode ser negativo");
  } else {
    setError(id, "");
  }

  state[fieldMap[id]] = rawValue;
  scheduleCalculation();
}

function setDefaults() {
  Object.entries(defaults).forEach(([key, value]) => {
    state[key] = value;
    if (key === "nome_cliente" && nameInput) {
      nameInput.value = value;
      return;
    }
    if (key === "nome_empresa" && companyInput) {
      companyInput.value = value;
      return;
    }
    setInputValue(key, value);
  });
  updateResumo();
}

function setCheckboxGroup(regime) {
  if (presumedRegimeStandard) {
    presumedRegimeStandard.checked = regime === "standard";
  }
  if (presumedRegimeHospital) {
    presumedRegimeHospital.checked = regime === "hospital";
  }
}

function initTabs() {
  const tabs = document.querySelectorAll(".tab");
  const panels = document.querySelectorAll(".panel");

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((btn) => btn.classList.remove("active"));
      panels.forEach((panel) => panel.classList.remove("active"));

      tab.classList.add("active");
      document.getElementById(tab.dataset.tab).classList.add("active");
    });
  });
}

inputs.forEach((input) => {
  input.addEventListener("input", handleInput);
  input.addEventListener("blur", (event) => {
    const value = parseInput(event.target.value);
    event.target.value = formatCurrency(value);
  });
  input.addEventListener("focus", (event) => {
    const value = parseInput(event.target.value);
    event.target.value = value ? value.toString() : "";
  });
});

if (nameInput) {
  nameInput.addEventListener("input", (event) => {
    state.nome_cliente = event.target.value.trim();
  });
}

if (companyInput) {
  companyInput.addEventListener("input", (event) => {
    state.nome_empresa = event.target.value.trim();
  });
}

document.getElementById("reset").addEventListener("click", (event) => {
  event.preventDefault();
  setDefaults();
  if (getToken()) {
    scheduleCalculation();
  }
});

function hydratePrintArea(data) {
  const today = new Date();
  document.getElementById("print-cliente").textContent = state.nome_cliente || "-";
  document.getElementById("print-empresa").textContent = state.nome_empresa || "-";
  document.getElementById("print-data").textContent = today.toLocaleDateString("pt-BR");

  document.getElementById("print-cmp-pf-rendimento").textContent = formatCurrency(data.pf.rendimento_anual);
  document.getElementById("print-cmp-pf-inss").textContent = formatCurrency(data.pf.inss);
  document.getElementById("print-cmp-pf-irpf").textContent = formatCurrency(data.pf.irpf);
  document.getElementById("print-cmp-pj-irpj").textContent = formatCurrency(data.pj.irpj_total);
  document.getElementById("print-cmp-pj-csll").textContent = formatCurrency(data.pj.csll);
  document.getElementById("print-cmp-pj-pis").textContent = formatCurrency(data.pj.pis);
  document.getElementById("print-cmp-pj-cofins").textContent = formatCurrency(data.pj.cofins);
  document.getElementById("print-cmp-pj-iss").textContent = formatCurrency(data.pj.iss);
  document.getElementById("print-cmp-pf-total-tributos").textContent = formatCurrency(data.pf.total_tributos);
  document.getElementById("print-cmp-pj-total-impostos").textContent = formatCurrency(data.pj.total_impostos);
  document.getElementById("print-cmp-pj-inss").textContent = formatCurrency(data.pj.inss_folha);
  document.getElementById("print-cmp-pj-irpf").textContent = formatCurrency(data.pj.impacto_pf);
  document.getElementById("print-cmp-pj-impacto-pf").textContent = formatCurrency(data.pj.impacto_pf);
  document.getElementById("print-cmp-pf-aliquota").textContent = formatPercent(data.pf.aliquota_efetiva);
  document.getElementById("print-cmp-pj-aliquota-final").textContent = formatPercent(data.pj.aliquota_efetiva_final);
  document.getElementById("print-cmp-pf-receita").textContent = formatCurrency(data.pf.receita_liquida);
  document.getElementById("print-cmp-pj-lucro").textContent = formatCurrency(data.pj.lucro_liquido);
  document.getElementById("print-cmp-pj-dividendos").textContent = formatCurrency(data.pj.dividendos);
}

function updateConsolidated(data) {
  Object.entries(consolidatedMap).forEach(([id, getter]) => {
    const el = document.getElementById(id);
    if (!el) return;
    const value = getter(data);
    el.textContent = value;
  });
}

function annotateComparisonTables() {
  document.querySelectorAll(".compare-table:not(.print-compare-table)").forEach((table) => {
    const headers = Array.from(table.querySelectorAll("thead th")).map((th) => th.textContent?.trim() || "");
    table.querySelectorAll("tbody tr").forEach((row) => {
      const cells = row.querySelectorAll("td");
      cells.forEach((cell, index) => {
        const label = headers[index] || `Coluna ${index + 1}`;
        cell.setAttribute("data-label", label);
      });
    });
  });
}

async function generatePdf() {
  let clone = null;
  let wrapper = null;
  const debugPdf = false;
  try {
    if (!getToken()) {
      loginOverlay.classList.remove("hidden");
      statusError.textContent = "Faça login para gerar o PDF.";
      statusError.classList.remove("hidden");
      return;
    }
    if (!window.html2pdf) {
      statusError.textContent = "Biblioteca de PDF nao carregada. Recarregue a pagina.";
      statusError.classList.remove("hidden");
      return;
    }
    statusIndicator.textContent = "Gerando PDF...";
    let data = lastResult;
    if (!data) {
      data = await calculate();
    }
    if (!data) {
      statusError.textContent = "Preencha as premissas e aguarde o cálculo antes de gerar o PDF.";
      statusError.classList.remove("hidden");
      throw new Error("Falha no cálculo");
    }
    hydratePrintArea(data);
    const source = document.getElementById("print-area");
    if (!source) {
      throw new Error("Área de impressão não encontrada");
    }
    document.body.classList.add("pdf-export");
    clone = source.cloneNode(true);
    clone.classList.add("pdf-clone", "pdf-mode");
    clone.style.position = "static";
    if (debugPdf) {
      clone.style.outline = "2px dashed #ff9800";
      clone.style.boxShadow = "0 0 0 4px rgba(255, 152, 0, 0.15)";
    }
    wrapper = document.createElement("div");
    wrapper.style.position = "fixed";
    wrapper.style.left = "-10000px";
    wrapper.style.top = "0";
    wrapper.style.visibility = debugPdf ? "visible" : "hidden";
    wrapper.style.pointerEvents = "none";
    wrapper.appendChild(clone);
    document.body.appendChild(wrapper);

    // Aguarda renderização e carregamento de imagens
    await new Promise((resolve) => requestAnimationFrame(resolve));
    await waitForImages(clone);
    await new Promise((resolve) => setTimeout(resolve, debugPdf ? 1200 : 100));

    const filenameBase = (state.nome_cliente || "simulacao").replace(/\s+/g, "_").toLowerCase();
    const options = {
      margin: [6, 6, 6, 6],
      filename: `${filenameBase}_pf_pj.pdf`,
      image: { type: "jpeg", quality: 0.95 },
      html2canvas: {
        scale: 1.6,
        useCORS: true,
        allowTaint: true,
        backgroundColor: "#ffffff",
      },
      jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
      pagebreak: { mode: ["css", "avoid-all", "legacy"] },
    };

    await html2pdf().set(options).from(clone).save();
    statusIndicator.textContent = "PDF gerado";
  } catch (error) {
    if (error.message === "Não autorizado" || error.message === "Sem autenticação") {
      statusError.textContent = "Sessão expirada. Faça login novamente.";
    } else {
      statusError.textContent = "Nao foi possivel gerar o PDF. Verifique o backend.";
    }
    statusError.classList.remove("hidden");
  } finally {
    if (wrapper) {
      wrapper.remove();
    } else if (clone) {
      clone.remove();
    }
    document.body.classList.remove("pdf-export");
  }
}

async function waitForImages(container) {
  const images = Array.from(container.querySelectorAll("img"));
  if (!images.length) return;
  await Promise.all(
    images.map((img) => {
      if (img.complete) return Promise.resolve();
      return new Promise((resolve) => {
        img.onload = () => resolve();
        img.onerror = () => resolve();
      });
    })
  );
}

const pdfButton = document.getElementById("generate-pdf");
if (pdfButton) {
  pdfButton.addEventListener("click", generatePdf);
}

document.getElementById("save-session").addEventListener("click", async (event) => {
  event.preventDefault();
  if (isSavingSimulation) return;
  const saveButton = event.currentTarget;
  const saveStartedAt = Date.now();
  try {
    if (!getToken()) {
      loginOverlay.classList.remove("hidden");
      return;
    }
    if (!state.nome_empresa) {
      statusError.textContent = "Informe o nome da empresa para salvar.";
      statusError.classList.remove("hidden");
      return;
    }
    isSavingSimulation = true;
    if (saveButton) saveButton.disabled = true;
    statusError.classList.add("hidden");
    statusIndicator.textContent = "Salvando simulação...";
    saveAlert?.classList.remove("hidden");
    const response = await authFetch(`${API_BASE}/simulations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nome_cliente: state.nome_cliente,
        nome_empresa: state.nome_empresa,
        rendimento_mensal: state.rendimento_mensal,
        despesas_anuais: {
          secretaria: state.secretaria,
          aluguel_condominio: state.aluguel_condominio,
          contador: state.contador,
          outras_despesas: state.outras_despesas,
        },
        pro_labore: state.pro_labore,
        iss_fixo: state.iss_fixo,
      }),
    });

    if (!response.ok) {
      throw new Error("Falha ao salvar");
    }
    await loadHistory();
    await loadAnalysis();
    statusIndicator.textContent = "Simulação salva com sucesso";
  } catch (error) {
    statusError.textContent = "Nao foi possivel salvar a simulacao.";
    statusError.classList.remove("hidden");
    statusIndicator.textContent = "Falha ao salvar simulação";
  } finally {
    const minVisibleMs = 900;
    const elapsedMs = Date.now() - saveStartedAt;
    if (elapsedMs < minVisibleMs) {
      await new Promise((resolve) => setTimeout(resolve, minVisibleMs - elapsedMs));
    }
    saveAlert?.classList.add("hidden");
    if (saveButton) saveButton.disabled = false;
    isSavingSimulation = false;
  }
});

async function loadHistory() {
  if (!getToken()) return;
  const container = document.getElementById("history-list");
  if (!container) return;
  container.innerHTML = "";
  try {
    const response = await authFetch(`${API_BASE}/simulations`);
    if (!response.ok) return;
    const data = await response.json();
    if (!data.length) {
      container.innerHTML = "<p class=\"muted\">Nenhuma simulação salva.</p>";
      return;
    }
    data.forEach((item) => {
      const row = document.createElement("div");
      row.className = "list-row";
      row.innerHTML = `
        <span>${item.nome_empresa || "-"}</span>
        <span>${item.nome_cliente || "-"}</span>
        <span>${item.created_at ? new Date(item.created_at).toLocaleDateString("pt-BR") : "-"}</span>
        <div class="list-actions">
          <button data-id="${item.id}" data-action="load">Carregar</button>
          <button data-id="${item.id}" data-action="delete">Excluir</button>
        </div>
      `;
      row.querySelectorAll("button").forEach((btn) => {
        btn.addEventListener("click", () => {
          const action = btn.dataset.action;
          if (action === "delete") {
            deleteSimulation(item.id);
            return;
          }
          loadSimulation(item.id);
        });
      });
      container.appendChild(row);
    });
  } catch (error) {
    statusError.textContent = "Faça login para acessar o histórico.";
    statusError.classList.remove("hidden");
  }
}

async function loadSimulation(id) {
  if (!getToken()) return;
  const response = await authFetch(`${API_BASE}/simulations/${id}`);
  if (!response.ok) return;
  const payload = await response.json();
  const input = payload.input || {};
  state.nome_cliente = input.nome_cliente || "";
  state.nome_empresa = input.nome_empresa || "";
  if (nameInput) nameInput.value = state.nome_cliente;
  if (companyInput) companyInput.value = state.nome_empresa;

  state.rendimento_mensal = input.rendimento_mensal || 0;
  state.pro_labore = input.pro_labore || 0;
  state.iss_fixo = input.iss_fixo || 0;

  state.secretaria = input.despesas_anuais?.secretaria || 0;
  state.aluguel_condominio = input.despesas_anuais?.aluguel_condominio || 0;
  state.contador = input.despesas_anuais?.contador || 0;
  state.outras_despesas = input.despesas_anuais?.outras_despesas || 0;

  setInputValue("rendimento_mensal", state.rendimento_mensal);
  setInputValue("pro_labore", state.pro_labore);
  setInputValue("iss_fixo", state.iss_fixo);
  setInputValue("secretaria", state.secretaria);
  setInputValue("aluguel_condominio", state.aluguel_condominio);
  setInputValue("contador", state.contador);
  setInputValue("outras_despesas", state.outras_despesas);

  const premissasTab = document.querySelector('.tab[data-tab="premissas"]');
  if (premissasTab) {
    premissasTab.click();
  }

  updateResumo();
  calculate();
}

async function deleteSimulation(id) {
  if (!getToken()) return;
  const response = await authFetch(`${API_BASE}/simulations/${id}`, { method: "DELETE" });
  if (!response.ok) return;
  loadHistory();
  loadAnalysis();
}

async function loadAnalysis() {
  if (!getToken()) return;
  const body = document.getElementById("analysis-body");
  if (!body) return;
  body.innerHTML = "";
  try {
    const response = await authFetch(`${API_BASE}/analysis`);
    if (!response.ok) return;
    const data = await response.json();
    data.forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${row.created_at ? new Date(row.created_at).toLocaleDateString("pt-BR") : "-"}</td>
        <td>${row.nome_empresa || "-"}</td>
        <td>${row.nome_cliente || "-"}</td>
        <td>${formatCurrency(row.rendimento_anual || 0)}</td>
        <td>${formatCurrency(row.total_tributos_pf || 0)}</td>
        <td>${formatCurrency(row.total_impostos_pj || 0)}</td>
        <td>${formatCurrency(row.impacto_pf || 0)}</td>
        <td>${formatPercent(row.aliquota_pf || 0)}</td>
        <td>${formatPercent(row.aliquota_pj_final || 0)}</td>
        <td>${formatCurrency(row.economia_tributaria || 0)}</td>
      `;
      body.appendChild(tr);
    });
  } catch (error) {
    statusError.textContent = "Faça login para acessar a análise.";
    statusError.classList.remove("hidden");
  }
}

async function handleLogin() {
  loginError.textContent = "";
  const login = loginUser.value.trim();
  const senha = loginPass.value.trim();
  if (!login || !senha) {
    loginError.textContent = "Informe usuario e senha.";
    return;
  }
  const response = await fetch(`${API_BASE}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ login, senha }),
  });
  if (!response.ok) {
    loginError.textContent = "Credenciais invalidas.";
    return;
  }
  const data = await response.json();
  setToken(data.token);
  loginOverlay.classList.add("hidden");
  calculate();
  loadHistory();
  loadAnalysis();
  loadConfig();
}

if (loginButton) {
  loginButton.addEventListener("click", handleLogin);
}

[loginUser, loginPass].forEach((input) => {
  if (!input) return;
  input.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    handleLogin();
  });
});

function enforceLogin() {
  const token = getToken();
  if (!token) {
    loginOverlay.classList.remove("hidden");
    return;
  }
  loginOverlay.classList.add("hidden");
  loadHistory();
  loadAnalysis();
  loadConfig();
}

initTabs();
annotateComparisonTables();
setDefaults();
enforceLogin();

if (sidebarToggle) {
  sidebarToggle.addEventListener("click", () => {
    if (window.innerWidth <= 900) {
      sidebar.classList.toggle("open");
      appShell.classList.toggle("menu-open", sidebar.classList.contains("open"));
      return;
    }
    appShell.classList.toggle("collapsed");
  });
}

if (sidebarBackdrop) {
  sidebarBackdrop.addEventListener("click", () => {
    sidebar.classList.remove("open");
    appShell.classList.remove("menu-open");
  });
}

if (sidebarClose) {
  sidebarClose.addEventListener("click", () => {
    sidebar.classList.remove("open");
    appShell.classList.remove("menu-open");
  });
}

if (logoutButton) {
  logoutButton.addEventListener("click", () => {
    localStorage.removeItem("auth_token");
    setDefaults();
    loginOverlay.classList.remove("hidden");
    statusIndicator.textContent = "Faça login para continuar";
    statusError.classList.add("hidden");
  });
}

async function loadConfig() {
  if (!configForm || !getToken()) return;
  try {
    syncConfigForm(DEFAULT_CONFIG);
    const response = await authFetch(`${API_BASE}/config`);
    if (!response.ok) return;
    const data = mergeConfig(await response.json());
    currentConfig = data;
    syncConfigForm(data);
    syncPresumedProfitRateInput(data);
  } catch (error) {
    currentConfig = mergeConfig(currentConfig || DEFAULT_CONFIG);
    syncConfigForm(currentConfig);
    statusError.textContent = "Faça login para acessar os parâmetros.";
    statusError.classList.remove("hidden");
  }
}

function syncPresumedProfitRateInput(config) {
  const regime = config?.pj?.presumed_profit_regime === "hospital" ? "hospital" : "standard";
  setCheckboxGroup(regime);
}

function syncConfigForm(config) {
  if (!configForm) return;
  const mergedConfig = mergeConfig(config);
  currentConfig = mergedConfig;
  configVersionInput.value = mergedConfig.version || "";
  configPfIrpfFlatInput.value = percentInputValue(mergedConfig.pf.irpf_flat);
  configPfInssPfRateInput.value = percentInputValue(mergedConfig.pf.inss_pf_rate);
  configPfProlaboreInssRateInput.value = percentInputValue(mergedConfig.pf.prolabore_inss_rate);

  const regime = mergedConfig.pj.presumed_profit_regime === "hospital" ? "hospital" : "standard";
  configRegimeStandard.checked = regime === "standard";
  configRegimeHospital.checked = regime === "hospital";

  configPjStandardIrpjPresumedRateInput.value = percentInputValue(mergedConfig.pj.standard_irpj_presumed_rate);
  configPjStandardCsllPresumedRateInput.value = percentInputValue(mergedConfig.pj.standard_csll_presumed_rate);
  configPjHospitalPresumedRateInput.value = percentInputValue(mergedConfig.pj.hospital_presumed_rate);
  configPjIrpjRateInput.value = percentInputValue(mergedConfig.pj.irpj_rate);
  configPjIrpjAdditionalRateInput.value = percentInputValue(mergedConfig.pj.irpj_additional_rate);
  configPjIrpjAdditionalThresholdInput.value = String(mergedConfig.pj.irpj_additional_threshold ?? 0);
  configPjCsllRateInput.value = percentInputValue(mergedConfig.pj.csll_rate);
  configPjPisRateInput.value = percentInputValue(mergedConfig.pj.pis_rate);
  configPjCofinsRateInput.value = percentInputValue(mergedConfig.pj.cofins_rate);
  configPjCbsRateInput.value = percentInputValue(mergedConfig.pj.cbs_rate);
  configPjIbsRateInput.value = percentInputValue(mergedConfig.pj.ibs_rate);
  configPjInssFolhaRateInput.value = percentInputValue(mergedConfig.pj.inss_folha_rate);
  configPjCbsEnabledInput.checked = Boolean(mergedConfig.pj.cbs_enabled);
  configPjIbsEnabledInput.checked = Boolean(mergedConfig.pj.ibs_enabled);
  configPjDoubleExpenseInput.checked = Boolean(mergedConfig.pj.double_expense_in_pj);
}

function buildConfigFromForm() {
  const regime = configRegimeHospital?.checked ? "hospital" : "standard";
  return {
    version: configVersionInput.value.trim(),
    pf: {
      irpf_flat: parseNumberInput(configPfIrpfFlatInput, "IRPF", { percent: true }),
      inss_pf_rate: parseNumberInput(configPfInssPfRateInput, "INSS PF", { percent: true }),
      prolabore_inss_rate: parseNumberInput(configPfProlaboreInssRateInput, "INSS pró-labore", { percent: true }),
    },
    pj: {
      presumed_profit_regime: regime,
      standard_irpj_presumed_rate: parseNumberInput(configPjStandardIrpjPresumedRateInput, "Base IRPJ padrão", { percent: true }),
      standard_csll_presumed_rate: parseNumberInput(configPjStandardCsllPresumedRateInput, "Base CSLL padrão", { percent: true }),
      hospital_presumed_rate: parseNumberInput(configPjHospitalPresumedRateInput, "Base hospitalar", { percent: true }),
      irpj_rate: parseNumberInput(configPjIrpjRateInput, "Alíquota IRPJ", { percent: true }),
      irpj_additional_rate: parseNumberInput(configPjIrpjAdditionalRateInput, "Adicional IRPJ", { percent: true }),
      irpj_additional_threshold: parseNumberInput(configPjIrpjAdditionalThresholdInput, "Limite adicional IRPJ"),
      csll_rate: parseNumberInput(configPjCsllRateInput, "Alíquota CSLL", { percent: true }),
      pis_rate: parseNumberInput(configPjPisRateInput, "PIS", { percent: true }),
      cofins_rate: parseNumberInput(configPjCofinsRateInput, "COFINS", { percent: true }),
      cbs_rate: parseNumberInput(configPjCbsRateInput, "CBS", { percent: true }),
      ibs_rate: parseNumberInput(configPjIbsRateInput, "IBS", { percent: true }),
      inss_folha_rate: parseNumberInput(configPjInssFolhaRateInput, "INSS folha", { percent: true }),
      cbs_enabled: Boolean(configPjCbsEnabledInput.checked),
      ibs_enabled: Boolean(configPjIbsEnabledInput.checked),
      double_expense_in_pj: Boolean(configPjDoubleExpenseInput.checked),
    },
  };
}

async function saveConfig() {
  if (!configForm || !getToken()) return;
  try {
    const parsed = buildConfigFromForm();
    const response = await authFetch(`${API_BASE}/config`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(parsed),
    });
    if (!response.ok) {
      throw new Error("Falha ao salvar");
    }
    currentConfig = mergeConfig(parsed);
    syncConfigForm(currentConfig);
    syncPresumedProfitRateInput(currentConfig);
    statusError.classList.add("hidden");
    statusIndicator.textContent = "Parâmetros salvos";
    calculate();
  } catch (error) {
    statusError.textContent = error.message || "Erro ao salvar parâmetros.";
    statusError.classList.remove("hidden");
  }
}

async function persistPresumedProfitRate() {
  if (!getToken()) return;

  const regime = presumedRegimeHospital?.checked ? "hospital" : presumedRegimeStandard?.checked ? "standard" : null;
  if (!regime) {
    setError("presumed_profit_regime", "Selecione um regime");
    return;
  }

  setError("presumed_profit_regime", "");
  const nextConfig = JSON.parse(JSON.stringify(currentConfig || {}));
  nextConfig.pj = nextConfig.pj || {};
  nextConfig.pj.presumed_profit_regime = regime;
  Object.assign(nextConfig.pj, PRESUMED_REGIMES[regime]);

  try {
    const response = await authFetch(`${API_BASE}/config`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(nextConfig),
    });
    if (!response.ok) {
      throw new Error("Falha ao salvar");
    }
    currentConfig = mergeConfig(nextConfig);
    syncConfigForm(currentConfig);
    syncPresumedProfitRateInput(currentConfig);
    statusIndicator.textContent = "Parâmetros salvos";
    calculate();
  } catch (error) {
    statusError.textContent = "Não foi possível salvar o regime de presunção.";
    statusError.classList.remove("hidden");
  }
}

if (configRefresh) {
  configRefresh.addEventListener("click", loadConfig);
}

if (configSave) {
  configSave.addEventListener("click", saveConfig);
}

if (configLockInput) {
  configLockInput.addEventListener("change", () => {
    setConfigLocked(configLockInput.checked);
  });
}

function schedulePresumedProfitSave() {
  clearTimeout(configSaveTimer);
  configSaveTimer = setTimeout(() => {
    persistPresumedProfitRate();
  }, 400);
}

if (presumedRegimeStandard) {
  presumedRegimeStandard.addEventListener("change", () => {
    if (!presumedRegimeStandard.checked) {
      presumedRegimeStandard.checked = true;
    }
    if (presumedRegimeHospital) {
      presumedRegimeHospital.checked = false;
    }
    setCheckboxGroup("standard");
    schedulePresumedProfitSave();
  });
}

if (presumedRegimeHospital) {
  presumedRegimeHospital.addEventListener("change", () => {
    if (!presumedRegimeHospital.checked) {
      presumedRegimeHospital.checked = true;
    }
    if (presumedRegimeStandard) {
      presumedRegimeStandard.checked = false;
    }
    setCheckboxGroup("hospital");
    schedulePresumedProfitSave();
  });
}

if (!presumedRegimeStandard?.checked && !presumedRegimeHospital?.checked) {
  setCheckboxGroup("standard");
}

currentConfig = mergeConfig(DEFAULT_CONFIG);
syncConfigForm(currentConfig);
setConfigLocked(true);

window.addEventListener("resize", () => {
  if (window.innerWidth > 900) {
    sidebar.classList.remove("open");
    appShell.classList.remove("menu-open");
  }
});
