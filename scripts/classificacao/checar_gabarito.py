"""CLI: confere o gabarito anotado e emite o VEREDITO da regra de decisao (protocolo §2.1).

Roda DEPOIS da anotacao humana, antes das predicoes/metricas. Valida:
  - todos os rotulos de `tema_gold` pertencem a taxonomia (5 rotulos);
  - cobertura (>=150 itens anotados);
  - contagem por classe;
e imprime o ramo acionado da regra fixada a priori:
  - toda classe >=20            -> MANTER 5 rotulos;
  - uma classe em 15-19         -> ACEITAR com ressalva (n baixo), enfatizar macro/ponderada;
  - qualquer <15 OU >=2 classes <20 -> CONSOLIDAR para 4 rotulos (fundir a menor na afim).

O veredito e descritivo: a decisao e da pesquisadora; o script so torna a regra auditavel.

Uso:
    .\\.venv\\Scripts\\python.exe scripts\\classificacao\\checar_gabarito.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from scripts.classificacao._comum import COL_GOLD, GABARITO_CSV, rotulo_canonico, rotulos

COBERTURA_MINIMA = 150


def main() -> int:
    if not GABARITO_CSV.exists():
        raise SystemExit(
            f"Gabarito nao encontrado: {GABARITO_CSV}\n"
            "Preencha 'tema_gold' no template e salve como gabarito.csv."
        )
    df = pd.read_csv(GABARITO_CSV, encoding="utf-8")
    if COL_GOLD not in df.columns:
        raise SystemExit(f"Coluna '{COL_GOLD}' ausente no gabarito.")

    labels = rotulos()
    gold = df[COL_GOLD].fillna("").astype(str).str.strip()
    anotados = gold[gold != ""]
    # Normaliza para o rotulo canonico (aceita acento/caixa naturais na anotacao).
    canon = anotados.map(rotulo_canonico)

    # --- Validacao de rotulos ---
    invalidos = sorted(set(anotados[canon.isna()]))
    n_total = len(df)
    n_anotados = len(anotados)
    n_vazios = n_total - n_anotados

    print(f"Gabarito: {GABARITO_CSV.name}")
    print(f"  Linhas totais: {n_total} | anotadas: {n_anotados} | vazias: {n_vazios}")
    if invalidos:
        print(f"  [ERRO] rotulos fora da taxonomia em 'tema_gold': {invalidos}")
        print(f"         validos: {labels}")
    if n_vazios:
        print(f"  [aviso] {n_vazios} linha(s) sem anotacao.")
    if n_anotados < COBERTURA_MINIMA:
        print(f"  [aviso] cobertura {n_anotados} < minimo {COBERTURA_MINIMA}.")

    # --- Contagem por classe (todas as 5, incluindo zeradas; sobre o rotulo canonico) ---
    contagem = {lab: int((canon == lab).sum()) for lab in labels}
    print("\nContagem por classe (tema_gold):")
    for lab in labels:
        print(f"  {lab:>32}: {contagem[lab]}")

    # --- Veredito da regra (§2.1) ---
    abaixo_20 = [lab for lab in labels if contagem[lab] < 20]
    abaixo_15 = [lab for lab in labels if contagem[lab] < 15]
    menor = min(labels, key=lambda l: contagem[l])

    print("\n=== VEREDITO DA REGRA DE DECISAO (protocolo §2.1) ===")
    if invalidos:
        print("  INDEFINIDO: corrija os rotulos invalidos antes de aplicar a regra.")
    elif not abaixo_20:
        print("  MANTER 5 rotulos (todas as classes >= 20).")
    elif not abaixo_15 and len(abaixo_20) == 1:
        c = abaixo_20[0]
        print(f"  ACEITAR 5 rotulos COM RESSALVA na classe '{c}' (n={contagem[c]}, 15-19):")
        print("    reportar a metrica por classe dessa categoria com ressalva de "
              "instabilidade (n baixo) e enfatizar macro/ponderada.")
    else:
        motivo = []
        if abaixo_15:
            motivo.append(f"classe(s) <15: {abaixo_15}")
        if len(abaixo_20) >= 2:
            motivo.append(f"{len(abaixo_20)} classes <20: {abaixo_20}")
        print(f"  CONSOLIDAR para 4 rotulos ({'; '.join(motivo)}).")
        print(f"    candidata a fusao: menor classe '{menor}' (n={contagem[menor]}) "
              "-> macrocategoria afim, ancorada no esquema do Senado e documentada.")

    print("\nLembrete: o veredito e auditavel, mas a decisao final (e a justificativa da "
          "fusao) e da pesquisadora; registre o ramo acionado no texto do artigo.")
    return 0 if not invalidos else 1


if __name__ == "__main__":
    raise SystemExit(main())
