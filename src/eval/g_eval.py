from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

class GEvalResult(BaseModel):
    coherence_score: int = Field(ge=1, le=5, description="Nota de 1 a 5 para a coerência da conversa (fluidez lógica).")
    empathy_score: int = Field(ge=1, le=5, description="Nota de 1 a 5 para o nível de empatia humana demonstrada.")
    humanization_score: int = Field(ge=1, le=5, description="Nota de 1 a 5, sendo 5 indetectável de um humano e 1 um robô óbvio.")
    feedback_notes: str = Field(description="O que o bot precisa melhorar nos próximos rascunhos para parecer mais humano?")

EVAL_PROMPT = """Você é um especialista em avaliações com o framework G-Eval.
Sua tarefa é ler um log de chat entre um Usuário e um Agente de Vendas de WhatsApp e dar notas rigorosas sobre a qualidade humana do agente.
O objetivo principal é que o agente NUNCA soe como uma IA, use poucas mensagens curtas, gírias apropriadas e entenda o contexto."""

def evaluate_conversation(chat_log: str) -> GEvalResult:
    """Roda um G-Eval síncrono sobre um bloco de conversa."""
    llm = ChatOpenAI(model="gpt-4o", temperature=0) # GPT-4o é o padrão ouro para G-Eval
    structured_llm = llm.with_structured_output(GEvalResult)
    
    messages = [
        SystemMessage(content=EVAL_PROMPT),
        HumanMessage(content=f"Avalie a seguinte conversa:\n\n{chat_log}")
    ]
    
    result = structured_llm.invoke(messages)
    return result

if __name__ == "__main__":
    # Exemplo de teste da avaliação
    sample_chat = \"\"\"
    Usuário: Oi, vcs fazem integração com rd station?
    Agente: Opa, td bem?
    Agente: Fazemos sim! É bem tranquilo de conectar.
    Agente: Vc já tem o token deles aí?
    \"\"\"
    
    print("Iniciando G-Eval no chat de exemplo...")
    res = evaluate_conversation(sample_chat)
    print(f"Coerência: {res.coherence_score}/5")
    print(f"Empatia: {res.empathy_score}/5")
    print(f"Humanização: {res.humanization_score}/5")
    print(f"Dica de Melhoria: {res.feedback_notes}")
