const API_BASE = "";
const API_URL = `${API_BASE}/calculate`;

const defaults = {
  nome_cliente: "",
  nome_empresa: "",
  rendimento_mensal: 0,
  pro_labore: 0,
  iss_fixo: 0,
  salario_minimo: 0,
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
const configArea = document.getElementById("config-json");
const configRefresh = document.getElementById("config-refresh");
const configSave = document.getElementById("config-save");
const consolidatedMap = {
  "cons-rendimento": () => formatCurrency(state.rendimento_mensal),
  "cons-prolabore": () => formatCurrency(state.pro_labore),
  "cons-iss": () => formatCurrency(state.iss_fixo),
  "cons-salario": () => formatCurrency(state.salario_minimo),
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
  salario_minimo: "salario_minimo",
  secretaria: "secretaria",
  aluguel_condominio: "aluguel_condominio",
  contador: "contador",
  outras_despesas: "outras_despesas",
};

const outputMap = {
  "pf-rendimento": (data) => data.pf.rendimento_anual,
  "pf-inss": (data) => data.pf.inss,
  "pf-irpf": (data) => data.pf.irpf,
  "pf-total-tributos": (data) => data.pf.total_tributos,
  "pf-aliquota": (data) => data.pf.aliquota_efetiva,
  "pf-receita": (data) => data.pf.receita_liquida,
  "pj-irpj": (data) => data.pj.irpj_total,
  "pj-csll": (data) => data.pj.csll,
  "pj-pis": (data) => data.pj.pis,
  "pj-cofins": (data) => data.pj.cofins,
  "pj-iss": (data) => data.pj.iss,
  "pj-total-impostos": (data) => data.pj.total_impostos,
  "pj-lucro": (data) => data.pj.lucro_liquido,
  "pj-dividendos": (data) => data.pj.dividendos,
  "pj-impacto-pf": (data) => data.pj.impacto_pf,
  "pj-aliquota-final": (data) => data.pj.aliquota_efetiva_final,
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

  const parecer = document.getElementById("parecer-texto");
  if (parecer) {
    parecer.textContent = getParecerText(data);
  }
}

function getParecerText(data) {
  const economia = data.comparativo.economia_tributaria;
  if (economia > 0) {
    return "Com base nas premissas, a estrutura PJ apresenta menor carga tributária total e maior eficiência fiscal, indicando vantagem econômica em relação à PF.";
  }
  if (economia < 0) {
    return "Com base nas premissas, a estrutura PF apresenta melhor resultado tributário total do que a PJ. Recomenda-se manter o modelo PF ou revisar as premissas.";
  }
  return "Com base nas premissas, os resultados entre PF e PJ são equivalentes. Avalie outros fatores operacionais antes de decidir.";
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
    salario_minimo: state.salario_minimo,
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

document.getElementById("reset").addEventListener("click", () => {
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

  document.getElementById("print-rendimento").textContent = formatCurrency(state.rendimento_mensal);
  document.getElementById("print-prolabore").textContent = formatCurrency(state.pro_labore);
  document.getElementById("print-iss").textContent = formatCurrency(state.iss_fixo);
  document.getElementById("print-salario").textContent = formatCurrency(state.salario_minimo);
  document.getElementById("print-despesas").textContent = formatCurrency(
    state.secretaria + state.aluguel_condominio + state.contador + state.outras_despesas
  );

  document.getElementById("print-pf-rendimento").textContent = formatCurrency(data.pf.rendimento_anual);
  document.getElementById("print-pf-inss").textContent = formatCurrency(data.pf.inss);
  document.getElementById("print-pf-irpf").textContent = formatCurrency(data.pf.irpf);
  document.getElementById("print-pf-total").textContent = formatCurrency(data.pf.total_tributos);
  document.getElementById("print-pf-aliquota").textContent = formatPercent(data.pf.aliquota_efetiva);
  document.getElementById("print-pf-receita").textContent = formatCurrency(data.pf.receita_liquida);

  document.getElementById("print-pj-irpj").textContent = formatCurrency(data.pj.irpj_total);
  document.getElementById("print-pj-csll").textContent = formatCurrency(data.pj.csll);
  document.getElementById("print-pj-pis").textContent = formatCurrency(data.pj.pis);
  document.getElementById("print-pj-cofins").textContent = formatCurrency(data.pj.cofins);
  document.getElementById("print-pj-iss").textContent = formatCurrency(data.pj.iss);
  document.getElementById("print-pj-total").textContent = formatCurrency(data.pj.total_impostos);
  document.getElementById("print-pj-lucro").textContent = formatCurrency(data.pj.lucro_liquido);
  document.getElementById("print-pj-dividendos").textContent = formatCurrency(data.pj.dividendos);
  document.getElementById("print-pj-impacto").textContent = formatCurrency(data.pj.impacto_pf);
  document.getElementById("print-pj-aliquota").textContent = formatPercent(data.pj.aliquota_efetiva_final);

  document.getElementById("print-comp-economia").textContent = formatCurrency(data.comparativo.economia_tributaria);
  document.getElementById("print-comp-aliquota-pf").textContent = formatPercent(data.comparativo.aliquota_pf);
  document.getElementById("print-comp-aliquota-pj").textContent = formatPercent(data.comparativo.aliquota_pj_final);
  document.getElementById("print-comp-receita-pf").textContent = formatCurrency(data.comparativo.receita_liquida_pf);
  document.getElementById("print-comp-lucro-pj").textContent = formatCurrency(data.comparativo.lucro_liquido_pj);

  document.getElementById("print-analise-tributos-pf").textContent = formatCurrency(data.pf.total_tributos);
  document.getElementById("print-analise-impostos-pj").textContent = formatCurrency(data.pj.total_impostos);
  document.getElementById("print-analise-impacto-pf").textContent = formatCurrency(data.pj.impacto_pf);
  document.getElementById("print-parecer").textContent = getParecerText(data);
}

function updateConsolidated(data) {
  Object.entries(consolidatedMap).forEach(([id, getter]) => {
    const el = document.getElementById(id);
    if (!el) return;
    const value = getter(data);
    el.textContent = value;
  });
  const parecer = document.getElementById("cons-parecer");
  if (parecer) {
    parecer.textContent = getParecerText(data);
  }
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
      margin: [10, 10, 10, 10],
      filename: `${filenameBase}_pf_pj.pdf`,
      image: { type: "jpeg", quality: 0.95 },
      html2canvas: {
        scale: 2,
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

document.getElementById("save-session").addEventListener("click", async () => {
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
        salario_minimo: state.salario_minimo,
      }),
    });

    if (!response.ok) {
      throw new Error("Falha ao salvar");
    }
    await loadHistory();
    await loadAnalysis();
    statusIndicator.textContent = "Simulação salva";
  } catch (error) {
    statusError.textContent = "Nao foi possivel salvar a simulacao.";
    statusError.classList.remove("hidden");
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
  const response = await authFetch(`/simulations/`);
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
  state.salario_minimo = input.salario_minimo || 0;

  state.secretaria = input.despesas_anuais?.secretaria || 0;
  state.aluguel_condominio = input.despesas_anuais?.aluguel_condominio || 0;
  state.contador = input.despesas_anuais?.contador || 0;
  state.outras_despesas = input.despesas_anuais?.outras_despesas || 0;

  setInputValue("rendimento_mensal", state.rendimento_mensal);
  setInputValue("pro_labore", state.pro_labore);
  setInputValue("iss_fixo", state.iss_fixo);
  setInputValue("salario_minimo", state.salario_minimo);
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
  const response = await authFetch(`/simulations/`, { method: "DELETE" });
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
  if (!configArea || !getToken()) return;
  try {
    const response = await authFetch(`${API_BASE}/config`);
    if (!response.ok) return;
    const data = await response.json();
    configArea.value = JSON.stringify(data, null, 2);
  } catch (error) {
    statusError.textContent = "Faça login para acessar os parâmetros.";
    statusError.classList.remove("hidden");
  }
}

async function saveConfig() {
  if (!configArea || !getToken()) return;
  try {
    const parsed = JSON.parse(configArea.value);
    const response = await authFetch(`${API_BASE}/config`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(parsed),
    });
    if (!response.ok) {
      throw new Error("Falha ao salvar");
    }
    statusIndicator.textContent = "Parâmetros salvos";
  } catch (error) {
    statusError.textContent = "JSON inválido ou erro ao salvar parâmetros.";
    statusError.classList.remove("hidden");
  }
}

if (configRefresh) {
  configRefresh.addEventListener("click", loadConfig);
}

if (configSave) {
  configSave.addEventListener("click", saveConfig);
}

window.addEventListener("resize", () => {
  if (window.innerWidth > 900) {
    sidebar.classList.remove("open");
    appShell.classList.remove("menu-open");
  }
});
