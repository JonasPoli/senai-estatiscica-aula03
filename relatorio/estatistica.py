"""Helpers estatísticos reutilizáveis do relatório.

Este módulo concentra o cálculo numérico puro: não conhece o conteúdo
editorial do relatório nem a estrutura do site. Tudo que ele devolve usa
apenas tipos nativos do Python (``float``, ``int``, ``str``, ``list``,
``dict``) ou objetos do pandas, de modo que o resultado possa ser
serializado em JSON e renderizado em Jinja2 sem conversões extras.

Convenções adotadas em todo o projeto:

* ``.dropna()`` antes de qualquer cálculo (a base tem valores faltantes);
* variância e desvio-padrão **amostrais** (``ddof=1``);
* quartis pelo método linear padrão do pandas;
* outliers pelo critério de Tukey (1,5 × IQR);
* taxas de um grupo são sempre **razões agregadas**
  (soma do numerador / soma do denominador), nunca média de razões.
"""

from __future__ import annotations

import itertools
import math

import pandas as pd

# Valor crítico aproximado da normal padrão para 95% de confiança.
# Usado no intervalo de confiança da média (amostras com n >= 30).
Z_95 = 1.959964

# Faixas de classificação da força de uma correlação de Pearson.
FAIXAS_FORCA = (
    (0.90, "muito forte"),
    (0.70, "forte"),
    (0.50, "moderada"),
    (0.30, "fraca"),
    (0.00, "desprezível"),
)


# ------------------------------------------------------------------ base --
def numero(valor) -> float | None:
    """Converte qualquer escalar numérico para ``float`` nativo ou ``None``.

    Trata ``pd.NA``, ``NaN`` e infinitos como ausência de valor, porque o
    dicionário final é serializado em JSON (que não representa ``NaN``).
    """
    if valor is None or valor is pd.NA:
        return None
    try:
        convertido = float(valor)
    except (TypeError, ValueError):
        return None
    if math.isnan(convertido) or math.isinf(convertido):
        return None
    return convertido


def inteiro(valor) -> int | None:
    """Converte um escalar numérico para ``int`` nativo ou ``None``."""
    convertido = numero(valor)
    return None if convertido is None else int(round(convertido))


def serie_limpa(serie: pd.Series) -> pd.Series:
    """Devolve a série convertida para ``float64`` e sem valores faltantes."""
    return pd.to_numeric(serie, errors="coerce").astype("float64").dropna()


def arredondar(valor, casas: int = 4) -> float | None:
    """Arredonda preservando ``None`` (útil antes de serializar em JSON)."""
    convertido = numero(valor)
    return None if convertido is None else round(convertido, casas)


# ------------------------------------------------------------------ moda --
def modas(serie: pd.Series, limite: int = 5) -> list[float]:
    """Lista os valores modais da série, no máximo ``limite`` deles.

    Quando a distribuição é multimodal (caso de variáveis contínuas com
    poucas repetições) todas as modas empatadas são devolvidas, para que o
    relatório possa declarar explicitamente a multimodalidade em vez de
    esconder o empate atrás de um único número.
    """
    s = serie_limpa(serie)
    if s.empty:
        return []
    encontradas = s.mode()
    return [float(v) for v in encontradas.head(limite)]


# ---------------------------------------------------------------- Tukey ---
def limites_outliers(serie: pd.Series, k: float = 1.5) -> tuple[float, float]:
    """Limites inferior e superior pelo critério de Tukey (``k`` × IQR)."""
    s = serie_limpa(serie)
    if s.empty:
        return (float("nan"), float("nan"))
    q1, q3 = s.quantile([0.25, 0.75])
    iqr = q3 - q1
    return float(q1 - k * iqr), float(q3 + k * iqr)


def contar_outliers(serie: pd.Series, k: float = 1.5) -> tuple[int, float]:
    """Quantidade e percentual de observações fora dos limites de Tukey."""
    s = serie_limpa(serie)
    if s.empty:
        return 0, 0.0
    lim_inf, lim_sup = limites_outliers(s, k=k)
    fora = int(((s < lim_inf) | (s > lim_sup)).sum())
    return fora, float(fora / s.size)


# ---------------------------------------------------------- descritivas ---
def descritivas(serie: pd.Series) -> dict:
    """Medidas de posição, dispersão e forma de uma variável quantitativa.

    Devolve dicionário com tipos nativos, pronto para o template. Inclui
    as medidas exigidas pelo enunciado (média, mediana, moda, amplitude,
    variância, desvio-padrão, quartis e IQR) e ainda coeficiente de
    variação, erro-padrão, intervalo de confiança de 95%, assimetria,
    curtose e a contagem de outliers de Tukey.
    """
    bruta = pd.to_numeric(serie, errors="coerce")
    s = bruta.astype("float64").dropna()
    faltantes = int(bruta.isna().sum())
    if s.empty:
        return {"n": 0, "faltantes": faltantes}

    n = int(s.size)
    q1, q2, q3 = (float(v) for v in s.quantile([0.25, 0.50, 0.75]))
    iqr = q3 - q1
    media = float(s.mean())
    minimo = float(s.min())
    maximo = float(s.max())

    variancia = float(s.var(ddof=1)) if n > 1 else 0.0
    desvio = float(s.std(ddof=1)) if n > 1 else 0.0
    erro_padrao = desvio / math.sqrt(n) if n > 0 else 0.0
    margem = Z_95 * erro_padrao

    lista_modas = modas(s)
    lim_inf, lim_sup = limites_outliers(s)
    n_outliers, pct_outliers = contar_outliers(s)

    return {
        "n": n,
        "faltantes": faltantes,
        "media": media,
        "mediana": q2,
        "moda": lista_modas[0] if lista_modas else None,
        "modas": lista_modas,
        "minimo": minimo,
        "maximo": maximo,
        "amplitude": maximo - minimo,
        "q1": q1,
        "q2": q2,
        "q3": q3,
        "iqr": iqr,
        "variancia": variancia,
        "desvio_padrao": desvio,
        "coef_variacao": (desvio / media) if media else None,
        "erro_padrao": erro_padrao,
        "ic95": (media - margem, media + margem),
        "assimetria": numero(s.skew()) if n > 2 else None,
        "curtose": numero(s.kurt()) if n > 3 else None,
        "lim_inf": lim_inf,
        "lim_sup": lim_sup,
        "n_outliers": n_outliers,
        "pct_outliers": pct_outliers,
        "soma": float(s.sum()),
    }


def frequencias(serie: pd.Series) -> pd.DataFrame:
    """Tabela de frequências (absoluta, relativa e acumuladas)."""
    contagem = serie.value_counts(dropna=False).sort_index()
    tabela = contagem.rename("frequencia").to_frame()
    tabela["relativa"] = tabela["frequencia"] / tabela["frequencia"].sum()
    tabela["acumulada"] = tabela["frequencia"].cumsum()
    tabela["relativa_acumulada"] = tabela["relativa"].cumsum()
    return tabela.reset_index(names="categoria")


def classes(serie: pd.Series, n_classes: int = 12) -> dict:
    """Define classes de mesma largura para um histograma.

    Devolve o início (``inicio``), a largura (``largura``), os limites e as
    contagens por classe. É usado pelos gráficos de distribuição e pela
    posição dos marcadores estatísticos sobre o eixo de categorias.
    """
    s = serie_limpa(serie)
    if s.empty or n_classes < 1:
        return {"inicio": 0.0, "largura": 0.0, "limites": [], "contagens": []}

    minimo, maximo = float(s.min()), float(s.max())
    largura = (maximo - minimo) / n_classes or 1.0
    limites = [minimo + i * largura for i in range(n_classes + 1)]
    contagens = [0] * n_classes
    for valor in s:
        indice = int((valor - minimo) / largura)
        indice = min(max(indice, 0), n_classes - 1)
        contagens[indice] += 1
    return {
        "inicio": minimo,
        "largura": largura,
        "limites": limites,
        "contagens": contagens,
    }


# ------------------------------------------------------------ razões ------
def razao(numerador, denominador) -> float | None:
    """Razão segura entre dois totais; ``None`` se o denominador for nulo."""
    num = numero(numerador)
    den = numero(denominador)
    if num is None or den is None or den == 0:
        return None
    return num / den


def taxa_defeitos_agregada(df: pd.DataFrame) -> float | None:
    """soma(unidades_defeituosas) / soma(unidades_produzidas).

    Nunca a média das taxas individuais: registros com produções muito
    diferentes (Micro-ondas ~300 un, Geladeira ~130 un) têm pesos
    distintos na qualidade do grupo.
    """
    return razao(df["unidades_defeituosas"].sum(), df["unidades_produzidas"].sum())


def produtividade_agregada(df: pd.DataFrame) -> float | None:
    """soma(unidades_produzidas) / soma(horas_efetivas) do grupo."""
    return razao(df["unidades_produzidas"].sum(), df["horas_efetivas"].sum())


def energia_por_unidade_agregada(df: pd.DataFrame) -> float | None:
    """soma(consumo_energia_kwh) / soma(unidades_produzidas) do grupo.

    Só considera os registros com consumo informado, para que numerador e
    denominador se refiram exatamente às mesmas observações.
    """
    validos = df[df["consumo_energia_kwh"].notna()]
    if validos.empty:
        return None
    return razao(
        validos["consumo_energia_kwh"].sum(), validos["unidades_produzidas"].sum()
    )


def residuo_por_unidade_agregado(df: pd.DataFrame) -> float | None:
    """soma(residuo_kg) / soma(unidades_produzidas) do grupo."""
    validos = df[df["residuo_kg"].notna()]
    if validos.empty:
        return None
    return razao(validos["residuo_kg"].sum(), validos["unidades_produzidas"].sum())


# ------------------------------------------------------- correlações ------
def correlacoes(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    """Matriz de correlação de Pearson entre as colunas informadas."""
    presentes = [c for c in colunas if c in df.columns]
    numerico = df[presentes].apply(pd.to_numeric, errors="coerce").astype("float64")
    return numerico.corr(method="pearson")


def forca_correlacao(r) -> str:
    """Classifica verbalmente a força de um coeficiente de Pearson."""
    valor = numero(r)
    if valor is None:
        return "indefinida"
    absoluto = abs(valor)
    for corte, rotulo in FAIXAS_FORCA:
        if absoluto >= corte:
            return rotulo
    return "desprezível"


def pares_correlacao(matriz: pd.DataFrame, quantos: int = 6) -> list[tuple[str, str, float]]:
    """Os ``quantos`` pares de variáveis com maior correlação em módulo."""
    pares: list[tuple[str, str, float]] = []
    for a, b in itertools.combinations(list(matriz.columns), 2):
        r = numero(matriz.loc[a, b])
        if r is not None:
            pares.append((a, b, r))
    pares.sort(key=lambda item: abs(item[2]), reverse=True)
    return pares[:quantos]


def z_scores(serie: pd.Series) -> pd.Series:
    """Escore padronizado ``(x - média) / desvio-padrão`` da série."""
    s = pd.to_numeric(serie, errors="coerce").astype("float64")
    limpa = s.dropna()
    if limpa.empty:
        return s
    desvio = float(limpa.std(ddof=1))
    if desvio == 0:
        return s * 0.0
    return (s - float(limpa.mean())) / desvio
