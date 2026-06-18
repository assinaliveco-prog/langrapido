/**
 * humanizer.js
 * Utility module to simulate natural human chatting patterns (Brazilian Portuguese focus).
 * Includes message splitting, dynamic typing delays, and realistic typo generation.
 */

// Adjacency map for QWERTY keyboard to generate realistic typos
const KEYBOARD_ADJACENCY = {
  'a': ['s', 'q', 'z', 'w'],
  'b': ['v', 'g', 'h', 'n'],
  'c': ['x', 'd', 'f', 'v'],
  'd': ['s', 'e', 'r', 'f', 'c', 'x'],
  'e': ['w', 's', 'd', 'r'],
  'f': ['d', 'r', 't', 'g', 'v', 'c'],
  'g': ['f', 't', 'y', 'h', 'b', 'v'],
  'h': ['g', 'y', 'u', 'j', 'n', 'b'],
  'i': ['u', 'j', 'k', 'o', 'eight'],
  'j': ['h', 'u', 'i', 'k', 'm', 'n'],
  'k': ['j', 'i', 'o', 'l', 'm'],
  'l': ['k', 'o', 'p', 'ç'],
  'm': ['n', 'j', 'k', 'l'],
  'n': ['b', 'h', 'j', 'm'],
  'o': ['i', 'k', 'l', 'p', 'nine'],
  'p': ['o', 'l', 'ç'],
  'q': ['1', '2', 'w', 'a'],
  'r': ['e', 'd', 'f', 't'],
  's': ['a', 'w', 'e', 'd', 'x', 'z'],
  't': ['r', 'f', 'g', 'y'],
  'u': ['y', 'h', 'j', 'i'],
  'v': ['c', 'f', 'g', 'b'],
  'w': ['q', 'a', 's', 'e'],
  'x': ['z', 's', 'd', 'c'],
  'y': ['t', 'g', 'h', 'u'],
  'z': ['a', 's', 'x'],
  'ç': ['l', 'p']
};

// Common Portuguese words with accent mappings for accent omissions
const ACCENT_WORDS = {
  'não': 'nao',
  'é': 'e',
  'você': 'voce',
  'também': 'tambem',
  'lá': 'la',
  'já': 'ja',
  'está': 'esta',
  'então': 'entao',
  'são': 'sao',
  'olá': 'ola',
  'crédito': 'credito',
  'amanhã': 'amanha'
};

/**
 * Splits a long text paragraph into smaller, natural chat message chunks.
 * Humans usually send thoughts in quick succession instead of blocks.
 */
function splitIntoChunks(text) {
  if (!text) return [];

  // Normalize newlines
  const paragraphs = text.split(/\n+/);
  let chunks = [];

  for (let paragraph of paragraphs) {
    paragraph = paragraph.trim();
    if (!paragraph) continue;

    // Split by sentence boundaries (. ! ?) but not after abbreviations (e.g., "Sr.", "Av.")
    // Keep it simple: split by sentence ends and filter empty chunks
    const sentences = paragraph.split(/(?<=[.!?])\s+/);
    
    let currentChunk = "";
    for (let sentence of sentences) {
      sentence = sentence.trim();
      if (!sentence) continue;

      // If sentence is very short, merge it with the current chunk
      if (currentChunk.length === 0) {
        currentChunk = sentence;
      } else if (currentChunk.length + sentence.length < 120) {
        currentChunk += " " + sentence;
      } else {
        chunks.push(currentChunk);
        currentChunk = sentence;
      }
    }
    if (currentChunk) {
      chunks.push(currentChunk);
    }
  }

  return chunks;
}

/**
 * Calculates human-like dynamic typing delays.
 * @param {string} text - Message text
 * @param {number} wpm - Typing speed in Words Per Minute (default 50)
 * @returns {object} - { thinkingTimeMs, typingTimeMs, totalTimeMs }
 */
function calculateDelay(text, wpm = 50) {
  const wordsCount = text.split(/\s+/).length;
  
  // Calculate average typing speed (50 WPM = ~350-400 characters per minute)
  // Let's use characters instead of words for more granular typing speed
  const charSpeedPerSec = (wpm * 5) / 60; // Average word has 5 chars
  const charCount = text.length;

  let typingTimeMs = (charCount / charSpeedPerSec) * 1000;
  
  // Base thinking delay before starting to type: 1 to 2.5 seconds
  let thinkingTimeMs = 1000 + Math.random() * 1500;

  // Add random human variance (+/- 20%) to typing speed
  const variance = 0.8 + Math.random() * 0.4;
  typingTimeMs = typingTimeMs * variance;

  // Enforce sensible bounds (minimum 1.5 seconds typing, max 12 seconds per chunk)
  typingTimeMs = Math.max(1500, Math.min(12000, typingTimeMs));

  return {
    thinkingTime: Math.round(thinkingTimeMs),
    typingTime: Math.round(typingTimeMs),
    totalTime: Math.round(thinkingTimeMs + typingTimeMs)
  };
}

/**
 * Introduces natural typos and sets up follow-up correction messages.
 * @param {string} text - Input text chunk
 * @param {number} typoProbability - Probability of generating a typo (0 to 1, default 0.15)
 */
function simulateTypos(text, typoProbability = 0.15) {
  if (Math.random() > typoProbability || text.length < 8) {
    return { resultText: text, needsCorrection: false };
  }

  const words = text.split(/\s+/);
  let typoMade = false;
  let wordToCorrect = "";
  let correctedWord = "";
  let typoWord = "";

  // Iterate backwards to make it feel like the user made a typo towards the end and noticed it later
  for (let i = words.length - 1; i >= 0; i--) {
    let word = words[i];
    // Remove punctuation at the end of the word for typing replacement
    const cleanWord = word.replace(/[.,\/#!$%\^&\*;:{}=\-_`~()?]/g, "").toLowerCase();
    
    if (cleanWord.length > 3 && !typoMade) {
      // Option 1: Accent omission (common in Portuguese)
      for (const [accented, plain] of Object.entries(ACCENT_WORDS)) {
        if (word.toLowerCase().includes(accented)) {
          wordToCorrect = word;
          correctedWord = word.replace(new RegExp(accented, 'gi'), accented); // Keep case
          typoWord = word.replace(new RegExp(accented, 'gi'), plain);
          words[i] = typoWord;
          typoMade = true;
          break;
        }
      }

      // Option 2: Keyboard character swap (adjacent keys)
      if (!typoMade && cleanWord.length > 4) {
        // Choose a random character to swap (excluding first and last letters for readability)
        const charIdx = 1 + Math.floor(Math.random() * (cleanWord.length - 2));
        const charToSwap = cleanWord[charIdx];
        const adjacent = KEYBOARD_ADJACENCY[charToSwap];

        if (adjacent && adjacent.length > 0) {
          const replacement = adjacent[Math.floor(Math.random() * adjacent.length)];
          
          wordToCorrect = word;
          correctedWord = word;
          
          // Reconstruct word with swapped character
          const wordChars = word.split('');
          wordChars[charIdx] = replacement;
          typoWord = wordChars.join('');
          
          words[i] = typoWord;
          typoMade = true;
        }
      }
    }
  }

  if (typoMade) {
    const resultText = words.join(" ");
    
    // Choose correction style
    const correctionStyles = [
      `*${correctedWord}`,
      `ops, *${correctedWord}`,
      `quis dizer *${correctedWord}`,
      `*${correctedWord.toLowerCase()}`
    ];
    const correctionMessage = correctionStyles[Math.floor(Math.random() * correctionStyles.length)];

    return {
      resultText,
      needsCorrection: true,
      correctionMessage,
      originalText: text
    };
  }

  return { resultText: text, needsCorrection: false };
}

module.exports = {
  splitIntoChunks,
  calculateDelay,
  simulateTypos
};
