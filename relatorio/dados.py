"""Leitura e limpeza do CSV de produção.

Centraliza toda a conversão do formato brasileiro (decimal com vírgula,
datas dd/mm/aaaa, percentuais com "%") para tipos numéricos do pandas.
O resto do projeto consome apenas o DataFrame já limpo devolvido por
:func:`carregar`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config


def localizar_csv(caminho: Path | str | None = None) -> Path:
    """Devolve o caminho do CSV de produção.

    Usa ``config.ARQUIVO_CSV`` e, se o nome tiver mudado, cai para o
    primeiro ``.csv`` encontrado na pasta ``csv/``.
    """
    if caminho is not None:
        arquivo = Path(caminho)
        if not arquivo.exists():
            raise FileNotFoundError(f"CSV não encontrado: {arquivo}")
        return arquivo

    if config.ARQUIVO_CSV.exists():
        return config.ARQUIVO_CSV

    candidatos = sorted(config.DIR_CSV.glob("*.csv"))
    if not candidatos:
        raise FileNotFoundError(
            f"Nenhum arquivo .csv encontrado em {config.DIR_CSV}"
        )
    return candidatos[0]


def _para_numero(serie: pd.Series) -> pd.Series:
    """Converte texto no formato brasileiro ("1.234,56") para float."""
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors="coerce")

    texto = (
        serie.astype("string")
        .str.strip()
        .str.replace(".", "", regex=False)    # separador de milhar
        .str.replace(",", ".", regex=False)   # separador decimal
        .replace({"": None, "-": None})
    )
    return pd.to_numeric(texto, errors="coerce")


def _para_fracao(serie: pd.Series) -> pd.Series:
    """Converte texto percentual ("4,08%") para fração decimal (0.0408)."""
    texto = serie.astype("string").str.strip().str.replace("%", "", regex=False)
    return _para_numero(texto) / 100.0


def carregar(caminho: Path | str | None = None) -> pd.DataFrame:
    """Lê o CSV e devolve um DataFrame com os tipos já convertidos."""
    arquivo = localizar_csv(caminho)

    df = pd.read_csv(
        arquivo,
        sep=config.CSV_SEPARADOR,
        encoding=config.CSV_ENCODING,
        dtype="string",
        keep_default_na=True,
    )
    df.columns = [c.strip() for c in df.columns]

    # Datas
    if config.COL_DATA in df.columns:
        df[config.COL_DATA] = pd.to_datetime(
            df[config.COL_DATA], format=config.FORMATO_DATA, errors="coerce"
        )

    # Numéricos
    for coluna in config.COLUNAS_NUMERICAS:
        if coluna in df.columns:
            df[coluna] = _para_numero(df[coluna])

    # Percentuais -> fração
    for coluna in config.COLUNAS_PERCENTUAIS:
        if coluna in df.columns:
            df[coluna] = _para_fracao(df[coluna])

    # Categóricas
    for coluna in config.COLUNAS_CATEGORICAS:
        if coluna in df.columns:
            df[coluna] = (
                df[coluna].astype("string").str.strip().astype("category")
            )

    return df


def resumo_carga(df: pd.DataFrame) -> dict:
    """Metadados básicos da carga, úteis para o cabeçalho do relatório."""
    faltantes = df.isna().sum()
    return {
        "linhas": int(len(df)),
        "colunas": int(df.shape[1]),
        "periodo_inicio": (
            df[config.COL_DATA].min() if config.COL_DATA in df else None
        ),
        "periodo_fim": (
            df[config.COL_DATA].max() if config.COL_DATA in df else None
        ),
        "colunas_com_faltantes": {
            str(coluna): int(qtd) for coluna, qtd in faltantes.items() if qtd > 0
        },
        "total_faltantes": int(faltantes.sum()),
    }
