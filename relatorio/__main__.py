"""Permite executar o gerador com ``python -m relatorio``."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
