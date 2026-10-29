"""Conector para o SAPL (Sistema de Apoio ao Processo Legislativo, Interlegis).

O SAPL é o sistema usado por centenas de Câmaras Municipais e Assembleias Legislativas.
Todas as instâncias expõem a mesma API REST (``/api/``), então um único conector,
parametrizado pela URL base da Casa, cobre qualquer câmara que use o sistema.

Este pacote é independente do Streamlit e do LLM: ``client`` fala com a API,
``normalizacao`` transforma o JSON em DataFrames e ``servico`` orquestra os dois.
Não altera nenhum fluxo do Senado nem os experimentos de avaliação.
"""
