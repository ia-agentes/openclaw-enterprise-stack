const state = {
  token: localStorage.getItem("ocesAdminToken") || "",
  loading: false,
  data: null,
  pending: [],
};

const tokenInput = document.querySelector("#tokenInput");
const saveToken = document.querySelector("#saveToken");
const refreshAll = document.querySelector("#refreshAll");
const tokenStatus = document.querySelector("#tokenStatus");
const cards = document.querySelector("#cards");
const rows = document.querySelector("#rows");
const notice = document.querySelector("#notice");
const createInstanceForm = document.querySelector("#createInstanceForm");
const createInstanceButton = document.querySelector("#createInstance");
const newName = document.querySelector("#newName");
const newDomain = document.querySelector("#newDomain");
const newPort = document.querySelector("#newPort");
const aiConfigForm = document.querySelector("#aiConfigForm");
const aiInstance = document.querySelector("#aiInstance");
const openAiKey = document.querySelector("#openAiKey");
const aiModel = document.querySelector("#aiModel");
const saveOpenAiKey = document.querySelector("#saveOpenAiKey");
const saveAiModel = document.querySelector("#saveAiModel");
const startOpenAiOAuth = document.querySelector("#startOpenAiOAuth");
const refreshOpenAiOAuth = document.querySelector("#refreshOpenAiOAuth");
const openAiOAuthPanel = document.querySelector("#openAiOAuthPanel");
const browserConfigForm = document.querySelector("#browserConfigForm");
const browserInstance = document.querySelector("#browserInstance");
const browserProfileName = document.querySelector("#browserProfileName");
const browserUserDataDir = document.querySelector("#browserUserDataDir");
const browserCdpUrl = document.querySelector("#browserCdpUrl");
const browserAttachOnly = document.querySelector("#browserAttachOnly");
const saveBrowserConfig = document.querySelector("#saveBrowserConfig");
const refreshBrowserConfig = document.querySelector("#refreshBrowserConfig");
const validateBrowserConfig = document.querySelector("#validateBrowserConfig");
const browserConfigPanel = document.querySelector("#browserConfigPanel");
const ticketsDbConfigForm = document.querySelector("#ticketsDbConfigForm");
const ticketsDbInstance = document.querySelector("#ticketsDbInstance");
const ticketsDbType = document.querySelector("#ticketsDbType");
const ticketsDbHost = document.querySelector("#ticketsDbHost");
const ticketsDbPort = document.querySelector("#ticketsDbPort");
const ticketsDbName = document.querySelector("#ticketsDbName");
const ticketsDbUser = document.querySelector("#ticketsDbUser");
const ticketsDbPassword = document.querySelector("#ticketsDbPassword");
const ticketsDbSafeView = document.querySelector("#ticketsDbSafeView");
const ticketsDbSslMode = document.querySelector("#ticketsDbSslMode");
const saveTicketsDbConfig = document.querySelector("#saveTicketsDbConfig");
const refreshTicketsDbConfig = document.querySelector("#refreshTicketsDbConfig");
const testTicketsDbConfig = document.querySelector("#testTicketsDbConfig");
const ticketsDbConfigPanel = document.querySelector("#ticketsDbConfigPanel");
const telegramConfigForm = document.querySelector("#telegramConfigForm");
const telegramInstance = document.querySelector("#telegramInstance");
const telegramBotToken = document.querySelector("#telegramBotToken");
const telegramExpectedUser = document.querySelector("#telegramExpectedUser");
const telegramPairingCode = document.querySelector("#telegramPairingCode");
const saveTelegramConfig = document.querySelector("#saveTelegramConfig");
const refreshTelegramPairings = document.querySelector("#refreshTelegramPairings");
const approveTelegramPairing = document.querySelector("#approveTelegramPairing");
const validateTelegram = document.querySelector("#validateTelegram");
const telegramPairingPanel = document.querySelector("#telegramPairingPanel");
const whatsappConfigForm = document.querySelector("#whatsappConfigForm");
const whatsappInstance = document.querySelector("#whatsappInstance");
const whatsappNumber = document.querySelector("#whatsappNumber");
const whatsappPairingCode = document.querySelector("#whatsappPairingCode");
const saveWhatsappNumber = document.querySelector("#saveWhatsappNumber");
const startWhatsappLogin = document.querySelector("#startWhatsappLogin");
const refreshWhatsappLogin = document.querySelector("#refreshWhatsappLogin");
const approveWhatsappPairing = document.querySelector("#approveWhatsappPairing");
const validateWhatsapp = document.querySelector("#validateWhatsapp");
const whatsappLoginPanel = document.querySelector("#whatsappLoginPanel");
const refreshPending = document.querySelector("#refreshPending");
const pendingAccessList = document.querySelector("#pendingAccessList");
const startOpenClawUpdate = document.querySelector("#startOpenClawUpdate");
const refreshOpenClawUpdate = document.querySelector("#refreshOpenClawUpdate");
const openClawUpdatePanel = document.querySelector("#openClawUpdatePanel");
const gatewayTokenForm = document.querySelector("#gatewayTokenForm");
const gatewayTokenInstance = document.querySelector("#gatewayTokenInstance");
const showGatewayToken = document.querySelector("#showGatewayToken");
const copyGatewayToken = document.querySelector("#copyGatewayToken");
const gatewayTokenPanel = document.querySelector("#gatewayTokenPanel");
const gatewayTokenValue = document.querySelector("#gatewayTokenValue");
const accessConfigForm = document.querySelector("#accessConfigForm");
const accessInstance = document.querySelector("#accessInstance");
const accessChannel = document.querySelector("#accessChannel");
const accessKind = document.querySelector("#accessKind");
const accessId = document.querySelector("#accessId");
const accessLabel = document.querySelector("#accessLabel");
const accessLevel = document.querySelector("#accessLevel");
const refreshChannelAccess = document.querySelector("#refreshChannelAccess");
const channelAccessPanel = document.querySelector("#channelAccessPanel");

let openClawUpdateTimer = null;
let revealedGatewayToken = "";

tokenInput.value = state.token;

saveToken.addEventListener("click", async () => {
  state.token = tokenInput.value.trim();
  localStorage.setItem("ocesAdminToken", state.token);
  await loadStatus(null, { source: "token" });
});

refreshAll.addEventListener("click", () => loadStatus(null, { source: "refresh" }));
refreshPending.addEventListener("click", () => loadPendingAccess());
startOpenClawUpdate.addEventListener("click", startOpenClawUpdateJob);
refreshOpenClawUpdate.addEventListener("click", refreshOpenClawUpdateStatus);
gatewayTokenForm.addEventListener("submit", (event) => event.preventDefault());
showGatewayToken.addEventListener("click", revealGatewayToken);
copyGatewayToken.addEventListener("click", copyRevealedGatewayToken);
gatewayTokenInstance.addEventListener("change", resetGatewayTokenPanel);
createInstanceForm.addEventListener("submit", createInstance);
saveOpenAiKey.addEventListener("click", configureOpenAiKey);
saveAiModel.addEventListener("click", configureAiModel);
startOpenAiOAuth.addEventListener("click", startOAuthLogin);
refreshOpenAiOAuth.addEventListener("click", refreshOAuthLogin);
aiConfigForm.addEventListener("submit", (event) => event.preventDefault());
browserConfigForm.addEventListener("submit", saveBrowserSettings);
refreshBrowserConfig.addEventListener("click", () => loadBrowserConfig());
validateBrowserConfig.addEventListener("click", validateBrowserSettings);
browserInstance.addEventListener("change", () => loadBrowserConfig());
ticketsDbConfigForm.addEventListener("submit", saveTicketsDbSettings);
refreshTicketsDbConfig.addEventListener("click", () => loadTicketsDbConfig());
testTicketsDbConfig.addEventListener("click", testTicketsDbSettings);
ticketsDbInstance.addEventListener("change", () => loadTicketsDbConfig());
ticketsDbType.addEventListener("change", syncTicketsDbPort);
saveTelegramConfig.addEventListener("click", saveTelegramSettings);
refreshTelegramPairings.addEventListener("click", refreshTelegramStatus);
approveTelegramPairing.addEventListener("click", approveTelegramCode);
validateTelegram.addEventListener("click", validateTelegramChannel);
telegramConfigForm.addEventListener("submit", (event) => event.preventDefault());
telegramInstance.addEventListener("change", () => refreshTelegramStatus());
startWhatsappLogin.addEventListener("click", startWhatsAppPairing);
saveWhatsappNumber.addEventListener("click", saveWhatsAppNumber);
refreshWhatsappLogin.addEventListener("click", refreshWhatsAppPairing);
approveWhatsappPairing.addEventListener("click", approveWhatsAppCode);
validateWhatsapp.addEventListener("click", validateWhatsApp);
whatsappConfigForm.addEventListener("submit", (event) => event.preventDefault());
whatsappInstance.addEventListener("change", () => refreshWhatsAppPairing());
accessConfigForm.addEventListener("submit", saveChannelAccess);
refreshChannelAccess.addEventListener("click", () => loadChannelAccess());
accessInstance.addEventListener("change", () => loadChannelAccess());
accessChannel.addEventListener("change", syncAccessForm);
accessKind.addEventListener("change", syncAccessForm);
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

async function loadStatus(instance = null, options = {}) {
  setNotice("");
  state.loading = true;
  const source = options.source || (instance ? "instance" : "auto");
  const previousSaveLabel = saveToken.textContent;
  const previousRefreshLabel = refreshAll.textContent;
  if (source === "token") {
    setTokenStatus("loading", "Validando token...");
    saveToken.textContent = "Salvando...";
    saveToken.disabled = true;
  } else if (source === "refresh") {
    setTokenStatus("loading", "Atualizando instâncias...");
    refreshAll.textContent = "Atualizando...";
  }
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
    loadPendingAccess();
    if (!instance) {
      const count = state.data?.instances?.length || 0;
      setTokenStatus("ok", `Conectado - ${count} instâncias carregadas`);
      if (source === "token") setNotice("Token salvo e conexão validada.");
    }
  } catch (error) {
    const message = readableError(error);
    if (!instance) setTokenStatus("bad", message);
    setNotice(message);
  } finally {
    state.loading = false;
    saveToken.disabled = false;
    saveToken.textContent = previousSaveLabel;
    refreshAll.textContent = previousRefreshLabel;
    refreshAll.disabled = false;
  }
}

async function loadPendingAccess() {
  try {
    const data = await api("/api/devices/pending");
    state.pending = data.items || [];
    renderPendingAccess(state.pending);
  } catch (error) {
    pendingAccessList.innerHTML = `<div class="empty-state">${escapeHtml(readableError(error))}</div>`;
  }
}

function renderPendingAccess(items) {
  const requests = [];
  for (const item of items || []) {
    for (const request of item.requests || []) {
      requests.push({ ...request, instance: item.instance });
    }
  }
  if (!requests.length) {
    pendingAccessList.innerHTML = '<div class="empty-state">Nenhum acesso pendente.</div>';
    return;
  }

  pendingAccessList.innerHTML = requests.map(renderPendingRequest).join("");
  document.querySelectorAll("[data-approve-device]").forEach((button) => {
    button.addEventListener("click", () =>
      approveDevice(button.dataset.instance, button.dataset.requestId),
    );
  });
}

function renderPendingRequest(request) {
  const scopes = Array.isArray(request.scopes) ? request.scopes.join(", ") : "";
  return `
    <div class="pending-item">
      <div>
        <strong>${escapeHtml(title(request.instance))}</strong>
        <span>${escapeHtml(request.remoteIp || "-")}</span>
      </div>
      <code>${escapeHtml(request.requestId)}</code>
      <small>${escapeHtml(scopes || request.clientId || "-")}</small>
      <button
        type="button"
        data-approve-device="true"
        data-instance="${escapeAttribute(request.instance)}"
        data-request-id="${escapeAttribute(request.requestId)}"
      >Aprovar</button>
    </div>
  `;
}

async function approveDevice(instance, requestId) {
  if (!window.confirm(`Aprovar acesso do navegador em ${title(instance)}?`)) return;
  setNotice(`Aprovando acesso em ${title(instance)}...`);
  try {
    await apiJsonPost("/api/devices/approve", { instance, requestId });
    setNotice(`Acesso aprovado em ${title(instance)}.`);
    await loadPendingAccess();
    window.setTimeout(() => loadStatus(instance), 2500);
  } catch (error) {
    setNotice(readableError(error));
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
  fillGatewayTokenInstances(instances);
  fillAiInstances(instances);
  fillBrowserInstances(instances);
  fillTicketsDbInstances(instances);
  fillTelegramInstances(instances);
  fillWhatsAppInstances(instances);
  fillAccessInstances(instances);
  if (accessInstance.value) {
    loadChannelAccess();
  }
  if (browserInstance.value) {
    loadBrowserConfig({ silent: true });
  }
  if (ticketsDbInstance.value) {
    loadTicketsDbConfig({ silent: true });
  }

  document.querySelectorAll("[data-refresh-instance]").forEach((button) => {
    button.addEventListener("click", () => loadStatus(button.dataset.refreshInstance));
  });

  document.querySelectorAll("[data-validate-channel]").forEach((button) => {
    button.addEventListener("click", async () => {
      const label = button.dataset.validateChannel === "whatsapp" ? "WhatsApp" : "Telegram";
      if (button.dataset.validateChannel === "whatsapp") {
        whatsappInstance.value = button.dataset.instance;
        await refreshWhatsAppPairing();
      } else if (button.dataset.validateChannel === "telegram") {
        telegramInstance.value = button.dataset.instance;
        await refreshTelegramStatus();
      } else {
        await loadStatus(button.dataset.instance);
        setNotice(`${label} validado para ${title(button.dataset.instance)}.`);
      }
    });
  });

  document.querySelectorAll("[data-restart-instance]").forEach((button) => {
    button.addEventListener("click", () => restartInstance(button.dataset.restartInstance));
  });
}

function fillAiInstances(instances) {
  const selected = aiInstance.value;
  aiInstance.innerHTML = instances
    .map((item) => `<option value="${escapeAttribute(item.name)}">${escapeHtml(title(item.name))}</option>`)
    .join("");
  if (instances.some((item) => item.name === selected)) {
    aiInstance.value = selected;
  }
  const current = instances.find((item) => item.name === aiInstance.value);
  const currentModel = current?.models?.default;
  if (currentModel && Array.from(aiModel.options).some((option) => option.value === currentModel)) {
    aiModel.value = currentModel;
  }
}

function fillGatewayTokenInstances(instances) {
  const selected = gatewayTokenInstance.value;
  gatewayTokenInstance.innerHTML = instances
    .map((item) => `<option value="${escapeAttribute(item.name)}">${escapeHtml(title(item.name))}</option>`)
    .join("");
  if (instances.some((item) => item.name === selected)) {
    gatewayTokenInstance.value = selected;
  }
  if (!revealedGatewayToken) resetGatewayTokenPanel();
}

function fillWhatsAppInstances(instances) {
  const selected = whatsappInstance.value;
  whatsappInstance.innerHTML = instances
    .map((item) => `<option value="${escapeAttribute(item.name)}">${escapeHtml(title(item.name))}</option>`)
    .join("");
  if (instances.some((item) => item.name === selected)) {
    whatsappInstance.value = selected;
  }
}

function fillBrowserInstances(instances) {
  const selected = browserInstance.value;
  browserInstance.innerHTML = instances
    .map((item) => `<option value="${escapeAttribute(item.name)}">${escapeHtml(title(item.name))}</option>`)
    .join("");
  if (instances.some((item) => item.name === selected)) {
    browserInstance.value = selected;
  }
}

function fillTicketsDbInstances(instances) {
  const selected = ticketsDbInstance.value || (instances.some((item) => item.name === "chamados") ? "chamados" : "");
  ticketsDbInstance.innerHTML = instances
    .map((item) => `<option value="${escapeAttribute(item.name)}">${escapeHtml(title(item.name))}</option>`)
    .join("");
  if (instances.some((item) => item.name === selected)) {
    ticketsDbInstance.value = selected;
  }
}

function fillTelegramInstances(instances) {
  const selected = telegramInstance.value;
  telegramInstance.innerHTML = instances
    .map((item) => `<option value="${escapeAttribute(item.name)}">${escapeHtml(title(item.name))}</option>`)
    .join("");
  if (instances.some((item) => item.name === selected)) {
    telegramInstance.value = selected;
  }
}

function fillAccessInstances(instances) {
  const selected = accessInstance.value;
  accessInstance.innerHTML = instances
    .map((item) => `<option value="${escapeAttribute(item.name)}">${escapeHtml(title(item.name))}</option>`)
    .join("");
  if (instances.some((item) => item.name === selected)) {
    accessInstance.value = selected;
  }
  syncAccessForm();
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

async function startOpenClawUpdateJob() {
  const total = state.data?.instances?.length || "todas as";
  const message =
    `Atualizar OpenClaw em ${total} instâncias?\n\n` +
    "O painel vai baixar a versão oficial mais recente, reconstruir a imagem e reiniciar as instâncias uma por vez.";
  if (!window.confirm(message)) return;

  startOpenClawUpdate.disabled = true;
  refreshOpenClawUpdate.disabled = true;
  setNotice("Atualização OpenClaw iniciada. Acompanhe o progresso abaixo.");
  try {
    const data = await apiPost("/api/admin/openclaw-update/start");
    renderOpenClawUpdatePanel(data.job || data);
    scheduleOpenClawUpdatePoll();
  } catch (error) {
    setNotice(readableError(error));
    await refreshOpenClawUpdateStatus();
  } finally {
    refreshOpenClawUpdate.disabled = false;
  }
}

async function refreshOpenClawUpdateStatus() {
  refreshOpenClawUpdate.disabled = true;
  try {
    const data = await api("/api/admin/openclaw-update/status");
    renderOpenClawUpdatePanel(data.job || data);
    if ((data.job || data).running) {
      scheduleOpenClawUpdatePoll();
    }
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    refreshOpenClawUpdate.disabled = false;
  }
}

function scheduleOpenClawUpdatePoll() {
  window.clearTimeout(openClawUpdateTimer);
  openClawUpdateTimer = window.setTimeout(refreshOpenClawUpdateStatus, 5000);
}

function renderOpenClawUpdatePanel(job = {}) {
  const status = job.running ? "Atualizando" : job.ok === true ? "Concluído" : job.ok === false ? "Falhou" : "Aguardando";
  const statusClass = job.running ? "warn" : job.ok === true ? "ok" : job.ok === false ? "bad" : "idle";
  const log = job.log || "Nenhuma atualização iniciada ainda.";
  startOpenClawUpdate.disabled = Boolean(job.running);
  openClawUpdatePanel.classList.remove("hidden");
  openClawUpdatePanel.innerHTML = `
    <div class="update-meta">
      ${pill(statusClass, status)}
      ${job.sourceRef ? `<span>Fonte: ${escapeHtml(job.sourceRef)}</span>` : ""}
      ${job.startedAt ? `<span>Início: ${escapeHtml(job.startedAt)}</span>` : ""}
      ${job.finishedAt ? `<span>Fim: ${escapeHtml(job.finishedAt)}</span>` : ""}
      ${job.error ? `<strong>${escapeHtml(job.error)}</strong>` : ""}
    </div>
    <pre>${escapeHtml(log)}</pre>
  `;
  if (job.ok === true) {
    setNotice("Atualização OpenClaw concluída. Vou atualizar os status das instâncias.");
    window.setTimeout(() => loadStatus(null, { source: "refresh" }), 8000);
  }
}

function resetGatewayTokenPanel() {
  revealedGatewayToken = "";
  copyGatewayToken.disabled = true;
  gatewayTokenPanel.classList.add("hidden");
  gatewayTokenValue.textContent = "••••••••••••••••••••••••";
}

async function revealGatewayToken() {
  const instance = gatewayTokenInstance.value;
  if (!instance) {
    setNotice("Selecione uma instância para mostrar o token.");
    return;
  }
  const confirmed = window.confirm(
    `Mostrar o token do Gateway de ${title(instance)}?\n\n` +
      "Esse token permite conectar a Control UI desta instância. Não compartilhe fora de canais seguros.",
  );
  if (!confirmed) return;

  showGatewayToken.disabled = true;
  copyGatewayToken.disabled = true;
  setNotice(`Buscando token do Gateway de ${title(instance)}...`);
  try {
    const data = await api(`/api/instances/${encodeURIComponent(instance)}/gateway-token`);
    revealedGatewayToken = data.token || "";
    if (!revealedGatewayToken) throw new Error("Token do Gateway não encontrado.");
    gatewayTokenPanel.classList.remove("hidden");
    gatewayTokenValue.textContent = revealedGatewayToken;
    copyGatewayToken.disabled = false;
    setNotice(`Token do Gateway de ${title(instance)} revelado.`);
  } catch (error) {
    resetGatewayTokenPanel();
    setNotice(readableError(error));
  } finally {
    showGatewayToken.disabled = false;
  }
}

async function copyRevealedGatewayToken() {
  if (!revealedGatewayToken) {
    setNotice("Mostre o token antes de copiar.");
    return;
  }
  try {
    await navigator.clipboard.writeText(revealedGatewayToken);
    setNotice("Token copiado para a área de transferência.");
  } catch (error) {
    setNotice("Não consegui copiar automaticamente. Selecione o token revelado e copie manualmente.");
  }
}

async function configureOpenAiKey() {
  const instance = aiInstance.value;
  const apiKey = openAiKey.value.trim();
  if (!instance) {
    setNotice("Selecione uma instância.");
    return;
  }
  if (!apiKey) {
    setNotice("Cole a nova OpenAI API key antes de salvar.");
    return;
  }
  if (!window.confirm(`Salvar nova API key da OpenAI em ${title(instance)} e recriar o container?`)) return;

  saveOpenAiKey.disabled = true;
  refreshAll.disabled = true;
  setNotice(`Atualizando API key em ${title(instance)}...`);
  try {
    await apiJsonPost(`/api/instances/${encodeURIComponent(instance)}/openai-key`, { apiKey });
    openAiKey.value = "";
    setNotice(`API key salva em ${title(instance)}. Atualizando status em alguns segundos.`);
    window.setTimeout(() => loadStatus(instance), 8000);
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    saveOpenAiKey.disabled = false;
    refreshAll.disabled = false;
  }
}

async function configureAiModel() {
  const instance = aiInstance.value;
  const model = aiModel.value;
  if (!instance || !model) {
    setNotice("Selecione uma instância e um modelo.");
    return;
  }
  if (!window.confirm(`Aplicar ${model} como modelo padrão de ${title(instance)}?`)) return;

  saveAiModel.disabled = true;
  refreshAll.disabled = true;
  setNotice(`Aplicando modelo em ${title(instance)}...`);
  try {
    await apiJsonPost(`/api/instances/${encodeURIComponent(instance)}/model`, { model });
    setNotice(`Modelo aplicado em ${title(instance)}. Atualizando status em alguns segundos.`);
    window.setTimeout(() => loadStatus(instance), 8000);
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    saveAiModel.disabled = false;
    refreshAll.disabled = false;
  }
}

async function startOAuthLogin() {
  const instance = aiInstance.value;
  if (!instance) {
    setNotice("Selecione uma instância.");
    return;
  }
  if (!window.confirm(`Iniciar login ChatGPT Plus em ${title(instance)}?`)) return;

  startOpenAiOAuth.disabled = true;
  refreshOpenAiOAuth.disabled = true;
  setNotice(`Iniciando OAuth ChatGPT em ${title(instance)}...`);
  try {
    await apiPost(`/api/instances/${encodeURIComponent(instance)}/oauth/openai/start`);
    setNotice(`OAuth iniciado em ${title(instance)}. Abra o link/código exibido abaixo.`);
    await refreshOAuthLogin();
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    startOpenAiOAuth.disabled = false;
    refreshOpenAiOAuth.disabled = false;
  }
}

async function refreshOAuthLogin() {
  const instance = aiInstance.value;
  if (!instance) {
    setNotice("Selecione uma instância.");
    return;
  }
  refreshOpenAiOAuth.disabled = true;
  try {
    const data = await api(`/api/instances/${encodeURIComponent(instance)}/oauth/openai/status`);
    renderOAuthPanel(data);
    if (data.exitCode === 0) {
      setNotice(`OAuth ChatGPT concluído em ${title(instance)}.`);
      window.setTimeout(() => loadStatus(instance), 2500);
    }
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    refreshOpenAiOAuth.disabled = false;
  }
}

function renderOAuthPanel(data) {
  const status = data.running ? "Aguardando autorização" : data.exitCode === 0 ? "Concluído" : "Parado";
  const links = (data.links || [])
    .map((link) => `<a href="${escapeAttribute(link)}" target="_blank" rel="noreferrer">${escapeHtml(link)}</a>`)
    .join("");
  const log = data.log || "Nenhum fluxo OAuth iniciado nesta instância.";
  const deviceCard =
    data.deviceUrl || data.deviceCode
      ? `
        <div class="device-code-card">
          <div>
            <span>Link de autorização</span>
            ${
              data.deviceUrl
                ? `<a href="${escapeAttribute(data.deviceUrl)}" target="_blank" rel="noreferrer">${escapeHtml(data.deviceUrl)}</a>`
                : '<strong>-</strong>'
            }
          </div>
          <div>
            <span>Código</span>
            <code>${escapeHtml(data.deviceCode || "-")}</code>
          </div>
          ${data.expiresText ? `<small>${escapeHtml(data.expiresText)}</small>` : ""}
        </div>
      `
      : "";
  openAiOAuthPanel.classList.remove("hidden");
  openAiOAuthPanel.innerHTML = `
    <div class="oauth-status">
      <strong>${escapeHtml(status)}</strong>
      <span>${data.exitCode === null || data.exitCode === undefined ? "" : `exit ${escapeHtml(data.exitCode)}`}</span>
    </div>
    ${deviceCard}
    ${links ? `<div class="oauth-links">${links}</div>` : ""}
    <pre>${escapeHtml(log)}</pre>
  `;
}

async function loadBrowserConfig(options = {}) {
  const instance = browserInstance.value;
  if (!instance) {
    browserConfigPanel.innerHTML = '<div class="empty-state">Selecione uma instância.</div>';
    browserConfigPanel.classList.remove("hidden");
    return;
  }
  refreshBrowserConfig.disabled = true;
  try {
    const data = await api(`/api/instances/${encodeURIComponent(instance)}/browser`);
    hydrateBrowserForm(data.browser || {});
    if (options.silent) return;
    renderBrowserPanel(data);
  } catch (error) {
    if (!options.silent) setNotice(readableError(error));
    browserConfigPanel.classList.remove("hidden");
    browserConfigPanel.innerHTML = `<div class="empty-state">${escapeHtml(readableError(error))}</div>`;
  } finally {
    refreshBrowserConfig.disabled = false;
  }
}

function hydrateBrowserForm(browser = {}) {
  const edge =
    (browser.profiles || []).find((profile) => profile.name === "edge") ||
    (browser.profiles || [])[0];
  if (!edge) return;
  browserProfileName.value = edge.name || "edge";
  browserUserDataDir.value = edge.userDataDir || "~/.config/microsoft-edge";
  browserCdpUrl.value = edge.cdpUrl || "http://127.0.0.1:9222";
  browserAttachOnly.checked = edge.attachOnly !== false;
}

async function saveBrowserSettings(event) {
  event.preventDefault();
  const instance = browserInstance.value;
  const payload = {
    profileName: browserProfileName.value.trim() || "edge",
    driver: "existing-session",
    attachOnly: browserAttachOnly.checked,
    userDataDir: browserUserDataDir.value.trim(),
    cdpUrl: browserCdpUrl.value.trim(),
    color: "#0078D7",
  };
  if (!instance) {
    setNotice("Selecione uma instância.");
    return;
  }
  if (!payload.userDataDir) {
    setNotice("Informe o diretório do perfil do navegador.");
    return;
  }
  const message =
    `Salvar perfil ${payload.profileName} em ${title(instance)} e reiniciar a instância?\n\n` +
    "O OpenClaw passará a tentar usar uma sessão existente do Edge nesse diretório.";
  if (!window.confirm(message)) return;

  saveBrowserConfig.disabled = true;
  refreshAll.disabled = true;
  setNotice(`Aplicando navegador em ${title(instance)}...`);
  try {
    const data = await apiJsonPost(`/api/instances/${encodeURIComponent(instance)}/browser`, payload);
    renderBrowserPanel(data);
    setNotice(`Configuração de navegador aplicada em ${title(instance)}. A instância foi reiniciada.`);
    window.setTimeout(() => loadStatus(instance), 7000);
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    saveBrowserConfig.disabled = false;
    refreshAll.disabled = false;
  }
}

async function validateBrowserSettings() {
  const instance = browserInstance.value;
  if (!instance) {
    setNotice("Selecione uma instância.");
    return;
  }
  validateBrowserConfig.disabled = true;
  setNotice(`Validando navegador em ${title(instance)}...`);
  try {
    const data = await apiPost(`/api/instances/${encodeURIComponent(instance)}/browser/validate`);
    renderBrowserPanel(data);
    setNotice(data.validated ? `Navegador validado em ${title(instance)}.` : `Validação de navegador retornou alerta em ${title(instance)}.`);
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    validateBrowserConfig.disabled = false;
  }
}

function renderBrowserPanel(data = {}) {
  const browser = data.browser || {};
  const profiles = browser.profiles || [];
  const raw = JSON.stringify(browser.raw || {}, null, 2);
  browserConfigPanel.classList.remove("hidden");
  browserConfigPanel.innerHTML = `
    <div class="oauth-status">
      <strong>${browser.enabled ? "Browser habilitado" : "Browser desabilitado"}</strong>
      <span>${profiles.length ? `${profiles.length} perfil(is)` : "Nenhum perfil configurado"}</span>
      ${data.validated === true ? "<span>CLI validada</span>" : ""}
    </div>
    ${
      profiles.length
        ? `<div class="browser-profile-list">${profiles.map(renderBrowserProfile).join("")}</div>`
        : '<div class="empty-state">Nenhum perfil de navegador configurado nesta instância.</div>'
    }
    ${data.output ? `<pre>${escapeHtml(data.output)}</pre>` : ""}
    <pre>${escapeHtml(raw)}</pre>
  `;
}

function renderBrowserProfile(profile) {
  return `
    <div class="browser-profile">
      <div>
        <strong>${escapeHtml(profile.name || "perfil")}</strong>
        <span>${escapeHtml(profile.driver || "-")}</span>
      </div>
      <code>${escapeHtml(profile.userDataDir || profile.cdpUrl || profile.executablePath || "-")}</code>
      ${pill(profile.attachOnly ? "warn" : "ok", profile.attachOnly ? "Sessão existente" : "Gerenciado")}
    </div>
  `;
}

function syncTicketsDbPort() {
  const defaults = {
    postgres: "5432",
    mysql: "3306",
    mariadb: "3306",
    mssql: "1433",
  };
  if (!ticketsDbPort.value.trim()) {
    ticketsDbPort.value = defaults[ticketsDbType.value] || "";
  }
}

async function loadTicketsDbConfig(options = {}) {
  const instance = ticketsDbInstance.value;
  if (!instance) {
    ticketsDbConfigPanel.innerHTML = '<div class="empty-state">Selecione uma instância.</div>';
    ticketsDbConfigPanel.classList.remove("hidden");
    return;
  }
  refreshTicketsDbConfig.disabled = true;
  try {
    const data = await api(`/api/instances/${encodeURIComponent(instance)}/tickets-db`);
    hydrateTicketsDbForm(data);
    if (options.silent) return;
    renderTicketsDbPanel(data);
  } catch (error) {
    if (!options.silent) setNotice(readableError(error));
    ticketsDbConfigPanel.classList.remove("hidden");
    ticketsDbConfigPanel.innerHTML = `<div class="empty-state">${escapeHtml(readableError(error))}</div>`;
  } finally {
    refreshTicketsDbConfig.disabled = false;
  }
}

function hydrateTicketsDbForm(data = {}) {
  if (data.type) ticketsDbType.value = data.type;
  ticketsDbHost.value = data.host || "";
  ticketsDbPort.value = data.port || "";
  ticketsDbName.value = data.database || "";
  ticketsDbUser.value = data.user || "";
  ticketsDbPassword.value = "";
  ticketsDbSafeView.value = data.safeView || "vw_chamados_agent";
  ticketsDbSslMode.value = data.sslmode || "prefer";
  syncTicketsDbPort();
}

function ticketsDbPayload() {
  return {
    type: ticketsDbType.value,
    host: ticketsDbHost.value.trim(),
    port: ticketsDbPort.value.trim(),
    database: ticketsDbName.value.trim(),
    user: ticketsDbUser.value.trim(),
    password: ticketsDbPassword.value.trim(),
    safeView: ticketsDbSafeView.value.trim() || "vw_chamados_agent",
    sslmode: ticketsDbSslMode.value,
  };
}

async function saveTicketsDbSettings(event) {
  event.preventDefault();
  const instance = ticketsDbInstance.value;
  const payload = ticketsDbPayload();
  if (!instance || !payload.host || !payload.database || !payload.user || !payload.safeView) {
    setNotice("Informe instância, host, banco, usuário de leitura e view segura.");
    return;
  }
  const passwordText = payload.password ? "A senha informada será salva no .env da instância." : "A senha salva, se existir, será preservada.";
  const message =
    `Salvar conexão somente leitura de chamados em ${title(instance)}?\n\n` +
    `${passwordText}\nA Diana deverá consultar apenas a view/tabela segura configurada.`;
  if (!window.confirm(message)) return;

  saveTicketsDbConfig.disabled = true;
  setNotice(`Salvando banco de chamados em ${title(instance)}...`);
  try {
    const data = await apiJsonPost(`/api/instances/${encodeURIComponent(instance)}/tickets-db`, payload);
    ticketsDbPassword.value = "";
    hydrateTicketsDbForm(data);
    renderTicketsDbPanel(data);
    setNotice(`Banco de chamados salvo em ${title(instance)}.`);
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    saveTicketsDbConfig.disabled = false;
  }
}

async function testTicketsDbSettings() {
  const instance = ticketsDbInstance.value;
  if (!instance) {
    setNotice("Selecione uma instância.");
    return;
  }
  testTicketsDbConfig.disabled = true;
  setNotice(`Testando alcance do banco de chamados em ${title(instance)}...`);
  try {
    const data = await apiPost(`/api/instances/${encodeURIComponent(instance)}/tickets-db/test`);
    renderTicketsDbPanel(data);
    setNotice(
      data.reachable
        ? `Banco de chamados alcançável em ${title(instance)}.`
        : `Banco de chamados configurado, mas host/porta não responderam em ${title(instance)}.`,
    );
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    testTicketsDbConfig.disabled = false;
  }
}

function renderTicketsDbPanel(data = {}) {
  const status = data.reachable === true ? "Alcançável" : data.configured ? "Configurado" : "Pendente";
  const statusClass = data.reachable === true ? "ok" : data.configured ? "warn" : "idle";
  const password = data.passwordSaved ? "senha salva" : "sem senha salva";
  ticketsDbConfigPanel.classList.remove("hidden");
  ticketsDbConfigPanel.innerHTML = `
    <div class="oauth-status">
      ${pill(statusClass, status)}
      <span>${escapeHtml(data.mode || "read-only")}</span>
      <span>${escapeHtml(password)}</span>
      ${data.latencyMs !== null && data.latencyMs !== undefined ? `<span>${escapeHtml(data.latencyMs)} ms</span>` : ""}
    </div>
    <div class="browser-profile-list">
      <div class="browser-profile">
        <div><span>Tipo</span><strong>${escapeHtml(data.type || "-")}</strong></div>
        <div><span>Host</span><code>${escapeHtml(data.host || "-")}</code></div>
        <div><span>Porta</span><code>${escapeHtml(data.port || "-")}</code></div>
        <div><span>Banco</span><code>${escapeHtml(data.database || "-")}</code></div>
        <div><span>Usuário</span><code>${escapeHtml(data.user || "-")}</code></div>
        <div><span>View segura</span><code>${escapeHtml(data.safeView || "-")}</code></div>
        <div><span>SSL</span><code>${escapeHtml(data.sslmode || "-")}</code></div>
      </div>
    </div>
    ${
      data.error
        ? `<div class="delivery-alert"><strong>Alerta de alcance</strong><span>${escapeHtml(data.error)}</span></div>`
        : '<div class="empty-state">Fase 1 pronta: a próxima etapa é mapear a view segura e criar consultas somente leitura.</div>'
    }
  `;
}

async function saveTelegramSettings() {
  const instance = telegramInstance.value;
  if (!instance) {
    setNotice("Selecione uma instância.");
    return;
  }
  const botToken = telegramBotToken.value.trim();
  const expectedUser = telegramExpectedUser.value.trim();
  if (!botToken && !expectedUser) {
    setNotice("Informe o token do bot ou o usuário esperado.");
    return;
  }
  if (botToken && !window.confirm(`Salvar token do Telegram em ${title(instance)} e reiniciar o container?`)) return;

  saveTelegramConfig.disabled = true;
  refreshAll.disabled = true;
  setNotice(`Atualizando Telegram em ${title(instance)}...`);
  try {
    await apiJsonPost(`/api/instances/${encodeURIComponent(instance)}/channels/telegram/config`, {
      botToken,
      expectedUser,
    });
    telegramBotToken.value = "";
    setNotice(`Configuração do Telegram salva em ${title(instance)}.`);
    window.setTimeout(() => loadStatus(instance), botToken ? 8000 : 1500);
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    saveTelegramConfig.disabled = false;
    refreshAll.disabled = false;
  }
}

async function refreshTelegramStatus() {
  const instance = telegramInstance.value;
  if (!instance) {
    setNotice("Selecione uma instância.");
    return;
  }
  refreshTelegramPairings.disabled = true;
  try {
    const data = await api(`/api/instances/${encodeURIComponent(instance)}/channels/telegram/status`);
    renderTelegramPanel(data);
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    refreshTelegramPairings.disabled = false;
  }
}

async function approveTelegramCode() {
  const instance = telegramInstance.value;
  const code = telegramPairingCode.value.trim();
  if (!instance) {
    setNotice("Selecione uma instância.");
    return;
  }
  if (!code) {
    setNotice("Informe o código de pareamento do Telegram.");
    return;
  }
  approveTelegramPairing.disabled = true;
  setNotice(`Aprovando código Telegram em ${title(instance)}...`);
  try {
    await apiJsonPost(`/api/instances/${encodeURIComponent(instance)}/channels/telegram/pairing/approve`, { code });
    telegramPairingCode.value = "";
    setNotice(`Código Telegram aprovado em ${title(instance)}.`);
    await refreshTelegramStatus();
    window.setTimeout(() => loadStatus(instance), 2500);
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    approveTelegramPairing.disabled = false;
  }
}

async function validateTelegramChannel() {
  const instance = telegramInstance.value;
  if (!instance) {
    setNotice("Selecione uma instância.");
    return;
  }
  await loadStatus(instance);
  const current = state.data?.instances?.find((item) => item.name === instance);
  const telegram = current?.channels?.telegram || {};
  if (channelOk(current || {}, "telegram")) {
    setNotice(`Telegram conectado em ${title(instance)}.`);
  } else if (telegram.configured) {
    setNotice(`Telegram configurado em ${title(instance)}, mas ainda sem usuário aprovado ou probe OK.`);
  } else {
    setNotice(`Telegram ainda não configurado em ${title(instance)}.`);
  }
}

function renderTelegramPanel(data) {
  if (data.expectedUser !== undefined) {
    telegramExpectedUser.value = data.expectedUser || "";
  }
  const pending = Array.isArray(data.pending) ? data.pending : [];
  telegramPairingPanel.classList.remove("hidden");
  telegramPairingPanel.innerHTML = `
    <div class="oauth-status">
      <strong>${data.configured ? "Bot configurado" : "Bot não configurado"}</strong>
      ${data.expectedUser ? `<span>Usuário esperado: ${escapeHtml(data.expectedUser)}</span>` : ""}
    </div>
    ${
      pending.length
        ? `<div class="pending-list">${pending.map(renderTelegramPending).join("")}</div>`
        : '<div class="empty-state">Nenhum pareamento Telegram pendente.</div>'
    }
    ${data.output ? `<pre>${escapeHtml(data.output)}</pre>` : ""}
  `;
  telegramPairingPanel.querySelectorAll("[data-telegram-code]").forEach((button) => {
    button.addEventListener("click", () => {
      telegramPairingCode.value = button.dataset.telegramCode;
      approveTelegramCode();
    });
  });
}

function renderTelegramPending(item) {
  const code = item.code || item.pairingCode || item.id || item.requestId || "";
  const user = item.userId || item.senderId || item.fromId || item.chatId || item.user || "";
  const label = code || JSON.stringify(item);
  return `
    <div class="pending-item">
      <div>
        <strong>${escapeHtml(code || "Código pendente")}</strong>
        <span>${escapeHtml(user || "Telegram")}</span>
      </div>
      <code>${escapeHtml(label)}</code>
      <small>${escapeHtml(item.createdAt || item.ts || item.age || "")}</small>
      ${
        code
          ? `<button type="button" data-telegram-code="${escapeAttribute(code)}">Aprovar</button>`
          : ""
      }
    </div>
  `;
}

async function startWhatsAppPairing() {
  const instance = whatsappInstance.value;
  if (!instance) {
    setNotice("Selecione uma instância.");
    return;
  }
  const number = whatsappNumber.value.trim();
  const target = number ? ` para ${number}` : "";
  if (!window.confirm(`Iniciar pareamento do WhatsApp${target} em ${title(instance)}?`)) return;

  startWhatsappLogin.disabled = true;
  refreshWhatsappLogin.disabled = true;
  setNotice(`Iniciando pareamento do WhatsApp em ${title(instance)}...`);
  try {
    await apiPost(`/api/instances/${encodeURIComponent(instance)}/channels/whatsapp/login-start`);
    setNotice(`Pareamento iniciado em ${title(instance)}. Escaneie o QR Code exibido abaixo.`);
    await refreshWhatsAppPairing();
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    startWhatsappLogin.disabled = false;
    refreshWhatsappLogin.disabled = false;
  }
}

async function saveWhatsAppNumber() {
  const instance = whatsappInstance.value;
  if (!instance) {
    setNotice("Selecione uma instância.");
    return;
  }
  const number = whatsappNumber.value.trim();
  saveWhatsappNumber.disabled = true;
  try {
    await apiJsonPost(`/api/instances/${encodeURIComponent(instance)}/channels/whatsapp/number`, { number });
    setNotice(number ? `Número esperado salvo para ${title(instance)}.` : `Número esperado removido de ${title(instance)}.`);
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    saveWhatsappNumber.disabled = false;
  }
}

async function refreshWhatsAppPairing() {
  const instance = whatsappInstance.value;
  if (!instance) {
    setNotice("Selecione uma instância.");
    return;
  }
  refreshWhatsappLogin.disabled = true;
  try {
    const [login, pairing] = await Promise.all([
      api(`/api/instances/${encodeURIComponent(instance)}/channels/whatsapp/login-status`),
      api(`/api/instances/${encodeURIComponent(instance)}/channels/whatsapp/pairing/status`),
    ]);
    renderWhatsAppPanel({ ...login, pairing });
    if (login.exitCode === 0) {
      setNotice(`Pareamento do WhatsApp concluído em ${title(instance)}.`);
      window.setTimeout(() => loadStatus(instance), 2500);
    }
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    refreshWhatsappLogin.disabled = false;
  }
}

async function approveWhatsAppCode() {
  const instance = whatsappInstance.value;
  const code = whatsappPairingCode.value.trim();
  if (!instance) {
    setNotice("Selecione uma instância.");
    return;
  }
  if (!code) {
    setNotice("Informe o código de pareamento do WhatsApp.");
    return;
  }
  approveWhatsappPairing.disabled = true;
  setNotice(`Aprovando código WhatsApp em ${title(instance)}...`);
  try {
    await apiJsonPost(`/api/instances/${encodeURIComponent(instance)}/channels/whatsapp/pairing/approve`, { code });
    whatsappPairingCode.value = "";
    setNotice(`Código WhatsApp aprovado em ${title(instance)}.`);
    await refreshWhatsAppPairing();
    window.setTimeout(() => loadStatus(instance), 2500);
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    approveWhatsappPairing.disabled = false;
  }
}

async function validateWhatsApp() {
  const instance = whatsappInstance.value;
  if (!instance) {
    setNotice("Selecione uma instância.");
    return;
  }
  await loadStatus(instance);
  const current = state.data?.instances?.find((item) => item.name === instance);
  const whatsapp = current?.channels?.whatsapp || {};
  if (channelOk(current || {}, "whatsapp")) {
    setNotice(`WhatsApp conectado em ${title(instance)}.`);
  } else if (whatsapp.configured) {
    setNotice(`WhatsApp configurado em ${title(instance)}, mas ainda não conectado.`);
  } else {
    setNotice(`WhatsApp ainda não configurado em ${title(instance)}.`);
  }
}

function renderWhatsAppPanel(data) {
  const status = data.running ? "Aguardando leitura do QR Code" : data.exitCode === 0 ? "Concluído" : "Parado";
  const log = data.log || "Nenhum pareamento de WhatsApp iniciado nesta instância.";
  const pending = Array.isArray(data.pairing?.pending) ? data.pairing.pending : [];
  const deliveryAlert = renderWhatsAppDeliveryAlert(data.deliveryAlert);
  if (data.number !== undefined) {
    whatsappNumber.value = data.number || "";
  }
  whatsappLoginPanel.classList.remove("hidden");
  whatsappLoginPanel.innerHTML = `
    <div class="oauth-status">
      <strong>${escapeHtml(status)}</strong>
      <span>${data.exitCode === null || data.exitCode === undefined ? "" : `exit ${escapeHtml(data.exitCode)}`}</span>
    </div>
    ${data.number ? `<div class="oauth-status"><strong>Número esperado</strong><span>${escapeHtml(data.number)}</span></div>` : ""}
    <div class="oauth-status">
      <strong>Autorizações WhatsApp</strong>
      <span>${pending.length ? `${pending.length} pendente(s)` : "Nenhuma pendente"}</span>
    </div>
    ${deliveryAlert}
    ${
      pending.length
        ? `<div class="pending-list">${pending.map(renderWhatsAppPending).join("")}</div>`
        : '<div class="empty-state">Nenhum número WhatsApp aguardando autorização.</div>'
    }
    <pre>${escapeHtml(log)}</pre>
  `;
  whatsappLoginPanel.querySelectorAll("[data-whatsapp-code]").forEach((button) => {
    button.addEventListener("click", () => {
      whatsappPairingCode.value = button.dataset.whatsappCode;
      approveWhatsAppCode();
    });
  });
}

function renderWhatsAppDeliveryAlert(alert) {
  if (!alert || alert.kind !== "reachout_timelock") return "";
  const until = formatDateTime(alert.until);
  const target = alert.target ? ` para ${alert.target}` : "";
  const status = alert.active ? "Envio bloqueado temporariamente" : "Bloqueio recente detectado";
  return `
    <div class="timelock-alert">
      <strong>${escapeHtml(status)}</strong>
      <span>
        O WhatsApp está recebendo mensagens, mas o envio de respostas${escapeHtml(target)}
        está bloqueado pela trava de companion device${until ? ` até ${escapeHtml(until)}` : ""}.
      </span>
      <small>${escapeHtml(alert.type || "reachout timelock")}</small>
    </div>
  `;
}

function renderWhatsAppPending(item) {
  const code = item.code || item.pairingCode || item.id || item.requestId || "";
  const phone = item.phone || item.phoneNumber || item.sender || item.senderId || item.from || "";
  const label = code || JSON.stringify(item);
  return `
    <div class="pending-item">
      <div>
        <strong>${escapeHtml(code || "Código pendente")}</strong>
        <span>${escapeHtml(phone || "WhatsApp")}</span>
      </div>
      <code>${escapeHtml(label)}</code>
      <small>${escapeHtml(item.createdAt || item.ts || item.age || "")}</small>
      ${
        code
          ? `<button type="button" data-whatsapp-code="${escapeAttribute(code)}">Aprovar</button>`
          : ""
      }
    </div>
  `;
}

function syncAccessForm() {
  const channel = accessChannel.value;
  const kind = accessKind.value;
  if (channel === "whatsapp" && kind === "contact") {
    accessId.placeholder = "+5541999578125";
  } else if (channel === "whatsapp") {
    accessId.placeholder = "120363000000000000@g.us";
  } else if (kind === "contact") {
    accessId.placeholder = "8831446238";
  } else {
    accessId.placeholder = "-1001234567890";
  }
  if (kind === "group" && accessLevel.value === "admin") {
    accessLevel.value = "chat";
  }
  Array.from(accessLevel.options).forEach((option) => {
    option.disabled = kind === "group" && option.value === "admin";
  });
}

async function loadChannelAccess() {
  const instance = accessInstance.value;
  if (!instance) {
    channelAccessPanel.innerHTML = '<div class="empty-state">Selecione uma instância.</div>';
    return;
  }
  refreshChannelAccess.disabled = true;
  try {
    const data = await api(`/api/instances/${encodeURIComponent(instance)}/access`);
    renderChannelAccess(data.items || []);
  } catch (error) {
    channelAccessPanel.innerHTML = `<div class="empty-state">${escapeHtml(readableError(error))}</div>`;
  } finally {
    refreshChannelAccess.disabled = false;
  }
}

async function saveChannelAccess(event) {
  event.preventDefault();
  const instance = accessInstance.value;
  const payload = {
    channel: accessChannel.value,
    kind: accessKind.value,
    id: accessId.value.trim(),
    label: accessLabel.value.trim(),
    access: accessLevel.value,
  };
  if (!instance || !payload.id) {
    setNotice("Selecione uma instância e informe o identificador do acesso.");
    return;
  }
  if (payload.kind === "group" && payload.access === "admin") {
    setNotice("Acesso admin é permitido apenas para contatos. Grupos ficam como conversa.");
    return;
  }
  const label = payload.label || payload.id;
  if (!window.confirm(`Salvar acesso ${accessText(payload.access)} para ${label} em ${title(instance)}?`)) return;

  const button = document.querySelector("#saveChannelAccess");
  button.disabled = true;
  setNotice(`Salvando acesso em ${title(instance)}...`);
  try {
    const data = await apiJsonPost(`/api/instances/${encodeURIComponent(instance)}/access`, payload);
    accessId.value = "";
    accessLabel.value = "";
    renderChannelAccess(data.items || []);
    setNotice(`Acesso salvo em ${title(instance)}. A instância foi reiniciada para aplicar a política.`);
    window.setTimeout(() => loadStatus(instance), 5000);
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    button.disabled = false;
  }
}

function renderChannelAccess(items) {
  if (!items.length) {
    channelAccessPanel.innerHTML = '<div class="empty-state">Nenhum contato ou grupo liberado nesta instância.</div>';
    return;
  }
  channelAccessPanel.innerHTML = `
    <div class="access-table">
      <table>
        <thead>
          <tr>
            <th>Canal</th>
            <th>Tipo</th>
            <th>Nome</th>
            <th>Identificador</th>
            <th>Acesso</th>
            <th>Origem</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${items.map(renderChannelAccessRow).join("")}
        </tbody>
      </table>
    </div>
  `;
  channelAccessPanel.querySelectorAll("[data-remove-access]").forEach((button) => {
    button.addEventListener("click", () =>
      removeChannelAccess({
        channel: button.dataset.channel,
        kind: button.dataset.kind,
        id: button.dataset.id,
        label: button.dataset.label,
      }),
    );
  });
}

function renderChannelAccessRow(item) {
  return `
    <tr>
      <td>${escapeHtml(channelText(item.channel))}</td>
      <td>${escapeHtml(kindText(item.kind))}</td>
      <td>${escapeHtml(item.label || "-")}</td>
      <td><code>${escapeHtml(item.id)}</code></td>
      <td>${pill(item.access === "admin" ? "warn" : "ok", accessText(item.access))}</td>
      <td>${escapeHtml(sourceText(item.source))}</td>
      <td>
        <button
          type="button"
          class="danger"
          data-remove-access="true"
          data-channel="${escapeAttribute(item.channel)}"
          data-kind="${escapeAttribute(item.kind)}"
          data-id="${escapeAttribute(item.id)}"
          data-label="${escapeAttribute(item.label || item.id)}"
        >Remover</button>
      </td>
    </tr>
  `;
}

async function removeChannelAccess(item) {
  const instance = accessInstance.value;
  if (!instance) return;
  if (!window.confirm(`Remover acesso de ${item.label || item.id} em ${title(instance)}?`)) return;
  setNotice(`Removendo acesso em ${title(instance)}...`);
  try {
    const data = await apiJsonPost(`/api/instances/${encodeURIComponent(instance)}/access/remove`, {
      channel: item.channel,
      kind: item.kind,
      id: item.id,
    });
    renderChannelAccess(data.items || []);
    setNotice(`Acesso removido em ${title(instance)}. A instância foi reiniciada para aplicar a política.`);
    window.setTimeout(() => loadStatus(instance), 5000);
  } catch (error) {
    setNotice(readableError(error));
  }
}

function channelText(value) {
  return value === "telegram" ? "Telegram" : "WhatsApp";
}

function kindText(value) {
  return value === "group" ? "Grupo" : "Contato";
}

function accessText(value) {
  return value === "admin" ? "Admin" : "Conversa";
}

function sourceText(value) {
  if (value === "owner") return "Admin nativo";
  return value === "dashboard" ? "Painel" : "Configuração";
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
  if (channel.deliveryAlert?.active) return pill("warn", "Envio bloqueado");
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

function setTokenStatus(kind, message) {
  tokenStatus.textContent = message;
  tokenStatus.className = `connection-status ${kind}`;
}

function readableError(error) {
  const text = String(error?.message || error);
  if (text.includes("unauthorized")) {
    return "Token administrativo inválido ou ausente.";
  }
  return text;
}

function formatDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    dateStyle: "short",
    timeStyle: "medium",
  });
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
