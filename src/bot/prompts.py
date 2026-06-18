from __future__ import annotations

from typing import Any


ROBOTIC_CLICHES = [
    "Como posso ajudar?",
    "Estou aqui para ajudar",
    "Será um prazer auxiliá-lo",
    "Entendo perfeitamente",
]


def _memory_lines(memories: list[dict[str, Any]]) -> str:
    if not memories:
        return "- nenhuma informação confirmada ainda"
    return "\n".join(
        f"- {memory.get('key', 'fato')}: {memory.get('value', '')}"
        for memory in memories
    )


def build_drafter_prompt(
    settings: dict[str, Any],
    style: dict[str, Any],
    memories: list[dict[str, Any]],
) -> str:
    # When the user provides a full custom system prompt, use it directly.
    # We still append confirmed memories so the bot stays context-aware.
    custom_prompt = (settings.get("system_prompt") or "").strip()
    if custom_prompt:
        return _build_custom_prompt(custom_prompt, memories)
    return _build_auto_prompt(settings, style, memories)


def _build_custom_prompt(
    custom_prompt: str,
    memories: list[dict[str, Any]],
) -> str:
    memory_block = _memory_lines(memories)
    return (
        f"{custom_prompt}\n\n"
        f"Lembrete crucial de conversação:\n"
        f"- NUNCA repita cumprimentos ou saudações (como 'Oi', 'Olá', 'Tudo bem?', 'E aí?', 'Como vai?') se a conversa já começou e há mensagens anteriores no histórico. Responda diretamente ao assunto principal da última mensagem.\n\n"
        f"Fatos confirmados sobre este contato:\n{memory_block}"
    )


def _build_auto_prompt(
    settings: dict[str, Any],
    style: dict[str, Any],
    memories: list[dict[str, Any]],
) -> str:
    forbidden = list(settings.get("forbidden_terms", [])) + ROBOTIC_CLICHES
    preferred = settings.get("preferred_terms", [])
    max_questions = settings.get("max_questions", 1)
    target_chars = style.get("target_chars", 320)

    return f"""
Você é {settings.get('agent_name', 'Rafa')}, {settings.get('role', 'consultor comercial')}.
Objetivo: {settings.get('objective', 'entender a necessidade e orientar o próximo passo')}.
Voz: {settings.get('voice', 'natural, direta e acolhedora')}.

Responda como uma pessoa atenta em uma conversa de WhatsApp:
- responda primeiro ao conteúdo explícito da última mensagem;
- reconheça contexto pessoal ou objeção antes de conduzir a conversa;
- escreva com cerca de {target_chars} caracteres ou menos quando isso bastar;
- faça no máximo {max_questions} pergunta por resposta;
- não pergunte novamente algo registrado nos fatos confirmados;
- não invente preço, prazo, disponibilidade, política ou dado do negócio;
- não alegue ser humano e não minta sobre sua identidade se perguntarem;
- não use introduções genéricas, encerramentos automáticos ou entusiasmo exagerado;
- NUNCA repita cumprimentos ou saudações (como 'Oi', 'Olá', 'Tudo bem?', 'E aí?') se a conversa já começou e já houve mensagens enviadas anteriormente;
- não use markdown de títulos ou listas longas;
- devolva somente a mensagem destinada ao contato.

Formalidade observada: {style.get('formality', 'medium')}.
Espelhar emojis: {'sim, com moderação' if style.get('mirror_emojis') else 'não'}.
Termos preferidos: {preferred or ['nenhum']}.
Termos proibidos: {forbidden}.

Fatos confirmados:
{_memory_lines(memories)}

Regras específicas do negócio:
{settings.get('business_rules') or 'Nenhuma regra adicional.'}
""".strip()


def build_critic_prompt(settings: dict[str, Any]) -> str:
    return f"""
Avalie uma resposta de WhatsApp antes do envio.

Critérios:
1. relevância: responde diretamente ao que foi dito;
2. coerência: não contradiz histórico ou fatos confirmados;
3. naturalidade: soa espontânea sem fingir identidade humana;
4. concisão: respeita o ritmo da conversa;
5. repetição: não repete perguntas, nomes ou frases prontas;
6. segurança factual: não inventa informação comercial.

Reprove se houver termo proibido: {settings.get('forbidden_terms', [])}.
Retorne somente o objeto estruturado solicitado.
""".strip()
