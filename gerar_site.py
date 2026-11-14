#!/usr/bin/env python
"""Atalho de execução: ``python gerar_site.py [--servir]``.

Equivalente a ``python -m relatorio``.
"""

from __future__ import annotations

from relatorio.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
