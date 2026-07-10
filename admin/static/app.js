const state = {
  token: localStorage.getItem("ocesAdminToken") || "",
  loading: false,
  data: null,
  pending: [],
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
const aiConfigForm = document.querySelector("#aiConfigForm");
const aiInstance = document.querySelector("#aiInstance");
const openAiKey = document.querySelector("#openAiKey");
const aiModel = document.querySelector("#aiModel");
const saveOpenAiKey = document.querySelector("#saveOpenAiKey");
const saveAiModel = document.querySelector("#saveAiModel");
const startOpenAiOAuth = document.querySelector("#startOpenAiOAuth");
const refreshOpenAiOAuth = document.querySelector("#refreshOpenAiOAuth");
const openAiOAuthPanel = document.querySelector("#openAiOAuthPanel");
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

tokenInput.value = state.token;

saveToken.addEventListener("click", () => {
  state.token = tokenInput.value.trim();
  localStorage.setItem("ocesAdminToken", state.token);
  loadStatus();
});

refreshAll.addEventListener("click", () => loadStatus());
refreshPending.addEventListener("click", () => loadPendingAccess());
createInstanceForm.addEventListener("submit", createInstance);
saveOpenAiKey.addEventListener("click", configureOpenAiKey);
saveAiModel.addEventListener("click", configureAiModel);
startOpenAiOAuth.addEventListener("click", startOAuthLogin);
refreshOpenAiOAuth.addEventListener("click", refreshOAuthLogin);
aiConfigForm.addEventListener("submit", (event) => event.preventDefault());
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
    loadPendingAccess();
  } catch (error) {
    setNotice(readableError(error));
  } finally {
    state.loading = false;
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
  fillAiInstances(instances);
  fillTelegramInstances(instances);
  fillWhatsAppInstances(instances);

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

function fillWhatsAppInstances(instances) {
  const selected = whatsappInstance.value;
  whatsappInstance.innerHTML = instances
    .map((item) => `<option value="${escapeAttribute(item.name)}">${escapeHtml(title(item.name))}</option>`)
    .join("");
  if (instances.some((item) => item.name === selected)) {
    whatsappInstance.value = selected;
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
