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
        f"- NUNCA repita cumprimentos ou saudações (como 'Oi', 'Olá', 'Tudo bem?', 'E aí?', 'Como vai?') se a conversa já começou e há mensagens anteriores no histórico. Responda diretamente ao assunto principal da última mensagem.\n"
        f"- JAMAIS repita uma frase, pergunta ou resposta que você já enviou antes; se o contato repetir algo que já disse, reconheça e AVANCE para o próximo passo concreto, sem repetir sua resposta anterior.\n\n"
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

    formality_map = {
        "baixa": "Tom informal e descontraído, como uma conversa entre amigos no WhatsApp.",
        "media": "Tom natural e cordial, nem engessado nem cheio de gírias.",
        "alta": "Tom profissional e respeitoso, sem gírias.",
    }
    concision_map = {
        "curta": "Seja muito breve: 1 a 2 frases curtas por mensagem.",
        "equilibrada": "Seja objetivo, sem encher linguiça.",
        "detalhada": "Pode dar mais detalhes quando ajudar, sem ser prolixo.",
    }
    emoji_map = {
        "nunca": "Não use emojis.",
        "espelhar": "Use emojis apenas se o contato usar, com moderação.",
        "leve": "Use emojis leves e ocasionais para soar natural.",
    }
    formality_line = formality_map.get(settings.get("formality", "media"), formality_map["media"])
    concision_line = concision_map.get(settings.get("concision", "equilibrada"), concision_map["equilibrada"])
    emoji_line = emoji_map.get(settings.get("emoji_mode", "espelhar"), emoji_map["espelhar"])
    initiative = settings.get("commercial_initiative", 50)
    if initiative >= 70:
        initiative_line = "Seja proativo: conduza ativamente a conversa para o fechamento."
    elif initiative <= 30:
        initiative_line = "Seja consultivo: priorize entender a necessidade, sem pressionar a venda."
    else:
        initiative_line = "Equilibre escuta e condução comercial."

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
- JAMAIS repita uma frase, pergunta ou resposta que você já enviou antes nesta conversa; varie sempre as palavras;
- se o contato repetir uma informação que já deu (ex.: dizer "pc" de novo), NÃO repita sua resposta anterior — reconheça brevemente e AVANCE para o próximo passo;
- sempre conduza para um próximo passo concreto (pedir o dado que falta, enviar o link/valor, propor o fechamento); nunca encerre com a mesma pergunta genérica de fechamento mais de uma vez;
- ao receber objeção (ex.: "tá caro", "vou pensar", "não sei"), NUNCA ignore nem apenas concorde: reconheça, reforce um benefício concreto ou ofereça alternativa (plano menor, vantagem), e faça uma pergunta que destrave a decisão;
- não invente preço, prazo, disponibilidade, política ou dado do negócio;
- não alegue ser humano e não minta sobre sua identidade se perguntarem;
- não use introduções genéricas, encerramentos automáticos ou entusiasmo exagerado;
- NUNCA repita cumprimentos ou saudações (como 'Oi', 'Olá', 'Tudo bem?', 'E aí?') se a conversa já começou e já houve mensagens enviadas anteriormente;
- não use markdown de títulos ou listas longas;
- devolva somente a mensagem destinada ao contato.

Tom e estilo (definidos por você):
- {formality_line}
- {concision_line}
- {emoji_line}
- {initiative_line}
Formalidade observada no contato: {style.get('formality', 'medium')} (ajuste o tom a ela quando fizer sentido).
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
