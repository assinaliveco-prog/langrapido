/**
 * agents.js
 * Multi-agent module for the Lead Chatbot Simulator.
 * Defines SalesAgent, LeadAgent, and ExtractorAgent using Gemini API.
 */

const humanizer = require('./humanizer');

let aiClient = null;
let useGenAISDK = false;

/**
 * Initializes the Gemini API client.
 * Supports both @google/genai (new SDK) and @google/generative-ai (older SDK).
 * @param {string} apiKey - Gemini API Key
 */
function initAI(apiKey) {
  const finalKey = apiKey || process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
  if (!finalKey) {
    throw new Error("No Gemini API key found. Provide it to initAI or set GEMINI_API_KEY env variable.");
  }

  try {
    // Attempt to load the new @google/genai SDK
    const { GoogleGenAI } = require('@google/genai');
    aiClient = new GoogleGenAI({ apiKey: finalKey });
    useGenAISDK = true;
    console.log("Gemini API initialized using @google/genai SDK.");
  } catch (e) {
    try {
      // Fallback to older @google/generative-ai SDK
      const { GoogleGenerativeAI } = require('@google/generative-ai');
      aiClient = new GoogleGenerativeAI(finalKey);
      useGenAISDK = false;
      console.log("Gemini API initialized using @google/generative-ai SDK.");
    } catch (err) {
      throw new Error("Failed to load Gemini SDK. Ensure @google/genai or @google/generative-ai is installed.");
    }
  }
}

/**
 * Base Agent class that handles direct LLM calls.
 */
class Agent {
  constructor(name, systemInstruction, modelName = 'gemini-2.5-flash', temperature = 0.7) {
    this.name = name;
    this.systemInstruction = systemInstruction;
    this.modelName = modelName;
    this.temperature = temperature;
  }

  async generate(contents, isJson = false) {
    if (!aiClient) {
      throw new Error("AI Client is not initialized. Call initAI() first.");
    }

    // Standardize contents format. 
    // If it's a string, format it into Gemini chat content format.
    let geminiContents = contents;
    if (typeof contents === 'string') {
      geminiContents = [{ role: 'user', parts: [{ text: contents }] }];
    }

    try {
      if (useGenAISDK) {
        const response = await aiClient.models.generateContent({
          model: this.modelName,
          contents: geminiContents,
          config: {
            systemInstruction: this.systemInstruction,
            temperature: this.temperature,
            responseMimeType: isJson ? 'application/json' : undefined
          }
        });
        return response.text;
      } else {
        const model = aiClient.getGenerativeModel({
          model: this.modelName,
          systemInstruction: this.systemInstruction,
        });
        const response = await model.generateContent({
          contents: geminiContents,
          generationConfig: {
            temperature: this.temperature,
            responseMimeType: isJson ? 'application/json' : undefined
          }
        });
        return response.response.text();
      }
    } catch (error) {
      console.error(`Error generating response from Agent ${this.name}:`, error);
      throw error;
    }
  }
}

/**
 * SalesAgent: The main lead generation bot.
 * Features humanization engine (text splitting, dynamic delays, realistic typos).
 */
class SalesAgent extends Agent {
  constructor(name, personality, modelName = 'gemini-2.5-flash', typoProbability = 0.15) {
    const systemInstruction = `
      Você é um atendente comercial humano chamado ${name}.
      Seu objetivo é conversar com o lead, responder suas dúvidas e conseguir suas informações de contato (como nome e whatsapp/email) de forma extremamente sutil e natural.

      INSTRUÇÕES DE PERSONALIDADE E ESTILO (SURREALMENTE HUMANO):
      - Personalidade/Tom: ${personality}
      - NUNCA escreva como um assistente de IA corporativo (ex: "Como posso ajudar você hoje?", "Estou aqui para auxiliar"). Escreva como uma pessoa real conversando no WhatsApp.
      - Use linguagem informal, abreviações naturais do português brasileiro (como "tb", "vc", "pq", "tlg", "blz") e gírias leves se apropriado para a personalidade.
      - Escreva em caixa baixa (letras minúsculas) com frequência, evite usar pontuação excessivamente formal no final de frases curtas.
      - Não mande blocos enormes de texto. Divida suas ideias em frases curtas.
      - Seja amigável, demonstre empatia e simpatia. Se o lead disser algo pessoal, reaja a isso antes de vender.
      - Mantenha o foco em conduzir a conversa para qualificar o lead e pegar os contatos dele, mas sem parecer desesperado ou invasivo.
    `;

    super(name, systemInstruction, modelName, 0.75);
    this.typoProbability = typoProbability;
  }

  /**
   * Process the chat history and return a list of humanized message actions.
   * Each action represents a message chunk with a specified typing delay and typo correction if needed.
   */
  async chat(history) {
    // Generate raw response text
    const rawResponse = await this.generate(history);
    
    // Split the text into natural chunks (sentences/phrases)
    const rawChunks = humanizer.splitIntoChunks(rawResponse);
    
    const actions = [];
    for (let chunk of rawChunks) {
      // Calculate dynamic human-like typing delays
      const delays = humanizer.calculateDelay(chunk);
      
      // Simulate natural typing mistakes and correction follow-ups
      const typoResult = humanizer.simulateTypos(chunk, this.typoProbability);
      
      if (typoResult.needsCorrection) {
        // First action: send message with typo
        actions.push({
          sender: this.name,
          role: 'model',
          text: typoResult.resultText,
          thinkingTime: delays.thinkingTime,
          typingTime: delays.typingTime,
          isTypo: true
        });
        
        // Second action: send follow-up correction after a short natural pause
        actions.push({
          sender: this.name,
          role: 'model',
          text: typoResult.correctionMessage,
          thinkingTime: 300,
          typingTime: 1200,
          isCorrection: true
        });
      } else {
        // Send normal message chunk
        actions.push({
          sender: this.name,
          role: 'model',
          text: chunk,
          thinkingTime: delays.thinkingTime,
          typingTime: delays.typingTime
        });
      }
    }
    
    return actions;
  }
}

/**
 * LeadAgent: Simulates a potential customer/lead for testing and auto-simulation.
 */
class LeadAgent extends Agent {
  constructor(profileName, profileDetails, modelName = 'gemini-2.5-flash') {
    const systemInstruction = `
      Você é um cliente real chamado ${profileName} conversando com um vendedor pelo WhatsApp.
      Seu perfil e objetivos são: ${profileDetails}

      REGRAS DE COMPORTAMENTO:
      - Responda como uma pessoa física real conversando pelo WhatsApp: de forma curta, informal e direta.
      - Não faça perguntas robóticas ou excessivamente longas.
      - Reaja ao que o vendedor fala de acordo com a sua personalidade (ex: se você é ocupado, responda com pressa; se é desconfiado, faça perguntas sobre preços e garantias; se é simpático, converse de forma fluida).
      - Vá revelando seu nome, whatsapp ou email aos poucos, SOMENTE se o vendedor for educado, humanizado e pedir de forma natural. Se ele for robótico, chato ou invasivo, mostre desinteresse ou recuse passar os dados.
      - Escreva usando abreviações do dia a dia (vc, tb, hj, pq) e use caixa baixa (letras minúsculas) frequentemente.
    `;

    super(profileName, systemInstruction, modelName, 0.8);
  }

  async reply(history) {
    const response = await this.generate(history);
    
    // Standardize lead response action
    const wordsCount = response.split(/\s+/).length;
    const typingTime = Math.max(1000, Math.round(wordsCount * 180 + Math.random() * 500));
    
    return {
      sender: this.name,
      role: 'user',
      text: response.trim(),
      thinkingTime: 800 + Math.round(Math.random() * 800),
      typingTime: typingTime
    };
  }
}

/**
 * ExtractorAgent: Silent CRM parser that updates lead details.
 */
class ExtractorAgent extends Agent {
  constructor(modelName = 'gemini-2.5-flash') {
    const systemInstruction = `
      Você é um robô de CRM silencioso. Sua tarefa é analisar o histórico de conversa entre um Atendente Comercial (model) e um Lead (user) e extrair os dados de contato e informações de qualificação.

      Você DEVE retornar um objeto JSON exatamente no seguinte formato:
      {
        "name": "Nome do lead (ou null se não identificado)",
        "contact": "Telefone, WhatsApp ou Email do lead (ou null se não identificado)",
        "interest": "Nível de interesse: 'alto', 'médio', 'baixo' ou 'indefinido'",
        "budget": "Orçamento/Budget mencionado pelo lead (ou null se não mencionado)",
        "objections": ["Lista de objeções identificadas (ex: preço, prazo, localização) ou array vazio"],
        "summary": "Resumo rápido de 1 frase do status da conversa",
        "nextAction": "Recomendação da próxima ação para o vendedor (ex: 'Pedir o Whatsapp', 'Marcar visita', 'Enviar catálogo')"
      }

      Não adicione nenhuma introdução ou explicação. Apenas o JSON puro.
    `;

    super('Extractor', systemInstruction, modelName, 0.2);
  }

  async extract(history) {
    // Format history for extraction
    const rawJson = await this.generate(history, true);
    try {
      return JSON.parse(rawJson);
    } catch (e) {
      console.error("Failed to parse ExtractorAgent JSON output:", rawJson);
      // Fallback parser in case JSON is wrapped in markdown code blocks
      const cleanJson = rawJson.replace(/```json/g, "").replace(/```/g, "").trim();
      return JSON.parse(cleanJson);
    }
  }
}

module.exports = {
  initAI,
  SalesAgent,
  LeadAgent,
  ExtractorAgent
};
