import streamlit as st
import google.generativeai as genai
import pandas as pd
from typing import Dict, Optional
from src.config.settings import get_gemini_models
import time
import random

_MODELOS = get_gemini_models()

def _resolve_model_name(nome: str) -> str:
    """Normaliza pequenas variações: remove prefixo 'models/' se presente."""
    if not nome:
        return ''
    return nome.replace('models/', '').strip()

def _get_model(contexto: str = 'discursos'):
    """Retorna modelo configurado para o contexto informado com cadeia de fallbacks.
    Ordem de tentativa:
      1. Nome configurado
      2. Nome configurado sem prefixo 'models/'
      3. 'gemini-2.5-pro' (pro estável)
      4. 'gemini-pro-latest'
      5. 'gemini-2.0-flash' (fallback final)
    """
    configurado = _MODELOS.get(contexto, 'gemini-2.0-flash')
    candidatos = [
        configurado,
        _resolve_model_name(configurado),
        'gemini-2.5-pro',
        'gemini-pro-latest',
        'gemini-2.0-flash'
    ]
    vistos = set()
    for c in candidatos:
        c_limpo = _resolve_model_name(c)
        if not c_limpo or c_limpo in vistos:
            continue
        vistos.add(c_limpo)
        try:
            return genai.GenerativeModel(c_limpo)
        except Exception:
            continue
    return genai.GenerativeModel('gemini-2.0-flash')


def responder_pergunta_usuario(dataframe_classificado: pd.DataFrame, pergunta: str, extra_context: str = None):
    """Responde à pergunta do usuário usando o contexto dos discursos.

    Inclui estatísticas resumidas (período, parlamentares mais ativos e distribuição de temas) para permitir
    inferências relativas mesmo em amostras pequenas, evitando respostas excessivamente negativas.
    """
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    st.session_state.messages.append({"role": "user", "content": pergunta})
    st.chat_message("user").write(pergunta)

    model = _get_model('discursos')

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

    contexto_dados = df.to_markdown(index=False)

    prompt_qa = f"""
    Você é um assistente parlamentar e cientista de dados. Analise os discursos e responda à pergunta abaixo.
    Gere insights RELATIVOS à amostra: frequências de parlamentares, predominância de temas, variações no período.
    Se a pergunta exigir dado ausente (ex.: presença física), explique brevemente a limitação e ofereça alternativa
    baseada em padrões de discursos e temas. Evite descartar totalmente a resposta; sempre traga ângulo útil.

    Estatísticas resumidas:
    {resumo_stats}

    Pergunta do usuário:
    "{pergunta}"

    {extra_context or ''}

    Dados tabulares (amostra):
    ---
    {contexto_dados[:16000]}
    ---

    Diretrizes de resposta:
    - Português brasileiro, claro e conciso.
    - 4–6 frases objetivas.
    - Referencie parlamentares com mais discursos quando pertinente.
    - Use temas para qualificar tendências.
    - Indique se período é curto, mas ainda ofereça leitura relativa.
    - Não repita a pergunta, não use jargões desnecessários.
    - Não invente fatos externos.

    Resposta:
    """

    with st.spinner("O Agente Gemini está analisando os dados e elaborando sua resposta..."):
        try:
            response = model.generate_content(prompt_qa)
            resposta = response.text
            st.session_state.messages.append({"role": "assistant", "content": resposta})
            st.chat_message("assistant").write(resposta)
        except Exception as e:
            st.error(f"Ocorreu um erro ao contatar o Gemini: {e}")


def _normalizar_voto(valor: str) -> str:
    if not valor:
        return ''
    v = valor.strip().lower()
    # normaliza acentos/sinonimos mais comuns
    m = {
        'sim': 'SIM',
        'não': 'NÃO',
        'nao': 'NÃO',
        'abstenção': 'ABSTENÇÃO',
        'abstencao': 'ABSTENÇÃO',
        'obstrução': 'OBSTRUÇÃO',
        'obstrucao': 'OBSTRUÇÃO'
    }
    return m.get(v, valor.strip().upper())


def _resumo_votos(df_votos: pd.DataFrame) -> Dict:
    if df_votos is None or df_votos.empty or 'Voto' not in df_votos.columns:
        return {'total': 0, 'contagens': {}, 'maioria': '', 'pct_maioria': 0.0}
    votos_norm = df_votos['Voto'].astype(str).map(_normalizar_voto)
    contagens = votos_norm.value_counts().to_dict()
    total = int(sum(contagens.values()) or 0)
    if total > 0:
        maioria_label = max(contagens, key=contagens.get)
        pct = round(100 * contagens[maioria_label] / total, 1)
    else:
        maioria_label, pct = '', 0.0
    return {'total': total, 'contagens': contagens, 'maioria': maioria_label, 'pct_maioria': pct}


def explicar_votacao(detalhes: Dict, df_votos: pd.DataFrame, descricao: Optional[str] = None) -> str:
    """Gera uma explicação em linguagem natural sobre a votação usando IA.

    Considera ementa, explicação, autores e distribuição de votos. Usa fallback de modelo.
    Cache simples por código da matéria para evitar custo repetido.
    """
    codigo = detalhes.get('codigo_materia') or detalhes.get('codigo') or ''
    cache_key = f"explic_votacao_{codigo}"
    if cache_key in st.session_state:
        cached = st.session_state[cache_key]
        # Se cache armazenou erro 429 anteriormente, permite tentar novamente
        if isinstance(cached, str) and '429' in cached and 'Quota' in cached:
            del st.session_state[cache_key]
        else:
            return cached

    votos = _resumo_votos(df_votos)
    resumo_votos = ', '.join([f"{k}: {v}" for k, v in votos['contagens'].items()])
    autores = detalhes.get('autores', '')
    ementa = detalhes.get('ementa', '')
    explicacao = detalhes.get('explicacao', '')
    resultado = detalhes.get('resultado', '')
    tipo_votacao = detalhes.get('tipo_votacao', '')

    titulo = descricao or ''
    prompt = f"""
    Você é um analista legislativo. Explique objetivamente a votação abaixo sem repetir longamente faltas de dados.
    Use somente os dados fornecidos. Se o campo 'resultado' estiver vazio, faça leitura condicional com base na
    distribuição de votos (ex.: "há tendência de aprovação dado X% de votos SIM"), sem afirmar algo não comprovado.

    Dados:
    Título/Descrição: {titulo or 'Sem título'}
    Código: {codigo or 'Não disponível'}
    Tipo de Votação: {tipo_votacao or 'Não informado'}
    Resultado: {resultado or 'Não informado'}
    Ementa: {ementa or 'Sem ementa'}
    Explicação da Ementa: {explicacao or 'Sem explicação'}
    Autores: {autores or 'Não informados'}
    Distribuição dos Votos: {resumo_votos or 'Sem votos'}
    Total de votos: {votos['total']}
    Maioria: {votos['maioria'] or 'N/D'} ({votos['pct_maioria']}%)

    Produza 3–5 frases em português brasileiro:
    - 1ª: sintetize o objeto (use a ementa; se ausente, use o título/descrição como base).
    - 2ª: explique o resultado (ou a ausência dele) em termos simples.
    - 3ª-4ª: interprete a distribuição de votos (consenso/divisão) com base nas porcentagens.
    - 5ª (opcional): impacto imediato ou próximo passo típico (sem especulação factual).
    Evite listar campos ausentes.
    """

    # Estratégia de retry/fallback: tenta modelo configurado (possivelmente pro),
    # depois gemini-2.5-pro (estável), depois flash.
    configurado = _MODELOS.get('votacoes', 'gemini-2.0-flash')
    candidatos = []
    for n in [configurado, 'gemini-2.5-pro', 'gemini-2.0-flash']:
        n_clean = n.replace('models/', '').strip()
        if n_clean and n_clean not in candidatos:
            candidatos.append(n_clean)

    max_retries = 3
    base_delay = 4.0
    resposta = ''
    erro_final = None
    for nome_modelo in candidatos:
        for tentativa in range(max_retries):
            try:
                modelo = genai.GenerativeModel(nome_modelo)
                resposta = modelo.generate_content(prompt).text.strip()
                erro_final = None
                break
            except Exception as e:
                msg = str(e)
                erro_final = e
                if '429' in msg or 'quota' in msg.lower() or 'exceeded' in msg.lower():
                    # Backoff exponencial com jitter
                    espera = base_delay * (2 ** tentativa) + random.uniform(0, 1.5)
                    st.warning(f"Limite atingido no modelo {nome_modelo}. Nova tentativa em {espera:.1f}s (tentativa {tentativa+1}/{max_retries})...")
                    time.sleep(espera)
                    continue
                else:
                    break
