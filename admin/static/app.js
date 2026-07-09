const state = {
  token: localStorage.getItem("ocesAdminToken") || "",
  loading: false,
  data: null,
};

const tokenInput = document.querySelector("#tokenInput");
const saveToken = document.querySelector("#saveToken");
const refreshAll = document.querySelector("#refreshAll");
const cards = document.querySelector("#cards");
const rows = document.querySelector("#rows");
const notice = document.querySelector("#notice");
const createInstanceForm = document.querySelector("#createInstanceForm");
const createInstanceButton = document.querySelector("#createInstance");
const newName = document.querySelector("#newName");
const newDomain = document.querySelector("#newDomain");
const newPort = document.querySelector("#newPort");

tokenInput.value = state.token;

saveToken.addEventListener("click", () => {
  state.token = tokenInput.value.trim();
  localStorage.setItem("ocesAdminToken", state.token);
  loadStatus();
});

refreshAll.addEventListener("click", () => loadStatus());
createInstanceForm.addEventListener("submit", createInstance);
newName.addEventListener("input", () => {
  if (!newDomain.value.trim()) {
    newDomain.value = suggestedDomain(newName.value.trim(), state.data?.instances || []);
  }
});

async function api(path) {
  const headers = {};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(path, { headers, cache: "no-store" });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

async function apiPost(path) {
  const headers = {};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(path, { method: "POST", headers, cache: "no-store" });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

async function apiJsonPost(path, payload) {
  const headers = { "Content-Type": "application/json" };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(path, {
    method: "POST",
    headers,
    cache: "no-store",
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

async function loadStatus(instance = null) {
  setNotice("");
  state.loading = true;
  refreshAll.disabled = true;
  try {
    const url = instance ? `/api/status?instance=${encodeURIComponent(instance)}` : "/api/status";
    const data = await api(url);
    if (instance && state.data) {
      const updated = data.instances[0];
      state.data.instances = state.data.instances.map((item) =>
        item.name === instance ? updated : item,
      );
      state.data.generatedAt = data.generatedAt;
    } else {
      state.data = data;
    }
    render(state.data);
    fillCreateDefaults();
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    state.loading = false;
    refreshAll.disabled = false;
  }
}

async function createInstance(event) {
  event.preventDefault();
  const payload = {
    name: newName.value.trim().toLowerCase(),
    domain: newDomain.value.trim().toLowerCase(),
    port: Number(newPort.value),
  };
  if (!payload.name || !payload.domain || !payload.port) {
    setNotice("Informe nome, domínio e porta para criar a instância.");
    return;
  }
  if (!window.confirm(`Criar e iniciar a instância ${title(payload.name)}?`)) return;

  createInstanceButton.disabled = true;
  refreshAll.disabled = true;
  setNotice(`Criando ${title(payload.name)}...`);
  try {
    await apiJsonPost("/api/instances", payload);
    setNotice(`${title(payload.name)} criada. Atualizando o painel em alguns segundos.`);
    createInstanceForm.reset();
    window.setTimeout(() => loadStatus(), 8000);
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    createInstanceButton.disabled = false;
    refreshAll.disabled = false;
  }
}

function render(data) {
  const instances = data.instances || [];
  document.querySelector("#countTotal").textContent = instances.length;
  document.querySelector("#countHealthy").textContent = instances.filter(isHealthy).length;
  document.querySelector("#countTelegram").textContent = instances.filter((item) =>
    channelOk(item, "telegram"),
  ).length;
  document.querySelector("#countWhatsapp").textContent = instances.filter((item) =>
    channelOk(item, "whatsapp"),
  ).length;

  cards.innerHTML = instances.map(renderCard).join("");
  rows.innerHTML = instances.map(renderRow).join("");

  document.querySelectorAll("[data-refresh-instance]").forEach((button) => {
    button.addEventListener("click", () => loadStatus(button.dataset.refreshInstance));
  });

  document.querySelectorAll("[data-validate-channel]").forEach((button) => {
    button.addEventListener("click", async () => {
      const label = button.dataset.validateChannel === "whatsapp" ? "WhatsApp" : "Telegram";
      await loadStatus(button.dataset.instance);
      setNotice(`${label} validado para ${title(button.dataset.instance)}.`);
    });
  });

  document.querySelectorAll("[data-restart-instance]").forEach((button) => {
    button.addEventListener("click", () => restartInstance(button.dataset.restartInstance));
  });
}

function renderCard(item) {
  const docker = item.docker || {};
  const health = item.publicHealth || {};
  const channels = item.channels || {};
  return `
    <article class="card">
      <div class="card-head">
        <div>
          <h2>${escapeHtml(title(item.name))}</h2>
          <div class="domain">${escapeHtml(item.domain)}</div>
        </div>
        ${gatewayPill(item)}
      </div>
      <div class="metrics">
        ${metric("Container", `${docker.status || "-"} / ${docker.health || "-"}`)}
        ${metric("HTTP", health.status ? String(health.status) : "-")}
        ${metric("Versão", versionText(item))}
        ${metric("Modelo", modelText(item))}
        ${metric("Telegram", channelPill(channels.telegram))}
        ${metric("WhatsApp", channelPill(channels.whatsapp))}
      </div>
    </article>
  `;
}

function renderRow(item) {
  const channels = item.channels || {};
  const models = item.models || {};
  return `
    <tr>
      <td>
        <div class="row-title">${escapeHtml(title(item.name))}</div>
        <div class="domain">${escapeHtml(item.domain)}</div>
      </td>
      <td>${gatewayPill(item)}</td>
      <td>${escapeHtml(versionText(item))}</td>
      <td>${escapeHtml(modelText(item))}</td>
      <td>${openAiPill(models.openai)}</td>
      <td>${channelPill(channels.telegram)}</td>
      <td>${channelPill(channels.whatsapp)}</td>
      <td>
        <div class="row-actions">
          <a href="${escapeAttribute(item.url)}" target="_blank" rel="noreferrer">Abrir</a>
          <button type="button" data-refresh-instance="${escapeAttribute(item.name)}">Validar</button>
          <button type="button" data-validate-channel="telegram" data-instance="${escapeAttribute(item.name)}">Telegram</button>
          <button type="button" data-validate-channel="whatsapp" data-instance="${escapeAttribute(item.name)}">WhatsApp</button>
          <button type="button" class="danger" data-restart-instance="${escapeAttribute(item.name)}">Reiniciar</button>
        </div>
      </td>
    </tr>
  `;
}

async function restartInstance(instance) {
  const name = title(instance);
  if (!window.confirm(`Reiniciar a instância ${name}?`)) return;

  setNotice(`Solicitando reinício de ${name}...`);
  refreshAll.disabled = true;
  try {
    await apiPost(`/api/instances/${encodeURIComponent(instance)}/restart`);
    setNotice(`Reinício enviado para ${name}. Vou atualizar o status em alguns segundos.`);
    window.setTimeout(() => loadStatus(instance), 7000);
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    refreshAll.disabled = false;
  }
}

function metric(label, value) {
  return `
    <div class="metric">
      <span>${escapeHtml(label)}</span>
      <span class="value">${typeof value === "string" ? escapeHtml(value) : value}</span>
    </div>
  `;
}

function gatewayPill(item) {
  if (isHealthy(item)) return pill("ok", "Online");
  if (item.docker?.running) return pill("warn", "Parcial");
  return pill("bad", "Offline");
}

function openAiPill(openai = {}) {
  if (openai.apiKey) return pill("ok", "API key");
  if (openai.oauth) return pill("warn", "OAuth");
  return pill("bad", "Sem auth");
}

function channelPill(channel = {}) {
  if (!channel.present) return pill("idle", "Ausente");
  if (channel.connected || channel.linked || channel.lastProbeOk) return pill("ok", "Conectado");
  if (channel.configured) return pill("warn", channel.statusState || channel.healthState || "Pendente");
  return pill("idle", channel.statusState || "Não configurado");
}

function pill(kind, label) {
  return `<span class="pill ${kind}">${escapeHtml(label)}</span>`;
}

function isHealthy(item) {
  return item.docker?.running && item.docker?.health === "healthy" && item.publicHealth?.ok;
}

function channelOk(item, channel) {
  const current = item.channels?.[channel];
  return Boolean(current?.connected || current?.linked || current?.lastProbeOk);
}

function versionText(item) {
  const version = item.version?.version || "-";
  return version.replace(/^OpenClaw\s+/, "");
}

function modelText(item) {
  return item.models?.default || "-";
}

function fillCreateDefaults() {
  const instances = state.data?.instances || [];
  if (!newPort.value) {
    const ports = instances.map((item) => Number(item.port)).filter(Number.isFinite);
    newPort.value = String(ports.length ? Math.max(...ports) + 1 : 3001);
  }
  if (newName.value.trim() && !newDomain.value.trim()) {
    newDomain.value = suggestedDomain(newName.value.trim(), instances);
  }
}

function suggestedDomain(name, instances) {
  const clean = name.toLowerCase().replace(/[^a-z0-9-]/g, "").replace(/^-+|-+$/g, "");
  if (!clean) return "";
  const domain = instances.find((item) => item.domain)?.domain || "";
  const suffix = domain.split(".").slice(1).join(".");
  return suffix ? `${clean}.${suffix}` : "";
}

function title(value) {
  if (value === "te") return "TE";
  if (value === "dp") return "DP";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function setNotice(message) {
  notice.textContent = message;
  notice.classList.toggle("hidden", !message);
}

function readableError(error) {
  const text = String(error?.message || error);
  if (text.includes("unauthorized")) {
    return "Token administrativo inválido ou ausente.";
  }
  return text;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}

loadStatus();
