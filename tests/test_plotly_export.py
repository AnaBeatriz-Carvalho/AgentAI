import plotly.express as px
import plotly.graph_objs as go


def test_plotly_figure_basic():
    # simple figure - ensure a plotly Figure is created
    fig = px.bar(x=[1, 2, 3], y=[1, 3, 2])
    assert isinstance(fig, go.Figure)
