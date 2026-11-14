"""Filtros de formatação no padrão brasileiro para os templates Jinja2."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd


def numero(valor: Any, casas: int = 2) -> str:
    """Formata número no padrão pt-BR: 1.234,56."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "—"
    try:
        texto = f"{float(valor):,.{casas}f}"
    except (TypeError, ValueError):
        return str(valor)
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def inteiro(valor: Any) -> str:
    """Formata inteiro com separador de milhar: 1.234."""
    return numero(valor, casas=0)


def percentual(valor: Any, casas: int = 1, fracao: bool = True) -> str:
    """Formata percentual. Com ``fracao=True``, 0.0408 -> "4,1%"."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "—"
    try:
        v = float(valor) * (100.0 if fracao else 1.0)
    except (TypeError, ValueError):
        return str(valor)
    return f"{numero(v, casas)}%"


def data(valor: Any, formato: str = "%d/%m/%Y") -> str:
    """Formata data/timestamp em dd/mm/aaaa."""
    if valor is None or valor is pd.NaT:
        return "—"
    if isinstance(valor, (datetime, date, pd.Timestamp)):
        return valor.strftime(formato)
    return str(valor)


#: Filtros registrados no ambiente Jinja2 por :mod:`relatorio.site`.
FILTROS = {
    "num": numero,
    "int_br": inteiro,
    "pct": percentual,
    "data_br": data,
}
