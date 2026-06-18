# PRD — LangRápido (Agente de Vendas WhatsApp humanizado)

> Documento vivo. Construído iterativamente a partir de testes reais do agente.
> **Versão:** 0.1 · **Status:** em avaliação · **Data:** 2026-06-18

---

## 1. Visão & objetivo

LangRápido é um agente conversacional de IA para WhatsApp focado em **vender de forma
humanizada** — conduzir o lead da abordagem inicial até a conversão, soando como uma
pessoa real (não um bot), com memória de CRM e fluxos automáticos por intenção.

**Métrica-norte:** taxa de conversão por conversa. **Proxy de qualidade:** quão
"humana" e não-repetitiva a conversa parece (avaliada abaixo).

---

## 2. Estado atual (o que já existe)

| Área | Estado |
|------|--------|
| Backend | FastAPI + LangGraph (drafter → critic → splitter → sender → crm_extractor), SQLite |
| LLM | OpenAI (gpt-4o-mini padrão), chave configurável por env **ou** painel |
| Painel | `/painel` — visão geral, conversas, laboratório, fluxos, personalidade, instâncias, integrações, registros |
| Canais | WhatsApp Cloud API (oficial) **ou** Evolution API (QR) |
| Deploy | Backend na VPS (Easypanel, projeto `jota`, serviço `langrapido`, Docker). Painel espelhado em `langrapido.vercel.app` via proxy reverso |
| Humanização | Split de mensagens por pausa semântica, timing de digitação, estilo espelhado |

Funcionalidades recém-entregues: ver conversas, campo de chave OpenAI no painel,
botão "Conectar instância" (Evolution). Auth: adiado.

---

## 3. Resultados de teste

### Iteração 1 — 2026-06-18

**Ambiente:** testes rodados contra **produção** (VPS) porque o ambiente local do dev
tem `OPENAI_API_KEY=nvapi-…` + `OPENAI_BASE_URL=https://integrate.api.nvidia.com/v1`
(NVIDIA NIM) exportados no profile do shell, que sobrepõem o `.env` do projeto
(`load_dotenv` não força override). Produção não tem esse conflito e funciona.

**Cenário testado:** persona "vendedor de Game Pass", conversa curta.

```
LEAD: eae           → BOT: Qual plataforma você usa para jogar? Assim posso te indicar o plano de Game Pass mais adequado.
LEAD: pc            → BOT: Beleza! O plano de Game Pass para PC é R$29/mês. Você gostaria de saber mais sobre os jogos disponíveis ou alguma outra informação?
LEAD: pc            → BOT: O plano de Game Pass para PC é R$29/mês. Quer saber mais sobre os jogos disponíveis?
LEAD: quanto custa? → BOT: O plano de Game Pass para PC custa R$29/mês. Posso te enviar mais informações sobre os jogos disponíveis?
```

**Avaliação de humanização:** ⚠️ abaixo do ideal.

- ❌ **Repetição** — a frase de fechamento "saber mais sobre os jogos disponíveis"
  apareceu em 3 de 4 respostas. Info de preço repetida quase idêntica.
- ❌ **Formal/longo demais para WhatsApp** — "Você gostaria de saber mais sobre os
  jogos disponíveis ou alguma outra informação?" não é como gente fala no zap.
- ✅ Responde ao conteúdo (pegou "pc", deu preço certo).
- ✅ "Beleza!" — tom informal pontual, bom.
- ⚠️ Não avança a venda: repete pergunta de fechamento em vez de progredir
  (ex.: oferecer link, criar urgência, pedir o passo seguinte).

> Nota: o screenshot original do usuário mostrava repetição mais grave (mesma
> pergunta "Qual plataforma você joga?" duas vezes). Não reproduziu idêntico nesta
> config — provável variância do LLM ou config diferente no momento. O **padrão**
> de repetição, porém, está confirmado.

### Iteração 2 — 2026-06-18 (fix de repetição)

Montado runner local in-process (`D:\Temp\runner.py`) que contorna o env NVIDIA
(parse manual do `.env`, limpa `OPENAI_BASE_URL`/`OPENAI_API_BASE`/`OPENAI_MODEL`).
Permite testar sem tocar produção.

**Fix aplicado:** `src/bot/prompts.py` — regras anti-repetição fortes + "sempre
avançar para o próximo passo concreto" no `_build_auto_prompt` e `_build_custom_prompt`.

**Antes × depois (mesmo cenário Game Pass):**

| Turno | ANTES | DEPOIS |
|-------|-------|--------|
| `eae` | "E aí! Tudo certo?" (não avança) | "Já tem em mente qual plataforma vai usar...?" (avança) |
| `pc` | "Beleza! Você joga no PC. Já pensou em assinar?" | "Perfeito! Plano PC R$29/mês. Posso te enviar o link?" |
| `pc` (repetido) | "Beleza! Você joga no computador. Já pensou em assinar?" ❌ repete | "Entendi que vai assinar para PC. Vou te enviar o link: pag.gamepass/x" ✅ avança |
| `quanto custa?` | "R$29/mês. Tem interesse?" | "R$29/mês. Posso te enviar o link?" |

✅ Repetição eliminada; o bot reconhece input repetido e **avança a venda** (manda link).

**Novo achado (objeção):** no cenário de objeção, "tá caro" foi ignorado — o bot
não trata objeção de preço (não oferece desconto/valor/plano menor). → vira P4.

### Iteração 3 — 2026-06-18 (objeção + personalidade funcional)

Dois fixes em `src/bot/prompts.py`:
- **P4** — regra de tratamento de objeção (reconhecer, reforçar valor/alternativa,
  fazer pergunta que destrava).
- **P6 (novo, grave)** — os controles do painel `formality`, `concision`,
  `emoji_mode`, `commercial_initiative` eram **placebo**: salvos no DB mas nunca
  usados no prompt (só o estilo inferido do lead afetava). Agora cada um vira
  instrução explícita no `_build_auto_prompt`.

**Resultados (runner local):**

| Cenário | Saída | Veredito |
|---------|-------|----------|
| Objeção "tá caro" | "R$29 pode parecer alto, mas tem acesso a vasta biblioteca… que jogos você curte?" | ✅ trata objeção |
| "vou pensar" | "Claro… tem algum jogo que gostaria de jogar?" | ✅ mantém porta aberta |
| FORMAL (alta/sem emoji/curta) | "Sobre o que gostaria de conversar?" / "Legal, você joga no PC. Tem interesse?" | ✅ seco, sem emoji |
| INFORMAL (baixa/emoji/curta) | "Vamos direto ao ponto! …😊" | ✅ contraste claro |
| CUSTOM (gamer raiz) | "Mano, qual é a boa? …Quer fechar essa?" | ✅ tom custom |
| Lead frio ("quem é vc?") | "Sou o Rafa… já tem plataforma em mente?" | ✅ honesto, avança |

A troca de personalidade agora é **real e perceptível** (formal × informal × custom).

---

## 4. Problemas identificados (priorizados)

| # | Severidade | Problema | Onde | Status |
|---|-----------|----------|------|--------|
| P0 | Alta | Respostas repetem frases de fechamento e info entre turnos | drafter | ✅ corrigido (it.2) |
| P1 | Alta | Respostas longas e formais demais para o estilo WhatsApp | prompt/splitter | 🟡 melhorou; reavaliar |
| P2 | Média | Agente não progride a venda (repete fechamento em vez de avançar) | prompt/objetivo | ✅ corrigido (it.2) |
| P3 | Baixa (dev) | Env local NVIDIA sobrepõe `.env` → bot quebra só em dev | `load_dotenv` | 📌 contornado no runner |
| P4 | Média | Não trata objeção de preço ("tá caro" ignorado) | prompt | ✅ corrigido (it.3) |
| P5 | Baixa | Critic é cego ao histórico (defesa 2ª contra repetição) | critic_node | ⬜ aberto |
| P6 | Alta | Controles de personalidade do painel (formality/concision/emoji/iniciativa) eram placebo | prompt | ✅ corrigido (it.3) |

---

## 5. Hipóteses técnicas de root cause (a confirmar)

- **P0 — o crítico não vê o histórico.** `critic_node` recebe apenas a última
  mensagem do lead + o draft atual; **não** recebe as respostas anteriores do bot.
  Logo é impossível ele cumprir o próprio critério "5. repetição: não repete
  perguntas/frases prontas" — ele não tem como saber o que já foi dito.
  → *Fix candidato:* passar um resumo do histórico recente do bot ao crítico, ou
  adicionar um checador de similaridade contra as últimas N respostas.
- **P1 — `target_chars` e prompt.** O prompt pede "cerca de N caracteres ou menos"
  mas não impõe brevidade real; gpt-4o-mini tende ao verboso/corporativo.
  → *Fix candidato:* endurecer o prompt (frases curtas, 1 ideia por mensagem,
  proibir perguntas de fechamento genéricas) e/ou baixar `target_chars`.
- **P2 — objetivo difuso.** Sem um "próximo passo" explícito por estágio, o agente
  estaciona. → *Fix candidato:* incluir estágios de venda no prompt e instruir a
  sempre propor o próximo passo concreto.

---

## 6. Roadmap de melhorias

1. **Confirmar P0** (crítico cego ao histórico) com teste instrumentado.
2. Endurecer prompt do drafter: brevidade WhatsApp, anti-repetição explícita,
   sempre avançar a venda.
3. Dar histórico de respostas do bot ao crítico (ou checador de repetição).
4. Re-testar os mesmos cenários e comparar (antes/depois).
5. Testar troca de personalidade (formal × informal × prompt custom) e medir.
6. Bateria de cenários: objeção de preço, lead frio, lead apressado, lead curioso.

---

## 7. Critérios de "conversível o suficiente" (rascunho)

- [ ] Zero repetição literal de frases entre turnos consecutivos.
- [ ] Mensagens curtas (estilo WhatsApp), 1 ideia por bolha.
- [ ] Sempre propõe um próximo passo concreto (não pergunta genérica).
- [ ] Reconhece o que o lead já disse (sem reperguntar).
- [ ] Tom natural, informal-profissional, sem clichês robóticos.
- [ ] Lida com objeção de preço sem repetir o mesmo argumento.

---

## 8. Backlog de testes (próximas iterações)

- [ ] Troca de personalidade: formalidade baixa × alta; emoji nunca × leve.
- [ ] Prompt custom completo (caminho `_build_custom_prompt`).
- [ ] Objeção: "tá caro", "vou pensar", "não tenho cartão".
- [ ] Lead apressado (mensagens curtas e secas).
- [ ] Fluxos inteligentes (trigger por intenção) — disparo e conteúdo.
- [ ] Extração de CRM (nome, e-mail, orçamento) ao longo da conversa.
