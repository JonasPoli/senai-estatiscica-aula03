"""Análise estatística completa da base de produção da EletroTech.

Ponto de entrada único: :func:`analisar`, que recebe o DataFrame limpo de
:func:`relatorio.dados.carregar` e devolve um dicionário com todo o
conteúdo analítico e interpretativo do relatório (identificação da
população, medidas descritivas, recortes por categoria, KPIs, matriz de
correlação, observações atípicas, as seis questões investigativas, o
parecer técnico e o glossário de variáveis).

Três decisões metodológicas valem para o módulo inteiro:

1. **Razões agregadas, não médias de razões.** A taxa de defeitos de um
   grupo é ``soma(unidades_defeituosas) / soma(unidades_produzidas)`` e a
   produtividade é ``soma(unidades_produzidas) / soma(horas_efetivas)``.
   Média de taxas daria peso igual a registros de tamanhos muito
   diferentes.
2. **Ritmos de fabricação diferentes.** Micro-ondas produz cerca de 300
   unidades por registro e Geladeira cerca de 130. Comparar produtos pela
   quantidade absoluta mede o ritmo do produto, não o desempenho da
   operação; por isso toda comparação entre produtos vem acompanhada de
   produtividade por hora efetiva e de produção relativa.
3. **Tipos nativos.** Todo valor devolvido é ``float``, ``int``, ``str``,
   ``bool``, ``list``, ``dict`` ou ``None``; ``pd.Timestamp`` aparece
   apenas nos campos de data. Nunca ``NaN``.
"""

from __future__ import annotations

import pandas as pd

from . import config
from . import estatistica as est

# ------------------------------------------------------------- constantes --

#: Variáveis quantitativas que entram na tabela de medidas descritivas.
COLUNAS_DESCRITIVAS = [
    "unidades_produzidas",
    "unidades_defeituosas",
    "taxa_defeitos",
    "produtividade_hora",
    "horas_planejadas",
    "horas_parada_maquina",
    "horas_efetivas",
    "consumo_energia_kwh",
    "energia_por_unidade",
    "residuo_kg",
    "entregas_no_prazo_pct",
    "pedidos_recebidos",
    "devolucoes_clientes",
    "temperatura_ambiente_c",
    "idade_maquina_anos",
    "experiencia_operador_anos",
    "producao_relativa",
]

#: Variáveis usadas na matriz de correlação de Pearson.
COLUNAS_CORRELACAO = [
    "unidades_produzidas",
    "unidades_defeituosas",
    "taxa_defeitos",
    "produtividade_hora",
    "horas_planejadas",
    "horas_parada_maquina",
    "horas_efetivas",
    "consumo_energia_kwh",
    "energia_por_unidade",
    "residuo_kg",
    "entregas_no_prazo_pct",
    "pedidos_recebidos",
    "devolucoes_clientes",
    "temperatura_ambiente_c",
    "idade_maquina_anos",
    "experiencia_operador_anos",
    "producao_relativa",
]

#: Unidades que não constam de ``config.UNIDADES``.
UNIDADES_EXTRA = {
    "taxa_defeitos": "fração",
    "entregas_no_prazo_pct": "%",
    "pedidos_recebidos": "un",
    "devolucoes_clientes": "un",
    "producao_relativa": "índice",
    "ordem_atipico": "ordem",
}

#: Ordem de apresentação das categorias que têm sequência lógica própria.
ORDEM_CATEGORIAS = {
    "turno": ["Manhã", "Tarde", "Noite"],
    "tipo_manutencao": ["Nenhuma", "Preventiva", "Corretiva"],
}

#: Glossário: descrição e classificação de cada uma das 25 variáveis.
GLOSSARIO_BASE: dict[str, tuple[str, str]] = {
    "id_registro": (
        "Identificador único do registro de produção (um turno de uma linha "
        "em uma data).",
        "Qualitativa nominal",
    ),
    "data": (
        "Data do registro de produção, entre janeiro de 2025 e dezembro de 2026.",
        "Temporal (quantitativa ordinal)",
    ),
    "turno": (
        "Turno de trabalho em que o registro foi apurado: Manhã, Tarde ou Noite.",
        "Qualitativa nominal",
    ),
    "linha_producao": (
        "Linha de montagem responsável pelo lote: Linha A, B, C ou D.",
        "Qualitativa nominal",
    ),
    "produto": (
        "Produto fabricado no registro: Geladeira, Lavadora, Ar-condicionado "
        "ou Micro-ondas. Cada produto tem ritmo de fabricação próprio.",
        "Qualitativa nominal",
    ),
    "horas_planejadas": (
        "Horas de produção previstas para o turno antes de qualquer parada.",
        "Quantitativa contínua",
    ),
    "horas_parada_maquina": (
        "Horas em que a máquina ficou indisponível por parada no turno.",
        "Quantitativa contínua",
    ),
    "idade_maquina_anos": (
        "Idade do equipamento utilizado, em anos completos.",
        "Quantitativa discreta",
    ),
    "tipo_manutencao": (
        "Manutenção associada ao registro: Nenhuma, Preventiva ou Corretiva.",
        "Qualitativa nominal",
    ),
    "temperatura_ambiente_c": (
        "Temperatura ambiente média do chão de fábrica durante o turno.",
        "Quantitativa contínua",
    ),
    "experiencia_operador_anos": (
        "Tempo de experiência do operador responsável, em anos completos.",
        "Quantitativa discreta",
    ),
    "unidades_produzidas": (
        "Quantidade de unidades boas e defeituosas produzidas no turno.",
        "Quantitativa discreta",
    ),
    "unidades_defeituosas": (
        "Quantidade de unidades reprovadas na inspeção de qualidade.",
        "Quantitativa discreta",
    ),
    "consumo_energia_kwh": (
        "Energia elétrica consumida pela linha no turno, em quilowatt-hora.",
        "Quantitativa contínua",
    ),
    "residuo_kg": (
        "Massa de resíduo gerado no turno, em quilogramas.",
        "Quantitativa contínua",
    ),
    "devolucoes_clientes": (
        "Número de devoluções de clientes associadas ao registro.",
        "Quantitativa discreta",
    ),
    "pedidos_recebidos": (
        "Pedidos recebidos para o turno; funciona como medida de demanda.",
        "Quantitativa discreta",
    ),
    "entregas_no_prazo_pct": (
        "Percentual de entregas cumpridas no prazo, de 0 a 100.",
        "Quantitativa contínua",
    ),
    "horas_efetivas": (
        "Horas realmente produtivas: horas planejadas menos horas de parada.",
        "Quantitativa contínua (derivada)",
    ),
    "taxa_defeitos": (
        "Unidades defeituosas divididas pelas unidades produzidas do "
        "registro, expressa como fração de 0 a 1.",
        "Quantitativa contínua (derivada)",
    ),
    "produtividade_hora": (
        "Unidades produzidas por hora efetiva; permite comparar produtos "
        "com ritmos de fabricação diferentes.",
        "Quantitativa contínua (derivada)",
    ),
    "energia_por_unidade": (
        "Consumo de energia dividido pelas unidades produzidas do registro.",
        "Quantitativa contínua (derivada)",
    ),
    "producao_relativa": (
        "Unidades produzidas divididas pela média do próprio produto; 1,00 "
        "indica produção no padrão do produto.",
        "Quantitativa contínua (derivada)",
    ),
    "atipico_energia": (
        "Marcação Sim/Não indicando se o consumo de energia do registro foi "
        "classificado como atípico na própria base.",
        "Qualitativa nominal (derivada)",
    ),
    "ordem_atipico": (
        "Ordem sequencial dos registros atípicos de energia; preenchida "
        "apenas nesses registros.",
        "Quantitativa discreta (derivada)",
    ),
}

#: Leituras interpretativas prontas para os pares de correlação relevantes.
#: A chave é o par de colunas (``frozenset``) e o texto recebe o ``r`` real.
LEITURAS_PARES: dict[frozenset, str] = {
    frozenset({"unidades_produzidas", "produtividade_hora"}): (
        "Relação em grande parte construtiva: a produtividade é a produção "
        "dividida pelas horas efetivas, que variam pouco entre registros. "
        "O coeficiente de {r} confirma que, com jornada praticamente fixa, "
        "produzir mais e produzir mais rápido são quase a mesma informação."
    ),
    frozenset({"unidades_produzidas", "pedidos_recebidos"}): (
        "A produção acompanha a demanda: r = {r}. É o par mais informativo "
        "do conjunto, porque indica que o volume fabricado é puxado pelos "
        "pedidos e não por decisão isolada da fábrica."
    ),
    frozenset({"horas_parada_maquina", "horas_efetivas"}): (
        "Relação definicional e negativa (r = {r}): horas efetivas são as "
        "horas planejadas menos a parada, de modo que cada hora parada sai "
        "diretamente da capacidade disponível."
    ),
    frozenset({"unidades_produzidas", "energia_por_unidade"}): (
        "Quanto maior o volume do registro, menor a energia por unidade "
        "(r = {r}): há forte diluição do consumo fixo da linha. Parte do "
        "efeito vem do mix de produtos, já que os registros de maior volume "
        "são de Micro-ondas."
    ),
    frozenset({"produtividade_hora", "energia_por_unidade"}): (
        "Produzir mais por hora reduz a energia gasta por unidade (r = {r}), "
        "o que sugere ganho energético de escala e não economia por "
        "contenção de consumo."
    ),
    frozenset({"produtividade_hora", "pedidos_recebidos"}): (
        "A produtividade também acompanha a demanda (r = {r}), indicando que "
        "o ritmo da linha é ajustado ao volume de pedidos do turno."
    ),
    frozenset({"taxa_defeitos", "residuo_kg"}): (
        "Defeito e resíduo caminham juntos (r = {r}): turnos que reprovam "
        "mais unidades também descartam mais material, o que reforça a "
        "leitura de perda de processo e não de erro de inspeção."
    ),
    frozenset({"horas_parada_maquina", "entregas_no_prazo_pct"}): (
        "Parada de máquina deteriora o prazo (r = {r}): o atraso de entrega "
        "é o efeito visível ao cliente da indisponibilidade da linha."
    ),
    frozenset({"horas_parada_maquina", "producao_relativa"}): (
        "Com a produção normalizada pelo padrão de cada produto, a parada "
        "mantém correlação negativa (r = {r}), ou seja, o efeito não é "
        "artefato do mix de produtos."
    ),
    frozenset({"horas_efetivas", "producao_relativa"}): (
        "Mais horas efetivas elevam a produção acima do padrão do produto "
        "(r = {r}); é a leitura limpa do ganho de disponibilidade."
    ),
    frozenset({"consumo_energia_kwh", "energia_por_unidade"}): (
        "O consumo total e o consumo unitário compartilham o mesmo "
        "numerador (r = {r}); a associação é em boa medida construtiva."
    ),
    frozenset({"unidades_defeituosas", "taxa_defeitos"}): (
        "Numerador e taxa compartilham a mesma informação (r = {r}); a taxa "
        "é a leitura preferível porque desconta o tamanho do lote."
    ),
    frozenset({"horas_efetivas", "entregas_no_prazo_pct"}): (
        "Disponibilidade e pontualidade andam juntas (r = {r}): o prazo é "
        "sustentado pelas horas efetivamente produtivas."
    ),
    frozenset({"unidades_defeituosas", "residuo_kg"}): (
        "Unidades reprovadas e resíduo gerado se acompanham (r = {r}), "
        "consistente com perda física no processo."
    ),
}


# ----------------------------------------------------------- formatadores --
def _fmt(valor, casas: int = 2, sufixo: str = "") -> str:
    """Formata um número no padrão brasileiro para uso nos textos."""
    numero = est.numero(valor)
    if numero is None:
        return "não disponível"
    texto = f"{numero:,.{casas}f}"
    texto = texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"{texto}{sufixo}"


def _fmt_int(valor, sufixo: str = "") -> str:
    """Formata um inteiro com separador de milhar brasileiro."""
    numero = est.inteiro(valor)
    if numero is None:
        return "não disponível"
    return f"{numero:,}".replace(",", ".") + sufixo


def _fmt_pct(fracao, casas: int = 2) -> str:
    """Formata uma fração 0–1 como percentual brasileiro."""
    numero = est.numero(fracao)
    if numero is None:
        return "não disponível"
    return _fmt(numero * 100.0, casas, "%")


def _rotulo(coluna: str) -> str:
    """Rótulo amigável da coluna, com o nome técnico como alternativa."""
    return config.ROTULOS.get(coluna, coluna)


def _unidade(coluna: str) -> str:
    """Unidade de medida da coluna, consultando config e os complementos."""
    return config.UNIDADES.get(coluna, UNIDADES_EXTRA.get(coluna, ""))


def _ordenar_categorias(coluna: str, categorias: list[str]) -> list[str]:
    """Aplica a ordem lógica da categoria, quando existir uma definida."""
    preferida = ORDEM_CATEGORIAS.get(coluna)
    if not preferida:
        return sorted(categorias)
    conhecidas = [c for c in preferida if c in categorias]
    restantes = sorted(c for c in categorias if c not in preferida)
    return conhecidas + restantes


# ------------------------------------------------------------------ meta --
def _meta(df: pd.DataFrame) -> dict:
    """Metadados da base: tamanho, período, meses cobertos e faltantes."""
    faltantes = df.isna().sum()
    datas = df[config.COL_DATA].dropna()
    meses = int(datas.dt.to_period("M").nunique()) if not datas.empty else 0
    return {
        "n_registros": int(len(df)),
        "n_variaveis": int(df.shape[1]),
        "periodo_inicio": datas.min() if not datas.empty else None,
        "periodo_fim": datas.max() if not datas.empty else None,
        "n_meses": meses,
        "faltantes": {
            str(coluna): int(qtd) for coluna, qtd in faltantes.items() if qtd > 0
        },
        "total_faltantes": int(faltantes.sum()),
    }


# -------------------------------------------------------------- população --
def _faltantes_medicao(meta: dict) -> dict[str, int]:
    """Faltantes que são de fato ausência de medição.

    Exclui ``ordem_atipico``, cuja ausência é estrutural: a coluna só é
    preenchida nos registros classificados como atípicos de energia.
    """
    return {
        coluna: qtd
        for coluna, qtd in meta["faltantes"].items()
        if coluna != "ordem_atipico"
    }


def _populacao(df: pd.DataFrame, meta: dict) -> dict:
    """Atividade 1: população, unidade de análise, amostra e amostragem."""
    n = meta["n_registros"]
    inicio = meta["periodo_inicio"]
    fim = meta["periodo_fim"]
    periodo = (
        f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}"
        if inicio is not None and fim is not None
        else "período não identificado"
    )
    n_produtos = int(df["produto"].dropna().nunique())
    n_linhas = int(df["linha_producao"].dropna().nunique())
    n_turnos = int(df["turno"].dropna().nunique())
    medicao = _faltantes_medicao(meta)
    total_medicao = sum(medicao.values())

    por_tipo: dict[str, list[str]] = {
        "qualitativas_nominais": [],
        "quantitativas_discretas": [],
        "quantitativas_continuas": [],
        "temporais": [],
    }
    for coluna, (_, tipo) in GLOSSARIO_BASE.items():
        if coluna not in df.columns:
            continue
        rotulo = _rotulo(coluna)
        if tipo.startswith("Temporal"):
            por_tipo["temporais"].append(rotulo)
        elif tipo.startswith("Qualitativa"):
            por_tipo["qualitativas_nominais"].append(rotulo)
        elif "discreta" in tipo:
            por_tipo["quantitativas_discretas"].append(rotulo)
        else:
            por_tipo["quantitativas_continuas"].append(rotulo)

    return {
        "populacao": (
            "A população de interesse é o conjunto de todos os turnos de "
            f"produção da EletroTech nas {n_linhas} linhas de montagem "
            f"(Linha A a Linha D), nos {n_turnos} turnos diários e para os "
            f"{n_produtos} produtos da carteira (Geladeira, Lavadora, "
            "Ar-condicionado e Micro-ondas). Conceitualmente essa população "
            "é aberta no tempo: ela continua sendo gerada a cada novo turno "
            "operado pela fábrica. O que está disponível para análise é a "
            f"janela de {periodo}, com {meta['n_meses']} meses de operação "
            f"e {n} turnos registrados."
        ),
        "unidade_analise": (
            "A unidade de análise é o registro de produção, isto é, a "
            "combinação de uma data, um turno, uma linha de montagem e um "
            "produto, identificada pela variável id_registro. Cada uma das "
            f"{n} linhas da base descreve um desses turnos produtivos, e "
            f"não um produto nem um funcionário. Como consequência, todas as "
            "médias calculadas são médias por turno de produção."
        ),
        "amostra": (
            f"A base inicial é composta por {n} registros e "
            f"{meta['n_variaveis']} variáveis, cobrindo {meta['n_meses']} "
            f"meses ({periodo}). Esses {n} registros são tratados aqui como "
            "a amostra disponível da população de turnos produtivos: são "
            "todos os registros entregues no arquivo, mas não todos os "
            f"turnos que a fábrica já operou ou irá operar. Há "
            f"{total_medicao} células sem medição, distribuídas em "
            f"{len(medicao)} variáveis ("
            + ", ".join(f"{_rotulo(col)} {qtd}" for col, qtd in medicao.items())
            + "), tratadas por exclusão caso a caso: cada medida usa apenas "
            "os registros em que a variável correspondente está preenchida. "
            "A coluna ordem_atipico aparece vazia em "
            f"{meta['faltantes'].get('ordem_atipico', 0)} registros por "
            "construção, pois só é numerada nos turnos classificados como "
            "atípicos de energia."
        ),
        "tecnica_amostragem": (
            "O arquivo não documenta sorteio: os registros chegam completos "
            "no período informado, o que caracteriza um censo da janela "
            f"observada ({periodo}) e, ao mesmo tempo, uma amostra não "
            "probabilística por conveniência da população de turnos da "
            "fábrica. A distinção é importante para a leitura dos "
            "resultados: as estatísticas descritivas descrevem com exatidão "
            "os turnos registrados, mas a extrapolação para turnos futuros "
            "depende da hipótese de que o processo permaneça estável. Se o "
            "objetivo fosse inferência formal, a técnica indicada seria "
            "amostragem aleatória estratificada por produto, linha e turno, "
            "já que o número de registros por produto é desigual: "
            + ", ".join(
                f"{str(cat)} {int(qtd)}"
                for cat, qtd in df["produto"]
                .value_counts()
                .sort_values(ascending=False)
                .items()
            )
            + ". Os intervalos de confiança de 95% apresentados na tabela "
            "de medidas descritivas devem, por isso, ser lidos como "
            "referência de precisão e não como garantia de "
            "representatividade."
        ),
        "variaveis_por_tipo": por_tipo,
    }


# ----------------------------------------------------------- descritivas --
def _frase_media_vs_mediana(coluna: str, d: dict) -> str:
    """Frase curta dizendo qual medida de centro representa melhor a variável."""
    media = d.get("media")
    mediana = d.get("mediana")
    assimetria = d.get("assimetria") or 0.0
    n_outliers = d.get("n_outliers") or 0
    unidade = _unidade(coluna)
    sufixo = f" {unidade}" if unidade and unidade not in {"fração", "índice", "%"} else ""

    if media is None or mediana is None:
        return "Sem valores suficientes para comparar média e mediana."

    desvio_relativo = abs(media - mediana) / abs(media) if media else 0.0
    lado = "acima" if media > mediana else "abaixo"
    base = (
        f"Média {_fmt(media, 2, sufixo)} contra mediana "
        f"{_fmt(mediana, 2, sufixo)} ({_fmt_pct(desvio_relativo, 1)} {lado}), "
        f"assimetria {_fmt(assimetria, 2)} e {n_outliers} outliers de Tukey: "
    )
    if desvio_relativo < 0.02 and abs(assimetria) < 0.5:
        return base + (
            "distribuição praticamente simétrica, a média representa bem o "
            "conjunto."
        )
    if desvio_relativo < 0.05:
        return base + (
            "assimetria discreta, a média segue utilizável e a mediana serve "
            "de confirmação."
        )
    return base + (
        "a cauda desloca a média, de modo que a mediana descreve melhor o "
        "turno típico."
    )


def _descritivas(df: pd.DataFrame) -> dict:
    """Tabela completa de medidas descritivas, uma entrada por variável."""
    resultado: dict[str, dict] = {}
    for coluna in COLUNAS_DESCRITIVAS:
        if coluna not in df.columns:
            continue
        d = est.descritivas(df[coluna])
        if not d or not d.get("n"):
            continue
        ic = d.get("ic95") or (None, None)
        item = {
            "coluna": coluna,
            "rotulo": _rotulo(coluna),
            "unidade": _unidade(coluna),
            "n": int(d["n"]),
            "faltantes": int(d["faltantes"]),
            "media": est.arredondar(d["media"], 4),
            "mediana": est.arredondar(d["mediana"], 4),
            "moda": est.arredondar(d["moda"], 4),
            "modas": [est.arredondar(v, 4) for v in d["modas"]],
            "minimo": est.arredondar(d["minimo"], 4),
            "maximo": est.arredondar(d["maximo"], 4),
            "amplitude": est.arredondar(d["amplitude"], 4),
            "q1": est.arredondar(d["q1"], 4),
            "q2": est.arredondar(d["q2"], 4),
            "q3": est.arredondar(d["q3"], 4),
            "iqr": est.arredondar(d["iqr"], 4),
            "variancia": est.arredondar(d["variancia"], 4),
            "desvio_padrao": est.arredondar(d["desvio_padrao"], 4),
            "coef_variacao": est.arredondar(d["coef_variacao"], 4),
            "erro_padrao": est.arredondar(d["erro_padrao"], 4),
            "ic95": (est.arredondar(ic[0], 4), est.arredondar(ic[1], 4)),
            "assimetria": est.arredondar(d["assimetria"], 4),
            "curtose": est.arredondar(d["curtose"], 4),
            "lim_inf": est.arredondar(d["lim_inf"], 4),
            "lim_sup": est.arredondar(d["lim_sup"], 4),
            "n_outliers": int(d["n_outliers"]),
            "pct_outliers": est.arredondar(d["pct_outliers"], 4),
            "soma": est.arredondar(d["soma"], 4),
        }
        item["media_vs_mediana"] = _frase_media_vs_mediana(coluna, d)
        resultado[coluna] = item
    return resultado


# --------------------------------------------------------------- recortes --
def _metricas_grupo(recorte: pd.DataFrame, total_geral: float) -> dict:
    """Métricas padronizadas de um grupo, prontas para tabela."""
    unidades = recorte["unidades_produzidas"]
    produtividade = est.serie_limpa(recorte["produtividade_hora"])
    prazo = est.serie_limpa(recorte["entregas_no_prazo_pct"])
    relativa = est.serie_limpa(recorte["producao_relativa"])
    parada = est.serie_limpa(recorte["horas_parada_maquina"])

    media_un = est.numero(unidades.mean())
    dp_un = est.numero(unidades.std(ddof=1)) if len(unidades) > 1 else 0.0
    total_un = est.numero(unidades.sum()) or 0.0

    return {
        "n": int(len(recorte)),
        "pct_registros": est.arredondar(
            est.razao(len(recorte), total_geral), 4
        ),
        "unidades_total": est.inteiro(total_un),
        "unidades_media": est.arredondar(media_un, 2),
        "unidades_mediana": est.arredondar(unidades.median(), 2),
        "unidades_dp": est.arredondar(dp_un, 2),
        "unidades_cv": est.arredondar(est.razao(dp_un, media_un), 4),
        "producao_relativa_media": est.arredondar(relativa.mean(), 4),
        "produtividade_media": est.arredondar(
            est.produtividade_agregada(recorte), 2
        ),
        "produtividade_media_simples": est.arredondar(produtividade.mean(), 2),
        "produtividade_dp": est.arredondar(
            produtividade.std(ddof=1) if produtividade.size > 1 else 0.0, 2
        ),
        "produtividade_cv": est.arredondar(
            est.razao(
                produtividade.std(ddof=1) if produtividade.size > 1 else 0.0,
                produtividade.mean(),
            ),
            4,
        ),
        "horas_efetivas_total": est.arredondar(
            recorte["horas_efetivas"].sum(), 2
        ),
        "defeituosas_total": est.inteiro(recorte["unidades_defeituosas"].sum()),
        "taxa_defeitos": est.arredondar(est.taxa_defeitos_agregada(recorte), 6),
        "taxa_defeitos_media_simples": est.arredondar(
            est.serie_limpa(recorte["taxa_defeitos"]).mean(), 6
        ),
        "energia_por_unidade": est.arredondar(
            est.energia_por_unidade_agregada(recorte), 4
        ),
        "parada_media": est.arredondar(parada.mean(), 4),
        "parada_total": est.arredondar(parada.sum(), 2),
        "residuo_por_unidade": est.arredondar(
            est.residuo_por_unidade_agregado(recorte), 5
        ),
        "entregas_prazo": est.arredondar(prazo.mean(), 2),
    }


def _recorte(df: pd.DataFrame, coluna: str) -> list[dict]:
    """Lista achatada de métricas por categoria da coluna informada."""
    if coluna not in df.columns:
        return []
    categorias = [str(c) for c in df[coluna].dropna().unique()]
    total = float(len(df))
    linhas = []
    for categoria in _ordenar_categorias(coluna, categorias):
        recorte = df[df[coluna].astype("string") == categoria]
        if recorte.empty:
            continue
        item = {coluna: categoria}
        item.update(_metricas_grupo(recorte, total))
        linhas.append(item)
    return linhas


def _maior(linhas: list[dict], campo: str) -> dict:
    """Item com o maior valor do campo (ignora ``None``)."""
    validos = [x for x in linhas if x.get(campo) is not None]
    return max(validos, key=lambda x: x[campo]) if validos else {}


def _menor(linhas: list[dict], campo: str) -> dict:
    """Item com o menor valor do campo (ignora ``None``)."""
    validos = [x for x in linhas if x.get(campo) is not None]
    return min(validos, key=lambda x: x[campo]) if validos else {}


# -------------------------------------------------------------- KPIs ------
def _status_por_faixas(valor, faixas: list[tuple[float, str]]) -> str | None:
    """Classifica um valor em faixas crescentes de corte.

    Usada em indicadores em que "menor é melhor" (taxa de defeitos,
    participação da parada na capacidade).
    """
    numero = est.numero(valor)
    if numero is None:
        return None
    for corte, rotulo in faixas:
        if numero <= corte:
            return rotulo
    return faixas[-1][1]


def _status_decrescente(valor, faixas: list[tuple[float, str]]) -> str | None:
    """Classifica um valor em faixas decrescentes de corte.

    Usada em indicadores em que "maior é melhor", como o percentual de
    entregas no prazo. O último rótulo vale para tudo abaixo do menor corte.
    """
    numero = est.numero(valor)
    if numero is None:
        return None
    for corte, rotulo in faixas:
        if numero >= corte:
            return rotulo
    return faixas[-1][1]


def _kpis(df: pd.DataFrame) -> list[dict]:
    """Os oito indicadores da faixa de visão geral."""
    produzidas = est.inteiro(df["unidades_produzidas"].sum()) or 0
    defeituosas = est.inteiro(df["unidades_defeituosas"].sum()) or 0
    taxa = est.taxa_defeitos_agregada(df)
    produtividade = est.produtividade_agregada(df)
    energia = est.energia_por_unidade_agregada(df)
    parada = est.serie_limpa(df["horas_parada_maquina"])
    planejadas = est.numero(df["horas_planejadas"].sum()) or 0.0
    parada_relativa = est.razao(parada.sum(), planejadas)
    prazo = est.serie_limpa(df["entregas_no_prazo_pct"]).mean()
    residuo = est.numero(df["residuo_kg"].sum())
    devolucoes = est.inteiro(df["devolucoes_clientes"].sum()) or 0
    horas_efetivas = est.numero(df["horas_efetivas"].sum()) or 0.0

    return [
        {
            "id": "producao-total",
            "rotulo": "Produção total",
            "valor": float(produzidas),
            "unidade": "un",
            "formato": "int",
            "nota": (
                f"{_fmt_int(produzidas)} unidades em {len(df)} registros, "
                f"média de {_fmt(produzidas / len(df), 1)} un por turno."
            ),
            "status": None,
        },
        {
            "id": "produtividade-global",
            "rotulo": "Produtividade global",
            "valor": est.arredondar(produtividade, 2),
            "unidade": "un/h",
            "formato": "num",
            "nota": (
                f"{_fmt_int(produzidas)} unidades divididas por "
                f"{_fmt(horas_efetivas, 1)} horas efetivas. Indicador "
                "comparável entre produtos de ritmos diferentes."
            ),
            "status": None,
        },
        {
            "id": "taxa-defeitos-global",
            "rotulo": "Taxa de defeitos",
            "valor": est.arredondar(taxa, 6),
            "unidade": "%",
            "formato": "pct",
            "nota": (
                f"{_fmt_int(defeituosas)} unidades defeituosas sobre "
                f"{_fmt_int(produzidas)} produzidas (razão agregada, não "
                "média das taxas por registro)."
            ),
            "status": _status_por_faixas(
                taxa,
                [(0.03, "bom"), (0.05, "atencao"), (0.08, "grave"), (1.0, "critico")],
            ),
        },
        {
            "id": "parada-media",
            "rotulo": "Parada média por turno",
            "valor": est.arredondar(parada.mean(), 4),
            "unidade": "h",
            "formato": "num",
            "nota": (
                f"Mediana de {_fmt(parada.median(), 2)} h e máximo de "
                f"{_fmt(parada.max(), 2)} h. No total, "
                f"{_fmt(parada.sum(), 2)} h paradas sobre "
                f"{_fmt(planejadas, 1)} h planejadas "
                f"({_fmt_pct(parada_relativa, 2)} da capacidade)."
            ),
            "status": _status_por_faixas(
                parada_relativa,
                [(0.05, "bom"), (0.10, "atencao"), (0.20, "grave"), (1.0, "critico")],
            ),
        },
        {
            "id": "energia-por-unidade",
            "rotulo": "Energia por unidade",
            "valor": est.arredondar(energia, 4),
            "unidade": "kWh/un",
            "formato": "num",
            "nota": (
                "Consumo total dividido pelas unidades produzidas nos "
                "registros com energia informada. Varia muito por produto, "
                "o que exige leitura por linha e produto."
            ),
            "status": None,
        },
        {
            "id": "entregas-prazo",
            "rotulo": "Entregas no prazo",
            "valor": est.arredondar(prazo, 2),
            "unidade": "%",
            "formato": "num",
            "nota": (
                "Média simples do percentual de entregas no prazo informado "
                "em cada registro; a variável já vem na escala de 0 a 100."
            ),
            "status": _status_decrescente(
                prazo,
                [(95.0, "bom"), (92.0, "atencao"), (88.0, "grave"), (0.0, "critico")],
            ),
        },
        {
            "id": "residuo-total",
            "rotulo": "Resíduo gerado",
            "valor": est.arredondar(residuo, 2),
            "unidade": "kg",
            "formato": "num",
            "nota": (
                f"{_fmt(residuo, 1)} kg no período, equivalentes a "
                f"{_fmt(est.razao(residuo, produzidas), 4)} kg por unidade "
                "produzida."
            ),
            "status": None,
        },
        {
            "id": "devolucoes-total",
            "rotulo": "Devoluções de clientes",
            "valor": float(devolucoes),
            "unidade": "un",
            "formato": "int",
            "nota": (
                f"{devolucoes} devoluções registradas, "
                f"{_fmt_pct(est.razao(devolucoes, produzidas), 3)} das "
                "unidades produzidas."
            ),
            "status": None,
        },
    ]


# ------------------------------------------------------- correlações ------
def _correlacoes(df: pd.DataFrame) -> dict:
    """Matriz de Pearson e os seis pares de maior correlação em módulo."""
    colunas = [c for c in COLUNAS_CORRELACAO if c in df.columns]
    matriz = est.correlacoes(df, colunas)
    valores = [
        [est.arredondar(matriz.loc[a, b], 4) for b in colunas] for a in colunas
    ]

    destaques = []
    for a, b, r in est.pares_correlacao(matriz, quantos=6):
        modelo = LEITURAS_PARES.get(frozenset({a, b}))
        if modelo:
            leitura = modelo.format(r=_fmt(r, 3))
        else:
            sentido = "positiva" if r > 0 else "negativa"
            leitura = (
                f"Associação {sentido} {est.forca_correlacao(r)} entre "
                f"{_rotulo(a).lower()} e {_rotulo(b).lower()} "
                f"(r = {_fmt(r, 3)}). Correlação não estabelece causa."
            )
        destaques.append(
            {
                "x": a,
                "y": b,
                "rotulo_x": _rotulo(a),
                "rotulo_y": _rotulo(b),
                "r": est.arredondar(r, 4),
                "forca": est.forca_correlacao(r),
                "leitura": leitura,
            }
        )

    return {
        "colunas": colunas,
        "rotulos": [_rotulo(c) for c in colunas],
        "matriz": valores,
        "destaques": destaques,
        "nota": (
            "Coeficiente de Pearson calculado par a par, usando apenas os "
            "registros em que ambas as variáveis estão preenchidas. Alguns "
            "pares de alta correlação são construtivos (a variável é "
            "definida a partir da outra) e estão sinalizados na leitura; "
            "em nenhum caso a correlação demonstra causalidade."
        ),
    }


# ------------------------------------------------------ atípicos ----------
def _outliers_energia(df: pd.DataFrame) -> dict:
    """Observações atípicas de consumo de energia pelo critério de Tukey."""
    coluna = "consumo_energia_kwh"
    serie = est.serie_limpa(df[coluna])
    lim_inf, lim_sup = est.limites_outliers(df[coluna])
    media = est.numero(serie.mean())
    desvio = est.numero(serie.std(ddof=1))

    validos = df[df[coluna].notna()]
    mascara = (validos[coluna] < lim_inf) | (validos[coluna] > lim_sup)
    atipicos = validos[mascara].sort_values(coluna, ascending=False)

    registros = []
    for _, linha in atipicos.iterrows():
        valor = est.numero(linha[coluna])
        registros.append(
            {
                "id_registro": str(linha["id_registro"]),
                "data": linha[config.COL_DATA],
                "produto": str(linha["produto"]),
                "linha_producao": str(linha["linha_producao"]),
                "turno": str(linha["turno"]),
                "consumo_energia_kwh": est.arredondar(valor, 2),
                "energia_por_unidade": est.arredondar(
                    linha["energia_por_unidade"], 4
                ),
                "unidades_produzidas": est.inteiro(linha["unidades_produzidas"]),
                "z": est.arredondar(
                    est.razao((valor or 0.0) - (media or 0.0), desvio), 2
                ),
                "tipo": "acima" if valor is not None and valor > lim_sup else "abaixo",
            }
        )

    n_atipicos = len(registros)
    pct = est.razao(n_atipicos, serie.size)
    acima = [r for r in registros if r["tipo"] == "acima"]
    abaixo = [r for r in registros if r["tipo"] == "abaixo"]

    # Coerência com a marcação que já vem na base.
    marcados = set(
        df.loc[df["atipico_energia"].astype("string") == "Sim", "id_registro"]
        .astype("string")
        .tolist()
    )
    detectados = {r["id_registro"] for r in registros}
    coincidem = marcados & detectados
    so_tukey = sorted(detectados - marcados)
    so_base = sorted(marcados - detectados)
    sem_marcacao = int(df["atipico_energia"].isna().sum())

    if not so_tukey and not so_base:
        coerencia = (
            f"Coincidência integral: o critério de Tukey apontou "
            f"{n_atipicos} registros e a coluna atipico_energia marca os "
            f"mesmos {len(marcados)} registros como Sim, sem nenhuma "
            f"divergência. Isso indica que a marcação original da base foi "
            f"construída com o mesmo critério de 1,5 × IQR aqui replicado. "
            f"Restam {sem_marcacao} registros sem consumo informado e, por "
            f"consequência, sem marcação de atipicidade."
        )
    else:
        coerencia = (
            f"Divergência parcial: Tukey apontou {n_atipicos} registros e a "
            f"base marca {len(marcados)}; {len(coincidem)} coincidem, "
            f"{len(so_tukey)} aparecem apenas no cálculo "
            f"({', '.join(so_tukey) or 'nenhum'}) e {len(so_base)} apenas na "
            f"marcação original ({', '.join(so_base) or 'nenhum'}). "
            f"Há ainda {sem_marcacao} registros sem consumo informado."
        )

    produtos_acima = sorted({r["produto"] for r in acima})
    produtos_abaixo = sorted({r["produto"] for r in abaixo})
    leitura = (
        f"Pelo critério de Tukey, o consumo esperado de um turno fica entre "
        f"{_fmt(lim_inf, 2)} kWh e {_fmt(lim_sup, 2)} kWh; "
        f"{n_atipicos} dos {serie.size} registros com energia informada "
        f"({_fmt_pct(pct, 2)}) ficam fora dessa faixa. São "
        f"{len(acima)} casos de consumo excepcionalmente alto "
        f"(até {_fmt(registros[0]['consumo_energia_kwh'], 1) if registros else 'n/d'} kWh, "
        f"z = {_fmt(registros[0]['z'], 2) if registros else 'n/d'}), "
        f"todos de {' e '.join(produtos_acima) or 'produtos não identificados'}, "
        f"e {len(abaixo)} casos de consumo excepcionalmente baixo "
        f"(mínimo de {_fmt(registros[-1]['consumo_energia_kwh'], 1) if registros else 'n/d'} kWh, "
        f"z = {_fmt(registros[-1]['z'], 2) if registros else 'n/d'}), "
        f"todos de {' e '.join(produtos_abaixo) or 'produtos não identificados'}. "
        f"O padrão não é aleatório: ele separa justamente o produto de maior "
        f"consumo unitário do produto de maior volume por turno, o que "
        f"aponta para causas de processo (ajuste de equipamento ou medição) "
        f"e não para erro de digitação isolado."
    )

    return {
        "metodo": (
            "Critério de Tukey (1,5 × IQR) aplicado ao consumo de energia "
            "em kWh, complementado pelo escore padronizado z de cada "
            "registro atípico"
        ),
        "coluna": coluna,
        "media": est.arredondar(media, 2),
        "desvio_padrao": est.arredondar(desvio, 2),
        "lim_inf": est.arredondar(lim_inf, 2),
        "lim_sup": est.arredondar(lim_sup, 2),
        "n": n_atipicos,
        "n_avaliados": int(serie.size),
        "pct": est.arredondar(pct, 4),
        "n_acima": len(acima),
        "n_abaixo": len(abaixo),
        "registros": registros,
        "coerencia_coluna_atipico": coerencia,
        "leitura": leitura,
    }


# ------------------------------------------------------- questões ---------
def _questao_1(df: pd.DataFrame, por_produto: list[dict]) -> dict:
    """Produto com maior produção média por registro."""
    top_media = _maior(por_produto, "unidades_media")
    menor_media = _menor(por_produto, "unidades_media")
    top_prod = _maior(por_produto, "produtividade_media")
    top_total = _maior(por_produto, "unidades_total")
    relativas = [
        f"{x['produto']} {_fmt(x['producao_relativa_media'], 4)}"
        for x in por_produto
    ]
    razao_ritmo = est.razao(
        top_media.get("unidades_media"), menor_media.get("unidades_media")
    )

    return {
        "n": 1,
        "pergunta": "Qual produto apresenta maior produção média por registro?",
        "resposta_curta": (
            f"{top_media.get('produto')}, com "
            f"{_fmt(top_media.get('unidades_media'), 2)} un por registro"
        ),
        "resposta": (
            f"O produto {top_media.get('produto')} lidera a produção média "
            f"por registro, com "
            f"{_fmt(top_media.get('unidades_media'), 2)} unidades por turno "
            f"em {top_media.get('n')} registros, contra "
            f"{_fmt(menor_media.get('unidades_media'), 2)} unidades de "
            f"{menor_media.get('produto')} — uma diferença de "
            f"{_fmt(razao_ritmo, 2)} vezes. Essa comparação direta, porém, "
            f"não mede desempenho, porque os produtos têm ritmos de "
            f"fabricação distintos: um turno de "
            f"{top_media.get('produto')} e um turno de "
            f"{menor_media.get('produto')} não são lotes equivalentes. "
            f"Corrigindo pela hora efetivamente produtiva, o produto "
            f"{top_prod.get('produto')} segue à frente, com "
            f"{_fmt(top_prod.get('produtividade_media'), 2)} un/h contra "
            f"{_fmt(menor_media.get('produtividade_media'), 2)} un/h de "
            f"{menor_media.get('produto')}, de modo que a liderança se "
            f"confirma nas duas leituras. Já a produção relativa, que "
            f"divide cada registro pela média do próprio produto, fica "
            f"praticamente em 1,00 nos quatro produtos "
            f"({'; '.join(relativas)}), o que mostra que nenhum produto "
            f"opera sistematicamente acima ou abaixo do seu próprio padrão."
        ),
        "evidencias": [
            f"Produção média por registro: "
            + "; ".join(
                f"{x['produto']} {_fmt(x['unidades_media'], 1)} un"
                for x in sorted(
                    por_produto, key=lambda x: x["unidades_media"], reverse=True
                )
            ),
            f"Produtividade por hora efetiva (soma de unidades / soma de "
            f"horas efetivas): "
            + "; ".join(
                f"{x['produto']} {_fmt(x['produtividade_media'], 1)} un/h"
                for x in sorted(
                    por_produto,
                    key=lambda x: x["produtividade_media"] or 0,
                    reverse=True,
                )
            ),
            f"Volume total do período: {top_total.get('produto')} responde "
            f"por {_fmt_int(top_total.get('unidades_total'))} unidades em "
            f"apenas {top_total.get('n')} registros "
            f"({_fmt_pct(top_total.get('pct_registros'), 1)} da base), "
            f"enquanto {menor_media.get('produto')} soma "
            f"{_fmt_int(menor_media.get('unidades_total'))} unidades em "
            f"{menor_media.get('n')} registros.",
            f"Produção relativa média próxima de 1,00 em todos os produtos "
            f"({'; '.join(relativas)}): a diferença entre eles é de ritmo de "
            f"fabricação, não de aderência ao padrão.",
        ],
        "grafico": "producao-media-por-produto",
    }


def _questao_2(df: pd.DataFrame, por_turno: list[dict]) -> dict:
    """Turno com maior variabilidade de produção."""
    top_dp = _maior(por_turno, "unidades_dp")
    ranking_cv = sorted(
        [x for x in por_turno if x.get("unidades_cv") is not None],
        key=lambda x: x["unidades_cv"],
        reverse=True,
    )
    top_cv = ranking_cv[0]
    segundo_cv = ranking_cv[1] if len(ranking_cv) > 1 else {}
    menor_cv = ranking_cv[-1]

    # Variabilidade controlada pelo mix de produtos, via produção relativa.
    relativa = {}
    for item in por_turno:
        turno = item["turno"]
        serie = est.serie_limpa(
            df.loc[df["turno"].astype("string") == turno, "producao_relativa"]
        )
        media = est.numero(serie.mean())
        desvio = est.numero(serie.std(ddof=1))
        relativa[turno] = {
            "dp": desvio,
            "cv": est.razao(desvio, media),
        }
    top_relativa = max(relativa.items(), key=lambda kv: kv[1]["cv"] or 0)

    return {
        "n": 2,
        "pergunta": "Qual turno apresenta maior variabilidade de produção?",
        "resposta_curta": (
            f"{top_dp.get('turno')}, com desvio-padrão de "
            f"{_fmt(top_dp.get('unidades_dp'), 2)} un e CV de "
            f"{_fmt_pct(top_dp.get('unidades_cv'), 2)}"
        ),
        "resposta": (
            f"Em valores absolutos, o turno da {top_dp.get('turno')} "
            f"apresenta a maior dispersão de produção: desvio-padrão de "
            f"{_fmt(top_dp.get('unidades_dp'), 2)} unidades em torno de uma "
            f"média de {_fmt(top_dp.get('unidades_media'), 2)} unidades, o "
            f"que corresponde a um coeficiente de variação de "
            f"{_fmt_pct(top_dp.get('unidades_cv'), 2)}. O coeficiente de "
            f"variação, que neutraliza a diferença de nível entre turnos, "
            f"mantém {top_cv.get('turno')} em primeiro lugar com "
            f"{_fmt_pct(top_cv.get('unidades_cv'), 2)}, seguido de perto "
            f"por {segundo_cv.get('turno')} com "
            f"{_fmt_pct(segundo_cv.get('unidades_cv'), 2)} e, por último, "
            f"{menor_cv.get('turno')} com "
            f"{_fmt_pct(menor_cv.get('unidades_cv'), 2)} — ou seja, os três "
            f"turnos ficam em uma faixa estreita e a diferença entre os dois "
            f"primeiros é marginal "
            f"({_fmt((top_cv.get('unidades_cv', 0) - segundo_cv.get('unidades_cv', 0)) * 100, 2)} "
            f"ponto percentual). Vale registrar que boa parte dessa "
            f"dispersão não é "
            f"do turno, e sim do mix de produtos alocado a ele: como "
            f"Micro-ondas rende cerca de 300 unidades por turno e Geladeira "
            f"cerca de 130, qualquer turno que concentre mais Micro-ondas "
            f"herda variância maior. Repetindo o cálculo sobre a produção "
            f"relativa, que já normaliza cada registro pela média do seu "
            f"produto, a maior variabilidade passa a ser do turno "
            f"{top_relativa[0]} ({_fmt_pct(top_relativa[1]['cv'], 2)}), e "
            f"todos os turnos caem para a casa de 11%, o que confirma que o "
            f"efeito bruto é dominado pelo mix."
        ),
        "evidencias": [
            "Desvio-padrão e CV da produção bruta: "
            + "; ".join(
                f"{x['turno']} {_fmt(x['unidades_dp'], 1)} un / "
                f"{_fmt_pct(x['unidades_cv'], 2)}"
                for x in por_turno
            ),
            "Nível de produção por turno (para contextualizar a dispersão): "
            + "; ".join(
                f"{x['turno']} média {_fmt(x['unidades_media'], 1)} un, "
                f"mediana {_fmt(x['unidades_mediana'], 1)} un, "
                f"{x['n']} registros"
                for x in por_turno
            ),
            "CV da produção relativa (mix de produtos neutralizado): "
            + "; ".join(
                f"{turno} {_fmt_pct(valores['cv'], 2)}"
                for turno, valores in relativa.items()
            ),
            "Variabilidade da produtividade por hora efetiva: "
            + "; ".join(
                f"{x['turno']} DP {_fmt(x['produtividade_dp'], 2)} un/h "
                f"(CV {_fmt_pct(x['produtividade_cv'], 2)})"
                for x in por_turno
            ),
        ],
        "grafico": "boxplot-producao-por-turno",
    }


def _questao_3(df: pd.DataFrame, por_linha: list[dict]) -> dict:
    """Linha com maior taxa de defeitos."""
    ordenadas = sorted(
        [x for x in por_linha if x.get("taxa_defeitos") is not None],
        key=lambda x: x["taxa_defeitos"],
        reverse=True,
    )
    pior = ordenadas[0]
    melhor = ordenadas[-1]
    global_taxa = est.taxa_defeitos_agregada(df)
    diferenca = est.razao(pior["taxa_defeitos"], melhor["taxa_defeitos"])

    return {
        "n": 3,
        "pergunta": "Qual linha de produção apresenta maior taxa de defeitos?",
        "resposta_curta": (
            f"{pior['linha_producao']}, com "
            f"{_fmt_pct(pior['taxa_defeitos'], 2)} de defeitos"
        ),
        "resposta": (
            f"A {pior['linha_producao']} tem a maior taxa de defeitos da "
            f"fábrica: {_fmt_int(pior['defeituosas_total'])} unidades "
            f"reprovadas sobre {_fmt_int(pior['unidades_total'])} "
            f"produzidas, ou {_fmt_pct(pior['taxa_defeitos'], 2)}, contra "
            f"{_fmt_pct(melhor['taxa_defeitos'], 2)} da "
            f"{melhor['linha_producao']} — razão de "
            f"{_fmt(diferenca, 2)} entre a pior e a melhor linha. A "
            f"taxa global da fábrica é {_fmt_pct(global_taxa, 2)}, de modo "
            f"que a {pior['linha_producao']} está "
            f"{_fmt(((pior['taxa_defeitos'] or 0) - (global_taxa or 0)) * 100, 2)} "
            f"ponto percentual acima da média. Todas as taxas aqui são "
            f"razões agregadas (soma de defeituosas dividida pela soma de "
            f"produzidas do grupo) e não médias das taxas de cada registro, "
            f"o que evita dar o mesmo peso a lotes de tamanhos muito "
            f"diferentes. Vale notar que a {pior['linha_producao']} é também "
            f"a de menor produtividade "
            f"({_fmt(pior['produtividade_media'], 2)} un/h) e maior consumo "
            f"unitário de energia "
            f"({_fmt(pior['energia_por_unidade'], 3)} kWh/un), o que sugere "
            f"um problema de processo concentrado nessa linha."
        ),
        "evidencias": [
            "Taxa de defeitos por linha (razão agregada): "
            + "; ".join(
                f"{x['linha_producao']} {_fmt_pct(x['taxa_defeitos'], 2)} "
                f"({_fmt_int(x['defeituosas_total'])}/"
                f"{_fmt_int(x['unidades_total'])})"
                for x in ordenadas
            ),
            f"Taxa global da fábrica: {_fmt_pct(global_taxa, 2)} "
            f"({_fmt_int(df['unidades_defeituosas'].sum())} defeituosas em "
            f"{_fmt_int(df['unidades_produzidas'].sum())} produzidas).",
            "Comparação com a média simples das taxas por registro, que "
            "distorce o resultado ao ignorar o tamanho do lote: "
            + "; ".join(
                f"{x['linha_producao']} agregada "
                f"{_fmt_pct(x['taxa_defeitos'], 2)} contra média simples "
                f"{_fmt_pct(x['taxa_defeitos_media_simples'], 2)}"
                for x in ordenadas
            ),
            f"Resíduo por unidade produzida, da linha que mais descarta "
            f"para a que menos descarta: "
            + "; ".join(
                f"{x['linha_producao']} {_fmt(x['residuo_por_unidade'], 4)} kg/un"
                for x in sorted(
                    por_linha,
                    key=lambda x: x["residuo_por_unidade"] or 0,
                    reverse=True,
                )
            )
            + f". O maior descarte por unidade é da "
            f"{_maior(por_linha, 'residuo_por_unidade').get('linha_producao')}; "
            f"a ordenação completa das linhas não é idêntica à da taxa de "
            f"defeitos, o que indica que os dois indicadores de perda, "
            f"embora correlacionados, não são redundantes.",
        ],
        "grafico": "taxa-defeitos-por-linha",
    }


def _questao_4(df: pd.DataFrame, por_manutencao: list[dict]) -> dict:
    """Tempo médio de parada das máquinas."""
    d = est.descritivas(df["horas_parada_maquina"])
    planejadas = est.numero(df["horas_planejadas"].sum()) or 0.0
    relativa = est.razao(d["soma"], planejadas)
    corretiva = next(
        (x for x in por_manutencao if x["tipo_manutencao"] == "Corretiva"), {}
    )
    nenhuma = next(
        (x for x in por_manutencao if x["tipo_manutencao"] == "Nenhuma"), {}
    )
    media_min = (d["media"] or 0.0) * 60.0
    mediana_min = (d["mediana"] or 0.0) * 60.0

    return {
        "n": 4,
        "pergunta": "Qual é o tempo médio de parada das máquinas?",
        "resposta_curta": (
            f"{_fmt(d['media'], 2)} h por turno "
            f"({_fmt(media_min, 0)} minutos), com mediana de "
            f"{_fmt(d['mediana'], 2)} h"
        ),
        "resposta": (
            f"A parada média é de {_fmt(d['media'], 3)} hora por turno, o "
            f"equivalente a {_fmt(media_min, 0)} minutos, com desvio-padrão "
            f"de {_fmt(d['desvio_padrao'], 3)} h e coeficiente de variação "
            f"de {_fmt_pct(d['coef_variacao'], 1)}. A distribuição é "
            f"assimétrica à direita (assimetria {_fmt(d['assimetria'], 2)}, "
            f"curtose {_fmt(d['curtose'], 2)}, {d['n_outliers']} registros "
            f"acima do limite de Tukey de {_fmt(d['lim_sup'], 2)} h), de "
            f"modo que a mediana de {_fmt(d['mediana'], 2)} h "
            f"({_fmt(mediana_min, 0)} minutos) descreve melhor o turno "
            f"típico do que a média. O intervalo vai de "
            f"{_fmt(d['minimo'], 2)} h a {_fmt(d['maximo'], 2)} h e metade "
            f"dos turnos fica entre {_fmt(d['q1'], 2)} h e "
            f"{_fmt(d['q3'], 2)} h. No agregado, as "
            f"{_fmt(d['soma'], 2)} horas paradas consomem "
            f"{_fmt_pct(relativa, 2)} das {_fmt(planejadas, 1)} horas "
            f"planejadas do período."
        ),
        "evidencias": [
            f"Média {_fmt(d['media'], 3)} h, mediana {_fmt(d['mediana'], 2)} h, "
            f"moda {_fmt(d['moda'], 2)} h, desvio-padrão "
            f"{_fmt(d['desvio_padrao'], 3)} h, variância "
            f"{_fmt(d['variancia'], 3)} h², amplitude "
            f"{_fmt(d['amplitude'], 2)} h.",
            f"Quartis: Q1 {_fmt(d['q1'], 2)} h, Q2 {_fmt(d['q2'], 2)} h, "
            f"Q3 {_fmt(d['q3'], 2)} h, IQR {_fmt(d['iqr'], 2)} h; "
            f"{d['n_outliers']} turnos ({_fmt_pct(d['pct_outliers'], 1)}) "
            f"acima de {_fmt(d['lim_sup'], 2)} h.",
            f"Perda agregada de capacidade: {_fmt(d['soma'], 2)} h paradas "
            f"sobre {_fmt(planejadas, 1)} h planejadas "
            f"({_fmt_pct(relativa, 2)}).",
            f"Registros com manutenção Corretiva param "
            f"{_fmt(corretiva.get('parada_media'), 2)} h em média, contra "
            f"{_fmt(nenhuma.get('parada_media'), 2)} h dos registros sem "
            f"manutenção — razão de "
            f"{_fmt(est.razao(corretiva.get('parada_media'), nenhuma.get('parada_media')), 2)} "
            f"vezes, em apenas {corretiva.get('n')} registros.",
        ],
        "grafico": "dist-horas-parada",
    }


def _questao_5(outliers: dict) -> dict:
    """Existência de observações atípicas no consumo de energia."""
    registros = outliers["registros"]
    extremo_alto = next((r for r in registros if r["tipo"] == "acima"), None)
    extremo_baixo = next(
        (r for r in reversed(registros) if r["tipo"] == "abaixo"), None
    )

    detalhes_altos = "; ".join(
        f"{r['id_registro']} ({r['produto']}, {r['data']:%d/%m/%Y}) "
        f"{_fmt(r['consumo_energia_kwh'], 1)} kWh, z = {_fmt(r['z'], 2)}"
        for r in registros
        if r["tipo"] == "acima"
    )
    detalhes_baixos = "; ".join(
        f"{r['id_registro']} ({r['produto']}, {r['data']:%d/%m/%Y}) "
        f"{_fmt(r['consumo_energia_kwh'], 1)} kWh, z = {_fmt(r['z'], 2)}"
        for r in registros
        if r["tipo"] == "abaixo"
    )

    return {
        "n": 5,
        "pergunta": "Existem observações atípicas no consumo de energia?",
        "resposta_curta": (
            f"Sim: {outliers['n']} registros "
            f"({_fmt_pct(outliers['pct'], 2)}) fora da faixa de "
            f"{_fmt(outliers['lim_inf'], 1)} a "
            f"{_fmt(outliers['lim_sup'], 1)} kWh"
        ),
        "resposta": (
            f"Sim. Aplicando o critério de Tukey ao consumo de energia, a "
            f"faixa esperada de um turno vai de "
            f"{_fmt(outliers['lim_inf'], 2)} kWh a "
            f"{_fmt(outliers['lim_sup'], 2)} kWh, e "
            f"{outliers['n']} dos {outliers['n_avaliados']} registros com "
            f"consumo informado ({_fmt_pct(outliers['pct'], 2)}) ficam fora "
            f"dela: {outliers['n_acima']} acima e "
            f"{outliers['n_abaixo']} abaixo. O caso mais extremo para cima é "
            f"o registro {extremo_alto['id_registro'] if extremo_alto else 'n/d'} "
            f"com {_fmt(extremo_alto['consumo_energia_kwh'], 1) if extremo_alto else 'n/d'} kWh "
            f"(z = {_fmt(extremo_alto['z'], 2) if extremo_alto else 'n/d'}) e, "
            f"para baixo, o registro "
            f"{extremo_baixo['id_registro'] if extremo_baixo else 'n/d'} com "
            f"{_fmt(extremo_baixo['consumo_energia_kwh'], 1) if extremo_baixo else 'n/d'} kWh "
            f"(z = {_fmt(extremo_baixo['z'], 2) if extremo_baixo else 'n/d'}). "
            f"Os atípicos altos são todos de Ar-condicionado e os baixos "
            f"todos de Micro-ondas, o que indica causa de processo e não "
            f"ruído aleatório. {outliers['coerencia_coluna_atipico']} "
            f"Importa separar esses casos de um efeito diferente: a variável "
            f"energia por unidade tem muitos valores fora dos limites de "
            f"Tukey apenas porque o Micro-ondas produz lotes grandes e "
            f"dilui o consumo fixo, o que é característica do produto e não "
            f"anomalia do turno."
        ),
        "evidencias": [
            f"Critério: {outliers['metodo']}. Faixa esperada de "
            f"{_fmt(outliers['lim_inf'], 2)} a "
            f"{_fmt(outliers['lim_sup'], 2)} kWh, em torno de uma média de "
            f"{_fmt(outliers['media'], 2)} kWh e desvio-padrão de "
            f"{_fmt(outliers['desvio_padrao'], 2)} kWh.",
            f"Consumos excepcionalmente altos: {detalhes_altos or 'nenhum'}.",
            f"Consumos excepcionalmente baixos: {detalhes_baixos or 'nenhum'}.",
            outliers["coerencia_coluna_atipico"],
        ],
        "grafico": "atipicos-consumo-energia",
    }


def _questao_6(descritivas: dict) -> dict:
    """Adequação da média frente à mediana."""
    candidatas = []
    for coluna, d in descritivas.items():
        media, mediana = d.get("media"), d.get("mediana")
        if not media or mediana is None:
            continue
        candidatas.append(
            {
                "coluna": coluna,
                "rotulo": d["rotulo"],
                "gap": abs(media - mediana) / abs(media),
                "media": media,
                "mediana": mediana,
                "assimetria": d.get("assimetria") or 0.0,
                "n_outliers": d.get("n_outliers") or 0,
                "pct_outliers": d.get("pct_outliers") or 0.0,
                "cv": d.get("coef_variacao") or 0.0,
                "unidade": d.get("unidade") or "",
            }
        )
    candidatas.sort(key=lambda x: x["gap"], reverse=True)
    # Variáveis com mediana zero (caso das devoluções) produzem uma
    # divergência de 100% que é verdadeira mas pouco informativa como
    # exemplo; ficam fora do ranking e aparecem na lista de assimétricas.
    piores = [c for c in candidatas if c["mediana"]][:3]
    melhores = [
        c
        for c in reversed(candidatas)
        if abs(c["assimetria"]) < 0.6 and c["pct_outliers"] < 0.05
    ][:3]
    assimetricas = [c for c in candidatas if abs(c["assimetria"]) >= 0.8]

    def _descreve(c: dict) -> str:
        sufixo = f" {c['unidade']}" if c["unidade"] not in {"fração", "índice", "%"} else ""
        return (
            f"{c['rotulo']}: média {_fmt(c['media'], 2, sufixo)} contra "
            f"mediana {_fmt(c['mediana'], 2, sufixo)} "
            f"({_fmt_pct(c['gap'], 1)} de diferença, assimetria "
            f"{_fmt(c['assimetria'], 2)}, {c['n_outliers']} outliers)"
        )

    return {
        "n": 6,
        "pergunta": (
            "A média representa adequadamente os dados ou a mediana é mais "
            "informativa?"
        ),
        "resposta_curta": (
            "Depende da variável: para as assimétricas, como "
            f"{piores[0]['rotulo'].lower()}, a mediana é mais informativa"
        ),
        "resposta": (
            f"Não há resposta única: a adequação da média depende da forma "
            f"de cada distribuição. Nas variáveis assimétricas à direita a "
            f"média é puxada pela cauda e superestima o turno típico — é o "
            f"caso de {_descreve(piores[0])} e de {_descreve(piores[1])}. "
            f"Entre as {len(descritivas)} variáveis analisadas, "
            f"{len(assimetricas)} têm assimetria igual ou superior a 0,80 em "
            f"módulo, e nelas a mediana, acompanhada do IQR, descreve melhor "
            f"o comportamento usual. Em contrapartida, variáveis "
            f"aproximadamente simétricas toleram bem a média: "
            f"{_descreve(melhores[0])} é um exemplo, com diferença "
            f"desprezível entre as duas medidas. A recomendação prática é "
            f"relatar sempre as duas, porque elas respondem a perguntas "
            f"diferentes: a média é a única compatível com o total "
            f"(média × número de turnos reconstrói a produção acumulada, o "
            f"que a torna indispensável para planejamento de capacidade), "
            f"enquanto a mediana responde ao que esperar de um turno comum. "
            f"Uma observação metodológica reforça o ponto: na produção, "
            f"parte da assimetria não é do processo, mas do mix de produtos, "
            f"já que Micro-ondas rende cerca de 300 unidades por turno e "
            f"Geladeira cerca de 130; por isso a comparação entre produtos "
            f"deve usar produtividade por hora efetiva ou produção relativa, "
            f"onde a distribuição é bem mais simétrica."
        ),
        "evidencias": [
            "Maiores divergências entre média e mediana: "
            + "; ".join(_descreve(c) for c in piores),
            "Variáveis em que a média é adequada: "
            + "; ".join(_descreve(c) for c in melhores),
            f"{len(assimetricas)} das {len(descritivas)} variáveis têm "
            f"assimetria |a| >= 0,80: "
            + ", ".join(
                f"{c['rotulo']} ({_fmt(c['assimetria'], 2)})"
                for c in assimetricas
            )
            + ". Nessas, a média isolada não descreve o turno típico, "
            "porque é deslocada pela cauda da distribuição.",
            "A produção relativa, que normaliza cada registro pela média do "
            "próprio produto, tem média "
            f"{_fmt(descritivas['producao_relativa']['media'], 3)} e mediana "
            f"{_fmt(descritivas['producao_relativa']['mediana'], 3)} "
            f"(assimetria "
            f"{_fmt(descritivas['producao_relativa']['assimetria'], 2)}): "
            "removido o efeito de ritmo de fabricação, média e mediana "
            "praticamente coincidem."
            if "producao_relativa" in descritivas
            else "Produção relativa não disponível nesta carga.",
        ],
        "grafico": "dist-unidades-produzidas",
    }


def _questoes(
    df: pd.DataFrame,
    descritivas: dict,
    por_produto: list[dict],
    por_turno: list[dict],
    por_linha: list[dict],
    por_manutencao: list[dict],
    outliers: dict,
) -> list[dict]:
    """As seis questões investigativas do enunciado, na ordem pedida."""
    return [
        _questao_1(df, por_produto),
        _questao_2(df, por_turno),
        _questao_3(df, por_linha),
        _questao_4(df, por_manutencao),
        _questao_5(outliers),
        _questao_6(descritivas),
    ]


# -------------------------------------------------------------- parecer ---
def _parecer(
    df: pd.DataFrame,
    meta: dict,
    descritivas: dict,
    por_produto: list[dict],
    por_turno: list[dict],
    por_linha: list[dict],
    por_manutencao: list[dict],
    kpis: list[dict],
    correlacoes: dict,
    outliers: dict,
) -> dict:
    """Parecer técnico: síntese, evidências, limitações e recomendações."""
    taxa_global = est.taxa_defeitos_agregada(df)
    produtividade_global = est.produtividade_agregada(df)
    parada = descritivas["horas_parada_maquina"]
    producao = descritivas["unidades_produzidas"]
    planejadas = est.numero(df["horas_planejadas"].sum()) or 0.0
    parada_relativa = est.razao(parada["soma"], planejadas)

    pior_linha = _maior(por_linha, "taxa_defeitos")
    melhor_linha = _menor(por_linha, "taxa_defeitos")
    top_produtividade = _maior(por_produto, "produtividade_media")
    menor_produtividade = _menor(por_produto, "produtividade_media")
    pior_produto_taxa = _maior(por_produto, "taxa_defeitos")
    corretiva = next(
        (x for x in por_manutencao if x["tipo_manutencao"] == "Corretiva"), {}
    )
    nenhuma = next(
        (x for x in por_manutencao if x["tipo_manutencao"] == "Nenhuma"), {}
    )
    prazo = next((k for k in kpis if k["id"] == "entregas-prazo"), {})
    residuo = descritivas["residuo_kg"]
    faltantes_medicao = _faltantes_medicao(meta)
    menor_n = min(d["n"] for d in descritivas.values())

    par_parada_prazo = next(
        (
            d
            for d in correlacoes["destaques"]
            if {d["x"], d["y"]} == {"horas_parada_maquina", "entregas_no_prazo_pct"}
        ),
        None,
    )
    r_parada_prazo = (
        par_parada_prazo["r"]
        if par_parada_prazo
        else est.arredondar(
            est.correlacoes(
                df, ["horas_parada_maquina", "entregas_no_prazo_pct"]
            ).iloc[0, 1],
            4,
        )
    )

    sintese = (
        f"A base reúne {meta['n_registros']} registros de produção em "
        f"{meta['n_meses']} meses ({meta['periodo_inicio']:%d/%m/%Y} a "
        f"{meta['periodo_fim']:%d/%m/%Y}), com "
        f"{_fmt_int(df['unidades_produzidas'].sum())} unidades produzidas, "
        f"produtividade global de {_fmt(produtividade_global, 2)} un/h e "
        f"taxa de defeitos agregada de {_fmt_pct(taxa_global, 2)}. O "
        f"processo é estável no nível agregado, mas desigual entre linhas: a "
        f"{pior_linha.get('linha_producao')} reprova "
        f"{_fmt_pct(pior_linha.get('taxa_defeitos'), 2)} da produção contra "
        f"{_fmt_pct(melhor_linha.get('taxa_defeitos'), 2)} da "
        f"{melhor_linha.get('linha_producao')}, e é também a de menor "
        f"produtividade e maior consumo unitário de energia. As paradas de "
        f"máquina consomem {_fmt_pct(parada_relativa, 2)} da capacidade "
        f"planejada ({_fmt(parada['soma'], 1)} h de "
        f"{_fmt(planejadas, 1)} h) e concentram-se nos registros de "
        f"manutenção corretiva, que param "
        f"{_fmt(corretiva.get('parada_media'), 2)} h por turno contra "
        f"{_fmt(nenhuma.get('parada_media'), 2)} h dos demais. Toda "
        f"comparação entre produtos neste relatório é apresentada em "
        f"produtividade por hora efetiva e em produção relativa, porque os "
        f"ritmos de fabricação são muito diferentes "
        f"({top_produtividade.get('produto')} "
        f"{_fmt(top_produtividade.get('produtividade_media'), 1)} un/h "
        f"contra {menor_produtividade.get('produto')} "
        f"{_fmt(menor_produtividade.get('produtividade_media'), 1)} un/h) e "
        f"a quantidade absoluta mediria o produto, não a operação. "
        f"Finalmente, {outliers['n']} registros "
        f"({_fmt_pct(outliers['pct'], 2)}) apresentam consumo de energia "
        f"fora dos limites de Tukey, em padrão concentrado por produto, o "
        f"que recomenda investigação técnica antes de qualquer meta de "
        f"eficiência energética."
    )

    evidencias = [
        {
            "titulo": "Qualidade desigual entre linhas",
            "texto": (
                f"A taxa de defeitos agregada da fábrica é "
                f"{_fmt_pct(taxa_global, 2)} "
                f"({_fmt_int(df['unidades_defeituosas'].sum())} unidades "
                f"reprovadas em "
                f"{_fmt_int(df['unidades_produzidas'].sum())} produzidas). "
                f"Entre as linhas, varia de "
                f"{_fmt_pct(melhor_linha.get('taxa_defeitos'), 2)} "
                f"({melhor_linha.get('linha_producao')}) a "
                f"{_fmt_pct(pior_linha.get('taxa_defeitos'), 2)} "
                f"({pior_linha.get('linha_producao')}), razão de "
                f"{_fmt(est.razao(pior_linha.get('taxa_defeitos'), melhor_linha.get('taxa_defeitos')), 2)} "
                f"entre as duas. Por produto, o maior índice é do "
                f"{pior_produto_taxa.get('produto')}, com "
                f"{_fmt_pct(pior_produto_taxa.get('taxa_defeitos'), 2)}."
            ),
        },
        {
            "titulo": "Parada de máquina é o gargalo de capacidade",
            "texto": (
                f"As paradas somam {_fmt(parada['soma'], 2)} h, ou "
                f"{_fmt_pct(parada_relativa, 2)} das "
                f"{_fmt(planejadas, 1)} h planejadas. A média por turno é "
                f"{_fmt(parada['media'], 3)} h e a mediana "
                f"{_fmt(parada['mediana'], 2)} h, com assimetria de "
                f"{_fmt(parada['assimetria'], 2)} e "
                f"{parada['n_outliers']} turnos acima do limite de Tukey de "
                f"{_fmt(parada['lim_sup'], 2)} h — a perda está concentrada "
                f"em poucos eventos longos, até {_fmt(parada['maximo'], 2)} h."
            ),
        },
        {
            "titulo": "Manutenção corretiva custa mais que o dobro em parada",
            "texto": (
                f"Registros com manutenção Corretiva param "
                f"{_fmt(corretiva.get('parada_media'), 2)} h por turno, "
                f"contra {_fmt(nenhuma.get('parada_media'), 2)} h dos "
                f"registros sem manutenção, razão de "
                f"{_fmt(est.razao(corretiva.get('parada_media'), nenhuma.get('parada_media')), 2)} "
                f"vezes, em apenas {corretiva.get('n')} de "
                f"{meta['n_registros']} registros "
                f"({_fmt_pct(corretiva.get('pct_registros'), 1)}). Nesses "
                f"turnos as entregas no prazo caem para "
                f"{_fmt(corretiva.get('entregas_prazo'), 2)}%, contra "
                f"{_fmt(nenhuma.get('entregas_prazo'), 2)}% nos demais."
            ),
        },
        {
            "titulo": "Ritmos de fabricação impedem comparação direta de volume",
            "texto": (
                f"A produção média por registro vai de "
                f"{_fmt(_menor(por_produto, 'unidades_media').get('unidades_media'), 1)} un "
                f"({_menor(por_produto, 'unidades_media').get('produto')}) a "
                f"{_fmt(_maior(por_produto, 'unidades_media').get('unidades_media'), 1)} un "
                f"({_maior(por_produto, 'unidades_media').get('produto')}), "
                f"razão de "
                f"{_fmt(est.razao(_maior(por_produto, 'unidades_media').get('unidades_media'), _menor(por_produto, 'unidades_media').get('unidades_media')), 2)} "
                f"vezes. A produção relativa média, porém, fica em torno de "
                f"1,00 nos quatro produtos, confirmando que a diferença é de "
                f"ritmo e não de desempenho. Qualquer ranking de produtos "
                f"deve usar produtividade por hora efetiva: "
                + "; ".join(
                    f"{x['produto']} {_fmt(x['produtividade_media'], 1)} un/h"
                    for x in sorted(
                        por_produto,
                        key=lambda x: x["produtividade_media"] or 0,
                        reverse=True,
                    )
                )
                + "."
            ),
        },
        {
            "titulo": "Disponibilidade explica o cumprimento de prazo",
            "texto": (
                f"A correlação entre horas de parada e percentual de "
                f"entregas no prazo é r = {_fmt(r_parada_prazo, 3)}, "
                f"classificada como {est.forca_correlacao(r_parada_prazo)}. "
                f"O nível médio de pontualidade é "
                f"{_fmt(prazo.get('valor'), 2)}%, com "
                f"{descritivas['entregas_no_prazo_pct']['n_outliers']} "
                f"registros abaixo do limite inferior de Tukey de "
                f"{_fmt(descritivas['entregas_no_prazo_pct']['lim_inf'], 2)}%. "
                f"A associação é estatística e não prova causalidade, mas é "
                f"consistente com o mecanismo operacional."
            ),
        },
        {
            "titulo": "Energia tem atípicos concentrados por produto",
            "texto": (
                f"{outliers['n']} dos {outliers['n_avaliados']} registros "
                f"com energia informada ({_fmt_pct(outliers['pct'], 2)}) "
                f"estão fora da faixa de {_fmt(outliers['lim_inf'], 2)} a "
                f"{_fmt(outliers['lim_sup'], 2)} kWh: "
                f"{outliers['n_acima']} acima, todos de Ar-condicionado, e "
                f"{outliers['n_abaixo']} abaixo, todos de Micro-ondas. "
                f"{outliers['coerencia_coluna_atipico']}"
            ),
        },
        {
            "titulo": "Defeito e resíduo compartilham a mesma causa aparente",
            "texto": (
                f"O resíduo total é {_fmt(residuo['soma'], 1)} kg, média de "
                f"{_fmt(residuo['media'], 2)} kg por turno e mediana de "
                f"{_fmt(residuo['mediana'], 2)} kg. A correlação entre taxa "
                f"de defeitos e resíduo em quilos é r = "
                f"{_fmt(est.correlacoes(df, ['taxa_defeitos', 'residuo_kg']).iloc[0, 1], 3)}, "
                f"o que indica que reprovação de unidade e descarte de "
                f"material medem a mesma perda de processo."
            ),
        },
    ]

    # Contagem de registros por mês: o último mês da janela é parcial e
    # aparece como extremo em séries mensais só por efeito de tamanho de
    # amostra. A limitação correspondente precisa dos números reais.
    _por_mes = df[config.COL_DATA].dropna().dt.to_period("M").value_counts()
    _por_mes = _por_mes.sort_index()
    _mes_final_n = int(_por_mes.iloc[-1]) if len(_por_mes) else 0
    _mes_final_rotulo = (
        f"{_por_mes.index[-1].month:02d}/{_por_mes.index[-1].year}"
        if len(_por_mes)
        else "—"
    )
    _mes_tipico_n = (
        int(_por_mes.iloc[:-1].median()) if len(_por_mes) > 1 else _mes_final_n
    )

    limitacoes = [
        (
            "A base é um exercício acadêmico com dados fictícios da "
            "EletroTech. Os valores servem para demonstrar o método "
            "estatístico; nenhuma conclusão deve ser transportada para uma "
            "operação real sem nova coleta."
        ),
        (
            "Trata-se de um estudo observacional. Todas as associações "
            "apresentadas, inclusive as muito fortes como a de parada de "
            f"máquina com entregas no prazo (r = {_fmt(r_parada_prazo, 3)}), "
            "são correlações e não relações de causa e efeito; não houve "
            "experimento nem controle de variáveis de confusão."
        ),
        (
            f"Há {sum(faltantes_medicao.values())} células sem medição, "
            f"distribuídas em {len(faltantes_medicao)} variáveis ("
            + ", ".join(
                f"{_rotulo(col)} {qtd}" for col, qtd in faltantes_medicao.items()
            )
            + "). O tratamento foi por exclusão caso a caso, o que faz o n "
            f"variar entre medidas (de {menor_n} a {meta['n_registros']} "
            "observações). Além dessas, a coluna ordem_atipico está vazia em "
            f"{meta['faltantes'].get('ordem_atipico', 0)} registros por "
            f"construção — ela só numera os "
            f"{meta['n_registros'] - meta['faltantes'].get('ordem_atipico', 0)} "
            "turnos atípicos de energia — e por isso não entra na análise "
            "descritiva."
        ),
        (
            f"O período coberto é de {meta['n_meses']} meses "
            f"({meta['periodo_inicio']:%d/%m/%Y} a "
            f"{meta['periodo_fim']:%d/%m/%Y}), suficiente para descrever "
            "sazonalidade aproximada, mas curto para separar tendência de "
            "ciclo. Séries mensais chegam a ter poucos registros por produto "
            "em alguns meses, o que torna instáveis as médias mensais "
            "desagregadas."
        ),
        (
            "O último mês da janela observada "
            f"({_mes_final_rotulo}) tem apenas {_mes_final_n} "
            f"{'registro' if _mes_final_n == 1 else 'registros'}, contra "
            f"{_mes_tipico_n} nos meses completos: é um mês parcial. Ele "
            "aparece como extremo em algumas séries mensais (menor produção "
            "total e maior taxa de defeitos) apenas por efeito do tamanho da "
            "amostra, e não deve ser comparado aos demais nem usado para "
            "afirmar tendência de fim de período."
        ),
        (
            "Os registros não estão distribuídos de forma equilibrada entre "
            "os estratos: por produto vão de "
            f"{_menor(por_produto, 'n').get('n')} "
            f"({_menor(por_produto, 'n').get('produto')}) a "
            f"{_maior(por_produto, 'n').get('n')} "
            f"({_maior(por_produto, 'n').get('produto')}) e, por linha, de "
            f"{_menor(por_linha, 'n').get('n')} a "
            f"{_maior(por_linha, 'n').get('n')}. Comparações entre grupos "
            "pequenos têm erro-padrão maior e devem ser lidas com cautela. "
            "Somado a isso, não se aplicaram testes de hipótese nem controle "
            "de múltiplas comparações: os intervalos de confiança de 95% "
            "usam a aproximação normal e pressupõem amostra aleatória, "
            "hipótese que a técnica de coleta não garante."
        ),
        (
            "A base não traz custo, preço, margem, consumo de insumos nem "
            "horas de mão de obra. Sem isso, não é possível converter horas "
            "de parada, defeitos ou quilowatt-hora em impacto financeiro, "
            "nem calcular indicadores como OEE completo ou custo da má "
            "qualidade."
        ),
        (
            "Os indicadores derivados (taxa de defeitos, produtividade por "
            "hora, energia por unidade, produção relativa) já vêm calculados "
            "no arquivo e foram reproduzidos e conferidos, mas compartilham "
            "numeradores e denominadores com as variáveis de origem. Isso "
            "infla artificialmente algumas correlações, e os pares afetados "
            "estão sinalizados como construtivos na seção de relações."
        ),
    ]

    recomendacoes = [
        {
            "titulo": f"Auditar o processo da {pior_linha.get('linha_producao')}",
            "texto": (
                f"A {pior_linha.get('linha_producao')} concentra a maior "
                f"taxa de defeitos ({_fmt_pct(pior_linha.get('taxa_defeitos'), 2)} "
                f"contra {_fmt_pct(taxa_global, 2)} da fábrica), a menor "
                f"produtividade ({_fmt(pior_linha.get('produtividade_media'), 2)} un/h) "
                f"e o maior consumo unitário de energia "
                f"({_fmt(pior_linha.get('energia_por_unidade'), 3)} kWh/un). "
                f"Trazê-la ao nível da {melhor_linha.get('linha_producao')} "
                f"({_fmt_pct(melhor_linha.get('taxa_defeitos'), 2)}) "
                f"evitaria cerca de "
                f"{_fmt_int((pior_linha.get('taxa_defeitos', 0) - melhor_linha.get('taxa_defeitos', 0)) * (pior_linha.get('unidades_total') or 0))} "
                f"unidades reprovadas no mesmo volume produzido."
            ),
            "prioridade": "alta",
            "indicador": "taxa de defeitos por linha (razão agregada)",
        },
        {
            "titulo": "Deslocar manutenção corretiva para preventiva",
            "texto": (
                f"Os {corretiva.get('n')} registros com manutenção corretiva "
                f"param {_fmt(corretiva.get('parada_media'), 2)} h por "
                f"turno, contra {_fmt(nenhuma.get('parada_media'), 2)} h dos "
                f"registros sem manutenção. Como as paradas já consomem "
                f"{_fmt_pct(parada_relativa, 2)} da capacidade planejada, "
                f"antecipar a intervenção nos equipamentos de maior idade "
                f"(a idade média das máquinas é "
                f"{_fmt(descritivas['idade_maquina_anos']['media'], 1)} anos, "
                f"chegando a "
                f"{_fmt(descritivas['idade_maquina_anos']['maximo'], 0)}) "
                f"tende a recuperar horas efetivas sem investimento em "
                f"capacidade nova."
            ),
            "prioridade": "alta",
            "indicador": "horas de parada por turno e participação da corretiva",
        },
        {
            "titulo": "Investigar os registros atípicos de energia",
            "texto": (
                f"Os {outliers['n']} registros fora da faixa de "
                f"{_fmt(outliers['lim_inf'], 2)} a "
                f"{_fmt(outliers['lim_sup'], 2)} kWh devem ser verificados "
                f"individualmente antes de qualquer meta de eficiência: "
                f"{outliers['n_acima']} são consumos muito altos de "
                f"Ar-condicionado e {outliers['n_abaixo']} são consumos "
                f"muito baixos de Micro-ondas. A concentração por produto "
                f"sugere desvio de ajuste de equipamento ou falha de "
                f"medição, hipóteses que só o chão de fábrica pode separar."
            ),
            "prioridade": "alta",
            "indicador": "registros de energia fora dos limites de Tukey",
        },
        {
            "titulo": "Padronizar o indicador de comparação entre produtos",
            "texto": (
                f"Relatórios gerenciais devem abandonar a comparação por "
                f"quantidade absoluta, que varia "
                f"{_fmt(est.razao(_maior(por_produto, 'unidades_media').get('unidades_media'), _menor(por_produto, 'unidades_media').get('unidades_media')), 2)} "
                f"vezes entre "
                f"{_maior(por_produto, 'unidades_media').get('produto')} e "
                f"{_menor(por_produto, 'unidades_media').get('produto')} "
                f"apenas por diferença de ritmo de fabricação. A "
                f"produtividade por hora efetiva e a produção relativa "
                f"devem constar ao lado de todo volume publicado, para "
                f"evitar que um produto de lote grande pareça mais eficiente "
                f"do que é."
            ),
            "prioridade": "alta",
            "indicador": "produtividade por hora efetiva e produção relativa",
        },
        {
            "titulo": "Monitorar defeito e resíduo como um único indicador de perda",
            "texto": (
                f"A correlação entre taxa de defeitos e resíduo em quilos é "
                f"r = "
                f"{_fmt(est.correlacoes(df, ['taxa_defeitos', 'residuo_kg']).iloc[0, 1], 3)}, "
                f"e o resíduo acumulado chega a "
                f"{_fmt(residuo['soma'], 1)} kg "
                f"({_fmt(est.razao(residuo['soma'], df['unidades_produzidas'].sum()), 4)} kg "
                f"por unidade produzida). Um painel único de perda de "
                f"processo, somando unidades reprovadas e material "
                f"descartado, evita contabilizar duas vezes a mesma causa e "
                f"facilita priorizar ações."
            ),
            "prioridade": "media",
            "indicador": "taxa de defeitos e resíduo por unidade produzida",
        },
        {
            "titulo": "Reportar média e mediana juntas nos indicadores assimétricos",
            "texto": (
                f"Variáveis como horas de parada (média "
                f"{_fmt(parada['media'], 3)} h contra mediana "
                f"{_fmt(parada['mediana'], 2)} h, assimetria "
                f"{_fmt(parada['assimetria'], 2)}) e unidades produzidas "
                f"(média {_fmt(producao['media'], 1)} un contra mediana "
                f"{_fmt(producao['mediana'], 1)} un) têm cauda longa. "
                f"Publicar apenas a média sugere um turno típico que não "
                f"existe; a prática recomendada é apresentar média, mediana "
                f"e IQR na mesma linha do painel."
            ),
            "prioridade": "media",
            "indicador": "média, mediana e IQR das variáveis de assimetria alta",
        },
        {
            "titulo": "Completar e enriquecer a base de coleta",
            "texto": (
                f"Duas lacunas limitam a próxima rodada de análise. A "
                f"primeira são as {sum(faltantes_medicao.values())} células "
                f"sem medição, concentradas em "
                + ", ".join(
                    f"{_rotulo(col)} ({qtd})"
                    for col, qtd in faltantes_medicao.items()
                )
                + ": são poucos registros, mas afetam justamente energia e "
                "temperatura, e a coleta automática eliminaria a exclusão "
                "caso a caso. A segunda é a ausência de valores monetários: "
                f"com {_fmt(parada['soma'], 1)} h de parada, "
                f"{_fmt_int(df['unidades_defeituosas'].sum())} unidades "
                f"reprovadas e "
                f"{_fmt_int(df['consumo_energia_kwh'].sum())} kWh "
                f"consumidos no período, acrescentar custo de hora parada, "
                f"custo da má qualidade e tarifa de energia permitiria "
                f"hierarquizar por retorno financeiro todas as "
                f"recomendações acima."
            ),
            "prioridade": "baixa",
            "indicador": (
                "percentual de preenchimento por variável e custo por hora "
                "parada, por unidade reprovada e por kWh"
            ),
        },
    ]

    return {
        "sintese": sintese,
        "evidencias": evidencias,
        "limitacoes": limitacoes,
        "recomendacoes": recomendacoes,
    }


# ------------------------------------------------------------ glossário ---
def _glossario(df: pd.DataFrame) -> list[dict]:
    """Glossário das 25 variáveis, com descrição, tipo e unidade."""
    itens = []
    for coluna in df.columns:
        descricao, tipo = GLOSSARIO_BASE.get(
            coluna, ("Variável não documentada no enunciado.", "Não classificada")
        )
        itens.append(
            {
                "variavel": coluna,
                "rotulo": _rotulo(coluna),
                "descricao": descricao,
                "tipo": tipo,
                "unidade": _unidade(coluna),
            }
        )
    return itens


# -------------------------------------------------------------- entrada ---
def analisar(df: pd.DataFrame) -> dict:
    """Produz o dicionário completo de análise usado pelo relatório.

    Parâmetros
    ----------
    df:
        DataFrame limpo devolvido por :func:`relatorio.dados.carregar`.

    Retorno
    -------
    dict
        Estrutura com as chaves ``meta``, ``populacao``, ``descritivas``,
        ``por_produto``, ``por_turno``, ``por_linha``, ``por_manutencao``,
        ``kpis``, ``correlacoes``, ``outliers_energia``, ``questoes``,
        ``parecer`` e ``glossario``.
    """
    meta = _meta(df)
    populacao = _populacao(df, meta)
    descritivas = _descritivas(df)

    por_produto = _recorte(df, "produto")
    por_turno = _recorte(df, "turno")
    por_linha = _recorte(df, "linha_producao")
    por_manutencao = _recorte(df, "tipo_manutencao")

    kpis = _kpis(df)
    correlacoes = _correlacoes(df)
    outliers = _outliers_energia(df)

    questoes = _questoes(
        df,
        descritivas,
        por_produto,
        por_turno,
        por_linha,
        por_manutencao,
        outliers,
    )
    parecer = _parecer(
        df,
        meta,
        descritivas,
        por_produto,
        por_turno,
        por_linha,
        por_manutencao,
        kpis,
        correlacoes,
        outliers,
    )

    return {
        "meta": meta,
        "populacao": populacao,
        "descritivas": descritivas,
        "por_produto": por_produto,
        "por_turno": por_turno,
        "por_linha": por_linha,
        "por_manutencao": por_manutencao,
        "kpis": kpis,
        "correlacoes": correlacoes,
        "outliers_energia": outliers,
        "questoes": questoes,
        "parecer": parecer,
        "glossario": _glossario(df),
    }
