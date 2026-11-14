"""Linha de comando do gerador do relatório."""

from __future__ import annotations

import argparse
import http.server
import socketserver
import webbrowser
from functools import partial
from pathlib import Path

from . import __version__, config, site


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="relatorio",
        description="Gera o relatório estatístico one-page da EletroTech.",
    )
    parser.add_argument(
        "--csv",
        metavar="ARQUIVO",
        default=None,
        help="caminho do CSV de produção (padrão: pasta csv/)",
    )
    parser.add_argument(
        "--saida",
        metavar="ARQUIVO",
        default=None,
        help=f"HTML de saída (padrão: {config.ARQUIVO_SAIDA.name} em dist/)",
    )
    parser.add_argument(
        "--servir",
        action="store_true",
        help="após gerar, sobe um servidor local e abre o navegador",
    )
    parser.add_argument(
        "--porta",
        type=int,
        default=8000,
        help="porta do servidor local (padrão: 8000)",
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def servir(pasta: Path, porta: int) -> None:
    """Sobe um servidor estático simples na pasta de saída."""
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(pasta))
    with socketserver.TCPServer(("127.0.0.1", porta), handler) as servidor:
        url = f"http://127.0.0.1:{porta}/"
        print(f"Servindo {pasta} em {url} (Ctrl+C para parar)")
        webbrowser.open(url)
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor encerrado.")


def main(argv: list[str] | None = None) -> int:
    args = criar_parser().parse_args(argv)

    arquivo = site.gerar(caminho_csv=args.csv, saida=args.saida)
    print(f"Relatório gerado: {arquivo}")

    if args.servir:
        servir(arquivo.parent, args.porta)
    return 0
