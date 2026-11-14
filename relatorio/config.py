"""Caminhos, constantes e metadados usados por todo o projeto."""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------- caminhos --
RAIZ = Path(__file__).resolve().parent.parent

DIR_CSV = RAIZ / "csv"
DIR_TEMPLATES = RAIZ / "templates"
DIR_STATIC = RAIZ / "static"
DIR_SAIDA = RAIZ / "dist"

ARQUIVO_CSV = (
    DIR_CSV
    / "EletroTech - Análise Estatística da Produção "
      "(com glossário de funções) - Página1.csv"
)

ARQUIVO_SAIDA = DIR_SAIDA / "index.html"

# -------------------------------------------------------------- metadados --
TITULO_SITE = "EletroTech — Análise Estatística da Produção"
SUBTITULO_SITE = "Relatório gerado a partir da base de produção da fábrica"
INSTITUICAO = "SENAI · Estatística · Aula 03"

# -------------------------------------------------------- leitura do CSV ---
# Formato brasileiro: campos separados por vírgula, decimal com vírgula
# (entre aspas no arquivo), datas dd/mm/aaaa e percentuais com "%".
CSV_SEPARADOR = ","
CSV_DECIMAL = ","
CSV_ENCODING = "utf-8"
FORMATO_DATA = "%d/%m/%Y"

# Colunas por natureza. Funciona como contrato: se o CSV mudar, muda aqui.
COL_ID = "id_registro"
COL_DATA = "data"

COLUNAS_CATEGORICAS = [
    "turno",
    "linha_producao",
    "produto",
    "tipo_manutencao",
    "atipico_energia",
]

COLUNAS_NUMERICAS = [
    "horas_planejadas",
    "horas_parada_maquina",
    "idade_maquina_anos",
    "temperatura_ambiente_c",
    "experiencia_operador_anos",
    "unidades_produzidas",
    "unidades_defeituosas",
    "consumo_energia_kwh",
    "residuo_kg",
    "devolucoes_clientes",
    "pedidos_recebidos",
    "entregas_no_prazo_pct",
    "horas_efetivas",
    "produtividade_hora",
    "energia_por_unidade",
    "producao_relativa",
    "ordem_atipico",
]

# Colunas gravadas como texto com "%" -> convertidas para fração 0–1.
COLUNAS_PERCENTUAIS = [
    "taxa_defeitos",
]

# Rótulos amigáveis para exibição no relatório.
ROTULOS = {
    "id_registro": "ID do registro",
    "data": "Data",
    "turno": "Turno",
    "linha_producao": "Linha de produção",
    "produto": "Produto",
    "horas_planejadas": "Horas planejadas",
    "horas_parada_maquina": "Horas de parada de máquina",
    "idade_maquina_anos": "Idade da máquina (anos)",
    "tipo_manutencao": "Tipo de manutenção",
    "temperatura_ambiente_c": "Temperatura ambiente (°C)",
    "experiencia_operador_anos": "Experiência do operador (anos)",
    "unidades_produzidas": "Unidades produzidas",
    "unidades_defeituosas": "Unidades defeituosas",
    "consumo_energia_kwh": "Consumo de energia (kWh)",
    "residuo_kg": "Resíduo (kg)",
    "devolucoes_clientes": "Devoluções de clientes",
    "pedidos_recebidos": "Pedidos recebidos",
    "entregas_no_prazo_pct": "Entregas no prazo (%)",
    "horas_efetivas": "Horas efetivas",
    "taxa_defeitos": "Taxa de defeitos",
    "produtividade_hora": "Produtividade por hora",
    "energia_por_unidade": "Energia por unidade",
    "producao_relativa": "Produção relativa",
    "atipico_energia": "Atípico de energia",
    "ordem_atipico": "Ordem do atípico",
}

# ------------------------------------------------- seções da página -------
# Ordem das seções da one-page. O id precisa casar com o <section id="...">
# do template; a navegação do topo é montada a partir desta lista.
SECOES = [
    {"id": "visao-geral", "titulo": "Visão geral"},
    {"id": "populacao", "titulo": "População e amostra"},
    {"id": "descritivas", "titulo": "Medidas descritivas"},
    {"id": "distribuicoes", "titulo": "Distribuições"},
    {"id": "temporal", "titulo": "Evolução no tempo"},
    {"id": "comparativos", "titulo": "Comparativos"},
    {"id": "qualidade", "titulo": "Qualidade"},
    {"id": "energia", "titulo": "Energia"},
    {"id": "relacoes", "titulo": "Relações"},
    {"id": "atipicos", "titulo": "Valores atípicos"},
    {"id": "questoes", "titulo": "Questões investigativas"},
    {"id": "parecer", "titulo": "Parecer técnico"},
    {"id": "codigo", "titulo": "Código Python"},
    {"id": "glossario", "titulo": "Glossário"},
]

# Arquivos-fonte exibidos na seção "Código Python" do relatório.
ARQUIVOS_CODIGO = [
    ("relatorio/config.py", "Configuração: caminhos, tipos das colunas e rótulos"),
    ("relatorio/dados.py", "Leitura do CSV e conversão do formato brasileiro"),
    ("relatorio/estatistica.py", "Funções estatísticas reutilizáveis"),
    ("relatorio/analise.py", "Análise completa e respostas às questões"),
    ("relatorio/graficos.py", "Preparação das séries dos gráficos"),
    ("relatorio/formato.py", "Formatação numérica em padrão brasileiro"),
    ("relatorio/site.py", "Montagem do contexto e renderização do relatório"),
    ("relatorio/cli.py", "Linha de comando do gerador"),
]

# Paleta validada (skill dataviz). Entregue ao JavaScript via JSON.
PALETA = {
    "claro": {
        "superficie": "#fcfcfb",
        "texto": "#0b0b0b",
        "texto_suave": "#52514e",
        "neutro": "#f0efec",
        "series": [
            "#2a78d6", "#eb6834", "#1baf7a", "#eda100",
            "#e87ba4", "#008300", "#6250d6", "#e34948",
        ],
    },
    "escuro": {
        "superficie": "#1a1a19",
        "texto": "#f0efec",
        "texto_suave": "#c3c2b7",
        "neutro": "#383835",
        "series": [
            "#3987e5", "#d95926", "#199e70", "#c98500",
            "#d55181", "#0ca30c", "#9085e9", "#e66767",
        ],
    },
    "status": {
        "bom": "#0ca30c",
        "atencao": "#fab219",
        "grave": "#ec835a",
        "critico": "#d03b3b",
    },
    "sequencial": [
        "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
        "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281",
        "#0d366b",
    ],
    "divergente": {
        "negativo": "#2a78d6",
        "positivo": "#d03b3b",
        "neutro_claro": "#f0efec",
        "neutro_escuro": "#383835",
    },
}

# Cor fixa por entidade: a cor segue a entidade, nunca o ranking.
CORES_ENTIDADE = {
    "produto": {
        "Geladeira": "slot1",
        "Lavadora": "slot2",
        "Ar-condicionado": "slot3",
        "Micro-ondas": "slot4",
    },
    "turno": {"Manhã": "slot1", "Tarde": "slot2", "Noite": "slot3"},
    "linha_producao": {
        "Linha A": "slot1",
        "Linha B": "slot2",
        "Linha C": "slot3",
        "Linha D": "slot4",
    },
    "tipo_manutencao": {
        "Nenhuma": "slot1",
        "Preventiva": "slot3",
        "Corretiva": "slot2",
    },
}

# Unidades usadas na formatação de cada variável quantitativa.
UNIDADES = {
    "horas_planejadas": "h",
    "horas_parada_maquina": "h",
    "horas_efetivas": "h",
    "idade_maquina_anos": "anos",
    "temperatura_ambiente_c": "°C",
    "experiencia_operador_anos": "anos",
    "unidades_produzidas": "un",
    "unidades_defeituosas": "un",
    "consumo_energia_kwh": "kWh",
    "residuo_kg": "kg",
    "produtividade_hora": "un/h",
    "energia_por_unidade": "kWh/un",
}
