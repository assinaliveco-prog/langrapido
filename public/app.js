/**
 * app.js
 * Frontend client logic for LangaRápido Sim dashboard.
 */

// State variables
let currentLeadId = "";
let isLoopActive = false;
let config = {};
let leads = [];

// Personality Presets
const PERSONALITY_PRESETS = {
  friendly: "Amigável, atenciosa, fala de forma informal e calorosa. Usa emojis de forma leve (ex: 😊, 👍), escreve algumas frases em letras minúsculas. Evita linguagem técnica ou robótica.",
  formal: "Atencioso, formal e extremamente educado. Evita gírias ou abreviações. Mantém a pontuação gramatical perfeita. Se direciona ao lead usando termos respeitosos (Senhor/Senhora).",
  aggressive: "Focado estritamente em vendas rápidas. Bastante persuasivo, amigável mas incisivo. Tenta obter as informações de contato do lead e agendar uma demonstração do produto nas primeiras 3 interações."
};

// DOM Elements
const apiStatusEl = document.getElementById('api-status');
const apiKeyInput = document.getElementById('api-key');
const toggleApiKeyBtn = document.getElementById('toggle-api-key');
const botNameInput = document.getElementById('bot-name');
const modelNameSelect = document.getElementById('model-name');
const personalityTextarea = document.getElementById('personality');
const typoRange = document.getElementById('typo-probability');
const typoValText = document.getElementById('typo-val');
const configForm = document.getElementById('bot-config-form');

const leadSelect = document.getElementById('lead-select');
const leadDetailsText = document.getElementById('lead-details-text');
const newLeadBtn = document.getElementById('new-lead-btn');

const chatLeadName = document.getElementById('chat-lead-name');
const chatLeadStatus = document.getElementById('chat-lead-status');
const chatMessagesContainer = document.getElementById('chat-messages-container');
const chatInput = document.getElementById('chat-input');
const sendMsgBtn = document.getElementById('send-msg-btn');
const resetChatBtn = document.getElementById('reset-chat-btn');
const simulateTurnBtn = document.getElementById('simulate-turn-btn');
const startLoopBtn = document.getElementById('start-loop-btn');
const stopLoopBtn = document.getElementById('stop-loop-btn');

const crmName = document.getElementById('crm-name');
const crmContact = document.getElementById('crm-contact');
const crmBudget = document.getElementById('crm-budget');
const crmInterest = document.getElementById('crm-interest');
const crmObjectionsContainer = document.getElementById('crm-objections-container');
const crmSummary = document.getElementById('crm-summary');
const crmNextAction = document.getElementById('crm-next-action');

// Modal Elements
const customLeadModal = document.getElementById('custom-lead-modal');
const customLeadForm = document.getElementById('custom-lead-form');
const closeModalBtn = document.getElementById('close-modal-btn');
const newLeadNameInput = document.getElementById('new-lead-name');
const newLeadBudgetInput = document.getElementById('new-lead-budget');
const newLeadDetailsTextarea = document.getElementById('new-lead-details');

// Initialize App
window.addEventListener('DOMContentLoaded', async () => {
  setupEventListeners();
  await loadConfig();
  await loadLeads();
});

// Event Handlers Setup
function setupEventListeners() {
  // Toggle password visibility
  toggleApiKeyBtn.addEventListener('click', () => {
    const type = apiKeyInput.type === 'password' ? 'text' : 'password';
    apiKeyInput.type = type;
    toggleApiKeyBtn.textContent = type === 'password' ? '👁️' : '🔒';
  });

  // Slider change
  typoRange.addEventListener('input', (e) => {
    typoValText.textContent = e.target.value + '%';
  });

  // Presets selector
  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      const presetType = e.target.getAttribute('data-preset');
      personalityTextarea.value = PERSONALITY_PRESETS[presetType];
    });
  });

  // Submit config
  configForm.addEventListener('submit', handleConfigSubmit);

  // Lead selection change
  leadSelect.addEventListener('change', (e) => {
    selectLead(e.target.value);
  });

  // Chat send message
  sendMsgBtn.addEventListener('click', handleSendMessage);
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleSendMessage();
  });

  // Simulate Turn & Loop Controls
  simulateTurnBtn.addEventListener('click', handleSimulateTurn);
  startLoopBtn.addEventListener('click', startSimulationLoop);
  stopLoopBtn.addEventListener('click', stopSimulationLoop);
  resetChatBtn.addEventListener('click', handleResetChat);

  // Modal open/close
  newLeadBtn.addEventListener('click', () => customLeadModal.classList.remove('hidden'));
  closeModalBtn.addEventListener('click', () => customLeadModal.classList.add('hidden'));
  customLeadForm.addEventListener('submit', handleCreateLeadSubmit);
}

// Load Configuration from API
async function loadConfig() {
  try {
    const res = await fetch('/api/config');
    config = await res.json();
    
    botNameInput.value = config.botName;
    modelNameSelect.value = config.modelName;
    personalityTextarea.value = config.personality;
    typoRange.value = config.typoProbability * 100;
    typoValText.textContent = (config.typoProbability * 100) + '%';
    
    if (config.geminiApiKey) {
      apiKeyInput.placeholder = "API Key configurada (oculta)";
      updateApiStatus('success', 'Gemini Conectado');
    } else {
      updateApiStatus('warning', 'Falta API Key');
    }
  } catch (err) {
    console.error("Error loading config:", err);
    updateApiStatus('danger', 'Erro ao carregar');
  }
}

// Update Header API Connection status
function updateApiStatus(type, text) {
  apiStatusEl.className = `header-status`;
  const indicator = apiStatusEl.querySelector('.status-indicator');
  const label = apiStatusEl.querySelector('.status-text');
  
  indicator.className = `status-indicator ${type}`;
  label.textContent = text;
}

// Save config
async function handleConfigSubmit(e) {
  e.preventDefault();
  
  const payload = {
    botName: botNameInput.value,
    modelName: modelNameSelect.value,
    personality: personalityTextarea.value,
    typoProbability: parseFloat(typoRange.value) / 100
  };

  const keyVal = apiKeyInput.value.trim();
  if (keyVal) {
    payload.geminiApiKey = keyVal;
  }

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    const data = await res.json();
    if (data.success) {
      alert("Configuração salva com sucesso!");
      apiKeyInput.value = ""; // Clear input
      await loadConfig();
    } else {
      alert("Erro ao validar API Key: " + data.error);
    }
  } catch (err) {
    alert("Erro de conexão ao salvar configuração.");
  }
}

// Load Leads from API
async function loadLeads() {
  try {
    const res = await fetch('/api/leads');
    leads = await res.json();
    
    leadSelect.innerHTML = "";
    leads.forEach(lead => {
      const option = document.createElement('option');
      option.value = lead.id;
      option.textContent = lead.name;
      leadSelect.appendChild(option);
    });

    if (leads.length > 0) {
      selectLead(leads[0].id);
    }
  } catch (err) {
    console.error("Error loading leads:", err);
  }
}

// Select lead and render details & chat history
async function selectLead(leadId) {
  currentLeadId = leadId;
  const lead = leads.find(l => l.id === leadId);
  if (!lead) return;

  // Render details card
  leadDetailsText.textContent = lead.details;
  chatLeadName.textContent = lead.name;
  
  // Render CRM stats
  updateCrmPanel(lead);

  // Load chat history
  await loadChatHistory(leadId);
}

// Load chat history from API and render
async function loadChatHistory(leadId) {
  try {
    const res = await fetch(`/api/leads/${leadId}/chat`);
    const messages = await res.json();
    
    chatMessagesContainer.innerHTML = "";
    messages.forEach(msg => {
      appendMessageUI(msg);
    });
    scrollToBottom();
  } catch (err) {
    console.error("Error loading chat history:", err);
  }
}

// Update CRM Panel UI values
function updateCrmPanel(lead) {
  crmName.textContent = lead.name || "-";
  crmContact.textContent = lead.contact || "-";
  crmBudget.textContent = lead.budget || "-";
  
  // Set interest badge
  crmInterest.textContent = (lead.interest || "indefinido").toUpperCase();
  crmInterest.className = "interest-badge";
  if (lead.interest === 'alto') {
    crmInterest.classList.add('status-high');
  } else if (lead.interest === 'médio') {
    crmInterest.classList.add('status-medium');
  } else if (lead.interest === 'baixo') {
    crmInterest.classList.add('status-low');
  } else {
    crmInterest.classList.add('status-neutral');
  }

  // Set objection tags
  crmObjectionsContainer.innerHTML = "";
  if (lead.objections && lead.objections.length > 0) {
    lead.objections.forEach(obj => {
      const tag = document.createElement('span');
      tag.className = 'objection-tag';
      tag.textContent = obj;
      crmObjectionsContainer.appendChild(tag);
    });
  } else {
    crmObjectionsContainer.innerHTML = '<span class="no-data">Nenhuma objeção</span>';
  }

  crmSummary.textContent = lead.summary || "Aguardando início da conversa.";
  crmNextAction.textContent = lead.nextAction || "Aguardando início da conversa.";
}

// Render message in chat UI
function appendMessageUI(msg) {
  const row = document.createElement('div');
  row.className = `message-row ${msg.role === 'model' ? 'sales-row' : 'lead-row'}`;

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  if (msg.isTypo) bubble.classList.add('typo-bubble');
  if (msg.isCorrection) bubble.classList.add('correction-bubble');
  
  bubble.textContent = msg.text;

  // Add metadata (timestamp & read indicators)
  const meta = document.createElement('div');
  meta.className = 'message-meta';
  
  const time = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  meta.textContent = time;

  if (msg.role !== 'model') {
    // Lead messages get blue checkmarks
    const ticks = document.createElement('span');
    ticks.className = 'message-status';
    ticks.textContent = ' ✓✓';
    meta.appendChild(ticks);
  }

  bubble.appendChild(meta);
  row.appendChild(bubble);
  chatMessagesContainer.appendChild(row);
}

// Typing Indicator helper
let typingIndicatorEl = null;

function showTypingIndicator() {
  if (typingIndicatorEl) return;
  
  typingIndicatorEl = document.createElement('div');
  typingIndicatorEl.className = 'typing-bubble';
  typingIndicatorEl.innerHTML = `
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>
  `;
  chatMessagesContainer.appendChild(typingIndicatorEl);
  scrollToBottom();
}

function hideTypingIndicator() {
  if (typingIndicatorEl) {
    typingIndicatorEl.remove();
    typingIndicatorEl = null;
  }
}

// Scroll chat window to bottom
function scrollToBottom() {
  chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
}

// Handle sending message from manual lead input
async function handleSendMessage() {
  const text = chatInput.value.trim();
  if (!text || !currentLeadId) return;

  chatInput.value = "";
  chatInput.disabled = true;
  sendMsgBtn.disabled = true;

  // Render client message immediately
  appendMessageUI({
    sender: "Lead",
    role: "user",
    text: text,
    timestamp: new Date().toISOString()
  });
  scrollToBottom();

  try {
    const res = await fetch(`/api/leads/${currentLeadId}/chat/message`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    
    const data = await res.json();
    if (res.status !== 200) {
      throw new Error(data.error || "Erro ao processar mensagem.");
    }

    // Play humanized sequential responses
    await playActions(data.messages);
    
    // Update CRM variables
    await refreshCrmData();

  } catch (err) {
    alert("Erro no envio: " + err.message);
  } finally {
    chatInput.disabled = false;
    sendMsgBtn.disabled = false;
    chatInput.focus();
  }
}

// Sequentially animate typing actions from SalesAgent
async function playActions(actions) {
  for (let action of actions) {
    // Show typing status during thinking delay
    chatLeadStatus.textContent = "online";
    await sleep(action.thinkingTime || 1000);
    
    // Show active typing state
    chatLeadStatus.textContent = "digitando...";
    showTypingIndicator();
    await sleep(action.typingTime || 1500);
    
    // Clear typing states
    hideTypingIndicator();
    chatLeadStatus.textContent = "online";

    // Append to UI
    appendMessageUI({
      sender: action.sender,
      role: 'model',
      text: action.text,
      isTypo: action.isTypo,
      isCorrection: action.isCorrection,
      timestamp: new Date().toISOString()
    });
    scrollToBottom();
  }
}

// Fetch updated CRM details
async function refreshCrmData() {
  try {
    const res = await fetch('/api/leads');
    const allLeads = await res.json();
    leads = allLeads;
    
    const lead = leads.find(l => l.id === currentLeadId);
    if (lead) {
      updateCrmPanel(lead);
    }
  } catch (err) {
    console.error("Failed to refresh CRM data", err);
  }
}

// Trigger single turn in simulation
async function handleSimulateTurn() {
  if (!currentLeadId) return;
  simulateTurnBtn.disabled = true;

  try {
    const res = await fetch(`/api/leads/${currentLeadId}/simulate-turn`, {
      method: 'POST'
    });
    const data = await res.json();
    
    if (res.status !== 200) {
      throw new Error(data.error || "Erro no turno do simulador.");
    }

    // Process turn animations based on role
    if (data.turn === 'lead') {
      const msg = data.messages[0];
      // Simulate lead typing speed
      chatLeadStatus.textContent = "digitando...";
      showTypingIndicator();
      await sleep(msg.typingTime || 2000);
      hideTypingIndicator();
      chatLeadStatus.textContent = "online";

      appendMessageUI({
        sender: msg.sender,
        role: 'user',
        text: msg.text,
        timestamp: new Date().toISOString()
      });
      scrollToBottom();
    } else {
      // Sales Agent typing actions
      await playActions(data.messages);
    }

    await refreshCrmData();

  } catch (err) {
    alert("Erro na simulação: " + err.message);
  } finally {
    simulateTurnBtn.disabled = false;
  }
}

// Continuous auto-simulation loop
async function startSimulationLoop() {
  if (!currentLeadId) return;
  isLoopActive = true;
  
  startLoopBtn.classList.add('hidden');
  stopLoopBtn.classList.remove('hidden');
  simulateTurnBtn.disabled = true;
  chatInput.disabled = true;

  while (isLoopActive) {
    try {
      const res = await fetch(`/api/leads/${currentLeadId}/simulate-turn`, {
        method: 'POST'
      });
      const data = await res.json();
      
      if (res.status !== 200) {
        throw new Error(data.error);
      }

      if (data.turn === 'lead') {
        const msg = data.messages[0];
        chatLeadStatus.textContent = "digitando...";
        showTypingIndicator();
        await sleep(msg.typingTime || 2000);
        hideTypingIndicator();
        chatLeadStatus.textContent = "online";

        appendMessageUI({
          sender: msg.sender,
          role: 'user',
          text: msg.text,
          timestamp: new Date().toISOString()
        });
        scrollToBottom();
      } else {
        await playActions(data.messages);
      }

      await refreshCrmData();
      
      // Natural delay between conversational turns before continuing
      if (isLoopActive) {
        await sleep(2000 + Math.random() * 1000);
      }

    } catch (err) {
      console.error("Loop Error:", err);
      stopSimulationLoop();
      alert("Simulação pausada por um erro: " + err.message);
      break;
    }
  }
}

function stopSimulationLoop() {
  isLoopActive = false;
  startLoopBtn.classList.remove('hidden');
  stopLoopBtn.classList.add('hidden');
  simulateTurnBtn.disabled = false;
  chatInput.disabled = false;
}

// Reset chat log
async function handleResetChat() {
  if (!currentLeadId || !confirm("Tem certeza que deseja reiniciar o histórico dessa conversa?")) return;
  
  try {
    const res = await fetch(`/api/leads/${currentLeadId}/reset`, {
      method: 'POST'
    });
    
    if (res.status === 200) {
      chatMessagesContainer.innerHTML = "";
      await loadLeads();
      await selectLead(currentLeadId);
    }
  } catch (err) {
    alert("Erro ao reiniciar histórico.");
  }
}

// Submit new custom lead form
async function handleCreateLeadSubmit(e) {
  e.preventDefault();

  const name = newLeadNameInput.value.trim();
  const budget = newLeadBudgetInput.value.trim();
  const details = newLeadDetailsTextarea.value.trim();

  try {
    const res = await fetch('/api/leads/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, budget, details })
    });
    
    const data = await res.json();
    if (res.status === 200) {
      customLeadModal.classList.add('hidden');
      newLeadNameInput.value = "";
      newLeadBudgetInput.value = "";
      newLeadDetailsTextarea.value = "";
      
      await loadLeads();
      leadSelect.value = data.id;
      await selectLead(data.id);
    } else {
      alert("Erro ao criar lead: " + data.error);
    }
  } catch (err) {
    alert("Erro de conexão ao criar lead.");
  }
}

// Sleep helper
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
