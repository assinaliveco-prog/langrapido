/**
 * server.js
 * Express Backend API for the Humanized Lead Chatbot & Multi-Agent Simulator.
 */

require('dotenv').config();
const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const agents = require('./agents');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const DB_PATH = path.join(__dirname, 'db.json');

// Default presets for the database
const DEFAULT_DB = {
  config: {
    geminiApiKey: process.env.GEMINI_API_KEY || "",
    botName: "Ana",
    personality: "Amigável, atenciosa, fala de forma informal e calorosa. Usa emojis de forma leve (ex: 😊, 👍), escreve algumas frases em letras minúsculas. Evita linguagem técnica ou robótica.",
    modelName: "gemini-2.5-flash",
    typoProbability: 0.15
  },
  leads: [
    {
      id: "lead_joao",
      name: "João Silva",
      details: "Interessado em comprar um apartamento de 2 quartos no centro. Tem um orçamento de até 400 mil reais. É muito ocupado e um pouco desconfiado de corretores. Só passa o whatsapp se o vendedor for educado, explicar as vantagens do imóvel de forma clara e não for invasivo.",
      contact: null,
      interest: "indefinido",
      budget: "Até 400k",
      objections: [],
      summary: "Novo lead aguardando contato.",
      nextAction: "Iniciar contato inicial e identificar necessidades."
    },
    {
      id: "lead_mariana",
      name: "Mariana Souza",
      details: "Dona de uma clínica de estética procurando um software de gestão. Ela é muito simpática, mas odeia jargões técnicos. Quer entender como o sistema economiza tempo e quer saber o preço de forma clara. Se o atendente tentar enrolar ou não responder o preço de início, ela fica irritada.",
      contact: null,
      interest: "indefinido",
      budget: null,
      objections: [],
      summary: "Lead procurando automação para clínica.",
      nextAction: "Explicar facilidades do sistema de gestão."
    },
    {
      id: "lead_lucas",
      name: "Lucas Santos",
      details: "Quer trocar de carro por uma SUV semi-nova de até 90 mil. Ele é impaciente, digita mensagens curtíssimas e secas. Prefere respostas de uma linha. Quer saber se aceitam o carro dele na troca e se consegue fazer simulação de financiamento rápido.",
      contact: null,
      interest: "indefinido",
      budget: "Até 90k",
      objections: [],
      summary: "Lead direto querendo trocar de veículo.",
      nextAction: "Perguntar sobre o carro dele para avaliação."
    }
  ],
  conversations: []
};

// Initialize DB file
function readDb() {
  if (!fs.existsSync(DB_PATH)) {
    fs.writeFileSync(DB_PATH, JSON.stringify(DEFAULT_DB, null, 2));
    return DEFAULT_DB;
  }
  try {
    const data = fs.readFileSync(DB_PATH, 'utf-8');
    return JSON.parse(data);
  } catch (e) {
    console.error("Error reading db.json, resetting to defaults", e);
    return DEFAULT_DB;
  }
}

function writeDb(data) {
  fs.writeFileSync(DB_PATH, JSON.stringify(data, null, 2));
}

// Try to initialize Gemini API on startup if key is available
try {
  const db = readDb();
  if (db.config.geminiApiKey || process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY) {
    agents.initAI(db.config.geminiApiKey);
    console.log("Initialized Gemini AI on server startup.");
  }
} catch (e) {
  console.log("Failed to auto-initialize Gemini on startup (missing key or library):", e.message);
}

// Helper to convert DB conversation format to Gemini API message format
function formatHistoryForGemini(messages) {
  return messages.map(msg => {
    // Map backend roles ('user' / 'model') to Gemini roles
    const role = msg.role === 'model' ? 'model' : 'user';
    return {
      role: role,
      parts: [{ text: msg.text }]
    };
  });
}

/**
 * REST API ENDPOINTS
 */

// GET configuration
app.get('/api/config', (req, res) => {
  const db = readDb();
  // Mask the API key for security in responses
  const configCopy = { ...db.config };
  if (configCopy.geminiApiKey) {
    configCopy.geminiApiKey = configCopy.geminiApiKey.substring(0, 6) + "..." + configCopy.geminiApiKey.substring(configCopy.geminiApiKey.length - 4);
  }
  res.json(configCopy);
});

// POST configuration
app.post('/api/config', (req, res) => {
  const db = readDb();
  const { geminiApiKey, botName, personality, modelName, typoProbability } = req.body;

  // If new API key is provided, update it. Otherwise keep existing key.
  if (geminiApiKey && !geminiApiKey.startsWith("xxxx") && !geminiApiKey.includes("...")) {
    db.config.geminiApiKey = geminiApiKey;
  }
  
  db.config.botName = botName || db.config.botName;
  db.config.personality = personality || db.config.personality;
  db.config.modelName = modelName || db.config.modelName;
  db.config.typoProbability = typoProbability !== undefined ? typoProbability : db.config.typoProbability;

  writeDb(db);

  try {
    agents.initAI(db.config.geminiApiKey);
    res.json({ success: true, message: "Configuração salva e Gemini API inicializada com sucesso!" });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

// GET leads list
app.get('/api/leads', (req, res) => {
  const db = readDb();
  res.json(db.leads);
});

// POST create lead
app.post('/api/leads/create', (req, res) => {
  const db = readDb();
  const { name, details, budget } = req.body;
  
  if (!name || !details) {
    return res.status(400).json({ error: "Nome e detalhes são obrigatórios." });
  }

  const id = "lead_" + Date.now();
  const newLead = {
    id,
    name,
    details,
    contact: null,
    interest: "indefinido",
    budget: budget || null,
    objections: [],
    summary: "Novo lead criado pelo usuário.",
    nextAction: "Iniciar conversa."
  };

  db.leads.push(newLead);
  writeDb(db);
  res.json(newLead);
});

// GET chat history for lead
app.get('/api/leads/:id/chat', (req, res) => {
  const db = readDb();
  const leadId = req.params.id;
  
  const conversation = db.conversations.find(c => c.leadId === leadId);
  res.json(conversation ? conversation.messages : []);
});

// POST reset chat history
app.post('/api/leads/:id/reset', (req, res) => {
  const db = readDb();
  const leadId = req.params.id;
  
  db.conversations = db.conversations.filter(c => c.leadId !== leadId);
  
  // Reset lead status details in DB as well
  const lead = db.leads.find(l => l.id === leadId);
  if (lead) {
    lead.contact = null;
    lead.interest = "indefinido";
    lead.objections = [];
    lead.summary = "Histórico reiniciado.";
    lead.nextAction = "Iniciar contato inicial.";
  }
  
  writeDb(db);
  res.json({ success: true, message: "Histórico limpo e CRM reiniciado." });
});

// POST send message (manual user chat with SalesAgent)
app.post('/api/leads/:id/chat/message', async (req, res) => {
  const db = readDb();
  const leadId = req.params.id;
  const { text } = req.body;

  if (!text) {
    return res.status(400).json({ error: "Mensagem vazia." });
  }

  // Find or create conversation
  let conversation = db.conversations.find(c => c.leadId === leadId);
  if (!conversation) {
    conversation = { id: "conv_" + Date.now(), leadId, messages: [] };
    db.conversations.push(conversation);
  }

  // Append user message
  const userMessage = {
    sender: "Lead",
    role: "user",
    text: text,
    timestamp: new Date().toISOString()
  };
  conversation.messages.push(userMessage);

  try {
    // Instantiate SalesAgent dynamically based on config
    const salesAgent = new agents.SalesAgent(
      db.config.botName,
      db.config.personality,
      db.config.modelName,
      db.config.typoProbability
    );

    // Convert history for Gemini API
    const geminiHistory = formatHistoryForGemini(conversation.messages);

    // Call SalesAgent chat flow (processes chunks, typing speeds, typos)
    const agentActions = await salesAgent.chat(geminiHistory);

    // Save agent messages to history database
    for (let action of agentActions) {
      conversation.messages.push({
        sender: action.sender,
        role: 'model',
        text: action.text,
        timestamp: new Date().toISOString(),
        isTypo: action.isTypo || false,
        isCorrection: action.isCorrection || false
      });
    }

    writeDb(db);

    // Background Lead Extraction: run ExtractorAgent to parsed CRM status asynchronously
    runBackgroundExtraction(leadId, conversation.messages, db.config.modelName);

    // Return generated actions to the frontend client
    res.json({ messages: agentActions });

  } catch (error) {
    console.error("Error in chat message endpoint:", error);
    res.status(500).json({ error: error.message });
  }
});

// POST simulate turn (automatic Agent vs Agent simulation)
app.post('/api/leads/:id/simulate-turn', async (req, res) => {
  const db = readDb();
  const leadId = req.params.id;

  const lead = db.leads.find(l => l.id === leadId);
  if (!lead) {
    return res.status(404).json({ error: "Lead não encontrado." });
  }

  let conversation = db.conversations.find(c => c.leadId === leadId);
  if (!conversation) {
    conversation = { id: "conv_" + Date.now(), leadId, messages: [] };
    db.conversations.push(conversation);
  }

  // Determine whose turn it is
  const lastMsg = conversation.messages[conversation.messages.length - 1];
  const isLeadTurn = !lastMsg || lastMsg.role === 'model'; // If empty or agent spoke, it's Lead's turn

  try {
    if (isLeadTurn) {
      // Simulate Lead response
      const leadAgent = new agents.LeadAgent(lead.name, lead.details, db.config.modelName);
      const geminiHistory = formatHistoryForGemini(conversation.messages);
      
      const leadAction = await leadAgent.reply(geminiHistory);
      
      conversation.messages.push({
        sender: lead.name,
        role: 'user',
        text: leadAction.text,
        timestamp: new Date().toISOString()
      });
      writeDb(db);

      // Trigger CRM data parser
      runBackgroundExtraction(leadId, conversation.messages, db.config.modelName);

      // Return response as a list of actions
      res.json({
        turn: 'lead',
        messages: [{
          sender: lead.name,
          role: 'user',
          text: leadAction.text,
          thinkingTime: leadAction.thinkingTime,
          typingTime: leadAction.typingTime
        }]
      });

    } else {
      // Simulate SalesAgent response
      const salesAgent = new agents.SalesAgent(
        db.config.botName,
        db.config.personality,
        db.config.modelName,
        db.config.typoProbability
      );
      const geminiHistory = formatHistoryForGemini(conversation.messages);
      const agentActions = await salesAgent.chat(geminiHistory);

      for (let action of agentActions) {
        conversation.messages.push({
          sender: action.sender,
          role: 'model',
          text: action.text,
          timestamp: new Date().toISOString(),
          isTypo: action.isTypo || false,
          isCorrection: action.isCorrection || false
        });
      }
      writeDb(db);

      runBackgroundExtraction(leadId, conversation.messages, db.config.modelName);

      res.json({
        turn: 'sales',
        messages: agentActions
      });
    }

  } catch (error) {
    console.error("Error in simulate-turn endpoint:", error);
    res.status(500).json({ error: error.message });
  }
});

// Asynchronous background CRM parser
async function runBackgroundExtraction(leadId, messages, modelName) {
  try {
    const extractor = new agents.ExtractorAgent(modelName);
    const geminiHistory = formatHistoryForGemini(messages);
    
    const extractedData = await extractor.extract(geminiHistory);
    console.log("Lead qualifications extracted successfully:", extractedData);

    const db = readDb();
    const lead = db.leads.find(l => l.id === leadId);
    if (lead) {
      lead.contact = extractedData.contact || lead.contact;
      lead.interest = extractedData.interest || lead.interest;
      lead.objections = extractedData.objections || lead.objections;
      lead.budget = extractedData.budget || lead.budget;
      lead.summary = extractedData.summary || lead.summary;
      lead.nextAction = extractedData.nextAction || lead.nextAction;
      
      // Keep Name if identified, otherwise default back to the original database name
      if (extractedData.name && extractedData.name !== 'null') {
        lead.name = extractedData.name;
      }
      
      writeDb(db);
    }
  } catch (err) {
    console.error("Background lead data extraction failed:", err.message);
  }
}

app.listen(PORT, () => {
  console.log(`Server started running at http://localhost:${PORT}`);
});
