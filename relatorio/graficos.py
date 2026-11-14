"""Construção das séries de todos os gráficos do relatório.

Os gráficos do site são desenhados no navegador (ECharts) a partir de
dados em JSON, de modo que o gerador Python não depende de nenhuma
biblioteca de imagem. Este módulo concentra o cálculo das séries e
devolve, em :func:`construir_graficos`, a lista de dicionários no
formato exato esperado pelo motor JS.

Convenções seguidas em todos os gráficos:

* apenas tipos nativos do Python no retorno (``None`` em vez de ``NaN``),
  com arredondamento em quatro casas;
* ``.dropna()`` antes de qualquer cálculo;
* a chave ``estatisticas`` está **sempre** presente (n, média, mediana,
  moda, variância, desvio-padrão, CV, Q1, Q3, IQR, mínimo, máximo,
  unidade, formato e a variável a que os números se referem);
* a chave ``marcadores`` acompanha os gráficos em que as linhas de
  média/mediana/moda/quartis fazem sentido geometricamente (histogramas
  no eixo x, séries de valores no eixo y);
* a chave ``tabela`` está **sempre** presente — é a regra de alívio de
  contraste da paleta, não é opcional;
* as cores são informadas por *slot* (``slot1``..``slot8``), seguindo o
  mapeamento fixo por entidade: a cor acompanha a entidade (produto,
  turno, linha, tipo de manutenção) e nunca o ranking.

Cuidado metodológico registrado nas leituras: os produtos têm ritmos de
fabricação diferentes (Micro-ondas gira perto de 300 unidades por
registro, Geladeira perto de 130). Por isso os gráficos de volume vêm
sempre acompanhados dos de produtividade por hora efetiva.
"""

from __future__ import annotations

import json
import math
from typing import Any, Sequence

import pandas as pd

ALTURA_PADRAO = 340

# ------------------------------------------------------------- entidades --
# Ordem de exibição e cor fixa por entidade (item 3 do contrato).
ORDEM_PRODUTO = ["Geladeira", "Lavadora", "Ar-condicionado", "Micro-ondas"]
CORES_PRODUTO = {
    "Geladeira": "slot1",
    "Lavadora": "slot2",
    "Ar-condicionado": "slot3",
    "Micro-ondas": "slot4",
}

ORDEM_TURNO = ["Manhã", "Tarde", "Noite"]
CORES_TURNO = {"Manhã": "slot1", "Tarde": "slot2", "Noite": "slot3"}

ORDEM_LINHA = ["Linha A", "Linha B", "Linha C", "Linha D"]
CORES_LINHA = {
    "Linha A": "slot1",
    "Linha B": "slot2",
    "Linha C": "slot3",
    "Linha D": "slot4",
}

ORDEM_MANUTENCAO = ["Nenhuma", "Preventiva", "Corretiva"]
CORES_MANUTENCAO = {
    "Nenhuma": "slot1",
    "Preventiva": "slot3",
    "Corretiva": "slot2",
}

# Faixas de status da taxa de defeitos (fração), usadas nos gráficos de
# qualidade. A taxa global da base fica em torno de 3,7%.
FAIXAS_DEFEITOS = [
    (0.030, "status:bom"),
    (0.040, "status:atencao"),
    (0.050, "status:grave"),
]

# Rótulos curtos para a matriz de correlação (o rótulo longo não cabe).
ROTULOS_CURTOS = {
    "unidades_produzidas": "Unidades",
    "produtividade_hora": "Produtiv./h",
    "horas_efetivas": "Horas efet.",
    "horas_parada_maquina": "Parada (h)",
    "consumo_energia_kwh": "Energia",
    "energia_por_unidade": "Energia/un",
    "taxa_defeitos": "Taxa defeitos",
    "unidades_defeituosas": "Defeituosas",
    "residuo_kg": "Resíduo",
    "idade_maquina_anos": "Idade máq.",
    "experiencia_operador_anos": "Experiência",
    "temperatura_ambiente_c": "Temperatura",
    "entregas_no_prazo_pct": "Entregas prazo",
}

COLUNAS_CORRELACAO = list(ROTULOS_CURTOS)


# =========================================================== formatação ===
def _n(valor: float | None, casas: int = 2) -> str:
    """Formata um número no padrão pt-BR ("1.234,56")."""
    if valor is None or (isinstance(valor, float) and not math.isfinite(valor)):
        return "—"
    texto = f"{float(valor):,.{casas}f}"
    return texto.replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")


def _pc(fracao: float | None, casas: int = 1) -> str:
    """Formata uma fração (0–1) como percentual pt-BR ("3,7%")."""
    if fracao is None:
        return "—"
    return _n(float(fracao) * 100.0, casas) + "%"


def _casas(formato: str) -> int:
    """Casas decimais usadas nos rótulos de classe de cada formato."""
    return {"int": 0, "num": 2, "pct": 2}.get(formato, 2)


# ====================================================== utilidades base ===
def _f(valor: Any, casas: int = 4) -> float | None:
    """Converte para ``float`` nativo arredondado; ``None`` se não for finito."""
    if valor is None or valor is pd.NA:
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numero):
        return None
    return round(numero, casas)


def _i(valor: Any) -> int | None:
    """Converte para ``int`` nativo; ``None`` quando ausente."""
    numero = _f(valor)
    return None if numero is None else int(round(numero))


def _numerica(dados: Any) -> pd.Series:
    """Série numérica em ``float64``, já sem valores ausentes."""
    serie = pd.Series(dados) if not isinstance(dados, pd.Series) else dados
    serie = pd.to_numeric(serie, errors="coerce").dropna()
    return serie.astype("float64")


def _moda(serie: pd.Series) -> float | None:
    """Moda da série; ``None`` quando não há valor repetido."""
    if serie.empty:
        return None
    contagem = serie.value_counts()
    if contagem.empty or int(contagem.iloc[0]) < 2:
        return None
    return _f(contagem.index[0])


def _estat(
    dados: Any,
    variavel: str,
    unidade: str,
    formato: str,
) -> dict:
    """Bloco ``estatisticas`` completo de uma série de valores.

    Alimenta a faixa de legenda de cada cartão: n, média, mediana, moda,
    variância, desvio-padrão, coeficiente de variação, Q1, Q3, IQR,
    mínimo e máximo, além da unidade, do formato e do nome da variável.
    """
    serie = _numerica(dados)
    if serie.empty:
        return {
            "unidade": unidade,
            "formato": formato,
            "variavel": variavel,
            "n": 0,
            "media": None,
            "mediana": None,
            "moda": None,
            "variancia": None,
            "desvio_padrao": None,
            "coef_variacao": None,
            "q1": None,
            "q3": None,
            "iqr": None,
            "minimo": None,
            "maximo": None,
        }

    q1, q2, q3 = (float(x) for x in serie.quantile([0.25, 0.50, 0.75]))
    media = float(serie.mean())
    desvio = float(serie.std(ddof=1)) if serie.size > 1 else 0.0
    variancia = float(serie.var(ddof=1)) if serie.size > 1 else 0.0
    return {
        "unidade": unidade,
        "formato": formato,
        "variavel": variavel,
        "n": int(serie.size),
        "media": _f(media),
        "mediana": _f(q2),
        "moda": _moda(serie),
        "variancia": _f(variancia),
        "desvio_padrao": _f(desvio),
        "coef_variacao": _f(desvio / media) if media else None,
        "q1": _f(q1),
        "q3": _f(q3),
        "iqr": _f(q3 - q1),
        "minimo": _f(serie.min()),
        "maximo": _f(serie.max()),
    }


def _marcadores_y(est: dict) -> dict | None:
    """Marcadores no eixo de valores (eixo y).

    Usado em barras, linhas, áreas, boxplots e dispersões: as linhas são
    desenhadas na própria escala do eixo, por isso ``pos`` repete os
    valores. Média tracejada, mediana pontilhada, moda sólida fina,
    Q1/Q3 tracejado curto e faixa de ±1 desvio-padrão.
    """
    if est.get("media") is None:
        return None
    media = est["media"]
    desvio = est.get("desvio_padrao") or 0.0
    return {
        "eixo": "y",
        "media": media,
        "mediana": est.get("mediana"),
        "moda": est.get("moda"),
        "q1": est.get("q1"),
        "q3": est.get("q3"),
        "desvio_padrao": est.get("desvio_padrao"),
        "variancia": est.get("variancia"),
        "iqr": est.get("iqr"),
        "pos": {
            "media": media,
            "mediana": est.get("mediana"),
            "moda": est.get("moda"),
            "q1": est.get("q1"),
            "q3": est.get("q3"),
            "dp_inf": _f(media - desvio),
            "dp_sup": _f(media + desvio),
        },
    }


def _marcadores_x(est: dict, inicio: float, largura: float) -> dict | None:
    """Marcadores no eixo de classes de um histograma.

    A posição de um valor ``v`` em índice fracionário do eixo de
    categorias é ``(v - b0) / w - 0.5``, com ``b0`` igual à borda
    inferior da primeira classe e ``w`` igual à largura das classes.
    """
    if est.get("media") is None or not largura:
        return None

    def pos(valor: float | None) -> float | None:
        if valor is None:
            return None
        return _f((valor - inicio) / largura - 0.5)

    media = est["media"]
    desvio = est.get("desvio_padrao") or 0.0
    return {
        "eixo": "x",
        "media": media,
        "mediana": est.get("mediana"),
        "moda": est.get("moda"),
        "q1": est.get("q1"),
        "q3": est.get("q3"),
        "desvio_padrao": est.get("desvio_padrao"),
        "variancia": est.get("variancia"),
        "iqr": est.get("iqr"),
        "pos": {
            "media": pos(media),
            "mediana": pos(est.get("mediana")),
            "moda": pos(est.get("moda")),
            "q1": pos(est.get("q1")),
            "q3": pos(est.get("q3")),
            "dp_inf": pos(media - desvio),
            "dp_sup": pos(media + desvio),
        },
    }


def _tabela(colunas: Sequence[str], linhas: Sequence[Sequence[Any]]) -> dict:
    """Monta a tabela de alívio de contraste exibida sob cada gráfico."""
    return {"colunas": [str(c) for c in colunas], "linhas": [list(l) for l in linhas]}


def _serie(
    nome: str,
    tipo: str,
    cor: str,
    dados: list,
    rotulo_direto: bool = False,
    **extras: Any,
) -> dict:
    """Monta uma série no formato do motor JS.

    ``extras`` carrega chaves opcionais aceitas pelo motor: ``outliers``
    (boxplot) e ``cores`` (cor por marca, quando cada marca é uma
    entidade ou um status).
    """
    serie = {
        "nome": nome,
        "tipo": tipo,
        "cor": cor,
        "dados": dados,
        "rotulo_direto": bool(rotulo_direto),
    }
    serie.update(extras)
    return serie


def _grafico(
    id_: str,
    secao: str,
    titulo: str,
    subtitulo: str,
    tipo: str,
    eixo_x: dict,
    eixo_y: dict,
    series: list[dict],
    estatisticas: dict,
    tabela: dict,
    leitura: str,
    marcadores: dict | None = None,
    altura: int = ALTURA_PADRAO,
) -> dict:
    """Monta o dicionário de um gráfico no formato do item 6 do contrato."""
    return {
        "id": id_,
        "secao": secao,
        "titulo": titulo,
        "subtitulo": subtitulo,
        "tipo": tipo,
        "eixo_x": eixo_x,
        "eixo_y": eixo_y,
        "series": series,
        "marcadores": marcadores,
        "estatisticas": estatisticas,
        "tabela": tabela,
        "leitura": leitura,
        "altura": int(altura),
    }


# ======================================================= blocos de dados ===
def _classes(serie: pd.Series, n_classes: int, formato: str) -> dict:
    """Classes de igual amplitude para um histograma.

    Devolve rótulos, frequências, borda inicial e largura das classes —
    estes dois últimos alimentam a fórmula de posição dos marcadores.
    """
    s = _numerica(serie)
    minimo, maximo = float(s.min()), float(s.max())
    if maximo <= minimo:
        maximo = minimo + 1.0
    largura = (maximo - minimo) / n_classes
    bordas = [minimo + i * largura for i in range(n_classes + 1)]
    cortes = pd.cut(s, bins=bordas, include_lowest=True)
    freq = cortes.value_counts().sort_index()

    casas = _casas(formato)
    rotulos: list[str] = []
    for i in range(n_classes):
        a, b = bordas[i], bordas[i + 1]
        if formato == "pct":
            rotulos.append(f"{_pc(a, 1)} a {_pc(b, 1)}")
        else:
            rotulos.append(f"{_n(a, casas)} a {_n(b, casas)}")

    valores = [int(v) for v in freq.values]
    total = sum(valores) or 1
    acumulado = 0
    linhas = []
    for rotulo, valor in zip(rotulos, valores):
        acumulado += valor
        linhas.append(
            [
                rotulo,
                valor,
                _f(100.0 * valor / total, 2),
                _f(100.0 * acumulado / total, 2),
            ]
        )
    return {
        "rotulos": rotulos,
        "valores": valores,
        "inicio": minimo,
        "largura": largura,
        "bordas": [_f(b) for b in bordas],
        "linhas": linhas,
    }


def _boxplot(grupos: list[tuple[str, pd.Series]]) -> dict:
    """Caixas e pontos atípicos por grupo, na ordem informada."""
    rotulos: list[str] = []
    caixas: list[list[float | None]] = []
    atipicos: list[list[float]] = []
    resumo: list[list[Any]] = []
    todos: list[float] = []

    for indice, (rotulo, serie) in enumerate(grupos):
        s = _numerica(serie)
        if s.empty:
            continue
        q1, q2, q3 = (float(x) for x in s.quantile([0.25, 0.50, 0.75]))
        iqr = q3 - q1
        lim_inf, lim_sup = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        dentro = s[(s >= lim_inf) & (s <= lim_sup)]
        inferior = float(dentro.min()) if not dentro.empty else float(s.min())
        superior = float(dentro.max()) if not dentro.empty else float(s.max())
        rotulos.append(rotulo)
        caixas.append([_f(inferior), _f(q1), _f(q2), _f(q3), _f(superior)])
        for valor in s[(s < lim_inf) | (s > lim_sup)]:
            atipicos.append([indice, _f(valor)])
        resumo.append(
            [
                rotulo,
                int(s.size),
                _f(s.mean()),
                _f(q2),
                _f(q1),
                _f(q3),
                _f(iqr),
                _f(s.std(ddof=1)) if s.size > 1 else 0.0,
                _f(s.min()),
                _f(s.max()),
            ]
        )
        todos.extend(float(v) for v in s)

    return {
        "rotulos": rotulos,
        "caixas": caixas,
        "atipicos": atipicos,
        "resumo": resumo,
        "todos": todos,
    }


def _amostrar(pontos: list[list[float]], limite: int = 500) -> list[list[float]]:
    """Limita a nuvem de pontos ao teto de 500 marcas por gráfico."""
    if len(pontos) <= limite:
        return pontos
    passo = len(pontos) / limite
    return [pontos[int(i * passo)] for i in range(limite)]


def _faixas_resumo(
    xs: list[float],
    ys: list[float],
    rotulo_x: str,
    casas_x: int = 2,
    casas_y: int = 2,
    n_faixas: int = 8,
) -> list[list[Any]]:
    """Resumo por faixas de x — tabela de alívio das dispersões."""
    base = pd.DataFrame({"x": xs, "y": ys}).dropna()
    if base.empty:
        return []
    try:
        faixas = pd.qcut(base["x"], q=n_faixas, duplicates="drop")
    except ValueError:
        faixas = pd.cut(base["x"], bins=min(n_faixas, 4))
    linhas = []
    for intervalo, grupo in base.groupby(faixas, observed=True):
        linhas.append(
            [
                f"{_n(intervalo.left, casas_x)} a {_n(intervalo.right, casas_x)}",
                int(len(grupo)),
                _f(grupo["y"].mean(), casas_y + 2),
                _f(grupo["y"].median(), casas_y + 2),
            ]
        )
    return linhas


def _nota_parcial(rotulo: str, registros: int, minimo: int = 10) -> str:
    """Alerta quando um mês extremo tem poucos registros (mês parcial)."""
    if registros >= minimo:
        return ""
    return (
        f" O mês {rotulo} é parcial, com apenas {registros} registros, "
        "e por isso não deve ser comparado aos meses completos."
    )


def _correlacao(df: pd.DataFrame, coluna_x: str, coluna_y: str) -> float | None:
    """Correlação de Pearson entre duas colunas, com ``dropna`` prévio."""
    base = df[[coluna_x, coluna_y]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(base) < 3:
        return None
    return _f(base[coluna_x].corr(base[coluna_y]))


def _forca(r: float | None) -> str:
    """Classificação verbal da força de uma correlação."""
    if r is None:
        return "indefinida"
    a = abs(r)
    if a >= 0.70:
        return "forte"
    if a >= 0.40:
        return "moderada"
    if a >= 0.20:
        return "fraca"
    return "desprezível"


def _status_defeitos(taxa: float | None) -> str:
    """Cor de status conforme a faixa da taxa de defeitos."""
    if taxa is None:
        return "slot1"
    for limite, cor in FAIXAS_DEFEITOS:
        if taxa < limite:
            return cor
    return "status:critico"


def _categorias(df: pd.DataFrame, coluna: str, ordem: list[str]) -> list[str]:
    """Categorias presentes no recorte, na ordem fixa do contrato."""
    presentes = set(df[coluna].dropna().astype(str).unique())
    return [c for c in ordem if c in presentes]


def _meses(df: pd.DataFrame) -> tuple[list[pd.Period], list[str]]:
    """Períodos mensais presentes e seus rótulos ("01/2025")."""
    periodos = sorted(df["data"].dropna().dt.to_period("M").unique())
    return periodos, [f"{p.month:02d}/{p.year}" for p in periodos]


def _taxa(df: pd.DataFrame) -> float | None:
    """Taxa de defeitos agregada: soma(defeituosas) / soma(produzidas)."""
    produzidas = _numerica(df["unidades_produzidas"]).sum()
    defeituosas = _numerica(df["unidades_defeituosas"]).sum()
    if not produzidas:
        return None
    return _f(defeituosas / produzidas)


def _produtividade(df: pd.DataFrame) -> float | None:
    """Produtividade agregada: soma(produzidas) / soma(horas efetivas)."""
    horas = _numerica(df["horas_efetivas"]).sum()
    produzidas = _numerica(df["unidades_produzidas"]).sum()
    if not horas:
        return None
    return _f(produzidas / horas)


def _energia_unidade(df: pd.DataFrame) -> float | None:
    """Energia por unidade agregada: soma(kWh) / soma(produzidas)."""
    base = df[["consumo_energia_kwh", "unidades_produzidas"]].apply(
        pd.to_numeric, errors="coerce"
    ).dropna()
    produzidas = base["unidades_produzidas"].sum()
    if not produzidas:
        return None
    return _f(base["consumo_energia_kwh"].sum() / produzidas)


# ============================================================== seções ====
def _visao_geral(df: pd.DataFrame) -> list[dict]:
    """Composição da base: participação na produção e nos registros."""
    graficos: list[dict] = []
    produtos = _categorias(df, "produto", ORDEM_PRODUTO)

    totais = []
    medias = []
    for produto in produtos:
        recorte = df[df["produto"].astype(str) == produto]
        totais.append(int(_numerica(recorte["unidades_produzidas"]).sum()))
        medias.append(_f(_numerica(recorte["unidades_produzidas"]).mean(), 2))
    total_geral = sum(totais) or 1
    lider = produtos[totais.index(max(totais))]

    graficos.append(
        _grafico(
            "composicao-producao-por-produto",
            "visao-geral",
            "Participação de cada produto na produção total",
            f"{_n(total_geral, 0)} unidades produzidas em {len(df)} registros",
            "donut",
            {"nome": "Produto", "tipo": "category", "rotulos": produtos},
            {"nome": "Unidades produzidas (un)", "tipo": "value", "formato": "int"},
            [
                _serie(
                    "Unidades produzidas",
                    "pie",
                    CORES_PRODUTO.get(produtos[0], "slot1"),
                    [
                        {"name": produto, "value": total}
                        for produto, total in zip(produtos, totais)
                    ],
                    rotulo_direto=True,
                    cores=[CORES_PRODUTO.get(p, "slot1") for p in produtos],
                )
            ],
            _estat(totais, "Unidades produzidas por produto", "un", "int"),
            _tabela(
                ["Produto", "Registros", "Unidades (total)", "Participação (%)", "Média por registro (un)"],
                [
                    [
                        produto,
                        int((df["produto"].astype(str) == produto).sum()),
                        total,
                        _f(100.0 * total / total_geral, 2),
                        media,
                    ]
                    for produto, total, media in zip(produtos, totais, medias)
                ],
            ),
            (
                f"{lider} responde por {_pc(max(totais) / total_geral)} das "
                f"{_n(total_geral, 0)} unidades da base. A fatia reflete tanto o número de "
                "registros quanto o ritmo de fabricação de cada produto, por isso não deve "
                "ser lida como desempenho."
            ),
            altura=360,
        )
    )

    turnos = _categorias(df, "turno", ORDEM_TURNO)
    registros = [int((df["turno"].astype(str) == t).sum()) for t in turnos]
    total_reg = sum(registros) or 1
    unidades_turno = [
        int(_numerica(df[df["turno"].astype(str) == t]["unidades_produzidas"]).sum())
        for t in turnos
    ]
    graficos.append(
        _grafico(
            "composicao-registros-por-turno",
            "visao-geral",
            "Distribuição dos registros por turno",
            "Estrutura da amostra: 500 registros de produção",
            "donut",
            {"nome": "Turno", "tipo": "category", "rotulos": turnos},
            {"nome": "Registros", "tipo": "value", "formato": "int"},
            [
                _serie(
                    "Registros",
                    "pie",
                    CORES_TURNO.get(turnos[0], "slot1"),
                    [
                        {"name": turno, "value": qtd}
                        for turno, qtd in zip(turnos, registros)
                    ],
                    rotulo_direto=True,
                    cores=[CORES_TURNO.get(t, "slot1") for t in turnos],
                )
            ],
            _estat(registros, "Registros por turno", "registros", "int"),
            _tabela(
                ["Turno", "Registros", "Participação (%)", "Unidades (total)"],
                [
                    [turno, qtd, _f(100.0 * qtd / total_reg, 2), unidades]
                    for turno, qtd, unidades in zip(turnos, registros, unidades_turno)
                ],
            ),
            (
                f"O turno {turnos[registros.index(max(registros))]} concentra "
                f"{max(registros)} dos {total_reg} registros "
                f"({_pc(max(registros) / total_reg)}), enquanto o menor tem "
                f"{min(registros)}. A amostra é desbalanceada entre turnos, o que exige "
                "comparar médias e não totais."
            ),
            altura=360,
        )
    )
    return graficos


def _distribuicoes(df: pd.DataFrame) -> list[dict]:
    """Sete histogramas com marcadores estatísticos no eixo x."""
    especificacoes = [
        (
            "dist-unidades-produzidas",
            "unidades_produzidas",
            "Distribuição das unidades produzidas",
            "Unidades produzidas",
            "Unidades produzidas (un)",
            "un",
            "int",
            "slot1",
            13,
        ),
        (
            "dist-horas-parada",
            "horas_parada_maquina",
            "Distribuição das horas de parada de máquina",
            "Horas de parada de máquina",
            "Horas de parada (h)",
            "h",
            "num",
            "slot2",
            14,
        ),
        (
            "dist-consumo-energia",
            "consumo_energia_kwh",
            "Distribuição do consumo de energia",
            "Consumo de energia",
            "Consumo de energia (kWh)",
            "kWh",
            "num",
            "slot4",
            13,
        ),
        (
            "dist-unidades-defeituosas",
            "unidades_defeituosas",
            "Distribuição das unidades defeituosas",
            "Unidades defeituosas",
            "Unidades defeituosas (un)",
            "un",
            "int",
            "slot8",
            13,
        ),
        (
            "dist-taxa-defeitos",
            "taxa_defeitos",
            "Distribuição da taxa de defeitos",
            "Taxa de defeitos",
            "Taxa de defeitos (%)",
            "%",
            "pct",
            "slot8",
            14,
        ),
        (
            "dist-produtividade-hora",
            "produtividade_hora",
            "Distribuição da produtividade por hora",
            "Produtividade por hora",
            "Produtividade (un/h)",
            "un/h",
            "num",
            "slot3",
            14,
        ),
        (
            "dist-energia-por-unidade",
            "energia_por_unidade",
            "Distribuição da energia por unidade",
            "Energia por unidade",
            "Energia por unidade (kWh/un)",
            "kWh/un",
            "num",
            "slot4",
            13,
        ),
    ]

    graficos: list[dict] = []
    for (
        id_,
        coluna,
        titulo,
        variavel,
        nome_x,
        unidade,
        formato,
        cor,
        n_classes,
    ) in especificacoes:
        serie = _numerica(df[coluna])
        est = _estat(serie, variavel, unidade, formato)
        classes = _classes(serie, n_classes, formato)
        marcadores = _marcadores_x(est, classes["inicio"], classes["largura"])

        # Variáveis inteiras de escala pequena (defeituosas) perdem informação
        # se a leitura arredondar para zero casas.
        casas_leitura = _casas(formato)
        if formato == "int" and (est["maximo"] or 0) < 100:
            casas_leitura = 2
        formatar = (lambda v: _pc(v, 2)) if formato == "pct" else (
            lambda v: _n(v, casas_leitura)
        )
        assimetria = (est["media"] or 0) - (est["mediana"] or 0)
        if formato == "pct":
            diferenca = _pc(abs(assimetria), 2)
        else:
            diferenca = _n(abs(assimetria), casas_leitura)
        sentido = "acima" if assimetria > 0 else "abaixo"
        maior = classes["valores"].index(max(classes["valores"]))

        leitura = (
            f"A classe mais frequente é {classes['rotulos'][maior]}, com "
            f"{max(classes['valores'])} dos {est['n']} registros. A média "
            f"({formatar(est['media'])}) fica {diferenca} {sentido} da mediana "
            f"({formatar(est['mediana'])}), e o desvio-padrão de "
            f"{formatar(est['desvio_padrao'])} corresponde a um CV de "
            f"{_pc(est['coef_variacao'])}; metade dos registros está entre "
            f"{formatar(est['q1'])} e {formatar(est['q3'])}."
        )

        graficos.append(
            _grafico(
                id_,
                "distribuicoes",
                titulo,
                f"{est['n']} registros · {n_classes} classes de igual amplitude",
                "histograma",
                {"nome": nome_x, "tipo": "category", "rotulos": classes["rotulos"]},
                {"nome": "Frequência (registros)", "tipo": "value", "formato": "int"},
                [
                    _serie(
                        "Registros",
                        "bar",
                        cor,
                        classes["valores"],
                        rotulo_direto=True,
                    )
                ],
                est,
                _tabela(
                    ["Classe", "Frequência", "Relativa (%)", "Acumulada (%)"],
                    classes["linhas"],
                ),
                leitura,
                marcadores=marcadores,
                altura=360,
            )
        )
    return graficos


def _temporal(df: pd.DataFrame) -> list[dict]:
    """Cinco gráficos mensais: volume, produtividade, defeitos e entregas."""
    graficos: list[dict] = []
    periodos, rotulos = _meses(df)
    base = df.copy()
    base["_mes"] = base["data"].dt.to_period("M")
    produtos = _categorias(df, "produto", ORDEM_PRODUTO)
    # Quantidade de registros por mês: o último mês da base é parcial e isso
    # precisa ser avisado em toda leitura que cite um mês extremo.
    contagem_mes = base.groupby("_mes", observed=True)["id_registro"].count()
    registros_mes = [int(contagem_mes.get(p, 0)) for p in periodos]

    # 8. Produção mensal por produto (volume) ------------------------------
    series_produto: dict[str, list[float | None]] = {}
    for produto in produtos:
        recorte = base[base["produto"].astype(str) == produto]
        soma = recorte.groupby("_mes", observed=True)["unidades_produzidas"].sum()
        series_produto[produto] = [
            _i(soma.get(p)) if p in soma.index else None for p in periodos
        ]

    pool = [v for valores in series_produto.values() for v in valores if v is not None]
    est_pool = _estat(pool, "Unidades produzidas por mês e produto", "un", "int")
    graficos.append(
        _grafico(
            "producao-mensal-por-produto",
            "temporal",
            "Produção mensal por produto",
            f"Soma de unidades por mês · {len(periodos)} meses",
            "linhas",
            {"nome": "Mês", "tipo": "category", "rotulos": rotulos},
            {"nome": "Unidades produzidas (un)", "tipo": "value", "formato": "int"},
            [
                _serie(
                    produto,
                    "line",
                    CORES_PRODUTO.get(produto, "slot1"),
                    series_produto[produto],
                )
                for produto in produtos
            ],
            est_pool,
            _tabela(
                ["Mês"] + produtos,
                [
                    [rotulo] + [series_produto[p][i] for p in produtos]
                    for i, rotulo in enumerate(rotulos)
                ],
            ),
            (
                "As curvas de volume mensal variam entre "
                f"{_n(est_pool['minimo'], 0)} e {_n(est_pool['maximo'], 0)} unidades por "
                f"produto, com média de {_n(est_pool['media'], 0)}. Micro-ondas aparece no "
                "alto porque cada registro seu gira perto de 300 unidades, contra cerca de "
                "130 da Geladeira: compare a produtividade por hora antes de concluir."
                + _nota_parcial(rotulos[-1], registros_mes[-1])
            ),
            marcadores=_marcadores_y(est_pool),
            altura=380,
        )
    )

    # 9. Produção mensal total + média móvel de 3 meses --------------------
    total_mes = base.groupby("_mes", observed=True)["unidades_produzidas"].sum()
    totais = [_i(total_mes.get(p)) if p in total_mes.index else None for p in periodos]
    serie_totais = pd.Series([v for v in totais], dtype="float64")
    movel = serie_totais.rolling(3, min_periods=3).mean()
    movel_lista = [_f(v, 2) if pd.notna(v) else None for v in movel]
    est_total = _estat(totais, "Unidades produzidas por mês", "un", "int")
    pico = totais.index(max(v for v in totais if v is not None))
    vale = totais.index(min(v for v in totais if v is not None))
    graficos.append(
        _grafico(
            "producao-mensal-total",
            "temporal",
            "Produção total por mês e média móvel de 3 meses",
            f"{_n(sum(v for v in totais if v is not None), 0)} unidades no período",
            "area",
            {"nome": "Mês", "tipo": "category", "rotulos": rotulos},
            {"nome": "Unidades produzidas (un)", "tipo": "value", "formato": "int"},
            [
                _serie("Produção do mês", "line", "slot1", totais),
                _serie("Média móvel (3 meses)", "line", "slot2", movel_lista),
            ],
            est_total,
            _tabela(
                ["Mês", "Registros", "Unidades produzidas", "Média móvel (3 meses)"],
                [
                    [rotulo, registros_mes[i], totais[i], movel_lista[i]]
                    for i, rotulo in enumerate(rotulos)
                ],
            ),
            (
                f"A produção mensal média é de {_n(est_total['media'], 0)} unidades, com pico "
                f"de {_n(est_total['maximo'], 0)} em {rotulos[pico]} "
                f"({registros_mes[pico]} registros) e mínimo de "
                f"{_n(est_total['minimo'], 0)} em {rotulos[vale]} "
                f"({registros_mes[vale]} registros). A média móvel mostra oscilação de curto "
                f"prazo em torno de {_n(est_total['mediana'], 0)} unidades, sem tendência clara "
                "de alta ou de queda." + _nota_parcial(rotulos[vale], registros_mes[vale])
            ),
            marcadores=_marcadores_y(est_total),
            altura=380,
        )
    )

    # 10. Produtividade mensal por produto --------------------------------
    series_prod: dict[str, list[float | None]] = {}
    for produto in produtos:
        recorte = base[base["produto"].astype(str) == produto]
        agrupado = recorte.groupby("_mes", observed=True)[
            ["unidades_produzidas", "horas_efetivas"]
        ].sum()
        valores: list[float | None] = []
        for p in periodos:
            if p in agrupado.index and agrupado.loc[p, "horas_efetivas"]:
                valores.append(
                    _f(
                        agrupado.loc[p, "unidades_produzidas"]
                        / agrupado.loc[p, "horas_efetivas"],
                        2,
                    )
                )
            else:
                valores.append(None)
        series_prod[produto] = valores

    pool_prod = [v for valores in series_prod.values() for v in valores if v is not None]
    est_prod = _estat(pool_prod, "Produtividade mensal por produto", "un/h", "num")
    medias_prod = {
        produto: _f(
            pd.Series([v for v in valores if v is not None], dtype="float64").mean(), 2
        )
        for produto, valores in series_prod.items()
    }
    melhor = max(medias_prod, key=lambda k: medias_prod[k] or 0)
    graficos.append(
        _grafico(
            "produtividade-mensal-por-produto",
            "temporal",
            "Produtividade mensal por produto",
            "Soma de unidades dividida pela soma de horas efetivas do mês",
            "linhas",
            {"nome": "Mês", "tipo": "category", "rotulos": rotulos},
            {"nome": "Produtividade (un/h)", "tipo": "value", "formato": "num"},
            [
                _serie(
                    produto,
                    "line",
                    CORES_PRODUTO.get(produto, "slot1"),
                    series_prod[produto],
                )
                for produto in produtos
            ],
            est_prod,
            _tabela(
                ["Mês"] + produtos,
                [
                    [rotulo] + [series_prod[p][i] for p in produtos]
                    for i, rotulo in enumerate(rotulos)
                ],
            ),
            (
                f"Em produtividade por hora efetiva, {melhor} lidera com média mensal de "
                f"{_n(medias_prod[melhor], 1)} un/h. Esta é a comparação justa entre produtos: "
                "ela remove o efeito do ritmo de fabricação que infla o volume absoluto."
            ),
            marcadores=_marcadores_y(est_prod),
            altura=380,
        )
    )

    # 11. Taxa de defeitos mensal -----------------------------------------
    agregado = base.groupby("_mes", observed=True)[
        ["unidades_produzidas", "unidades_defeituosas"]
    ].sum()
    taxas: list[float | None] = []
    for p in periodos:
        if p in agregado.index and agregado.loc[p, "unidades_produzidas"]:
            taxas.append(
                _f(
                    agregado.loc[p, "unidades_defeituosas"]
                    / agregado.loc[p, "unidades_produzidas"]
                )
            )
        else:
            taxas.append(None)
    est_taxa = _estat(taxas, "Taxa de defeitos mensal", "%", "pct")
    pior = taxas.index(max(v for v in taxas if v is not None))
    # O maior entre os meses completos, para não premiar um mês parcial.
    completos = [
        i for i, n in enumerate(registros_mes) if n >= 10 and taxas[i] is not None
    ]
    pior_completo = max(completos, key=lambda i: taxas[i]) if completos else pior
    graficos.append(
        _grafico(
            "taxa-defeitos-mensal",
            "temporal",
            "Taxa de defeitos por mês",
            "Soma de defeituosas dividida pela soma de produzidas (não é média de taxas)",
            "linhas",
            {"nome": "Mês", "tipo": "category", "rotulos": rotulos},
            {"nome": "Taxa de defeitos (%)", "tipo": "value", "formato": "pct"},
            [_serie("Taxa de defeitos", "line", "slot8", taxas, rotulo_direto=False)],
            est_taxa,
            _tabela(
                ["Mês", "Registros", "Unidades produzidas", "Unidades defeituosas", "Taxa de defeitos (%)"],
                [
                    [
                        rotulo,
                        registros_mes[i],
                        _i(agregado.loc[p, "unidades_produzidas"])
                        if p in agregado.index
                        else None,
                        _i(agregado.loc[p, "unidades_defeituosas"])
                        if p in agregado.index
                        else None,
                        taxas[i],
                    ]
                    for i, (p, rotulo) in enumerate(zip(periodos, rotulos))
                ],
            ),
            (
                f"A taxa de defeitos mensal oscila entre {_pc(est_taxa['minimo'], 2)} e "
                f"{_pc(est_taxa['maximo'], 2)}, com média de {_pc(est_taxa['media'], 2)} e "
                f"mediana de {_pc(est_taxa['mediana'], 2)}. Entre os meses completos, o mais "
                f"alto é {rotulos[pior_completo]} ({_pc(taxas[pior_completo], 2)} em "
                f"{registros_mes[pior_completo]} registros), e nenhum mês cai abaixo de "
                f"{_pc(est_taxa['minimo'], 2)} — um patamar estrutural, não um evento isolado."
                + (
                    _nota_parcial(rotulos[pior], registros_mes[pior])
                    if pior != pior_completo
                    else ""
                )
            ),
            marcadores=_marcadores_y(est_taxa),
            altura=360,
        )
    )

    # 12. Entregas no prazo por mês ---------------------------------------
    entregas = base.groupby("_mes", observed=True)["entregas_no_prazo_pct"].mean()
    valores_entrega = [
        _f(entregas.get(p), 2) if p in entregas.index else None for p in periodos
    ]
    est_entrega = _estat(
        valores_entrega, "Entregas no prazo (média mensal)", "%", "num"
    )
    graficos.append(
        _grafico(
            "entregas-prazo-mensal",
            "temporal",
            "Entregas no prazo por mês",
            "Média mensal do percentual de entregas no prazo",
            "linhas",
            {"nome": "Mês", "tipo": "category", "rotulos": rotulos},
            {"nome": "Entregas no prazo (%)", "tipo": "value", "formato": "num"},
            [_serie("Entregas no prazo", "line", "slot3", valores_entrega)],
            est_entrega,
            _tabela(
                ["Mês", "Entregas no prazo (%)", "Registros"],
                [
                    [
                        rotulo,
                        valores_entrega[i],
                        int((base["_mes"] == p).sum()),
                    ]
                    for i, (p, rotulo) in enumerate(zip(periodos, rotulos))
                ],
            ),
            (
                f"O indicador de entregas no prazo fica em média {_n(est_entrega['media'], 1)}% "
                f"ao mês, variando de {_n(est_entrega['minimo'], 1)}% a "
                f"{_n(est_entrega['maximo'], 1)}%. O CV de "
                f"{_pc(est_entrega['coef_variacao'], 2)} indica um nível de serviço estável no "
                "período."
            ),
            marcadores=_marcadores_y(est_entrega),
            altura=360,
        )
    )
    return graficos


def _comparativos(df: pd.DataFrame) -> list[dict]:
    """Seis comparativos entre produtos, turnos e linhas."""
    graficos: list[dict] = []
    produtos = _categorias(df, "produto", ORDEM_PRODUTO)
    turnos = _categorias(df, "turno", ORDEM_TURNO)
    linhas_prod = _categorias(df, "linha_producao", ORDEM_LINHA)

    # 13. Produção média por produto --------------------------------------
    medias, medianas, desvios, ns, totais = [], [], [], [], []
    for produto in produtos:
        serie = _numerica(df[df["produto"].astype(str) == produto]["unidades_produzidas"])
        medias.append(_f(serie.mean(), 2))
        medianas.append(_f(serie.median(), 2))
        desvios.append(_f(serie.std(ddof=1), 2))
        ns.append(int(serie.size))
        totais.append(_i(serie.sum()))
    est_medias = _estat(medias, "Produção média por registro (produtos)", "un", "num")
    lider = produtos[medias.index(max(medias))]
    ultimo = produtos[medias.index(min(medias))]
    graficos.append(
        _grafico(
            "producao-media-por-produto",
            "comparativos",
            "Produção média por registro, por produto",
            "Responde à questão 1 — leia junto com a produtividade por hora",
            "barras",
            {"nome": "Produto", "tipo": "category", "rotulos": produtos},
            {"nome": "Unidades por registro (un)", "tipo": "value", "formato": "num"},
            [
                _serie(
                    "Produção média",
                    "bar",
                    CORES_PRODUTO.get(produtos[0], "slot1"),
                    [
                        {"name": produto, "value": media, "cor": CORES_PRODUTO.get(produto, "slot1")}
                        for produto, media in zip(produtos, medias)
                    ],
                    rotulo_direto=True,
                    cores=[CORES_PRODUTO.get(p, "slot1") for p in produtos],
                )
            ],
            est_medias,
            _tabela(
                ["Produto", "Registros", "Média (un)", "Mediana (un)", "Desvio-padrão (un)", "Total (un)"],
                [
                    [produto, n, media, mediana, desvio, total]
                    for produto, n, media, mediana, desvio, total in zip(
                        produtos, ns, medias, medianas, desvios, totais
                    )
                ],
            ),
            (
                f"{lider} apresenta a maior produção média por registro, "
                f"{_n(max(medias), 1)} un, contra {_n(min(medias), 1)} un de {ultimo} — "
                f"diferença de {_n(max(medias) - min(medias), 1)} un. Atenção: os ritmos de "
                "fabricação são diferentes, então o número mede o tamanho do lote típico de "
                "cada produto, não a eficiência da fábrica."
            ),
            marcadores=_marcadores_y(est_medias),
            altura=360,
        )
    )

    # 14. Produtividade por produto ---------------------------------------
    produtividades, horas_totais = [], []
    for produto in produtos:
        recorte = df[df["produto"].astype(str) == produto]
        produtividades.append(_produtividade(recorte))
        horas_totais.append(_f(_numerica(recorte["horas_efetivas"]).sum(), 2))
    est_produtividade = _estat(
        produtividades, "Produtividade por produto", "un/h", "num"
    )
    melhor = produtos[produtividades.index(max(produtividades))]
    graficos.append(
        _grafico(
            "produtividade-por-produto",
            "comparativos",
            "Produtividade por produto",
            "Soma de unidades produzidas dividida pela soma de horas efetivas",
            "barras",
            {"nome": "Produto", "tipo": "category", "rotulos": produtos},
            {"nome": "Produtividade (un/h)", "tipo": "value", "formato": "num"},
            [
                _serie(
                    "Produtividade",
                    "bar",
                    CORES_PRODUTO.get(produtos[0], "slot1"),
                    [
                        {"name": produto, "value": valor, "cor": CORES_PRODUTO.get(produto, "slot1")}
                        for produto, valor in zip(produtos, produtividades)
                    ],
                    rotulo_direto=True,
                    cores=[CORES_PRODUTO.get(p, "slot1") for p in produtos],
                )
            ],
            est_produtividade,
            _tabela(
                ["Produto", "Unidades (total)", "Horas efetivas (total)", "Produtividade (un/h)"],
                [
                    [produto, total, horas, valor]
                    for produto, total, horas, valor in zip(
                        produtos, totais, horas_totais, produtividades
                    )
                ],
            ),
            (
                f"Por hora efetiva, {melhor} rende {_n(max(produtividades), 1)} un/h, contra "
                f"{_n(min(produtividades), 1)} un/h de "
                f"{produtos[produtividades.index(min(produtividades))]} — uma relação de "
                f"{_n(max(produtividades) / min(produtividades), 1)} para 1. A ordem repete a do "
                "volume porque o ritmo de fabricação domina o indicador, mas aqui a diferença "
                "já está normalizada pelas horas trabalhadas."
            ),
            marcadores=_marcadores_y(est_produtividade),
            altura=360,
        )
    )

    # 15. Boxplot da produção por turno -----------------------------------
    caixa_turno = _boxplot(
        [
            (turno, df[df["turno"].astype(str) == turno]["unidades_produzidas"])
            for turno in turnos
        ]
    )
    est_turno = _estat(
        df["unidades_produzidas"], "Unidades produzidas (todos os turnos)", "un", "int"
    )
    acima_turno = sum(
        1
        for indice, valor in caixa_turno["atipicos"]
        if valor > (caixa_turno["caixas"][indice][4] or 0)
    )
    abaixo_turno = len(caixa_turno["atipicos"]) - acima_turno
    graficos.append(
        _grafico(
            "boxplot-producao-por-turno",
            "comparativos",
            "Distribuição da produção por turno",
            "Responde à questão 2 — caixas de Tukey com pontos atípicos",
            "boxplot",
            {"nome": "Turno", "tipo": "category", "rotulos": caixa_turno["rotulos"]},
            {"nome": "Unidades produzidas (un)", "tipo": "value", "formato": "int"},
            [
                _serie(
                    "Unidades produzidas",
                    "boxplot",
                    CORES_TURNO.get(caixa_turno["rotulos"][0], "slot1"),
                    caixa_turno["caixas"],
                    outliers=caixa_turno["atipicos"],
                    cores=[CORES_TURNO.get(t, "slot1") for t in caixa_turno["rotulos"]],
                )
            ],
            est_turno,
            _tabela(
                ["Turno", "n", "Média", "Mediana", "Q1", "Q3", "IQR", "Desvio-padrão", "Mínimo", "Máximo"],
                caixa_turno["resumo"],
            ),
            (
                "A mediana vai de "
                f"{_n(min(l[3] for l in caixa_turno['resumo']), 0)} a "
                f"{_n(max(l[3] for l in caixa_turno['resumo']), 0)} un e o IQR de "
                + " · ".join(
                    f"{linha[0]}: {_n(linha[6], 0)} un" for linha in caixa_turno["resumo"]
                )
                + f". São {len(caixa_turno['atipicos'])} pontos atípicos pelo critério de Tukey, "
                + (
                    "todos acima do limite superior"
                    if abaixo_turno == 0
                    else f"{acima_turno} acima e {abaixo_turno} abaixo dos limites"
                )
                + f", com máximo de {_n(est_turno['maximo'], 0)} un."
            ),
            marcadores=_marcadores_y(est_turno),
            altura=380,
        )
    )

    # 16. Variabilidade da produção por turno (DP e CV) -------------------
    dps, cvs, medias_turno, ns_turno = [], [], [], []
    for turno in turnos:
        serie = _numerica(df[df["turno"].astype(str) == turno]["unidades_produzidas"])
        media = float(serie.mean())
        dp = float(serie.std(ddof=1))
        dps.append(_f(dp, 2))
        cvs.append(_f(100.0 * dp / media, 2) if media else None)
        medias_turno.append(_f(media, 2))
        ns_turno.append(int(serie.size))
    est_dp = _estat(dps, "Desvio-padrão da produção por turno", "un", "num")
    maior_dp = turnos[dps.index(max(dps))]
    maior_cv = turnos[cvs.index(max(cvs))]
    graficos.append(
        _grafico(
            "variabilidade-producao-por-turno",
            "comparativos",
            "Variabilidade da produção por turno",
            "Desvio-padrão (un) e coeficiente de variação (%) na mesma escala — sem eixo duplo",
            "barras-agrupadas",
            {"nome": "Turno", "tipo": "category", "rotulos": turnos},
            {
                "nome": "Desvio-padrão (un) · Coeficiente de variação (%)",
                "tipo": "value",
                "formato": "num",
            },
            [
                _serie("Desvio-padrão (un)", "bar", "slot1", dps, rotulo_direto=True),
                _serie(
                    "Coeficiente de variação (%)",
                    "bar",
                    "slot7",
                    cvs,
                    rotulo_direto=True,
                ),
            ],
            est_dp,
            _tabela(
                ["Turno", "n", "Média (un)", "Desvio-padrão (un)", "CV (%)"],
                [
                    [turno, n, media, dp, cv]
                    for turno, n, media, dp, cv in zip(
                        turnos, ns_turno, medias_turno, dps, cvs
                    )
                ],
            ),
            (
                (
                    f"O turno {maior_dp} lidera as duas medidas de variabilidade: "
                    f"desvio-padrão de {_n(max(dps), 1)} un e CV de {_n(max(cvs), 1)}%, "
                    f"contra {_n(min(dps), 1)} un e {_n(min(cvs), 1)}% do turno menos "
                    f"variável. "
                    if maior_dp == maior_cv
                    else (
                        f"O turno {maior_dp} tem o maior desvio-padrão, {_n(max(dps), 1)} un, "
                        f"e o turno {maior_cv} o maior coeficiente de variação, "
                        f"{_n(max(cvs), 1)}%. "
                    )
                )
                + "As duas medidas aparecem no mesmo eixo porque têm magnitudes comparáveis; o "
                "CV é a leitura correta quando as médias dos turnos diferem."
            ),
            marcadores=_marcadores_y(est_dp),
            altura=360,
        )
    )

    # 17. Boxplot da produtividade por produto ----------------------------
    caixa_prod = _boxplot(
        [
            (produto, df[df["produto"].astype(str) == produto]["produtividade_hora"])
            for produto in produtos
        ]
    )
    est_prod_hora = _estat(
        df["produtividade_hora"], "Produtividade por hora (todos os produtos)", "un/h", "num"
    )
    graficos.append(
        _grafico(
            "boxplot-produtividade-por-produto",
            "comparativos",
            "Distribuição da produtividade por produto",
            "Caixas de Tukey sobre a produtividade de cada registro",
            "boxplot",
            {"nome": "Produto", "tipo": "category", "rotulos": caixa_prod["rotulos"]},
            {"nome": "Produtividade (un/h)", "tipo": "value", "formato": "num"},
            [
                _serie(
                    "Produtividade por hora",
                    "boxplot",
                    CORES_PRODUTO.get(caixa_prod["rotulos"][0], "slot1"),
                    caixa_prod["caixas"],
                    outliers=caixa_prod["atipicos"],
                    cores=[
                        CORES_PRODUTO.get(p, "slot1") for p in caixa_prod["rotulos"]
                    ],
                )
            ],
            est_prod_hora,
            _tabela(
                ["Produto", "n", "Média", "Mediana", "Q1", "Q3", "IQR", "Desvio-padrão", "Mínimo", "Máximo"],
                caixa_prod["resumo"],
            ),
            (
                "A mediana da produtividade vai de "
                f"{_n(min(l[3] for l in caixa_prod['resumo']), 1)} a "
                f"{_n(max(l[3] for l in caixa_prod['resumo']), 1)} un/h, enquanto o IQR de cada "
                f"produto fica entre {_n(min(l[6] for l in caixa_prod['resumo']), 1)} e "
                f"{_n(max(l[6] for l in caixa_prod['resumo']), 1)} un/h. A distância entre as "
                "caixas é muito maior que a largura delas, o que indica diferença de ritmo de "
                "fabricação e não de dispersão interna."
            ),
            marcadores=_marcadores_y(est_prod_hora),
            altura=380,
        )
    )

    # 18. Produção média por linha e turno --------------------------------
    series_linha: list[dict] = []
    matriz: list[list[Any]] = []
    valores_pool: list[float] = []
    for turno in turnos:
        valores: list[float | None] = []
        for linha in linhas_prod:
            recorte = df[
                (df["linha_producao"].astype(str) == linha)
                & (df["turno"].astype(str) == turno)
            ]
            serie = _numerica(recorte["unidades_produzidas"])
            valor = _f(serie.mean(), 2) if not serie.empty else None
            valores.append(valor)
            if valor is not None:
                valores_pool.append(valor)
        series_linha.append(
            _serie(turno, "bar", CORES_TURNO.get(turno, "slot1"), valores, rotulo_direto=False)
        )
    for i, linha in enumerate(linhas_prod):
        matriz.append(
            [linha]
            + [serie["dados"][i] for serie in series_linha]
            + [
                int(
                    (
                        (df["linha_producao"].astype(str) == linha)
                    ).sum()
                )
            ]
        )
    est_linha_turno = _estat(
        valores_pool, "Produção média por linha e turno", "un", "num"
    )
    graficos.append(
        _grafico(
            "producao-por-linha-e-turno",
            "comparativos",
            "Produção média por linha e turno",
            "Média de unidades por registro em cada cruzamento linha × turno",
            "barras-agrupadas",
            {"nome": "Linha de produção", "tipo": "category", "rotulos": linhas_prod},
            {"nome": "Unidades por registro (un)", "tipo": "value", "formato": "num"},
            series_linha,
            est_linha_turno,
            _tabela(["Linha"] + turnos + ["Registros na linha"], matriz),
            (
                f"As médias dos cruzamentos variam de {_n(est_linha_turno['minimo'], 1)} a "
                f"{_n(est_linha_turno['maximo'], 1)} un por registro, com média geral de "
                f"{_n(est_linha_turno['media'], 1)} un. A dispersão entre células é modesta "
                f"(CV de {_pc(est_linha_turno['coef_variacao'])}), indicando que o mix de "
                "produtos pesa mais que a linha ou o turno."
            ),
            marcadores=_marcadores_y(est_linha_turno),
            altura=380,
        )
    )
    return graficos


def _qualidade(df: pd.DataFrame) -> list[dict]:
    """Três gráficos de qualidade: linhas, cruzamento e Pareto."""
    graficos: list[dict] = []
    linhas_prod = _categorias(df, "linha_producao", ORDEM_LINHA)
    produtos = _categorias(df, "produto", ORDEM_PRODUTO)
    turnos = _categorias(df, "turno", ORDEM_TURNO)
    taxa_global = _taxa(df)

    # 19. Taxa de defeitos por linha --------------------------------------
    taxas, produzidas, defeituosas, ns = [], [], [], []
    for linha in linhas_prod:
        recorte = df[df["linha_producao"].astype(str) == linha]
        taxas.append(_taxa(recorte))
        produzidas.append(_i(_numerica(recorte["unidades_produzidas"]).sum()))
        defeituosas.append(_i(_numerica(recorte["unidades_defeituosas"]).sum()))
        ns.append(int(len(recorte)))
    est_taxa_linha = _estat(taxas, "Taxa de defeitos por linha", "%", "pct")
    pior = linhas_prod[taxas.index(max(taxas))]
    melhor = linhas_prod[taxas.index(min(taxas))]
    graficos.append(
        _grafico(
            "taxa-defeitos-por-linha",
            "qualidade",
            "Taxa de defeitos por linha de produção",
            "Responde à questão 3 — cor por faixa de status, não por ranking",
            "barras",
            {"nome": "Linha de produção", "tipo": "category", "rotulos": linhas_prod},
            {"nome": "Taxa de defeitos (%)", "tipo": "value", "formato": "pct"},
            [
                _serie(
                    "Taxa de defeitos",
                    "bar",
                    "slot1",
                    [
                        {"name": linha, "value": taxa, "cor": _status_defeitos(taxa)}
                        for linha, taxa in zip(linhas_prod, taxas)
                    ],
                    rotulo_direto=True,
                    cores=[_status_defeitos(t) for t in taxas],
                )
            ],
            est_taxa_linha,
            _tabela(
                ["Linha", "Registros", "Unidades produzidas", "Unidades defeituosas", "Taxa de defeitos (%)"],
                [
                    [linha, n, prod, defe, taxa]
                    for linha, n, prod, defe, taxa in zip(
                        linhas_prod, ns, produzidas, defeituosas, taxas
                    )
                ],
            ),
            (
                f"A {pior} tem a maior taxa de defeitos, {_pc(max(taxas), 2)}, contra "
                f"{_pc(min(taxas), 2)} da {melhor}; a taxa global da base é "
                f"{_pc(taxa_global, 2)}. A diferença de "
                f"{_n((max(taxas) - min(taxas)) * 100, 2)} pontos percentuais equivale a "
                f"{_n((max(taxas) - min(taxas)) * (produzidas[taxas.index(max(taxas))] or 0), 0)} "
                f"peças defeituosas a mais na {pior} no período, se ela operasse no nível da "
                f"{melhor}."
            ),
            marcadores=_marcadores_y(est_taxa_linha),
            altura=360,
        )
    )

    # 20. Heatmap taxa de defeitos por produto e turno --------------------
    dados_mapa: list[list[Any]] = []
    valores_mapa: list[float] = []
    linhas_tabela: list[list[Any]] = []
    for iy, produto in enumerate(produtos):
        linha_tabela: list[Any] = [produto]
        for ix, turno in enumerate(turnos):
            recorte = df[
                (df["produto"].astype(str) == produto)
                & (df["turno"].astype(str) == turno)
            ]
            taxa = _taxa(recorte) if len(recorte) else None
            dados_mapa.append([ix, iy, taxa])
            linha_tabela.append(taxa)
            if taxa is not None:
                valores_mapa.append(taxa)
        linha_tabela.append(_taxa(df[df["produto"].astype(str) == produto]))
        linhas_tabela.append(linha_tabela)
    est_mapa = _estat(valores_mapa, "Taxa de defeitos por produto e turno", "%", "pct")
    pico = max(dados_mapa, key=lambda c: c[2] if c[2] is not None else -1)
    graficos.append(
        _grafico(
            "taxa-defeitos-por-produto-e-turno",
            "qualidade",
            "Taxa de defeitos por produto e turno",
            f"{len(produtos)} produtos × {len(turnos)} turnos · escala sequencial azul",
            "heatmap",
            {"nome": "Turno", "tipo": "category", "rotulos": turnos},
            {"nome": "Produto", "tipo": "category", "rotulos": produtos, "formato": "pct"},
            [
                _serie(
                    "Taxa de defeitos",
                    "heatmap",
                    "sequencial",
                    dados_mapa,
                    rotulo_direto=True,
                )
            ],
            est_mapa,
            _tabela(
                ["Produto"] + turnos + ["Produto (total)"],
                linhas_tabela,
            ),
            (
                f"A célula mais crítica é {produtos[pico[1]]} no turno {turnos[pico[0]]}, com "
                f"{_pc(pico[2], 2)}, contra média de {_pc(est_mapa['media'], 2)} entre as "
                f"{len(valores_mapa)} células. A amplitude de "
                f"{_n((est_mapa['maximo'] - est_mapa['minimo']) * 100, 2)} pontos percentuais "
                "mostra que o problema se concentra em combinações específicas."
            ),
            altura=360,
        )
    )

    # 21. Pareto dos defeitos por produto ---------------------------------
    pares = []
    for produto in produtos:
        recorte = df[df["produto"].astype(str) == produto]
        pares.append(
            (
                produto,
                _i(_numerica(recorte["unidades_defeituosas"]).sum()) or 0,
                _i(_numerica(recorte["unidades_produzidas"]).sum()) or 0,
            )
        )
    pares.sort(key=lambda p: p[1], reverse=True)
    total_defeitos = sum(p[1] for p in pares) or 1
    rotulos_pareto = [p[0] for p in pares]
    participacao = [_f(100.0 * p[1] / total_defeitos, 2) for p in pares]
    acumulado: list[float] = []
    soma = 0.0
    for valor in participacao:
        soma += valor
        acumulado.append(_f(soma, 2))
    est_pareto = _estat(
        [p[1] for p in pares], "Unidades defeituosas por produto", "un", "int"
    )
    quantos_80 = next(
        (i + 1 for i, valor in enumerate(acumulado) if valor >= 80.0), len(acumulado)
    )
    if quantos_80 < len(pares):
        frase_pareto = (
            f"{quantos_80} dos {len(pares)} produtos acumulam "
            f"{_n(acumulado[quantos_80 - 1], 1)}% dos defeitos"
        )
    else:
        frase_pareto = (
            "não há concentração no estilo 80/20: as fatias ficam entre "
            f"{_n(min(participacao), 1)}% e {_n(max(participacao), 1)}%"
        )
    graficos.append(
        _grafico(
            "pareto-defeitos-por-produto",
            "qualidade",
            "Pareto dos defeitos por produto",
            "Participação e acumulado no total de unidades defeituosas — tudo em % no mesmo eixo",
            "pareto",
            {"nome": "Produto", "tipo": "category", "rotulos": rotulos_pareto},
            {"nome": "Participação no total de defeitos (%)", "tipo": "value", "formato": "num"},
            [
                _serie(
                    "Participação (%)",
                    "bar",
                    CORES_PRODUTO.get(rotulos_pareto[0], "slot1"),
                    [
                        {"name": produto, "value": valor, "cor": CORES_PRODUTO.get(produto, "slot1")}
                        for produto, valor in zip(rotulos_pareto, participacao)
                    ],
                    rotulo_direto=True,
                    cores=[CORES_PRODUTO.get(p, "slot1") for p in rotulos_pareto],
                ),
                _serie("Acumulado (%)", "line", "slot7", acumulado, rotulo_direto=True),
            ],
            est_pareto,
            _tabela(
                ["Produto", "Unidades defeituosas", "Participação (%)", "Acumulado (%)", "Unidades produzidas", "Taxa de defeitos (%)"],
                [
                    [
                        produto,
                        defeitos,
                        parte,
                        acum,
                        prod,
                        _f(defeitos / prod) if prod else None,
                    ]
                    for (produto, defeitos, prod), parte, acum in zip(
                        pares, participacao, acumulado
                    )
                ],
            ),
            (
                f"{rotulos_pareto[0]} concentra {_n(participacao[0], 1)}% das "
                f"{_n(total_defeitos, 0)} unidades defeituosas e os dois primeiros produtos "
                f"somam {_n(acumulado[1], 1)}%. Ou seja, {frase_pareto}, porque a participação "
                "acompanha o volume produzido — a priorização precisa cruzar o Pareto com a "
                "taxa de defeitos de cada produto."
            ),
            marcadores=None,
            altura=380,
        )
    )
    return graficos


def _energia(df: pd.DataFrame) -> list[dict]:
    """Dois gráficos de energia: intensidade por produto e dispersão."""
    graficos: list[dict] = []
    produtos = _categorias(df, "produto", ORDEM_PRODUTO)

    # 22. Energia por unidade por produto ---------------------------------
    intensidades, consumos, unidades = [], [], []
    for produto in produtos:
        recorte = df[df["produto"].astype(str) == produto]
        intensidades.append(_energia_unidade(recorte))
        consumos.append(_f(_numerica(recorte["consumo_energia_kwh"]).sum(), 2))
        unidades.append(_i(_numerica(recorte["unidades_produzidas"]).sum()))
    est_intensidade = _estat(
        intensidades, "Energia por unidade (produtos)", "kWh/un", "num"
    )
    pior = produtos[intensidades.index(max(intensidades))]
    melhor = produtos[intensidades.index(min(intensidades))]
    graficos.append(
        _grafico(
            "energia-por-unidade-por-produto",
            "energia",
            "Energia por unidade produzida, por produto",
            "Soma de kWh dividida pela soma de unidades produzidas",
            "barras",
            {"nome": "Produto", "tipo": "category", "rotulos": produtos},
            {"nome": "Energia por unidade (kWh/un)", "tipo": "value", "formato": "num"},
            [
                _serie(
                    "Energia por unidade",
                    "bar",
                    CORES_PRODUTO.get(produtos[0], "slot1"),
                    [
                        {"name": produto, "value": valor, "cor": CORES_PRODUTO.get(produto, "slot1")}
                        for produto, valor in zip(produtos, intensidades)
                    ],
                    rotulo_direto=True,
                    cores=[CORES_PRODUTO.get(p, "slot1") for p in produtos],
                )
            ],
            est_intensidade,
            _tabela(
                ["Produto", "Consumo total (kWh)", "Unidades produzidas", "Energia por unidade (kWh/un)"],
                [
                    [produto, consumo, unidade, valor]
                    for produto, consumo, unidade, valor in zip(
                        produtos, consumos, unidades, intensidades
                    )
                ],
            ),
            (
                f"{pior} consome {_n(max(intensidades), 2)} kWh por unidade, "
                f"{_n(max(intensidades) / min(intensidades), 1)} vezes a intensidade de {melhor} "
                f"({_n(min(intensidades), 2)} kWh/un). A ordem é praticamente o inverso do "
                "volume: produtos de lote grande diluem o consumo fixo por peça."
            ),
            marcadores=_marcadores_y(est_intensidade),
            altura=360,
        )
    )

    # 23. Dispersão produção × consumo de energia -------------------------
    base = df[
        ["unidades_produzidas", "consumo_energia_kwh", "atipico_energia"]
    ].copy()
    base["unidades_produzidas"] = pd.to_numeric(
        base["unidades_produzidas"], errors="coerce"
    )
    base["consumo_energia_kwh"] = pd.to_numeric(
        base["consumo_energia_kwh"], errors="coerce"
    )
    base = base.dropna(subset=["unidades_produzidas", "consumo_energia_kwh"])
    marcados = base["atipico_energia"].astype("string") == "Sim"
    tipicos = _amostrar(
        [
            [_f(x, 2), _f(y, 2)]
            for x, y in base.loc[~marcados, ["unidades_produzidas", "consumo_energia_kwh"]].itertuples(
                index=False
            )
        ],
        limite=500,
    )
    atipicos = [
        [_f(x, 2), _f(y, 2)]
        for x, y in base.loc[marcados, ["unidades_produzidas", "consumo_energia_kwh"]].itertuples(
            index=False
        )
    ]
    r_energia = _correlacao(df, "unidades_produzidas", "consumo_energia_kwh")
    est_consumo = _estat(
        base["consumo_energia_kwh"], "Consumo de energia", "kWh", "num"
    )
    graficos.append(
        _grafico(
            "dispersao-producao-vs-energia",
            "energia",
            "Produção e consumo de energia",
            f"{len(tipicos) + len(atipicos)} registros · duas séries (típico e atípico)",
            "dispersao",
            {"nome": "Unidades produzidas (un)", "tipo": "value"},
            {"nome": "Consumo de energia (kWh)", "tipo": "value", "formato": "num"},
            [
                _serie("Registro típico", "scatter", "slot1", tipicos),
                _serie("Atípico de energia", "scatter", "status:critico", atipicos),
            ],
            est_consumo,
            _tabela(
                ["Faixa de unidades produzidas (un)", "Registros", "Consumo médio (kWh)", "Consumo mediano (kWh)"],
                _faixas_resumo(
                    [float(v) for v in base["unidades_produzidas"]],
                    [float(v) for v in base["consumo_energia_kwh"]],
                    "Unidades produzidas",
                    casas_x=0,
                ),
            ),
            (
                f"A correlação entre unidades produzidas e consumo de energia é "
                f"{_n(r_energia)}, associação {_forca(r_energia)} e de sinal "
                f"{'negativo' if (r_energia or 0) < 0 else 'positivo'}: os registros de maior "
                f"volume {'tendem a consumir menos' if (r_energia or 0) < 0 else 'tendem a consumir mais'} "
                "kWh no total, o que é coerente com a diluição do consumo fixo em lotes "
                f"grandes. Os {len(atipicos)} registros sinalizados como atípicos de energia "
                "estão detalhados na seção de atípicos."
            ),
            marcadores=_marcadores_y(est_consumo),
            altura=400,
        )
    )
    return graficos


def _relacoes(df: pd.DataFrame) -> list[dict]:
    """Matriz de correlação e três dispersões de interesse."""
    graficos: list[dict] = []

    # 24. Matriz de correlação --------------------------------------------
    colunas = [c for c in COLUNAS_CORRELACAO if c in df.columns]
    base = df[colunas].apply(pd.to_numeric, errors="coerce")
    matriz = base.corr(method="pearson", numeric_only=True)
    rotulos = [ROTULOS_CURTOS.get(c, c) for c in colunas]
    dados: list[list[Any]] = []
    valores_fora: list[float] = []
    destaques: list[tuple[str, str, float]] = []
    for iy, coluna_y in enumerate(colunas):
        for ix, coluna_x in enumerate(colunas):
            valor = _f(matriz.loc[coluna_y, coluna_x])
            dados.append([ix, iy, valor])
            if ix < iy and valor is not None:
                valores_fora.append(valor)
                destaques.append((coluna_x, coluna_y, valor))
    destaques.sort(key=lambda d: abs(d[2]), reverse=True)
    est_correlacao = _estat(
        valores_fora, "Correlações de Pearson (pares distintos)", "r", "num"
    )
    linhas_matriz = [
        [rotulos[iy]] + [_f(matriz.loc[colunas[iy], c]) for c in colunas]
        for iy in range(len(colunas))
    ]
    forte = destaques[0] if destaques else ("", "", 0.0)
    absolutos = pd.Series([abs(d[2]) for d in destaques], dtype="float64")
    mediana_absoluta = _f(absolutos.median()) if not absolutos.empty else None
    fortes_contagem = int((absolutos >= 0.40).sum())
    graficos.append(
        _grafico(
            "matriz-correlacao",
            "relacoes",
            "Matriz de correlação de Pearson",
            f"{len(colunas)} variáveis quantitativas · escala divergente azul–vermelho",
            "heatmap",
            {"nome": "Variável", "tipo": "category", "rotulos": rotulos},
            {"nome": "Variável", "tipo": "category", "rotulos": rotulos, "formato": "num"},
            [
                _serie(
                    "Correlação (r)",
                    "heatmap",
                    "divergente",
                    dados,
                    rotulo_direto=True,
                )
            ],
            est_correlacao,
            _tabela(["Variável"] + rotulos, linhas_matriz),
            (
                f"O par mais associado é {ROTULOS_CURTOS.get(forte[0], forte[0])} e "
                f"{ROTULOS_CURTOS.get(forte[1], forte[1])}, com r = {_n(forte[2])} "
                f"({_forca(forte[2])}). Entre os {len(valores_fora)} pares distintos, a mediana "
                f"do valor absoluto de r é {_n(mediana_absoluta)} e apenas {fortes_contagem} "
                "pares passam de 0,40 — a maioria das relações é fraca, e correlação não "
                "indica causalidade."
            ),
            altura=520,
        )
    )

    # 25 a 27. Dispersões --------------------------------------------------
    especificacoes = [
        (
            "dispersao-parada-vs-produtividade",
            "horas_parada_maquina",
            "produtividade_hora",
            "Parada de máquina e produtividade",
            "Horas de parada (h)",
            "Produtividade (un/h)",
            "un/h",
            "num",
            2,
            2,
            "slot2",
        ),
        (
            "dispersao-idade-maquina-vs-parada",
            "idade_maquina_anos",
            "horas_parada_maquina",
            "Idade da máquina e horas de parada",
            "Idade da máquina (anos)",
            "Horas de parada (h)",
            "h",
            "num",
            0,
            2,
            "slot1",
        ),
        (
            "dispersao-experiencia-vs-taxa-defeitos",
            "experiencia_operador_anos",
            "taxa_defeitos",
            "Experiência do operador e taxa de defeitos",
            "Experiência do operador (anos)",
            "Taxa de defeitos (%)",
            "%",
            "pct",
            0,
            4,
            "slot3",
        ),
    ]

    for (
        id_,
        coluna_x,
        coluna_y,
        titulo,
        nome_x,
        nome_y,
        unidade,
        formato,
        casas_x,
        casas_y,
        cor,
    ) in especificacoes:
        recorte = df[[coluna_x, coluna_y]].apply(pd.to_numeric, errors="coerce").dropna()
        pontos = _amostrar(
            [
                [_f(x, 4), _f(y, 6)]
                for x, y in recorte.itertuples(index=False)
            ]
        )
        r = _correlacao(df, coluna_x, coluna_y)
        est = _estat(recorte[coluna_y], ROTULOS_CURTOS.get(coluna_y, coluna_y), unidade, formato)
        formatar = (lambda v: _pc(v, 2)) if formato == "pct" else (
            lambda v: _n(v, max(casas_y, 2))
        )
        # Em formato percentual o símbolo já vem no número formatado.
        sufixo = "" if formato == "pct" else f" {unidade}"
        graficos.append(
            _grafico(
                id_,
                "relacoes",
                titulo,
                f"{len(pontos)} registros · r de Pearson = {_n(r)}",
                "dispersao",
                {"nome": nome_x, "tipo": "value"},
                {"nome": nome_y, "tipo": "value", "formato": formato},
                [_serie("Registros", "scatter", cor, pontos)],
                est,
                _tabela(
                    [f"Faixa de {nome_x}", "Registros", f"Média de {nome_y}", f"Mediana de {nome_y}"],
                    _faixas_resumo(
                        [float(v) for v in recorte[coluna_x]],
                        [float(v) for v in recorte[coluna_y]],
                        nome_x,
                        casas_x=casas_x,
                        casas_y=casas_y,
                    ),
                ),
                (
                    f"A correlação entre {nome_x.lower()} e {nome_y.lower()} é r = {_n(r)}, "
                    f"associação {_forca(r)} em {len(recorte)} registros válidos. O eixo y tem "
                    f"média {formatar(est['media'])}{sufixo} e desvio-padrão "
                    f"{formatar(est['desvio_padrao'])}{sufixo}; a nuvem é larga e a tabela "
                    "por faixas mostra que a média de y pouco se desloca ao longo de x."
                ),
                marcadores=_marcadores_y(est),
                altura=380,
            )
        )
    return graficos


def _atipicos(df: pd.DataFrame, analise: dict) -> list[dict]:
    """Dispersão temporal dos atípicos de energia e paradas por manutenção."""
    graficos: list[dict] = []

    # 28. Atípicos de consumo de energia ----------------------------------
    base = df[["data", "consumo_energia_kwh", "produto", "linha_producao", "turno", "id_registro"]].copy()
    base["consumo_energia_kwh"] = pd.to_numeric(
        base["consumo_energia_kwh"], errors="coerce"
    )
    base = base.dropna(subset=["data", "consumo_energia_kwh"]).sort_values("data")
    inicio = base["data"].min()
    base["_dias"] = (base["data"] - inicio).dt.days

    # Limites: usa os do AGENTE A quando disponíveis; senão calcula Tukey.
    bloco = (analise.get("outliers_energia") or {}) if analise else {}
    lim_inf = bloco.get("lim_inf")
    lim_sup = bloco.get("lim_sup")
    # O texto do método vem da análise quando é curto o bastante para o
    # subtítulo do cartão; caso contrário usa-se a descrição padrão.
    metodo = str(bloco.get("metodo") or "").strip()
    if not metodo or len(metodo) > 48:
        metodo = "Tukey (1,5 × IQR)"
    if lim_inf is None or lim_sup is None:
        serie = _numerica(base["consumo_energia_kwh"])
        q1, q3 = (float(x) for x in serie.quantile([0.25, 0.75]))
        iqr = q3 - q1
        lim_inf, lim_sup = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    lim_inf, lim_sup = float(lim_inf), float(lim_sup)

    fora = (base["consumo_energia_kwh"] < lim_inf) | (
        base["consumo_energia_kwh"] > lim_sup
    )
    marcada = base["produto"].notna() & (
        df.loc[base.index, "atipico_energia"].astype("string") == "Sim"
    )
    destacar = fora | marcada

    normais = _amostrar(
        [
            [_i(d), _f(v, 2)]
            for d, v in base.loc[~destacar, ["_dias", "consumo_energia_kwh"]].itertuples(
                index=False
            )
        ],
        limite=500,
    )
    extremos = [
        [_i(d), _f(v, 2)]
        for d, v in base.loc[destacar, ["_dias", "consumo_energia_kwh"]].itertuples(
            index=False
        )
    ]
    est_energia = _estat(base["consumo_energia_kwh"], "Consumo de energia", "kWh", "num")
    meses_atipicos = int(
        base.loc[destacar, "data"].dt.to_period("M").nunique()
    )
    linhas_atipicos = [
        [
            str(registro.id_registro),
            registro.data.strftime("%d/%m/%Y"),
            str(registro.produto),
            str(registro.linha_producao),
            str(registro.turno),
            _f(registro.consumo_energia_kwh, 2),
            _f(
                (float(registro.consumo_energia_kwh) - (est_energia["media"] or 0.0))
                / (est_energia["desvio_padrao"] or 1.0),
                2,
            ),
            "acima" if float(registro.consumo_energia_kwh) > lim_sup else (
                "abaixo" if float(registro.consumo_energia_kwh) < lim_inf else "marcado no CSV"
            ),
        ]
        for registro in base.loc[destacar].itertuples(index=False)
    ]
    graficos.append(
        _grafico(
            "atipicos-consumo-energia",
            "atipicos",
            "Observações atípicas no consumo de energia",
            (
                f"Responde à questão 5 · método {metodo} · limites de {_n(lim_inf, 1)} a "
                f"{_n(lim_sup, 1)} kWh"
            ),
            "dispersao",
            {"nome": f"Dias desde {inicio.strftime('%d/%m/%Y')}", "tipo": "value"},
            {"nome": "Consumo de energia (kWh)", "tipo": "value", "formato": "num"},
            [
                _serie("Consumo dentro do padrão", "scatter", "slot1", normais),
                _serie("Observação atípica", "scatter", "status:critico", extremos),
            ],
            est_energia,
            _tabela(
                ["ID", "Data", "Produto", "Linha", "Turno", "Consumo (kWh)", "Escore z", "Posição"],
                linhas_atipicos,
            ),
            (
                f"Dos {est_energia['n']} registros com consumo informado, {len(extremos)} são "
                f"atípicos ({_pc(len(extremos) / est_energia['n'], 1)}), fora da faixa de "
                f"{_n(lim_inf, 1)} a {_n(lim_sup, 1)} kWh. A média é "
                f"{_n(est_energia['media'], 1)} kWh com desvio-padrão de "
                f"{_n(est_energia['desvio_padrao'], 1)} kWh; os pontos destacados estão "
                f"distribuídos em {meses_atipicos} meses diferentes do período, sem "
                "concentração em um único mês."
            ),
            marcadores=_marcadores_y(est_energia),
            altura=400,
        )
    )

    # 29. Parada por tipo de manutenção -----------------------------------
    tipos = _categorias(df, "tipo_manutencao", ORDEM_MANUTENCAO)
    caixa = _boxplot(
        [
            (tipo, df[df["tipo_manutencao"].astype(str) == tipo]["horas_parada_maquina"])
            for tipo in tipos
        ]
    )
    est_parada = _estat(
        df["horas_parada_maquina"], "Horas de parada de máquina", "h", "num"
    )
    medias_tipo = {linha[0]: linha[2] for linha in caixa["resumo"]}
    maior = max(medias_tipo, key=lambda k: medias_tipo[k] or 0)
    menor = min(medias_tipo, key=lambda k: medias_tipo[k] or 0)
    graficos.append(
        _grafico(
            "parada-por-tipo-manutencao",
            "atipicos",
            "Horas de parada por tipo de manutenção",
            "Responde à questão 4 — caixas de Tukey e média geral marcada",
            "boxplot",
            {"nome": "Tipo de manutenção", "tipo": "category", "rotulos": caixa["rotulos"]},
            {"nome": "Horas de parada (h)", "tipo": "value", "formato": "num"},
            [
                _serie(
                    "Horas de parada",
                    "boxplot",
                    CORES_MANUTENCAO.get(caixa["rotulos"][0], "slot1"),
                    caixa["caixas"],
                    outliers=caixa["atipicos"],
                    cores=[
                        CORES_MANUTENCAO.get(t, "slot1") for t in caixa["rotulos"]
                    ],
                )
            ],
            est_parada,
            _tabela(
                ["Tipo de manutenção", "n", "Média", "Mediana", "Q1", "Q3", "IQR", "Desvio-padrão", "Mínimo", "Máximo"],
                caixa["resumo"],
            ),
            (
                f"A parada média geral é de {_n(est_parada['media'], 2)} h por registro "
                f"(mediana {_n(est_parada['mediana'], 2)} h). Em manutenção {maior.lower()} a "
                f"média sobe para {_n(medias_tipo[maior], 2)} h, contra "
                f"{_n(medias_tipo[menor], 2)} h quando a manutenção é {menor.lower()} — "
                f"diferença de {_n((medias_tipo[maior] or 0) - (medias_tipo[menor] or 0), 2)} h."
            ),
            marcadores=_marcadores_y(est_parada),
            altura=380,
        )
    )
    return graficos


# ============================================================= entrada ====
def construir_graficos(
    df: pd.DataFrame, analise: dict | None = None
) -> list[dict]:
    """Monta a lista completa de gráficos do relatório.

    O parâmetro ``analise`` é opcional: todas as séries são calculadas a
    partir do próprio ``df``, e o dicionário de análise é consultado
    apenas com ``.get()`` para reaproveitar valores já apurados (hoje,
    os limites de atípicos de energia). Com ``analise={}`` o resultado é
    o mesmo.
    """
    analise = analise or {}

    graficos: list[dict] = []
    graficos.extend(_visao_geral(df))
    graficos.extend(_distribuicoes(df))
    graficos.extend(_temporal(df))
    graficos.extend(_comparativos(df))
    graficos.extend(_qualidade(df))
    graficos.extend(_energia(df))
    graficos.extend(_relacoes(df))
    graficos.extend(_atipicos(df, analise))

    vistos: set[str] = set()
    for grafico in graficos:
        if grafico["id"] in vistos:
            raise ValueError(f"id de gráfico repetido: {grafico['id']}")
        vistos.add(grafico["id"])
    return graficos


# ========================================================= serialização ===
def _limpar(valor: Any) -> Any:
    """Troca NaN/Infinity por ``None`` para gerar JSON válido."""
    if isinstance(valor, dict):
        return {k: _limpar(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_limpar(v) for v in valor]
    if isinstance(valor, float) and not math.isfinite(valor):
        return None
    return valor


def para_json(dados: Any) -> str:
    """Serializa os dados dos gráficos para embutir no HTML."""
    return json.dumps(_limpar(dados), ensure_ascii=False, allow_nan=False)
