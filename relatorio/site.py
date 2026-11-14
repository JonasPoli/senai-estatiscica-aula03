"""Montagem do contexto e renderização do site estático.

Fluxo: ``dados.carregar`` -> ``analise.analisar`` -> ``graficos.construir_graficos``
-> ``construir_contexto`` -> template Jinja2 -> ``dist/index.html`` + cópia de
``static/``.
"""

from __future__ import annotations

import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from . import analise as mod_analise
from . import config, dados, formato, graficos


def criar_ambiente() -> Environment:
    """Ambiente Jinja2 com autoescape e filtros pt-BR registrados."""
    env = Environment(
        loader=FileSystemLoader(config.DIR_TEMPLATES),
        autoescape=select_autoescape(["html", "xml"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters.update(formato.FILTROS)
    return env


def ler_codigo() -> list[dict]:
    """Lê os arquivos-fonte exibidos na seção "Código Python"."""
    blocos = []
    for caminho_rel, descricao in config.ARQUIVOS_CODIGO:
        arquivo = config.RAIZ / caminho_rel
        if not arquivo.exists():
            continue
        fonte = arquivo.read_text(encoding="utf-8")
        blocos.append(
            {
                "arquivo": caminho_rel,
                "descricao": descricao,
                "linguagem": "python",
                "fonte": fonte,
                "linhas": fonte.count("\n") + 1,
            }
        )
    return blocos


def agrupar_graficos(lista: list[dict]) -> dict[str, list[dict]]:
    """Indexa os gráficos por seção, preservando a ordem de construção."""
    por_secao: dict[str, list[dict]] = defaultdict(list)
    for grafico in lista:
        por_secao[grafico.get("secao", "visao-geral")].append(grafico)
    return dict(por_secao)


def construir_contexto(df: pd.DataFrame) -> dict:
    """Monta o dicionário entregue ao template."""
    resultado = mod_analise.analisar(df)
    lista_graficos = graficos.construir_graficos(df, resultado)
    por_secao = agrupar_graficos(lista_graficos)
    blocos_codigo = ler_codigo()

    meta_js = {
        "paleta": config.PALETA,
        "cores_entidade": config.CORES_ENTIDADE,
        "n_registros": resultado["meta"]["n_registros"],
        "n_graficos": len(lista_graficos),
    }

    return {
        "titulo": config.TITULO_SITE,
        "subtitulo": config.SUBTITULO_SITE,
        "instituicao": config.INSTITUICAO,
        "gerado_em": datetime.now(),
        "rotulos": config.ROTULOS,
        "unidades": config.UNIDADES,
        "paleta": config.PALETA,
        "analise": resultado,
        "resumo": resultado["meta"],
        "graficos": lista_graficos,
        "graficos_por_secao": por_secao,
        "secoes": config.SECOES,
        "codigo": blocos_codigo,
        "dados_graficos": graficos.para_json(lista_graficos),
        "dados_meta": graficos.para_json(meta_js),
    }


def copiar_estaticos(destino: Path) -> None:
    """Copia ``static/`` para a pasta de saída, sobrescrevendo o que existir.

    A pasta do projeto fica dentro do OneDrive, que mantém arquivos e
    diretórios bloqueados enquanto sincroniza. Por isso a cópia nunca apaga
    a pasta de destino: sobrescreve arquivo por arquivo e, se um arquivo
    específico estiver travado, segue adiante avisando em vez de abortar
    a geração inteira.
    """
    if not config.DIR_STATIC.exists():
        return

    alvo = destino / "static"
    try:
        shutil.copytree(config.DIR_STATIC, alvo, dirs_exist_ok=True)
        return
    except (PermissionError, OSError):
        pass

    # Segunda tentativa, arquivo por arquivo, tolerando bloqueios pontuais.
    travados = []
    for origem in config.DIR_STATIC.rglob("*"):
        if origem.is_dir():
            continue
        copia = alvo / origem.relative_to(config.DIR_STATIC)
        copia.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(origem, copia)
        except (PermissionError, OSError):
            travados.append(str(copia.relative_to(destino)))

    if travados:
        print(
            "Aviso: não foi possível atualizar "
            f"{len(travados)} arquivo(s) estático(s) (bloqueados pelo "
            f"OneDrive ou pelo navegador): {', '.join(travados)}"
        )


def gerar(
    caminho_csv: Path | str | None = None,
    saida: Path | str | None = None,
) -> Path:
    """Gera o site e devolve o caminho do HTML produzido."""
    arquivo_saida = Path(saida) if saida else config.ARQUIVO_SAIDA
    arquivo_saida.parent.mkdir(parents=True, exist_ok=True)

    df = dados.carregar(caminho_csv)
    contexto = construir_contexto(df)

    env = criar_ambiente()
    html = env.get_template("index.html").render(**contexto)

    arquivo_saida.write_text(html, encoding="utf-8")
    copiar_estaticos(arquivo_saida.parent)
    return arquivo_saida
