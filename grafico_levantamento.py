import pandas as pd
import plotly.express as px

def gerar_grafico_por_data_interativo(df):
    # Verificar tipo da coluna DataSessao e converter se necessário
    if not pd.api.types.is_datetime64_any_dtype(df['DataSessao']):
        df['DataSessao'] = pd.to_datetime(df['DataSessao'], errors='coerce')

    # Excluir linhas onde a DataSessao falhou
    df = df.dropna(subset=['DataSessao'])
    print("Após dropna:", df.shape)

    # Adicionar uma coluna 'quantidade' com valor 1 para cada discurso
    df['quantidade'] = 1

    # Converter DataSessao para apenas a data (sem horário)
    df['DataSessao'] = df['DataSessao'].dt.date

    # Gráfico: uma barra por discurso
    fig = px.bar(df, x='DataSessao', y='quantidade', title="Discursos Individuais por Dia", text_auto=True)

    fig.update_layout(
        xaxis_title='Data',
        yaxis_title='Quantidade de Discursos',
        xaxis=dict(
            tickformat="%d/%m/%Y",
            tickangle=45,
            showgrid=True,
            zeroline=False,
            type='category'  # Tratar datas como categorias
        ),
        template="plotly_dark",
        margin=dict(l=40, r=40, t=40, b=40),
        bargap=0.5,  # Espaçamento entre barras
        bargroupgap=0.1  # Espaçamento entre grupos de barras (mesma data)
    )

    # Ajustar o intervalo do eixo y dinamicamente
    max_quantidade = df.groupby('DataSessao')['quantidade'].sum().max()
    fig.update_yaxes(range=[0, max_quantidade * 1.2])

    return fig