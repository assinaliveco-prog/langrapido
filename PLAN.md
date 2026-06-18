# Plano de Desenvolvimento: Agente WhatsApp com LangGraph

## Arquitetura Definida
- **Linguagem:** Python
- **Framework Web:** FastAPI (para receber Webhooks da Meta)
- **Framework de Agente:** LangGraph + LangChain
- **LLM:** OpenAI (GPT-4o-mini ou superior)
- **Integração WhatsApp:** Meta Cloud API (Oficial)

## Fases do Projeto

### Fase 1: Setup e Infraestrutura Base (Em Progresso)
- [x] Estrutura de diretórios e dependências (`requirements.txt`)
- [x] Arquivo `.env.example` para chaves de API
- [ ] Servidor FastAPI básico com validação de Webhook do WhatsApp

### Fase 2: O Grafo do Agente (LangGraph)
- [ ] Definir o **State** (Mensagens, Feedbacks internos, Contagem de revisões)
- [ ] **Node Drafter:** Gera rascunho de resposta extremamente humano.
- [ ] **Node Critic:** Avalia o rascunho com rigor, retornando feedback caso a resposta seja robótica ou incorreta.
- [ ] **Edges:** Roteamento condicional (Aprovado vs Precisa Revisão).

### Fase 3: Integração Meta API
- [ ] Serviço HTTP (`httpx`) para enviar mensagens de texto.
- [ ] Envio de status de "Lida" (mark as read).
- [ ] Envio de status "Digitando..." para aumentar humanização.

### Fase 4: Avaliação com G-Eval
- [ ] Implementar framework G-Eval assíncrono.
- [ ] Prompt de avaliação estruturado analisando Coerência (Coherence), Empatia (Empathy), Engajamento (Engagement).
- [ ] Salvar logs das avaliações.

### Fase 5: Memória e Humanização Avançada
- [ ] Persistência de memória (Checkpointer) usando banco de dados ou memória local para manter contexto entre mensagens.
- [ ] Variação de tempo de resposta baseada no tamanho da mensagem enviada pelo usuário (Time delays contextuais).
