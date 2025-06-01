
import pandas as pd
import plotly.graph_objects as go

def gerar_grafico_por_data_interativo_com_media(df):
    if not pd.api.types.is_datetime64_any_dtype(df['DataSessao']):
        df['DataSessao'] = pd.to_datetime(df['DataSessao'], errors='coerce')

    df = df.dropna(subset=['DataSessao'])
    df['DataSessao'] = df['DataSessao'].dt.date
    df_grouped = df.groupby('DataSessao').size().reset_index(name='quantidade')
    df_grouped['media_movel'] = df_grouped['quantidade'].rolling(window=3, min_periods=1).mean()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_grouped['DataSessao'],
        y=df_grouped['quantidade'],
        name='Discursos por Dia',
        marker_color='lightskyblue',
        text=df_grouped['quantidade'],
        textposition='outside'
    ))

    fig.add_trace(go.Scatter(
        x=df_grouped['DataSessao'],
        y=df_grouped['media_movel'],
        mode='lines+markers',
        name='Média Móvel (3 dias)',
        line=dict(color='orange', width=3),
        marker=dict(size=6)
    ))

    fig.update_layout(
        title="📈 Discursos por Dia com Média Móvel",
        xaxis_title='Data',
        yaxis_title='Quantidade de Discursos',
        template="plotly_dark",
        xaxis=dict(tickangle=45, type='category', showgrid=True),
        yaxis=dict(showgrid=True),
        bargap=0.2,
        margin=dict(l=40, r=40, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig
