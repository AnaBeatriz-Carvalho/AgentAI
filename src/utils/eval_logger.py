"""Logger de avaliação comparativa de modelos (gerador) do AgentAI.

Acopla ao pipeline existente para registrar, por par modelo x pergunta, tudo que a
planilha de avaliação (`AgentAI_avaliacao_modelos.xlsx`, aba "2. Coleta (bruta)")
espera. NÃO reimplementa nada do pipeline: a recuperação por palavra-chave, a
citação por ID e o painel de métricas continuam onde estão. Este módulo apenas
"carimba" cada resposta com o modelo ativo, mede custo/latência e calcula a
integridade referencial por linha, exportando no formato da constante `HEADER`.

Origem: `agentai_eval_logger.py` do handoff (Parte 1). Mantidos intactos os nomes e
a ordem das colunas (`HEADER`), o cálculo de integridade por linha
(`citacoes_validas / total_citacoes`), a heurística de alucinação (id citado fora do
conjunto válido -> 1) e a recusa correta (só quando a pergunta não tem resposta no
corpus). Único ajuste vs. o anexo: `to_csv` serializa as linhas a partir da própria
constante `HEADER`, garantindo que a ordem do CSV não dependa da ordem dos campos da
dataclass.

Notas de método (para o artigo):
- `alucinacao` = 1 se houver id citado fora do conjunto válido passado em `corpus_ids`.
  Afirmação factual sem citação exige marcação humana; use `alucinacao_override`.
- `recusou_correto` só se aplica quando `tem_resposta_no_corpus == "Nao"`.
- integridade referencial por linha = `citacoes_validas / total_citacoes`.
- suporte semântico, PT formal e completude NÃO entram aqui: são anotação humana
  cega (aba 3 da planilha). Não automatize, para não enviesar o Kappa de Cohen.
"""

from __future__ import annotations

import csv
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Iterable, Sequence


@dataclass
class _Row:
    run_id: str
    modelo: str
    quantizacao: str
    pergunta_id: str
    tipo: str
    resposta_gerada: str
    ids_recuperados: str
    ids_citados: str
    citacoes_validas: int
    total_citacoes: int
    alucinacao: int
    recusou_correto: str
    latencia_1tok_s: float | str
    tokens_por_s: float | str
    vram_gb: float | str
    temperatura: float
    seed: int | str
    timestamp: str


# Ordem idêntica aos cabeçalhos da aba "2. Coleta (bruta)".
HEADER = [
    "run_id", "modelo", "quantizacao", "pergunta_id", "tipo", "resposta_gerada",
    "ids_recuperados", "ids_citados", "citacoes_validas", "total_citacoes",
    "alucinacao", "recusou_correto", "latencia_1tok_s", "tokens_por_s",
    "vram_gb", "temperatura", "seed", "timestamp",
]


@dataclass
class _Timer:
    t0: float
    t_first_token: float | None = None

    def mark_first_token(self) -> None:
        if self.t_first_token is None:
            self.t_first_token = time.perf_counter()


class EvalLogger:
    def __init__(
        self,
        model: str,
        quant: str = "",
        temperature: float = 0.1,
        seed: int | str = "",
        run_prefix: str = "r",
    ) -> None:
        self.model = model
        self.quant = quant
        self.temperature = temperature
        self.seed = seed
        self.run_prefix = run_prefix
        self._rows: list[_Row] = []
        self._counter = 0

    def start(self) -> _Timer:
        """Chame imediatamente antes de gerar a resposta."""
        return _Timer(t0=time.perf_counter())

    def record(
        self,
        pergunta_id: str,
        tipo: str,
        resposta: str,
        ids_recuperados: Sequence[str],
        ids_citados: Sequence[str],
        corpus_ids: Iterable[str],
        tem_resposta_no_corpus: str,
        tokens_gerados: int | None = None,
        vram_gb: float | None = None,
        timer: _Timer | None = None,
        alucinacao_override: int | None = None,
    ) -> _Row:
        self._counter += 1
        run_id = f"{self.run_prefix}{self._counter:03d}"

        corpus = set(corpus_ids)
        citados = list(ids_citados)
        validas = sum(1 for cid in citados if cid in corpus)
        total = len(citados)

        # Heurística de alucinação: citou ID que não existe no conjunto válido.
        invalid_cite = any(cid not in corpus for cid in citados)
        if alucinacao_override is not None:
            aluc = int(alucinacao_override)
        else:
            aluc = 1 if invalid_cite else 0

        # Recusa correta só faz sentido quando NÃO há resposta no corpus.
        recusou = ""
        if str(tem_resposta_no_corpus).strip().lower() in ("nao", "não", "no"):
            # Heurística simples: resposta sem citação => provável recusa.
            # Ajuste o critério ao seu prompt; deixe explícito no artigo.
            citou_algo = total > 0
            recusou = "0" if citou_algo else "1"

        # Latência e throughput.
        lat_first: float | str = ""
        tok_s: float | str = ""
        if timer is not None:
            t_end = time.perf_counter()
            if timer.t_first_token is not None:
                lat_first = round(timer.t_first_token - timer.t0, 3)
            if tokens_gerados:
                dur = t_end - timer.t0
                tok_s = round(tokens_gerados / dur, 2) if dur > 0 else ""

        row = _Row(
            run_id=run_id,
            modelo=self.model,
            quantizacao=self.quant,
            pergunta_id=pergunta_id,
            tipo=tipo,
            resposta_gerada=resposta.replace("\n", " ").strip(),
            ids_recuperados=";".join(map(str, ids_recuperados)),
            ids_citados=";".join(map(str, citados)),
            citacoes_validas=validas,
            total_citacoes=total,
            alucinacao=aluc,
            recusou_correto=recusou,
            latencia_1tok_s=lat_first,
            tokens_por_s=tok_s,
            vram_gb=vram_gb if vram_gb is not None else "",
            temperatura=self.temperature,
            seed=self.seed,
            timestamp=datetime.now().isoformat(timespec="seconds"),
        )
        self._rows.append(row)
        return row

    def to_csv(self, path: str, write_header: bool = True) -> str:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(HEADER)
            for r in self._rows:
                d = asdict(r)
                w.writerow([d[col] for col in HEADER])
        return path

    def summary(self) -> dict:
        """Resumo rápido para sanity-check no console (não substitui a planilha)."""
        n = len(self._rows)
        if not n:
            return {"n": 0}
        aluc = sum(r.alucinacao for r in self._rows) / n
        tot_cit = sum(r.total_citacoes for r in self._rows)
        val_cit = sum(r.citacoes_validas for r in self._rows)
        integ = (val_cit / tot_cit) if tot_cit else None
        return {
            "modelo": self.model,
            "n": n,
            "taxa_alucinacao": round(aluc, 3),
            "integridade_referencial": round(integ, 3) if integ is not None else None,
        }
