const api = {
  async request(path, options = {}) {
    const { timeout = 25000, ...fetchOptions } = options;
    const method = (fetchOptions.method || "GET").toUpperCase();
    const isRetryable = method === "GET";
    const backoffs = [400, 1000];
    const maxAttempts = isRetryable ? backoffs.length + 1 : 1;
    const retryableStatuses = new Set([502, 503, 504]);
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

    let lastError = null;

    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeout);
      let response;

      try {
        response = await fetch(path, {
          headers: { "Content-Type": "application/json", ...(fetchOptions.headers || {}) },
          ...fetchOptions,
          signal: controller.signal,
        });
      } catch (error) {
        clearTimeout(timer);
        // AbortError => timeout; TypeError ("Failed to fetch") => network down.
        const isTimeout = error && (error.name === "AbortError" || error.code === 20);
        lastError = new Error(
          isTimeout
            ? "Tempo de resposta esgotado. Tente novamente."
            : "Sem conexão com o servidor. Verifique sua internet ou tente novamente.",
        );
        if (isRetryable && attempt < maxAttempts - 1) {
          await sleep(backoffs[attempt]);
          continue;
        }
        throw lastError;
      }

      clearTimeout(timer);

      // Retry transient server errors for GET only.
      if (isRetryable && retryableStatuses.has(response.status) && attempt < maxAttempts - 1) {
        lastError = new Error("Sem conexão com o servidor. Verifique sua internet ou tente novamente.");
        await sleep(backoffs[attempt]);
        continue;
      }

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.detail || "Não foi possível concluir a operação");
      }
      return payload;
    }

    throw lastError || new Error("Não foi possível concluir a operação");
  },
};

const state = {
  view: "overview",
  health: null,
  dashboard: null,
  contacts: [],
  events: [],
  eventFilter: "all",
  labSession: null,
};

const viewMeta = {
  overview: ["CENTRAL OPERACIONAL", "Visão geral"],
  conversations: ["RELACIONAMENTO", "Conversas"],
  lab: ["AMBIENTE SEGURO", "Laboratório"],
  flows: ["AUTOMAÇÃO", "Fluxos inteligentes"],
  personality: ["COMPORTAMENTO", "Personalidade"],
  instances: ["CONEXÃO", "Instâncias"],
  integrations: ["INFRAESTRUTURA", "Integrações"],
  events: ["OBSERVABILIDADE", "Registros"],
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function setText(selector, value) {
  const element = $(selector);
  if (element) element.textContent = value;
}

function initials(name = "") {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase() || "—";
}

function formatDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function toast(message, type = "info") {
  const item = document.createElement("div");
  item.className = `toast ${type}`;
  item.textContent = message;
  $("#toast-region").append(item);
  setTimeout(() => item.remove(), 4200);
}

function openView(view, pushHistory = true) {
  if (!viewMeta[view]) return;
  state.view = view;
  $$("[data-view]").forEach((section) => {
    const active = section.dataset.view === view;
    section.hidden = !active;
    section.classList.toggle("is-visible", active);
  });
  $$(".nav-item").forEach((item) => {
    item.classList.toggle("is-active", item.dataset.viewTarget === view);
  });
  setText("#view-eyebrow", viewMeta[view][0]);
  setText("#view-title", viewMeta[view][1]);
  if (pushHistory) history.replaceState({}, "", `#${view}`);
  refreshCurrentView();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function refreshCurrentView() {
  const loaders = {
    overview: loadOverview,
    conversations: loadContacts,
    flows: loadFlows,
    personality: loadSettings,
    instances: loadInstances,
    integrations: loadIntegrations,
    events: loadEvents,
  };
  if (loaders[state.view]) {
    try {
      await loaders[state.view]();
    } catch (error) {
      toast(error.message, "error");
    }
  }
}

function applyHealth(health) {
  state.health = health;
  const readyCount = [health.ai_configured, health.whatsapp_configured, health.database].filter(Boolean).length;
  setText("#health-score", `${readyCount}/3`);
  const mappings = [
    ["#health-ai", health.ai_configured],
    ["#health-whatsapp", health.whatsapp_configured],
    ["#health-database", health.database],
  ];
  mappings.forEach(([selector, ready]) => {
    const element = $(selector);
    element.textContent = ready ? "pronto" : "pendente";
    element.className = ready ? "ok" : "bad";
  });
  [
    ["#integration-ai", health.ai_configured],
    ["#integration-whatsapp", health.whatsapp_configured],
    ["#integration-database", health.database],
  ].forEach(([selector, ready]) => {
    const element = $(selector);
    element.textContent = ready ? "Configurado" : "Pendente";
    element.classList.toggle("ok", ready);
  });
  const dot = $("#sidebar-status-dot");
  dot.classList.toggle("ready", health.status === "ready");
  setText("#sidebar-status-title", health.status === "ready" ? "Sistema pronto" : "Configuração parcial");
  setText("#sidebar-status-copy", health.status === "ready" ? "Todos os serviços ativos" : `${readyCount} de 3 serviços prontos`);

  // Render connected WhatsApp numbers
  const card = $("#connected-numbers-card");
  const list = $("#connected-numbers-list");
  if (card && list) {
    if (health.whatsapp_configured && health.whatsapp_details) {
      card.style.display = "block";
      const details = health.whatsapp_details;
      list.innerHTML = `
        <div class="connected-number-row" style="display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; background: var(--surface-2); border: 1px solid var(--line); border-radius: 9px;">
          <div style="display: flex; align-items: center; gap: 12px;">
            <span style="font-size: 20px;">📞</span>
            <div>
              <strong style="display: block; font-size: 13px; color: var(--text);">${details.verified_name || 'WhatsApp Business Account'}</strong>
              <small style="display: block; font-size: 11px; color: var(--faint); font-family: var(--font-mono);">${details.display_phone_number || details.id || ''}</small>
            </div>
          </div>
          <span class="integration-state ok" style="font-size: 9px; font-family: var(--font-mono); text-transform: uppercase;">Conectado</span>
        </div>
      `;
    } else if (health.whatsapp_configured) {
      card.style.display = "block";
      list.innerHTML = `
        <div class="connected-number-row" style="display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; background: var(--surface-2); border: 1px solid var(--line); border-radius: 9px;">
          <div style="display: flex; align-items: center; gap: 12px;">
            <span style="font-size: 20px;">📞</span>
            <div>
              <strong style="display: block; font-size: 13px; color: var(--text);">WhatsApp Cloud API</strong>
              <small style="display: block; font-size: 11px; color: var(--faint); font-family: var(--font-mono);">Credenciais ativas, dados do número não sincronizados</small>
            </div>
          </div>
          <span class="integration-state ok" style="font-size: 9px; font-family: var(--font-mono); text-transform: uppercase;">Conectado</span>
        </div>
      `;
    } else {
      card.style.display = "none";
      list.innerHTML = "";
    }
  }
}

async function loadHealth() {
  const health = await api.request("/api/health");
  applyHealth(health);
}

async function loadIntegrations() {
  await loadHealth();
  try {
    const settings = await api.request("/api/settings");
    state.settings = settings;
    const field = $("#openai-key-form")?.elements?.openai_api_key;
    if (field) field.value = settings.openai_api_key || "";
    setText(
      "#openai-key-status",
      settings.openai_api_key
        ? "Chave configurada no servidor."
        : "Nenhuma chave salva — usando variável de ambiente, se houver.",
    );
  } catch (error) {
    // health already rendered; surface key load issues quietly
    setText("#openai-key-status", "Não foi possível carregar a chave atual.");
  }
}

async function saveOpenAiKey(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('[type="submit"]');
  button.disabled = true;
  setText("#openai-key-status", "Salvando chave…");
  const openai_api_key = form.elements.openai_api_key.value.trim();
  if (!state.settings) {
    try {
      state.settings = await api.request("/api/settings");
    } catch (err) {
      state.settings = {};
    }
  }
  const payload = { ...state.settings, openai_api_key };
  try {
    const saved = await api.request("/api/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    state.settings = saved;
    toast("Chave da OpenAI salva. Vale para a próxima mensagem.");
    await loadHealth();
    setText(
      "#openai-key-status",
      saved.openai_api_key ? "Chave configurada no servidor." : "Chave removida.",
    );
  } catch (error) {
    setText("#openai-key-status", error.message);
    toast(error.message, "error");
  } finally {
    button.disabled = false;
  }
}

function renderActivity(events) {
  const container = $("#overview-activity");
  container.replaceChildren();
  if (!events.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state compact";
    empty.textContent = "Nenhuma atividade registrada.";
    container.append(empty);
    return;
  }
  events.slice(0, 4).forEach((event) => {
    const row = document.createElement("div");
    row.className = "activity-item";
    const dot = document.createElement("i");
    dot.className = event.level;
    const copy = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = event.message;
    const category = document.createElement("small");
    category.textContent = event.category;
    copy.append(title, category);
    const time = document.createElement("time");
    time.textContent = formatDate(event.created_at);
    row.append(dot, copy, time);
    container.append(row);
  });
}

async function loadOverview() {
  const [dashboard, health, events] = await Promise.all([
    api.request("/api/dashboard"),
    api.request("/api/health"),
    api.request("/api/events?limit=4"),
  ]);
  state.dashboard = dashboard;
  state.events = events;
  setText("#metric-contacts", dashboard.contacts);
  setText("#metric-conversations", dashboard.open_conversations);
  setText("#metric-messages", dashboard.messages);
  setText("#metric-failures", dashboard.failures);
  setText("#nav-conversation-count", dashboard.open_conversations);
  applyHealth(health);
  renderActivity(events);
}

function renderContacts(filter = "") {
  const container = $("#contact-list");
  const term = filter.trim().toLowerCase();
  const contacts = state.contacts.filter((contact) =>
    [contact.name, contact.phone].some((value) => String(value || "").toLowerCase().includes(term))
  );
  container.replaceChildren();
  if (!contacts.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state compact";
    empty.textContent = term ? "Nenhum contato encontrado." : "Nenhum contato registrado.";
    container.append(empty);
    return;
  }
  contacts.forEach((contact) => {
    const button = document.createElement("button");
    button.className = "contact-row";
    button.dataset.contactId = contact.id;
    const avatar = document.createElement("span");
    avatar.className = "avatar";
    avatar.textContent = initials(contact.name || contact.phone);
    const copy = document.createElement("span");
    copy.className = "contact-copy";
    const name = document.createElement("strong");
    name.textContent = contact.name || contact.phone;
    const preview = document.createElement("small");
    preview.textContent = contact.summary || contact.phone;
    copy.append(name, preview);
    const time = document.createElement("time");
    time.textContent = formatDate(contact.updated_at);
    button.append(avatar, copy, time);
    button.addEventListener("click", () => selectContact(contact, button));
    container.append(button);
  });
}

async function loadContacts() {
  state.contacts = await api.request("/api/contacts");
  renderContacts($("#contact-search").value);
}

async function selectContact(contact, row) {
  $$(".contact-row").forEach((item) => item.classList.remove("is-active"));
  row.classList.add("is-active");
  setText("#chat-avatar", initials(contact.name || contact.phone));
  setText("#chat-contact-name", contact.name || contact.phone);
  setText("#chat-contact-phone", contact.phone);
  const detail = await api.request(`/api/contacts/${contact.id}`);
  setText("#context-interest", (detail.interest || "indefinido").toUpperCase());
  setText("#context-summary", detail.summary || "Sem resumo disponível.");
  setText("#context-next-action", detail.next_action || "Nenhum próximo passo definido.");
  renderMemories(detail.memories || []);
  const stream = $("#message-stream");
  stream.replaceChildren();
  if (!contact.conversation_id) {
    renderEmptyMessages(stream);
    return;
  }
  const messages = await api.request(`/api/conversations/${contact.conversation_id}/messages`);
  if (!messages.length) {
    renderEmptyMessages(stream);
    return;
  }
  messages.forEach((message) => appendMessage(stream, message.role, message.text, message.created_at));
  stream.scrollTop = stream.scrollHeight;
}

function renderEmptyMessages(container) {
  const empty = document.createElement("div");
  empty.className = "empty-state";
  const title = document.createElement("strong");
  title.textContent = "Conversa sem mensagens";
  const copy = document.createElement("span");
  copy.textContent = "O histórico aparecerá após a primeira interação.";
  empty.append(title, copy);
  container.append(empty);
}

function renderMemories(memories) {
  const container = $("#context-memories");
  container.replaceChildren();
  if (!memories.length) {
    const empty = document.createElement("small");
    empty.textContent = "Nenhum fato confirmado.";
    container.append(empty);
    return;
  }
  memories.forEach((memory) => {
    const chip = document.createElement("span");
    chip.className = "memory-chip";
    chip.textContent = `${memory.key}: ${memory.value}`;
    container.append(chip);
  });
}

function appendMessage(container, role, text, createdAt = new Date().toISOString()) {
  const bubble = document.createElement("article");
  bubble.className = `message ${role === "assistant" ? "assistant" : "user"}`;
  
  const copy = document.createElement("p");
  
  const mediaRegex = /^\[(Imagem|Documento|Vídeo|Áudio)\]\s*(https?:\/\/[^\s|]+|\/[^\s|]+)(?:\s*\|\s*(.*))?$/i;
  const match = text.match(mediaRegex);
  
  if (match) {
    const type = match[1].toLowerCase();
    const url = match[2].trim();
    const caption = match[3] ? match[3].trim() : "";
    
    if (caption) {
      copy.textContent = caption;
    } else {
      copy.style.display = "none";
    }
    
    const mediaDiv = document.createElement("div");
    mediaDiv.className = "chat-media-container";
    
    if (type === "imagem") {
      const img = document.createElement("img");
      img.src = url;
      img.alt = "Imagem enviada";
      img.loading = "lazy";
      mediaDiv.append(img);
      bubble.append(mediaDiv);
    } else if (type === "vídeo" || type === "video") {
      const video = document.createElement("video");
      video.src = url;
      video.controls = true;
      mediaDiv.append(video);
      bubble.append(mediaDiv);
    } else if (type === "áudio" || type === "audio") {
      const audio = document.createElement("audio");
      audio.src = url;
      audio.controls = true;
      mediaDiv.append(audio);
      bubble.append(mediaDiv);
    } else if (type === "documento") {
      const docLink = document.createElement("a");
      docLink.href = url;
      docLink.target = "_blank";
      docLink.className = "chat-media-doc-link";
      docLink.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
        </svg>
        <span>Visualizar Documento</span>
      `;
      bubble.append(docLink);
    }
  } else {
    copy.textContent = text;
  }
  
  bubble.append(copy);
  
  const footer = document.createElement("footer");
  footer.textContent = formatDate(createdAt);
  bubble.append(footer);
  container.append(bubble);
}

function updatePromptOverrideBanner(form) {
  const systemPromptField = form.elements.namedItem("system_prompt");
  const banner = document.getElementById("prompt-override-banner");
  if (!systemPromptField || !banner) return;
  const hasCustomPrompt = systemPromptField.value.trim().length > 0;
  banner.hidden = !hasCustomPrompt;
}

function fillSettings(settings) {
  state.settings = settings;
  const form = $("#settings-form");
  Object.entries(settings).forEach(([key, value]) => {
    const field = form.elements.namedItem(key);
    if (!field) return;
    if (field.type === "checkbox") field.checked = Boolean(value);
    else if (Array.isArray(value)) field.value = value.join(", ");
    else field.value = value ?? "";
  });
  setText("#initiative-output", settings.commercial_initiative);
  setText("#settings-save-status", "Configuração sincronizada com o servidor.");
  updatePromptOverrideBanner(form);
}

async function loadSettings() {
  fillSettings(await api.request("/api/settings"));
}

function settingsPayload(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  return {
    ...data,
    commercial_initiative: Number(data.commercial_initiative),
    max_questions: Number(data.max_questions),
    typo_probability: Number(data.typo_probability),
    split_messages: form.elements.split_messages.checked,
    preferred_terms: data.preferred_terms.split(",").map((item) => item.trim()).filter(Boolean),
    forbidden_terms: data.forbidden_terms.split(",").map((item) => item.trim()).filter(Boolean),
  };
}

async function saveSettings(event) {
  event.preventDefault();
  const button = event.currentTarget.querySelector('[type="submit"]');
  button.disabled = true;
  setText("#settings-save-status", "Salvando alterações…");
  
  if (!state.settings) {
    try {
      state.settings = await api.request("/api/settings");
    } catch (err) {
      state.settings = {};
    }
  }
  
  const payload = {
    ...state.settings,
    ...settingsPayload(event.currentTarget)
  };
  
  try {
    const saved = await api.request("/api/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    fillSettings(saved);
    toast("Personalidade salva e disponível para a próxima mensagem.");
  } catch (error) {
    setText("#settings-save-status", error.message);
    toast(error.message, "error");
  } finally {
    button.disabled = false;
  }
}

async function ensureLabSession() {
  if (state.labSession) return state.labSession;
  const name = $("#lab-profile-name").value.trim() || "Lead de demonstração";
  state.labSession = await api.request("/api/lab/sessions", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
  setText("#lab-session-status", `Sessão ${state.labSession.id.slice(0, 8)} ativa`);
  return state.labSession;
}

function renderInspection(result) {
  setText("#inspection-draft", result.draft || "Nenhum rascunho retornado.");
  const evaluation = $("#inspection-evaluation");
  evaluation.replaceChildren();
  const scores = ["naturalness", "relevance", "concision", "coherence", "repetition"];
  const available = scores.filter((key) => Number.isFinite(result.evaluation?.[key]));
  if (!available.length) {
    const empty = document.createElement("small");
    empty.textContent = result.evaluation?.approved ? "Resposta aprovada." : "Sem pontuações disponíveis.";
    evaluation.append(empty);
  } else {
    available.forEach((key) => {
      const row = document.createElement("div");
      row.className = "score-row";
      const label = document.createElement("span");
      label.textContent = key;
      const score = document.createElement("strong");
      score.textContent = `${result.evaluation[key]}/10`;
      row.append(label, score);
      evaluation.append(row);
    });
  }
  const delivery = $("#inspection-delivery");
  delivery.replaceChildren();
  result.messages.forEach((message, index) => {
    const row = document.createElement("div");
    row.className = "delivery-row";
    row.textContent = `${index + 1}. ${message}`;
    delivery.append(row);
  });
}

async function sendLabMessage(event) {
  event.preventDefault();
  const input = $("#lab-input");
  const text = input.value.trim();
  if (!text) return;
  const button = event.currentTarget.querySelector("button");
  button.disabled = true;
  const stream = $("#lab-stream");
  if ($(".empty-state", stream)) stream.replaceChildren();
  appendMessage(stream, "user", text);
  input.value = "";
  stream.scrollTop = stream.scrollHeight;
  try {
    const session = await ensureLabSession();
    const result = await api.request(`/api/lab/sessions/${session.id}/messages`, {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    result.messages.forEach((message) => appendMessage(stream, "assistant", message));
    renderInspection(result);
    stream.scrollTop = stream.scrollHeight;
  } catch (error) {
    toast(error.message, "error");
    const notice = document.createElement("div");
    notice.className = "toast error";
    notice.textContent = error.message;
    stream.append(notice);
  } finally {
    button.disabled = false;
    input.focus();
  }
}

async function resetLab() {
  if (state.labSession) {
    await api.request(`/api/lab/sessions/${state.labSession.id}`, { method: "DELETE" }).catch(() => {});
  }
  state.labSession = null;
  setText("#lab-session-status", "Sessão ainda não iniciada");
  $("#lab-stream").innerHTML = '<div class="empty-state"><strong>Nova sessão pronta</strong><span>Envie uma mensagem para começar.</span></div>';
  setText("#inspection-draft", "O rascunho aparecerá após uma resposta.");
  $("#inspection-evaluation").innerHTML = "<small>Sem avaliação disponível.</small>";
  $("#inspection-delivery").innerHTML = "<small>Nenhuma mensagem gerada.</small>";
}

function renderEvents() {
  const container = $("#event-table");
  const events = state.eventFilter === "all"
    ? state.events
    : state.events.filter((event) => event.level === state.eventFilter);
  container.replaceChildren();
  if (!events.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "Nenhum evento neste filtro.";
    container.append(empty);
    return;
  }
  events.forEach((event) => {
    const row = document.createElement("div");
    row.className = "event-row";
    const level = document.createElement("span");
    level.className = `event-level ${event.level}`;
    level.textContent = event.level;
    const category = document.createElement("span");
    category.className = "event-category";
    category.textContent = event.category;
    const message = document.createElement("span");
    message.textContent = event.message;
    const time = document.createElement("time");
    time.textContent = formatDate(event.created_at);
    row.append(level, category, message, time);
    container.append(row);
  });
}

async function loadEvents() {
  state.events = await api.request("/api/events?limit=200");
  renderEvents();
}

/* ============================================================
   FLUXOS CONTROLLER LOGIC
   ============================================================ */

async function loadFlows() {
  const container = $("#flows-list");
  container.innerHTML = '<div class="loading-state">Carregando fluxos…</div>';
  try {
    const flows = await api.request("/api/flows");
    renderFlows(flows);
  } catch (error) {
    toast(error.message, "error");
    container.innerHTML = `<div class="empty-state"><strong>Erro ao carregar</strong><span>${error.message}</span></div>`;
  }
}

function renderFlows(flows) {
  const container = $("#flows-list");
  container.replaceChildren();
  if (!flows.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = `
      <span class="empty-icon">🥞</span>
      <strong>Nenhum fluxo criado</strong>
      <span>Use o construtor para criar o seu primeiro fluxo inteligente.</span>
    `;
    container.append(empty);
    return;
  }
  flows.forEach((flow) => {
    const card = document.createElement("article");
    card.className = "flow-card";
    
    const header = document.createElement("div");
    header.className = "flow-card-header";
    
    const titleInfo = document.createElement("div");
    const name = document.createElement("h3");
    name.textContent = flow.name;
    const stepsCount = document.createElement("span");
    stepsCount.className = "flow-card-steps-count";
    stepsCount.innerHTML = `🥞 ${flow.steps.length} ${flow.steps.length === 1 ? 'passo' : 'passos'}`;
    titleInfo.append(name, stepsCount);
    
    const actions = document.createElement("div");
    actions.className = "flow-card-actions";
    
    const editBtn = document.createElement("button");
    editBtn.className = "button button-quiet button-small";
    editBtn.textContent = "Editar";
    editBtn.addEventListener("click", () => editFlow(flow));
    
    const delBtn = document.createElement("button");
    delBtn.className = "button button-quiet button-small";
    delBtn.style.color = "var(--danger)";
    delBtn.textContent = "Excluir";
    delBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteFlow(flow.id);
    });
    
    actions.append(editBtn, delBtn);
    header.append(titleInfo, actions);
    
    const trigger = document.createElement("div");
    trigger.className = "flow-card-trigger";
    trigger.textContent = `IA ativa em: "${flow.trigger_intent}"`;
    
    card.append(header, trigger);
    container.append(card);
  });
}

function editFlow(flow) {
  openFlowModal(flow);
}

function openFlowModal(flow = null) {
  const modal = $("#flow-modal");
  const form = $("#flow-form");
  form.reset();
  $("#steps-container").replaceChildren();
  
  if (flow) {
    $("#flow-id").value = flow.id;
    $("#flow-name").value = flow.name;
    $("#flow-trigger").value = flow.trigger_intent;
    $(".modal-header h3", modal).textContent = "Editar fluxo inteligente";
    
    if (flow.steps && flow.steps.length) {
      flow.steps.forEach(step => addStepRow(step));
    } else {
      renderEmptyStepsMessage();
    }
  } else {
    $("#flow-id").value = "";
    $(".modal-header h3", modal).textContent = "Novo fluxo inteligente";
    renderEmptyStepsMessage();
  }
  
  modal.classList.remove("hidden");
}

function closeFlowModal() {
  $("#flow-modal").classList.add("hidden");
}

function renderEmptyStepsMessage() {
  const container = $("#steps-container");
  container.replaceChildren();
  const empty = document.createElement("div");
  empty.className = "empty-steps-state";
  empty.id = "empty-steps-message";
  empty.innerHTML = '<span class="empty-icon">🥞</span><p>Nenhum passo adicionado ainda.</p>';
  container.append(empty);
}

function addStepRow(step = null) {
  const container = $("#steps-container");
  const emptyMsg = $("#empty-steps-message");
  if (emptyMsg) emptyMsg.remove();
  
  const stepIndex = container.children.length + 1;
  const row = document.createElement("div");
  row.className = "step-row";
  
  const header = document.createElement("div");
  header.className = "step-row-header";
  
  const badge = document.createElement("span");
  badge.className = "step-number-badge";
  badge.textContent = `PASSO ${stepIndex}`;
  
  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "step-delete-btn";
  deleteBtn.textContent = "×";
  deleteBtn.addEventListener("click", () => {
    row.remove();
    reindexSteps();
  });
  
  header.append(badge, deleteBtn);
  
  const inputsGrid = document.createElement("div");
  inputsGrid.className = "step-inputs-grid";
  
  const selectLabel = document.createElement("label");
  selectLabel.innerHTML = '<span>TIPO DE CONTEÚDO *</span>';
  const select = document.createElement("select");
  select.className = "step-type-select";
  select.required = true;
  
  const types = [
    { value: "text", label: "Mensagem de texto" },
    { value: "image", label: "Imagem ou foto" },
    { value: "document", label: "Documento" },
    { value: "video", label: "Vídeo" },
    { value: "audio", label: "Áudio" }
  ];
  types.forEach(t => {
    const opt = document.createElement("option");
    opt.value = t.value;
    opt.textContent = t.label;
    select.append(opt);
  });
  selectLabel.append(select);
  
  const fieldsWrapper = document.createElement("div");
  fieldsWrapper.className = "step-fields-wrapper";
  
  function updateFields(type, initialVal = {}) {
    fieldsWrapper.replaceChildren();
    if (type === "text") {
      const textareaLabel = document.createElement("label");
      textareaLabel.innerHTML = '<span>MENSAGEM *</span>';
      const textarea = document.createElement("textarea");
      textarea.className = "step-text-input";
      textarea.rows = 3;
      textarea.placeholder = "Escreva o texto do passo aqui...";
      textarea.required = true;
      textarea.value = initialVal.text || "";
      textareaLabel.append(textarea);
      fieldsWrapper.append(textareaLabel);
    } else {
      const uploadWrapper = document.createElement("div");
      uploadWrapper.className = "media-upload-wrapper";
      
      const dropZone = document.createElement("div");
      dropZone.className = "media-drop-zone";
      
      const typeLabels = {
        image: { icon: "🖼️", name: "imagem" },
        document: { icon: "📄", name: "documento" },
        video: { icon: "🎥", name: "vídeo" },
        audio: { icon: "🎵", name: "áudio" }
      };
      const info = typeLabels[type] || { icon: "📁", name: "arquivo" };
      
      dropZone.innerHTML = `
        <span class="upload-icon">${info.icon}</span>
        <span class="upload-text">Arraste uma ${info.name} ou <strong>clique para escolher</strong></span>
        <span class="upload-filename">Nenhum arquivo enviado</span>
        <input type="file" class="step-file-input" style="display: none;">
      `;
      
      const fileInput = $(".step-file-input", dropZone);
      fileInput.accept = { image: "image/*", video: "video/*", audio: "audio/*" }[type] || "*/*";
      
      const filenameLabel = $(".upload-filename", dropZone);
      
      const urlInput = document.createElement("input");
      urlInput.type = "hidden";
      urlInput.className = "step-url-input";
      urlInput.value = initialVal.media_url || "";
      
      if (initialVal.media_url) {
        dropZone.classList.add("success");
        filenameLabel.textContent = initialVal.media_url.split("/").pop();
      }
      
      dropZone.addEventListener("click", (e) => {
        if (e.target !== fileInput) {
          fileInput.click();
        }
      });
      
      dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
      });
      
      dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("dragover");
      });
      
      dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length) {
          handleUpload(e.dataTransfer.files[0]);
        }
      });
      
      fileInput.addEventListener("change", (e) => {
        if (e.target.files.length) {
          handleUpload(e.target.files[0]);
        }
      });
      
      async function handleUpload(file) {
        dropZone.classList.remove("success");
        dropZone.classList.add("loading");
        filenameLabel.textContent = "Enviando arquivo...";
        
        const formData = new FormData();
        formData.append("file", file);
        
        try {
          const response = await fetch("/api/upload", {
            method: "POST",
            body: formData
          });
          const result = await response.json();
          if (!response.ok) throw new Error(result.detail || "Falha no envio");
          
          urlInput.value = result.url;
          dropZone.classList.remove("loading");
          dropZone.classList.add("success");
          filenameLabel.textContent = `Enviado: ${result.filename}`;
          toast(`Upload de ${result.filename} concluído!`);
        } catch (err) {
          dropZone.classList.remove("loading");
          filenameLabel.textContent = "Erro no envio. Tente novamente.";
          toast(err.message, "error");
        }
      }
      
      uploadWrapper.append(dropZone, urlInput);
      
      const captionLabel = document.createElement("label");
      captionLabel.innerHTML = '<span>LEGENDA / DESCRIÇÃO (OPCIONAL)</span>';
      const captionInput = document.createElement("input");
      captionInput.type = "text";
      captionInput.className = "step-text-input";
      captionInput.placeholder = "Digite uma legenda se quiser...";
      captionInput.value = initialVal.text || "";
      captionLabel.append(captionInput);
      
      fieldsWrapper.append(uploadWrapper, captionLabel);
    }

  }
  
  select.addEventListener("change", (e) => {
    updateFields(e.target.value);
  });
  
  inputsGrid.append(selectLabel, fieldsWrapper);
  row.append(header, inputsGrid);
  container.append(row);
  
  if (step) {
    select.value = step.type;
    updateFields(step.type, step);
  } else {
    updateFields("text");
  }
}

function reindexSteps() {
  const container = $("#steps-container");
  if (!container.children.length) {
    renderEmptyStepsMessage();
    return;
  }
  $$(".step-row", container).forEach((row, i) => {
    const badge = $(".step-number-badge", row);
    if (badge) badge.textContent = `PASSO ${i + 1}`;
  });
}

async function saveFlow(event) {
  event.preventDefault();
  const flowId = $("#flow-id").value;
  const name = $("#flow-name").value.trim();
  const trigger = $("#flow-trigger").value.trim();
  
  const container = $("#steps-container");
  const stepRows = $$(".step-row", container);
  
  if (!stepRows.length) {
    toast("Adicione pelo menos um passo ao fluxo", "error");
    return;
  }
  
  const steps = stepRows.map(row => {
    const type = $(".step-type-select", row).value;
    const textInput = $(".step-text-input", row);
    const urlInput = $(".step-url-input", row);
    
    return {
      type,
      text: textInput ? textInput.value.trim() : null,
      media_url: urlInput ? urlInput.value.trim() : null
    };
  });
  
  const payload = { name, trigger_intent: trigger, steps };
  const method = flowId ? "PUT" : "POST";
  const path = flowId ? `/api/flows/${flowId}` : "/api/flows";
  
  const btn = $("#btn-save-flow");
  btn.disabled = true;
  btn.textContent = "Salvando...";
  
  try {
    await api.request(path, {
      method,
      body: JSON.stringify(payload)
    });
    toast(flowId ? "Fluxo atualizado com sucesso" : "Fluxo criado com sucesso");
    closeFlowModal();
    loadFlows();
  } catch (error) {
    toast(error.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Salvar fluxo";
  }
}

async function deleteFlow(flowId) {
  if (!confirm("Deseja realmente excluir este fluxo?")) return;
  try {
    await api.request(`/api/flows/${flowId}`, { method: "DELETE" });
    toast("Fluxo excluído com sucesso");
    loadFlows();
  } catch (error) {
    toast(error.message, "error");
  }
}

/* ============================================================
   INSTANCES CONTROLLER LOGIC
   ============================================================ */

async function loadInstances() {
  const settings = await api.request("/api/settings");
  state.settings = settings;
  
  const form = $("#instances-settings-form");
  if (form) {
    const providerRadios = form.querySelectorAll('input[name="whatsapp_provider"]');
    providerRadios.forEach(radio => {
      radio.checked = radio.value === settings.whatsapp_provider;
    });
    
    form.elements.evolution_url.value = settings.evolution_url || "";
    form.elements.evolution_key.value = settings.evolution_key || "";
    form.elements.evolution_instance.value = settings.evolution_instance || "";
    
    toggleProviderFields(settings.whatsapp_provider);
  }
  
  await refreshInstanceStatus();
}

function toggleProviderFields(provider) {
  const officialDiv = $("#official-config-fields");
  const evolutionDiv = $("#evolution-config-fields");
  if (officialDiv && evolutionDiv) {
    if (provider === "official") {
      officialDiv.style.display = "block";
      evolutionDiv.style.display = "none";
    } else {
      officialDiv.style.display = "none";
      evolutionDiv.style.display = "flex";
    }
  }
}

async function refreshInstanceStatus() {
  if (state.view !== "instances") return;
  const statusInfo = $("#instance-status-info");
  const qrcodeContainer = $("#instance-qrcode-container");
  if (!statusInfo || !qrcodeContainer) return;
  
  try {
    const statusData = await api.request("/api/instances/status");

    const connectBtn = $("#btn-connect-instance");
    if (connectBtn) {
      const showConnect =
        statusData.provider === "evolution" && statusData.status !== "connected";
      connectBtn.style.display = showConnect ? "block" : "none";
    }

    if (statusData.status === "connected") {
      qrcodeContainer.style.display = "none";
      statusInfo.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 8px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="width: 10px; height: 10px; background: var(--accent); border-radius: 50%; display: inline-block;"></span>
            <strong style="font-size: 13px; color: var(--text);">Conectado</strong>
          </div>
          <div style="font-size: 12px; color: var(--muted); margin-top: 4px;">
            <p style="margin: 2px 0;"><strong>Nome:</strong> ${statusData.display_name || 'Desconhecido'}</p>
            <p style="margin: 2px 0;"><strong>ID:</strong> ${statusData.id || ''}</p>
          </div>
          ${statusData.provider === 'evolution' ? `
            <button id="btn-logout-instance" type="button" class="button button-quiet button-small" style="color: var(--danger); border-color: var(--danger); margin-top: 10px; width: 100%;">
              Desconectar Whatsapp
            </button>
          ` : ''}
        </div>
      `;
      
      const logoutBtn = $("#btn-logout-instance");
      if (logoutBtn) {
        logoutBtn.addEventListener("click", logoutInstance);
      }
    } else if (statusData.status === "disconnected") {
      statusInfo.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 8px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="width: 10px; height: 10px; background: var(--warning); border-radius: 50%; display: inline-block;"></span>
            <strong style="font-size: 13px; color: var(--text);">Aguardando Conexão</strong>
          </div>
          <p style="font-size: 11px; color: var(--faint); margin: 0;">Aguardando leitura do QR code para autenticar.</p>
        </div>
      `;
      
      if (statusData.qrcode) {
        qrcodeContainer.style.display = "flex";
        const qrBox = $("#qrcode-img-box");
        if (qrBox) {
          const src = statusData.qrcode.startsWith('data:') ? statusData.qrcode : `data:image/png;base64,${statusData.qrcode}`;
          qrBox.innerHTML = `<img src="${src}" alt="QR Code" style="display: block; width: 180px; height: 180px; margin: 0 auto;">`;
        }
      } else {
        qrcodeContainer.style.display = "none";
      }
    } else if (statusData.status === "unconfigured") {
      qrcodeContainer.style.display = "none";
      statusInfo.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 8px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="width: 10px; height: 10px; background: var(--warning); border-radius: 50%; display: inline-block;"></span>
            <strong style="font-size: 13px; color: var(--text);">Não Configurado</strong>
          </div>
          <p style="font-size: 11px; color: var(--faint); margin: 0;">Insira as credenciais de acesso para ativar.</p>
        </div>
      `;
    } else {
      qrcodeContainer.style.display = "none";
      statusInfo.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 8px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="width: 10px; height: 10px; background: var(--danger); border-radius: 50%; display: inline-block;"></span>
            <strong style="font-size: 13px; color: var(--text);">Erro de Conexão</strong>
          </div>
          <p style="font-size: 11px; color: var(--danger); margin: 0;">${statusData.detail || 'Falha ao se conectar à API'}</p>
        </div>
      `;
    }
  } catch (error) {
    statusInfo.innerHTML = `<p style="color: var(--danger); font-size: 11px;">Erro ao carregar status: ${error.message}</p>`;
    qrcodeContainer.style.display = "none";
  }
}

async function connectInstance() {
  const button = $("#btn-connect-instance");
  if (button) {
    button.disabled = true;
    button.textContent = "Gerando QR Code…";
  }
  try {
    const result = await api.request("/api/instances/connect", { method: "POST" });
    if (result.status === "connected") {
      toast("Instância já está conectada.");
    } else if (result.qrcode) {
      toast("QR Code gerado. Escaneie no WhatsApp.");
    } else {
      toast("Aguardando QR Code do Evolution…");
    }
    await refreshInstanceStatus();
  } catch (error) {
    toast(error.message, "error");
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = "Conectar instância";
    }
  }
}

async function logoutInstance() {
  if (!confirm("Deseja realmente desconectar esta instância do WhatsApp?")) return;
  const logoutBtn = $("#btn-logout-instance");
  if (logoutBtn) logoutBtn.disabled = true;
  
  try {
    await api.request("/api/instances/logout", { method: "POST" });
    toast("Instância desconectada com sucesso");
    await refreshInstanceStatus();
  } catch (error) {
    toast(error.message, "error");
  } finally {
    if (logoutBtn) logoutBtn.disabled = false;
  }
}

async function saveInstances(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('[type="submit"]');
  button.disabled = true;
  
  const provider = form.elements.whatsapp_provider.value;
  const evolution_url = form.elements.evolution_url.value.trim();
  const evolution_key = form.elements.evolution_key.value.trim();
  const evolution_instance = form.elements.evolution_instance.value.trim();
  
  if (!state.settings) {
    try {
      state.settings = await api.request("/api/settings");
    } catch (err) {
      state.settings = {};
    }
  }
  
  const payload = {
    ...state.settings,
    whatsapp_provider: provider,
    evolution_url,
    evolution_key,
    evolution_instance
  };
  
  try {
    const saved = await api.request("/api/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    state.settings = saved;
    toast("Configurações de conexão salvas com sucesso!");
    await refreshInstanceStatus();
  } catch (error) {
    toast(error.message, "error");
  } finally {
    button.disabled = false;
  }
}

function bindEvents() {
  $("#btn-new-flow").addEventListener("click", () => openFlowModal());
  $("#btn-close-flow-modal").addEventListener("click", closeFlowModal);
  $("#btn-cancel-flow").addEventListener("click", closeFlowModal);
  $("#btn-add-step").addEventListener("click", () => addStepRow());
  $("#flow-form").addEventListener("submit", saveFlow);

  const instancesForm = $("#instances-settings-form");
  if (instancesForm) {
    instancesForm.addEventListener("submit", saveInstances);
    instancesForm.querySelectorAll('input[name="whatsapp_provider"]').forEach(radio => {
      radio.addEventListener("change", (e) => toggleProviderFields(e.target.value));
    });
  }

  const connectBtn = $("#btn-connect-instance");
  if (connectBtn) connectBtn.addEventListener("click", connectInstance);

  const openaiKeyForm = $("#openai-key-form");
  if (openaiKeyForm) openaiKeyForm.addEventListener("submit", saveOpenAiKey);

  $$(".nav-item").forEach((button) => button.addEventListener("click", () => openView(button.dataset.viewTarget)));
  $$("[data-open-view]").forEach((button) => button.addEventListener("click", () => openView(button.dataset.openView)));
  $("#refresh-view").addEventListener("click", refreshCurrentView);
  $("#contact-search").addEventListener("input", (event) => renderContacts(event.target.value));
  $("#settings-form").addEventListener("submit", saveSettings);
  $("#settings-form").elements.commercial_initiative.addEventListener("input", (event) => setText("#initiative-output", event.target.value));
  // Live banner: show warning when system_prompt has content
  const systemPromptField = $("#settings-form").elements.namedItem("system_prompt");
  if (systemPromptField) {
    systemPromptField.addEventListener("input", () => updatePromptOverrideBanner($("#settings-form")));
  }
  $("#lab-form").addEventListener("submit", sendLabMessage);
  $("#reset-lab").addEventListener("click", resetLab);
  $$(".filter-chip").forEach((button) => button.addEventListener("click", () => {
    $$(".filter-chip").forEach((chip) => chip.classList.remove("is-active"));
    button.classList.add("is-active");
    state.eventFilter = button.dataset.eventFilter;
    renderEvents();
  }));
  $("#lab-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      $("#lab-form").requestSubmit();
    }
  });

  setInterval(() => {
    if (state.view === "instances") {
      refreshInstanceStatus();
    }
  }, 5000);
}

document.addEventListener("DOMContentLoaded", async () => {
  bindEvents();
  const initial = location.hash.slice(1);
  openView(viewMeta[initial] ? initial : "overview", false);
});
