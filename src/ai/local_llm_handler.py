from openai import OpenAI
import json
import re
import unicodedata
import streamlit as st
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config.settings import get_local_llm_config
from src.config.constants import COL_ID_DISCURSO, MAX_FONTES_PROMPT, MAX_CHARS_CONTEXTO_PROMPT

_CFG = get_local_llm_config()
client = OpenAI(base_url=_CFG["base_url"], api_key=_CFG["api_key"])

# Caminho do log estruturado de rastreabilidade (uma linha JSON por consulta).
_TRACE_PATH = Path(__file__).resolve().parents[2] / "logs" / "qa_trace.jsonl"

# Colunas expostas como "fonte" na interface e no trace, quando presentes.
_COLUNAS_FONTE = [COL_ID_DISCURSO, "Data", "Parlamentar", "Partido", "Tema", "Resumo"]

# Stopwords mínimas para extrair termos úteis da pergunta no retrieval.
_STOPWORDS = {
    "qual", "quais", "quem", "como", "onde", "quando", "porque", "por", "que", "para",
    "sobre", "dos", "das", "uma", "uns", "umas", "com", "sem", "the", "and", "mais",
    "menos", "foi", "são", "sao", "tem", "têm", "teve", "está", "esta", "este", "esse",
    "essa", "isso", "aqui", "ali", "seu", "sua", "nos", "nas", "ele", "ela", "eles",
    "elas", "discurso", "discursos", "parlamentar", "parlamentares", "senado", "senador",
}


_ANALISE_SCHEMA_EXEMPLO = {
    "parlamentar": "",
    "partido": "",
    "estado": "",
    "agenda_politica": "",
    "tema_principal": "",
    "resumo": "",
    "posicionamento_governo": "",
    "tom_politico": "",
    "atores_mencionados": [],
}


def _extract_first_json_object(text: str) -> str:
    if not text:
        return ""
    cleaned = text.strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return ""
    return cleaned[start : end + 1]


def _default_insuficiente() -> dict:
    d = dict(_ANALISE_SCHEMA_EXEMPLO)
    d.update(
        {
            "parlamentar": "não identificado",
            "partido": "não identificado",
            "estado": "não identificado",
            "agenda_politica": "outros",
            "tema_principal": "não identificado",
            "resumo": "conteúdo insuficiente",
            "posicionamento_governo": "indeterminado",
            "tom_politico": "neutro",
            "atores_mencionados": [],
        }
    )
    return d


def _coerce_analise_payload(payload: object) -> dict:
    if not isinstance(payload, dict):
        return _default_insuficiente()
    out = dict(_ANALISE_SCHEMA_EXEMPLO)

    for k in _ANALISE_SCHEMA_EXEMPLO.keys():
        if k in payload:
            out[k] = payload[k]

    # Normalizações leves
    if not isinstance(out.get("atores_mencionados"), list):
        out["atores_mencionados"] = []
    else:
        out["atores_mencionados"] = [str(x).strip() for x in out["atores_mencionados"] if x and str(x).strip()][:5]

    for k in ["parlamentar", "partido", "estado", "agenda_politica", "tema_principal", "resumo", "posicionamento_governo", "tom_politico"]:
        val = out.get(k, "")
        out[k] = (str(val).strip() if val else "não identificado")

    # Regra: se foi explicitamente "conteúdo insuficiente" no payload, retorna defaults
    if payload.get("resumo", "").lower() in ["conteúdo insuficiente", "conteudo insuficiente"]:
        return _default_insuficiente()

    return out


def _build_prompt_analise_discurso(texto: str) -> str:
    return f"""
Você é um cientista político especializado em análise de discursos parlamentares brasileiros e análise de linguagem política.

Raciocine internamente para garantir consistência, mas NÃO mostre seu raciocínio.

Objetivos da análise:
- Identificar a agenda política do discurso usando uma categoria fixa.
- Identificar o tema principal do discurso.
- Produzir um resumo claro e objetivo.
- Identificar o posicionamento político em relação ao governo.
- Identificar o tom político do discurso.
- Extrair atores políticos ou institucionais mencionados.
- Identificar automaticamente o parlamentar, partido e estado se essas informações estiverem presentes no texto.

Categorias fixas de agenda política (escolha apenas 1):

economia - créditos, financiamentos, impostos, câmbio, PIB, mercado, investimentos, setor privado
saúde - SUS, medicamentos, hospitais, pandemia, vacinação, doenças, saúde pública
educação - escolas, universidades, ensino, pesquisa científica, bolsas de estudo
segurança pública - polícia, crime, violência, presídios, segurança pessoal
infraestrutura - rodovias, ferrovias, portos, aeroportos, água, saneamento, energia, telecomunicações
meio ambiente - desmatamento, poluição, mudanças climáticas, sustentabilidade, preservação
agricultura - produção agrícola, agropecuária, pecuária, fertilizantes, subsídios agrícolas
ciência e tecnologia - inovação, pesquisa, tecnologia, startups
direitos sociais - pobreza, desigualdade, programas sociais, seguro desemprego
política institucional - reforma política, poder judiciário, poder legislativo, constituição
relações internacionais - diplomacia, comércio exterior, acordos bilaterais, organismos internacionais
administração pública - reforma administrativa, funcionalismo público, orçamento
justiça e legislação - leis, regulamentações, direitos legais, processos judiciais
outros - não se encaixa nas categorias acima

Posicionamento em relação ao governo (escolha apenas 1):
apoio ao governo, oposição ao governo, posição institucional, neutro / informativo, indeterminado

Tom político (escolha apenas 1):
crítico, elogioso, defensivo, neutro

Regras obrigatórias:
- Não invente informações que não estejam no texto.
- Se alguma informação não puder ser identificada, retorne "não identificado".
- O resumo deve ter no máximo 2 frases.
- O tema principal deve ter no máximo 5 palavras e deve ser baseado no ASSUNTO PRINCIPAL, não em palavras-chave isoladas.
- Extraia no máximo 5 atores mencionados.
- Se o discurso for muito curto para análise adequada, retorne exatamente "conteúdo insuficiente" no campo "resumo".
- IMPORTANTE: Identifique o tema baseado no CONTEXTO E OBJETIVO PRINCIPAL do texto, não apenas em palavras isoladas.

Estrutura obrigatória da resposta:
- Responda EXCLUSIVAMENTE em JSON VÁLIDO (sem Markdown, sem texto extra).
- Use exatamente estas chaves:
{json.dumps(_ANALISE_SCHEMA_EXEMPLO, ensure_ascii=False)}

Discurso a ser analisado (texto bruto):
<<DISCURSO>>
{texto}
<<FIM>>
"""


def analisar_discurso_struct(texto: str) -> dict:
    """Analisa um discurso com o LLM local e retorna um dict (robusto a respostas fora do formato)."""
    if not texto or len(texto.strip()) < 40:
        return _default_insuficiente()

    prompt = _build_prompt_analise_discurso(texto)

    try:
        response = client.chat.completions.create(
            model=_CFG["model"],
            messages=[
                {"role": "system", "content": "Você responde apenas JSON válido, sem texto extra."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        text = response.choices[0].message.content.strip()
    except Exception:
        return _default_insuficiente()

    raw = _extract_first_json_object(text)
    if not raw:
        return _default_insuficiente()

    try:
        payload = json.loads(raw)
    except Exception:
        return _default_insuficiente()

    return _coerce_analise_payload(payload)


def analisar_discurso(texto: str) -> str:
    """Compat: retorna a análise como string JSON."""
    return json.dumps(analisar_discurso_struct(texto), ensure_ascii=False)


def classificar_tema_local(resumo: str, temas: list[str]) -> str:
    """Classifica um resumo em um tema da lista usando palavras-chave."""
    palavras_chave = {
        "Educação": ["educação", "ensino", "escola", "universidade", "aluno", "professor", "bolsa", "pesquisa", "ciência", "tecnologia", "inovação", "acadêmico"],
        "Saúde": ["saúde", "sus", "medicamento", "hospital", "médico", "doença", "vacinação", "pandemia", "enfermidade", "clínico"],
        "Economia": ["economia", "crédito", "financiamento", "imposto", "câmbio", "pib", "investimento", "setor privado", "mercado", "inflação", "operação de crédito"],
        "Segurança": ["segurança pública", "polícia", "crime", "violência", "prisão", "criminalidade", "delegacia", "criminal"],
        "Infraestrutura": ["rodovia", "ferrovia", "porto", "aeroporto", "saneamento", "energia", "água", "construção", "obra", "resiliência", "manutenção"],
        "Meio Ambiente": ["meio ambiente", "desmatamento", "poluição", "climática", "sustentabilidade", "preservação", "ecologia", "floresta", "carbono"],
        "Direitos Humanos": ["direitos humanos", "direito", "liberdade", "igualdade", "dignidade", "minorias", "discriminação", "humano"],
        "Trabalho": ["trabalho", "emprego", "labor", "agricultura", "agropecuária", "produtor", "sindicato", "trabalhador", "rural"],
        "Política": ["política", "congresso", "senado", "câmara", "governo", "poder", "instituição", "legislação", "lei", "reforma", "parlamentar"],
        "Relações Exteriores": ["relações exteriores", "diplomacia", "internacional", "exterior", "país", "comércio exterior", "acordo", "embaixada"],
        "Cultura": ["cultura", "arte", "música", "cinema", "patrimônio", "cultural", "artista", "festival"],
    }

    texto_lower = resumo.lower()
    contagem = {}

    for tema, palavras in palavras_chave.items():
        contagem[tema] = sum(1 for palavra in palavras if palavra in texto_lower)

    tema_vencedor = max(contagem, key=contagem.get)

    if contagem[tema_vencedor] > 0:
        from src.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info(f"Tema identificado: {tema_vencedor} (correspondências: {contagem[tema_vencedor]})")
        return tema_vencedor

    from src.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Classificado como: Outros")
    return "Outros"


def explicar_votacao_local(descricao_materia: str, ementa: str, tipo_votacao: str, resultado: str) -> str:
    """Explica uma matéria de votação de forma clara e acessível."""
    prompt = f"""
Você é um especialista em legislação brasileira explicando para um cidadão leigo o que significa uma votação no Senado.

Matéria: {descricao_materia}
Ementa: {ementa}
Tipo de Votação: {tipo_votacao}
Resultado: {resultado}

Forneça uma explicação clara e concisa (3-4 frases) que inclua:
1. O que é esta matéria em linguagem simples
2. O que significa o tipo de votação utilizado
3. O resultado e sua importância

Seja objetivo e evite jargão técnico desnecessário.
"""

    try:
        from src.utils.logger import get_logger
        logger = get_logger(__name__)

        response = client.chat.completions.create(
            model=_CFG["model"],
            messages=[
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        explicacao = response.choices[0].message.content.strip()
        logger.info(f"Explicação de votação gerada com sucesso")
        return explicacao
    except Exception as e:
        from src.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"Erro ao explicar votação: {str(e)}", exc_info=True)
        return "Desculpe, não consegui gerar uma explicação no momento. Tente novamente."


def _normalizar(texto: str) -> str:
    """Minúsculas + remoção de acentos, para casar termos independente de acentuação."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sem_acento.lower()


# Colunas padrão de busca para o retrieval de discursos.
_COLUNAS_BUSCA_PADRAO = ["Resumo", "Parlamentar", "Tema", "Partido"]


def _selecionar_fontes(
    df: pd.DataFrame,
    pergunta: str,
    limite: int = 40,
    colunas_busca: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Recupera as fontes relevantes à pergunta (retrieval por palavra-chave).

    Retorna o subconjunto que será efetivamente injetado no prompt — garantindo que
    as fontes exibidas/logadas correspondam ao contexto usado pelo modelo. Os registros
    são ranqueados pelo número de termos distintos da pergunta que casam (busca
    insensível a acento/caixa); empata-se pela ordem original. Se nenhum registro casar,
    devolve a amostra geral (até `limite`).

    `colunas_busca` permite reutilizar o retrieval para outras bases (ex.: votos), com
    fallback nas colunas padrão de discursos.
    """
    if df.empty:
        return df

    termos = {t for t in re.findall(r"\w{4,}", _normalizar(pergunta)) if t not in _STOPWORDS}

    if termos:
        candidatas = colunas_busca if colunas_busca is not None else _COLUNAS_BUSCA_PADRAO
        campos = [c for c in candidatas if c in df.columns]
        if campos:
            texto_busca = df[campos].fillna("").astype(str).agg(" ".join, axis=1).map(_normalizar)
            scores = texto_busca.apply(lambda txt: sum(1 for termo in termos if termo in txt))
            relevantes = df[scores > 0]
            if not relevantes.empty:
                # Ordena por nº de termos casados (desc.), mantendo a ordem original no empate.
                ordem = scores[scores > 0].sort_values(kind="stable", ascending=False).index
                return df.loc[ordem].head(limite)

    # Fallback: sem correspondência explícita, usa a amostra geral.
    return df.head(limite)


def _registrar_trace(
    pergunta: str,
    fontes_ids: list[str],
    resposta: str,
    origem: str = "discurso",
    fontes_codigos: Optional[list[str]] = None,
) -> None:
    """Persiste, por consulta, pergunta + ids das fontes + resposta (JSONL).

    Base para avaliar rastreabilidade posteriormente (sentido B). `origem` distingue
    as bases ("discurso" / "votacao") para análises segmentadas. `fontes_ids` são os
    ids citáveis (refs curtos usados na resposta); `fontes_codigos`, quando fornecido,
    guarda os identificadores reais correspondentes (ex.: código do Senado) para auditoria.
    """
    try:
        ids_fontes = [str(x) for x in (fontes_ids or [])]
        registro = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "origem": origem,
            "pergunta": pergunta,
            "fontes_ids": ids_fontes,
            "n_fontes": len(ids_fontes),
            "resposta": resposta,
        }
        if fontes_codigos is not None:
            registro["fontes_codigos"] = [str(x) for x in fontes_codigos]
        _TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _TRACE_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except Exception as e:
        from src.utils.logger import get_logger
        get_logger(__name__).debug(f"Falha ao registrar trace de rastreabilidade: {e}")


def _montar_prompt_qa(
    dataframe_classificado: pd.DataFrame,
    pergunta: str,
    extra_context: Optional[str] = None,
) -> tuple[str, pd.DataFrame, list[str], Optional[list[str]]]:
    """Constrói o prompt de QA de discursos (retrieval + estatísticas + fontes).

    Fonte única do prompt e da recuperação: tanto o chat (Streamlit) quanto o loop de
    avaliação headless chamam esta função, garantindo prompt byte-idêntico entre eles.
    Não altera a recuperação (`_selecionar_fontes`) nem o texto do prompt.

    Retorna: (prompt_qa, fontes_usadas, ids_fontes, codigos_fontes), onde `ids_fontes`
    são os refs citáveis por consulta (D1..Dn) e `codigos_fontes` os códigos reais do
    Senado correspondentes (auditoria), quando disponíveis.
    """
    df = dataframe_classificado.copy()

    # Estatísticas do período
    periodo_txt = ""
    if 'Data' in df.columns and not df['Data'].empty:
        datas_validas = df['Data'].dropna()
        if not datas_validas.empty:
            min_d = datas_validas.min().date()
            max_d = datas_validas.max().date()
            periodo_txt = f"Intervalo: {min_d} a {max_d} (registros: {len(datas_validas)})."

    # Parlamentares mais frequentes na amostra
    top_parlamentares_txt = ""
    if 'Parlamentar' in df.columns:
        vc_parl = df['Parlamentar'].value_counts()
        if not vc_parl.empty:
            top_parlamentares_txt = ", ".join([f"{nome} ({cont})" for nome, cont in vc_parl.head(7).items()])
            top_parlamentares_txt = f"Mais ativos (discursos): {top_parlamentares_txt}."

    # Distribuição de temas
    temas_dist_txt = ""
    if 'Tema' in df.columns:
        vc_tema = df['Tema'].value_counts()
        if not vc_tema.empty:
            temas_dist_txt = ", ".join([f"{tema}: {cont}" for tema, cont in vc_tema.head(10).items()])
            temas_dist_txt = f"Temas predominantes: {temas_dist_txt}."

    total_discursos = len(df)
    resumo_stats = f"Total: {total_discursos}. {periodo_txt} {top_parlamentares_txt} {temas_dist_txt}".strip()

    # Recupera os discursos relevantes (retrieval) que fundamentarão a resposta.
    fontes_usadas = _selecionar_fontes(df, pergunta, limite=MAX_FONTES_PROMPT).reset_index(drop=True)
    # Ref curto e citável por consulta (ex.: D1, D2…); casa com o exemplo do prompt e o
    # regex de avaliação. O código real do Senado (id_discurso) fica visível para auditoria.
    fontes_usadas["ref"] = [f"D{i + 1}" for i in range(len(fontes_usadas))]

    # Colunas vistas pelo modelo no prompt: só o ref curto + conteúdo (sem o código longo,
    # para não confundir o modelo sobre qual id citar).
    colunas_prompt = ["ref"] + [c for c in ["Data", "Parlamentar", "Partido", "Tema", "Resumo"] if c in fontes_usadas.columns]
    contexto_dados = fontes_usadas[colunas_prompt].to_markdown(index=False)

    prompt_qa = f"""Você é um assistente parlamentar e cientista de dados. Analise os pronunciamentos de senadores do Senado Federal e responda à pergunta abaixo.
Gere insights RELATIVOS à amostra: frequências de parlamentares, predominância de temas, variações no período.
Se a pergunta exigir dado ausente (ex.: presença física), explique brevemente a limitação e ofereça alternativa
baseada em padrões de discursos e temas. Evite descartar totalmente a resposta; sempre traga ângulo útil.

Estatísticas agregadas (toda a amostra de {total_discursos} discursos — use para totais e rankings globais):
{resumo_stats}

Pergunta do usuário:
"{pergunta}"

{extra_context or ''}

Fontes recuperadas (cada linha é um discurso com um id 'ref' único; os autores são senadores):
---
{contexto_dados[:MAX_CHARS_CONTEXTO_PROMPT]}
---

Diretrizes de resposta:
- Português brasileiro, claro e conciso. 4–6 frases objetivas.
- Use as estatísticas agregadas para números globais (totais, ranking de parlamentares/temas).
- Para afirmações apoiadas em discursos específicos, cite a fonte pelo 'ref' entre colchetes (ex.: [D3]) ao final da frase.
- UM id por colchete: escreva [D1] [D3], nunca [D1, D3]. Use só refs que aparecem na lista de fontes acima.
- Os autores são senadores — não afirme que "não há senadores" nos dados.
- Não invente fatos externos nem detalhes que não estejam nas estatísticas ou nas fontes acima.
- Indique se o período é curto, mas ainda ofereça leitura relativa. Não repita a pergunta.

Resposta:
"""

    ids_fontes = fontes_usadas["ref"].astype(str).tolist() if "ref" in fontes_usadas.columns else []
    codigos_fontes = (
        fontes_usadas[COL_ID_DISCURSO].astype(str).tolist()
        if COL_ID_DISCURSO in fontes_usadas.columns else None
    )
    return prompt_qa, fontes_usadas, ids_fontes, codigos_fontes


@dataclass
class RespostaQA:
    """Resultado headless de uma geração de QA, com metadados para o logger de avaliação."""
    resposta: str
    modelo: str
    tokens_gerados: Optional[int]
    ids_recuperados: list[str]            # refs citáveis por consulta (D1..Dn)
    fontes_codigos: Optional[list[str]]   # códigos reais do Senado (auditoria)
    fontes_usadas: pd.DataFrame = field(repr=False, default_factory=pd.DataFrame)


def gerar_resposta_qa(
    dataframe_classificado: pd.DataFrame,
    pergunta: str,
    *,
    temperature: float = 0.1,
    seed: Optional[int] = None,
    extra_context: Optional[str] = None,
    timer=None,
    stream: bool = True,
) -> RespostaQA:
    """Gera uma resposta de QA SEM Streamlit, para o loop de avaliação comparativa.

    Reutiliza exatamente a recuperação e o prompt do chat (`_montar_prompt_qa`); a única
    diferença em relação ao chat é o controle explícito de `temperature`/`seed` (fixados
    na avaliação) e a instrumentação de latência/tokens. `timer` é qualquer objeto com
    `mark_first_token()` (ex.: `EvalLogger.start()`), chamado no primeiro token de conteúdo.

    Carimba o modelo a partir do campo `model` da resposta do LM Studio (com fallback na
    config) e captura `completion_tokens` quando o servidor expõe `usage`.
    """
    prompt_qa, fontes_usadas, ids_fontes, codigos_fontes = _montar_prompt_qa(
        dataframe_classificado, pergunta, extra_context
    )

    kwargs = {
        "model": _CFG["model"],
        "messages": [{"role": "user", "content": prompt_qa}],
        "temperature": temperature,
    }
    if seed is not None and seed != "":
        kwargs["seed"] = seed

    modelo_resp = _CFG["model"]
    tokens_gerados: Optional[int] = None

    if stream:
        kwargs["stream"] = True
        # include_usage faz o LM Studio enviar um chunk final com usage (tokens).
        kwargs["stream_options"] = {"include_usage": True}
        partes: list[str] = []
        for chunk in client.chat.completions.create(**kwargs):
            if getattr(chunk, "model", None):
                modelo_resp = chunk.model
            choices = getattr(chunk, "choices", None) or []
            if choices:
                delta = getattr(choices[0], "delta", None)
                conteudo = getattr(delta, "content", None) if delta is not None else None
                if conteudo:
                    if timer is not None and not partes:
                        timer.mark_first_token()
                    partes.append(conteudo)
            usage = getattr(chunk, "usage", None)
            if usage is not None:
                tokens_gerados = getattr(usage, "completion_tokens", None)
        resposta = "".join(partes).strip()
    else:
        response = client.chat.completions.create(**kwargs)
        if timer is not None:
            timer.mark_first_token()
        resposta = response.choices[0].message.content.strip()
        modelo_resp = getattr(response, "model", None) or _CFG["model"]
        usage = getattr(response, "usage", None)
        tokens_gerados = getattr(usage, "completion_tokens", None) if usage is not None else None

    return RespostaQA(
        resposta=resposta,
        modelo=modelo_resp,
        tokens_gerados=tokens_gerados,
        ids_recuperados=ids_fontes,
        fontes_codigos=codigos_fontes,
        fontes_usadas=fontes_usadas,
    )


def responder_pergunta_usuario_local(dataframe_classificado: pd.DataFrame, pergunta: str, extra_context: Optional[str] = None):
    """Responde à pergunta do usuário usando o LLM local e o contexto dos discursos."""
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    st.session_state.messages.append({"role": "user", "content": pergunta})
    st.chat_message("user").write(pergunta)

    # Mesmo construtor de prompt/retrieval usado pelo loop de avaliação headless
    # (fonte única: o prompt e a recuperação ficam idênticos entre chat e avaliação).
    prompt_qa, fontes_usadas, ids_fontes, codigos_fontes = _montar_prompt_qa(
        dataframe_classificado, pergunta, extra_context
    )
    # Colunas exibidas ao usuário (inclui o código real do Senado para rastrear a fonte).
    colunas_fonte = ["ref"] + [c for c in _COLUNAS_FONTE if c in fontes_usadas.columns]

    with st.spinner("O LLM local está analisando os dados e elaborando sua resposta..."):
        try:
            from src.utils.logger import get_logger
            logger = get_logger(__name__)
            logger.info(f"Respondendo pergunta do usuário: {pergunta[:50]}...")

            response = client.chat.completions.create(
                model=_CFG["model"],
                messages=[
                    {"role": "user", "content": prompt_qa},
                ],
                temperature=0.2,
            )
            resposta = response.choices[0].message.content.strip()
            logger.info(f"Resposta gerada com sucesso: {resposta[:50]}...")
            st.session_state.messages.append({"role": "assistant", "content": resposta})
            with st.chat_message("assistant"):
                st.write(resposta)
                if not fontes_usadas.empty and colunas_fonte:
                    with st.expander(f"📚 Fontes utilizadas ({len(fontes_usadas)} discursos)"):
                        st.dataframe(
                            fontes_usadas[colunas_fonte],
                            use_container_width=True,
                            hide_index=True,
                        )
            _registrar_trace(pergunta, ids_fontes, resposta, origem="discurso", fontes_codigos=codigos_fontes)
        except Exception as e:
            from src.utils.logger import get_logger
            logger = get_logger(__name__)
            logger.error(f"Erro ao responder pergunta: {str(e)}", exc_info=True)
            resposta = "Desculpe, tive uma dificuldade momentânea em processar sua pergunta. Por favor, tente novamente em alguns instantes ou reformule a pergunta."
            st.session_state.messages.append({"role": "assistant", "content": resposta})
            st.chat_message("assistant").write(resposta)


# Colunas de busca e de exibição para o retrieval de votos.
_COLUNAS_BUSCA_VOTOS = ["Parlamentar", "Partido", "UF", "Voto"]
_COLUNAS_FONTE_VOTOS = ["id_voto", "Parlamentar", "Partido", "UF", "Voto"]


def responder_pergunta_votacao_local(
    df_votos: pd.DataFrame,
    detalhes: dict,
    descricao: str,
    tipo_votacao: str,
    resultado: str,
    pergunta: str,
) -> None:
    """Responde a uma pergunta sobre uma votação, com rastreabilidade voto→fonte.

    Espelha `responder_pergunta_usuario_local`: recupera os votos relevantes, injeta-os
    como fontes citáveis por `[id_voto]`, exibe as fontes usadas e registra o trace
    (origem="votacao"). O histórico `messages_votacoes` é gerido na UI; aqui tratamos
    apenas a geração/exibição da resposta do assistente.
    """
    detalhes = detalhes or {}
    df = df_votos.copy() if df_votos is not None else pd.DataFrame()
    # Identificador citável e estável por voto dentro desta votação.
    df["id_voto"] = [f"V{i + 1}" for i in range(len(df))]

    # Contexto agregado da matéria/votação.
    codigo_materia = detalhes.get("codigo_materia") or "não informado"
    ementa = detalhes.get("ementa") or "não informada"
    autores = detalhes.get("autores") or "não informados"
    distribuicao = df["Voto"].value_counts().to_dict() if "Voto" in df.columns else {}
    contexto_materia = (
        f"Matéria: {descricao}\n"
        f"Código da matéria: {codigo_materia}\n"
        f"Ementa: {ementa}\n"
        f"Autores: {autores}\n"
        f"Tipo de votação: {tipo_votacao}\n"
        f"Resultado: {resultado}\n"
        f"Total de votos: {len(df)}\n"
        f"Distribuição de votos: {distribuicao}"
    )

    # Recupera os votos relevantes (retrieval) que fundamentarão a resposta.
    fontes_usadas = _selecionar_fontes(df, pergunta, limite=MAX_FONTES_PROMPT, colunas_busca=_COLUNAS_BUSCA_VOTOS)
    colunas_fonte = [c for c in _COLUNAS_FONTE_VOTOS if c in fontes_usadas.columns]
    contexto_votos = (
        fontes_usadas[colunas_fonte].to_markdown(index=False)
        if colunas_fonte and not fontes_usadas.empty else "Nenhum voto disponível."
    )

    prompt_votacao = f"""Você é um assistente especializado em votações do Senado Federal brasileiro.
Responda à pergunta do usuário com base nos dados da votação e nos votos recuperados abaixo.

Dados da votação:
{contexto_materia}

Votos recuperados (fontes — cada linha tem um id_voto):
---
{contexto_votos[:MAX_CHARS_CONTEXTO_PROMPT]}
---

Pergunta do usuário:
"{pergunta}"

Diretrizes de resposta:
- Português brasileiro, claro e conciso.
- Fundamente as afirmações nos votos recuperados acima e cite as fontes usadas pelo id_voto entre colchetes (ex.: [V1], [V3]) ao final das frases pertinentes.
- UM id por colchete: escreva [V1] [V3], nunca [V1, V3]. Use só ids que aparecem na lista de votos acima.
- Não invente fatos externos nem cite ids que não estejam na lista acima.
- Se a pergunta exigir um dado ausente, explique brevemente a limitação. Se não souber responder, seja honesto.
"""

    from src.utils.logger import get_logger
    logger = get_logger(__name__)
    with st.spinner("O LLM local está analisando os votos e elaborando sua resposta..."):
        try:
            response = client.chat.completions.create(
                model=_CFG["model"],
                messages=[{"role": "user", "content": prompt_votacao}],
                temperature=0.2,
            )
            resposta = response.choices[0].message.content.strip()
            st.session_state.messages_votacoes.append({"role": "assistant", "content": resposta})
            with st.chat_message("assistant"):
                st.write(resposta)
                if not fontes_usadas.empty and colunas_fonte:
                    with st.expander(f"📚 Fontes utilizadas ({len(fontes_usadas)} votos)"):
                        st.dataframe(
                            fontes_usadas[colunas_fonte],
                            use_container_width=True,
                            hide_index=True,
                        )
            ids_fontes = fontes_usadas["id_voto"].astype(str).tolist() if "id_voto" in fontes_usadas.columns else []
            _registrar_trace(pergunta, ids_fontes, resposta, origem="votacao")
        except Exception as e:
            logger.error(f"Erro ao responder pergunta sobre votação: {str(e)}", exc_info=True)
            resposta = "Desculpe, tive uma dificuldade em processar sua pergunta. Tente novamente."
            st.session_state.messages_votacoes.append({"role": "assistant", "content": resposta})
            st.chat_message("assistant").write(resposta)