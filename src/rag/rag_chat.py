"""Orquestra o RAG: pergunta -> retriever -> LLM local -> resposta fundamentada com fontes.

Reutiliza o cliente/LLM e o log de rastreabilidade já existentes em
`src.ai.local_llm_handler`. Regra de ouro: se a informação não está no contexto recuperado,
a resposta é "não encontrei" — o modelo NÃO deve inventar.
"""

from src.ai import local_llm_handler
from src.config.constants import COL_ID_DISCURSO
from src.config.settings import get_rag_config
from src.rag import retriever
from src.utils.logger import get_logger

logger = get_logger(__name__)

MSG_SEM_RESULTADO = (
    "Não encontrei nada sobre isso nos discursos indexados. "
    "Verifique se os discursos do período foram coletados e indexados."
)


def _montar_prompt(contexto: str, pergunta: str) -> str:
    # f-string direta (não .format) para não colidir com eventuais chaves no contexto.
    return f"""Você é um assistente que responde perguntas sobre discursos de senadores brasileiros.
Use APENAS as informações do CONTEXTO abaixo. Se a resposta não estiver no contexto, diga que
não encontrou nos discursos indexados — NÃO invente. Sempre cite a fonte pelo ref entre
colchetes (ex.: [D1]) ao final de cada afirmação; use só refs que aparecem no contexto.

CONTEXTO:
{contexto}

PERGUNTA:
"{pergunta}"

RESPOSTA (em português, fundamentada e com citações [Dn]):"""


def responder(pergunta: str, k: int | None = None) -> dict:
    """Responde à `pergunta` via RAG. Retorna `{"resposta": str, "fontes": list[dict]}`."""
    k = k or get_rag_config()["top_k"]
    contexto, fontes = retriever.recuperar(pergunta, k)

    if not fontes:
        return {"resposta": MSG_SEM_RESULTADO, "fontes": []}

    prompt = _montar_prompt(contexto, pergunta)
    try:
        resp = local_llm_handler.client.chat.completions.create(
            model=local_llm_handler._CFG["model"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        resposta = resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Erro ao gerar resposta RAG: {e}", exc_info=True)
        return {
            "resposta": "Desculpe, tive uma dificuldade momentânea ao gerar a resposta. "
                        "Verifique se o LM Studio está servindo o modelo e tente novamente.",
            "fontes": fontes,
        }

    # Rastreabilidade: reaproveita o trace do chat (origem própria para segmentar keyword x RAG).
    refs = [f["ref"] for f in fontes]
    codigos = [str(f.get(COL_ID_DISCURSO, "")) for f in fontes]
    local_llm_handler._registrar_trace(
        pergunta, refs, resposta, origem="discurso_rag", fontes_codigos=codigos
    )
    return {"resposta": resposta, "fontes": fontes}
