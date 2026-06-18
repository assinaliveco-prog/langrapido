# LangRápido — Consolidação, painel operacional e humanização

Data: 17 de junho de 2026  
Status: aprovado para planejamento

## 1. Objetivo

Transformar o diretório atual em um produto único, coerente e operável para atendimento comercial pelo WhatsApp. O produto principal será a implementação Python com FastAPI e LangGraph.

O resultado deve:

- substituir o painel administrativo atual por uma interface operacional refinada e responsiva;
- centralizar configuração, conversas, CRM, testes e diagnóstico;
- tornar as respostas mais naturais por contexto e adaptação, sem depender de erros ortográficos artificiais;
- preservar memória relevante por contato;
- permitir testes locais seguros antes de enviar mensagens reais;
- remover a divergência funcional entre os backends Python e Node.

## 2. Estado atual

O projeto contém duas implementações independentes:

1. Python/FastAPI/LangGraph, conectado ao webhook e à API oficial do WhatsApp;
2. Node/Express/Gemini, contendo um simulador, CRM em JSON e um painel visual separado.

Cada implementação possui banco, configuração, prompts e fluxo próprios. Isso cria comportamentos diferentes entre simulação e produção, duplica manutenção e impede que o painel represente o estado real do agente.

O painel Python atual edita somente três campos de personalidade. Ele não permite acompanhar conversas, testar respostas, inspecionar memória, visualizar o CRM ou diagnosticar integrações.

## 3. Decisão arquitetural

FastAPI será o servidor único da aplicação. LangGraph continuará responsável pelo fluxo do agente. SQLite será a fonte de verdade para configuração operacional, contatos, conversas, mensagens, memória e avaliações.

O simulador passará a chamar o mesmo serviço de geração usado pelo webhook. Nenhum prompt ou comportamento existirá apenas no modo de teste.

O código Node permanecerá temporariamente como referência durante a migração. Depois que seus recursos úteis forem absorvidos e verificados, será movido para uma área de legado ou removido em uma etapa explícita e segura.

## 4. Módulos e responsabilidades

### 4.1 API

Responsável por:

- servir o painel;
- expor configuração e estado operacional;
- listar contatos e conversas;
- executar simulações;
- receber e validar webhooks;
- criar tarefas de processamento assíncrono;
- retornar erros em formato consistente.

Rotas administrativas e rotas públicas do webhook ficarão separadas por módulos.

### 4.2 Persistência

O SQLite armazenará:

- configurações do agente;
- contatos;
- conversas;
- mensagens recebidas e enviadas;
- fatos de memória;
- estado do CRM;
- avaliações do crítico;
- eventos e falhas de integração.

Migrações serão idempotentes. A inicialização não poderá apagar dados existentes.

### 4.3 Motor do agente

O fluxo será:

1. receber e persistir a mensagem;
2. carregar histórico recente, perfil e memória relevante;
3. identificar intenção, estágio comercial e estilo de comunicação;
4. elaborar uma resposta;
5. avaliar naturalidade, relevância, concisão, coerência e repetição;
6. revisar quando necessário, com limite rígido;
7. dividir a resposta em mensagens somente quando houver uma pausa semântica natural;
8. calcular pausas de leitura e digitação;
9. enviar ou retornar a resposta simulada;
10. atualizar memória, CRM e métricas.

Cada nó terá uma responsabilidade clara e um contrato testável.

### 4.4 Serviço do WhatsApp

Responsável exclusivamente por:

- validar se as credenciais necessárias existem;
- marcar mensagens como lidas;
- enviar mensagens;
- registrar respostas e erros da Meta;
- aplicar timeout e tratamento de falhas.

O modo de simulação não chamará a API da Meta.

## 5. Humanização

Humanização será tratada como qualidade conversacional, não como ruído tipográfico.

### 5.1 Adaptação

O agente adaptará:

- tamanho da resposta ao tamanho e urgência da mensagem recebida;
- formalidade ao vocabulário do contato e às regras do negócio;
- uso de emojis à configuração e ao padrão da conversa;
- ritmo à complexidade da resposta;
- quantidade de perguntas ao estágio da conversa;
- abordagem comercial aos sinais de interesse e resistência.

### 5.2 Continuidade

Antes de perguntar algo, o agente verificará se a informação já está no histórico ou na memória. Fatos confirmados não serão inventados nem sobrescritos por inferências fracas.

A memória será dividida em:

- dados explícitos: nome, contato, orçamento e preferências declaradas;
- contexto comercial: interesse, objeções, produto e próximo passo;
- preferências conversacionais: formalidade, concisão e canal preferido.

### 5.3 Naturalidade

O agente deverá:

- reconhecer o conteúdo principal antes de conduzir a venda;
- responder diretamente ao que foi perguntado;
- evitar introduções e encerramentos automáticos;
- evitar entusiasmo desproporcional;
- evitar repetir o nome do contato;
- evitar sequências de perguntas;
- usar uma ideia principal por mensagem;
- manter consistência de voz sem repetir frases prontas.

Erros de digitação serão desabilitados por padrão. Quando habilitados, terão frequência baixa e jamais afetarão nomes, valores, links, contatos ou informações sensíveis.

### 5.4 Crítico

O crítico retornará uma avaliação estruturada com:

- aprovação;
- motivos objetivos;
- problemas detectados;
- instrução curta de revisão;
- pontuações de naturalidade, relevância, concisão, coerência e repetição.

O limite inicial será de duas revisões. Atingido o limite, o sistema escolherá a melhor versão válida e registrará o motivo, sem loop infinito.

## 6. Painel

### 6.1 Direção visual

A interface terá estética operacional refinada:

- fundo grafite quente;
- superfícies sólidas e hierarquia por contraste;
- verde usado apenas para estados positivos e ações principais;
- âmbar e vermelho reservados para atenção e falha;
- tipografia de interface legível com uma fonte de destaque discreta;
- bordas, sombras e animações contidas;
- ícones vetoriais consistentes;
- nenhum emoji decorativo;
- nenhum gradiente roxo ou glassmorphism genérico.

O painel será responsivo e utilizável com teclado. Foco, contraste, rótulos e estados deverão ser perceptíveis.

### 6.2 Navegação

A navegação lateral conterá:

- Visão geral;
- Conversas;
- Laboratório;
- Personalidade;
- Integrações;
- Registros.

Em telas estreitas, a navegação será recolhida sem ocultar funções essenciais.

### 6.3 Visão geral

Mostrará:

- estado da API do WhatsApp;
- estado do provedor de IA;
- modelo ativo;
- conversas abertas;
- mensagens processadas;
- tempo médio de resposta;
- falhas recentes;
- atalhos para testar o agente e editar personalidade.

Métricas sem dados deverão exibir estado vazio, não valores fictícios.

### 6.4 Conversas

Layout de três áreas:

- lista pesquisável de contatos;
- conversa ativa;
- contexto do contato e CRM.

A conversa exibirá origem, horário, estado de envio e separação correta das mensagens. O painel contextual mostrará dados capturados, resumo, interesse, objeções, memória e próximo passo.

### 6.5 Estúdio de personalidade

Controles:

- nome e papel do atendente;
- objetivo principal;
- descrição da voz;
- nível de formalidade;
- concisão;
- uso de emojis;
- iniciativa comercial;
- frequência máxima de perguntas;
- divisão de mensagens;
- erros de digitação opcionais;
- termos preferidos;
- termos proibidos;
- regras específicas do negócio.

Alterações poderão ser testadas antes de salvar. Campos técnicos não serão misturados com escolhas de comportamento.

### 6.6 Laboratório

Permitirá:

- escolher ou criar um perfil de teste;
- iniciar uma conversa isolada;
- enviar mensagens manualmente;
- simular respostas do lead;
- visualizar rascunho, avaliação e mensagens finais;
- comparar a resposta antes e depois da revisão;
- limpar somente a sessão de teste.

O laboratório não poderá enviar mensagens reais.

### 6.7 Integrações e registros

A tela de integrações mostrará presença e validade operacional das configurações sem revelar segredos.

Os registros mostrarão eventos filtráveis de:

- webhook;
- geração;
- crítica;
- envio;
- persistência;
- falhas.

## 7. APIs administrativas

O contrato mínimo incluirá:

- `GET /api/health`
- `GET /api/dashboard`
- `GET /api/settings`
- `PUT /api/settings`
- `GET /api/contacts`
- `GET /api/contacts/{id}`
- `GET /api/conversations/{id}/messages`
- `POST /api/lab/sessions`
- `POST /api/lab/sessions/{id}/messages`
- `DELETE /api/lab/sessions/{id}`
- `GET /api/events`

Os formatos de resposta terão tipos explícitos em Pydantic. Segredos nunca serão retornados ao navegador.

## 8. Falhas e segurança operacional

- Webhooks serão validados e responderão rapidamente.
- Mensagens recebidas serão persistidas antes da geração.
- Repetições do mesmo identificador da Meta serão ignoradas de forma idempotente.
- Erros do provedor de IA não apagarão histórico.
- Erros de envio permanecerão visíveis e poderão ser diagnosticados.
- Credenciais não serão armazenadas ou exibidas em texto aberto pelo painel.
- Logs não incluirão tokens, chaves ou conteúdo sensível desnecessário.
- Rotas administrativas serão estruturadas para receber autenticação antes de exposição pública.

## 9. Migração

1. ampliar o esquema SQLite sem apagar a tabela de personalidade atual;
2. criar uma camada de repositório;
3. extrair serviços de agente e WhatsApp;
4. criar as APIs administrativas;
5. substituir o HTML atual pelo novo painel;
6. integrar o laboratório ao mesmo motor do webhook;
7. migrar recursos úteis do simulador Node;
8. verificar equivalência funcional;
9. arquivar ou remover o legado em uma mudança separada.

## 10. Testes e critérios de aceite

### Persistência

- inicialização repetida mantém dados;
- configurações são persistidas e recuperadas;
- contatos, conversas e mensagens preservam relacionamentos;
- mensagens duplicadas da Meta não são processadas novamente.

### Agente

- contexto de uma conversa permanece entre turnos;
- perguntas já respondidas não são repetidas;
- o ciclo de revisão respeita o limite;
- mensagens curtas não são divididas sem necessidade;
- dados críticos não recebem erros artificiais;
- o modo de laboratório não chama o WhatsApp;
- falhas do modelo são registradas sem perda da entrada.

### API

- contratos Pydantic são válidos;
- erros usam códigos HTTP e mensagens consistentes;
- segredos não aparecem nas respostas;
- rotas do painel funcionam sem credenciais reais no modo local.

### Interface

- todas as áreas previstas são navegáveis;
- carregamento, vazio, erro, sucesso e estado desabilitado estão representados;
- desktop e viewport reduzido não apresentam sobreposição ou conteúdo inacessível;
- formulário pode ser operado por teclado;
- a conversa permanece legível com mensagens longas;
- os dados visíveis correspondem ao backend real.

### Qualidade conversacional

Um conjunto fixo de cenários avaliará:

- pergunta direta de preço;
- contato impaciente;
- contato desconfiado;
- objeção;
- informação pessoal;
- retomada de conversa;
- informação já fornecida;
- pedido fora do escopo comercial.

As respostas serão verificadas quanto a relevância, naturalidade, concisão, coerência, continuidade e ausência de frases robóticas definidas.

## 11. Fora do escopo inicial

- campanhas em massa;
- múltiplas organizações;
- cobrança;
- construtor visual de fluxos;
- envio de mídia;
- treinamento ou ajuste fino de modelos;
- substituição da API oficial do WhatsApp por automação não oficial.

## 12. Evidência de conclusão

O trabalho será considerado concluído somente quando:

- o FastAPI for a implementação principal e única em execução;
- o novo painel consumir dados reais desse backend;
- laboratório e webhook compartilharem o mesmo motor;
- configurações, memória, CRM e conversas persistirem em SQLite;
- os testes automatizados relevantes passarem;
- a interface for verificada no navegador em desktop e tela reduzida;
- cenários conversacionais demonstrarem adaptação e continuidade;
- o legado Node não permanecer como uma segunda aplicação ativa e ambígua.
