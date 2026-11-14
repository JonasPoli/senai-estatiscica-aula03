# EletroTech — Relatório Estatístico da Produção

Site **one-page** com o relatório estatístico da base de produção da EletroTech,
gerado por um script Python a partir do CSV do projeto.

> SENAI — Estatística — Aula 03

## Como funciona

O projeto é um **gerador de site estático**: o Python lê o CSV, calcula as
estatísticas e renderiza um único `index.html` (mais CSS/JS) dentro de `dist/`.
Não há servidor de aplicação — o resultado é um arquivo que abre em qualquer
navegador, pode ser enviado por e-mail, impresso em PDF ou publicado no
GitHub Pages.

```
CSV  ──▶  relatorio/dados.py      (leitura e limpeza, formato pt-BR)
         relatorio/estatistica.py (medidas, frequências, outliers)
         relatorio/graficos.py    (séries dos gráficos em JSON)
         relatorio/site.py        (contexto + Jinja2)
                 │
                 ▼
         templates/index.html  +  static/  ──▶  dist/index.html
```

## Instalação

Requer Python 3.12 ou superior.

```powershell
# na raiz do projeto
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Uso

```powershell
# gera dist/index.html
python gerar_site.py

# gera e abre no navegador em http://127.0.0.1:8000
python gerar_site.py --servir

# opções
python gerar_site.py --csv "outro_arquivo.csv" --saida "dist/relatorio.html"
python gerar_site.py --servir --porta 8080
```

Equivalente: `python -m relatorio`.

## Estrutura

| Caminho | Função |
| --- | --- |
| `csv/` | base de dados de origem (versionada) |
| `relatorio/config.py` | caminhos, tipos das colunas e rótulos de exibição |
| `relatorio/dados.py` | leitura do CSV e conversão de tipos |
| `relatorio/estatistica.py` | funções de cálculo estatístico |
| `relatorio/graficos.py` | preparação das séries dos gráficos |
| `relatorio/formato.py` | filtros de formatação pt-BR para os templates |
| `relatorio/site.py` | montagem do contexto e renderização |
| `relatorio/cli.py` | linha de comando (`--csv`, `--saida`, `--servir`) |
| `templates/` | `base.html` (layout) e `index.html` (seções da página) |
| `templates/partials/` | seções longas do relatório, em arquivos separados |
| `static/css/estilo.css` | estilos (tokens de cor, tema claro/escuro, impressão) |
| `static/js/app.js` | navegação e, adiante, os gráficos |
| `dist/` | **saída gerada** — não versionada (veja `.gitignore`) |

## Base de dados

`csv/EletroTech - Análise Estatística da Produção (com glossário de funções) - Página1.csv`

500 registros de produção com 25 variáveis, no formato brasileiro: decimal com
vírgula, datas `dd/mm/aaaa` e percentuais com `%`. A conversão para tipos
numéricos fica inteiramente em `relatorio/dados.py`; o restante do código
trabalha com o DataFrame já limpo.

As variáveis estão classificadas em `relatorio/config.py`:

- **Identificação:** `id_registro`, `data`
- **Qualitativas:** `turno`, `linha_producao`, `produto`, `tipo_manutencao`,
  `atipico_energia`
- **Quantitativas:** horas planejadas e efetivas, parada de máquina, idade da
  máquina, temperatura, experiência do operador, unidades produzidas e
  defeituosas, consumo de energia, resíduo, devoluções, pedidos, entregas no
  prazo, produtividade/hora, energia por unidade, produção relativa
- **Percentual:** `taxa_defeitos` (armazenada como fração 0–1 após a leitura)

## O que o relatório contém

Página única com 14 seções e 31 gráficos interativos:

1. **Visão geral** — indicadores-chave do período e síntese do parecer
2. **População e amostra** — população, unidade de análise, técnica de
   amostragem e classificação das variáveis por tipo
3. **Medidas descritivas** — média, mediana, moda, amplitude, variância,
   desvio-padrão, CV, quartis, IQR, assimetria e curtose de 15 variáveis
4. **Distribuições** — 7 histogramas
5. **Evolução no tempo** — 5 séries mensais
6. **Comparativos** — por produto, turno, linha e tipo de manutenção
7. **Qualidade** — taxa de defeitos por linha, mapa de calor e Pareto
8. **Energia** — energia por unidade e relação volume × consumo
9. **Relações** — matriz de correlação e dispersões
10. **Valores atípicos** — os 6 registros atípicos de consumo de energia
11. **Questões investigativas** — as 6 perguntas do enunciado, respondidas
12. **Parecer técnico** — evidências, limitações e recomendações
13. **Código Python** — os fontes usados, lidos do próprio projeto
14. **Glossário** — as 25 variáveis da base

### Marcadores estatísticos

Todo gráfico traz a faixa com os sete indicadores (média, mediana, moda,
variância, desvio-padrão, quartis e IQR) e, nos 26 em que a geometria permite,
as linhas correspondentes desenhadas sobre o gráfico:

| medida | estilo da linha |
| --- | --- |
| média | tracejada |
| mediana | pontilhada |
| moda | sólida fina |
| Q1 e Q3 | tracejado curto, cinza |
| faixa ±1 desvio-padrão | área sombreada |

Nos gráficos de rosca, mapa de calor e Pareto as linhas não se aplicam
geometricamente; a faixa de indicadores continua presente.

### Convenções de cálculo

- **Taxa de defeitos de um grupo** = soma das unidades defeituosas ÷ soma das
  unidades produzidas do grupo, nunca a média das taxas individuais (que
  daria peso igual a registros de volumes muito diferentes).
- **Produtividade de um grupo** = soma das unidades produzidas ÷ soma das horas
  efetivas.
- Variância e desvio-padrão **amostrais** (`ddof=1`).
- Outliers pelo critério de **Tukey** (1,5 × IQR).
- Valores faltantes são descartados variável por variável (exclusão por par),
  por isso o `n` varia entre as linhas da tabela de descritivas.
- Produtos têm **ritmos de fabricação diferentes** (Micro-ondas ~302 un por
  registro, Geladeira ~130). Todo comparativo de volume por produto vem
  acompanhado da produtividade por hora efetiva.

## Tecnologia

- **Geração**: Python + pandas + Jinja2. Nenhum servidor de aplicação.
- **Gráficos**: [Apache ECharts](https://echarts.apache.org/) 5.5.1,
  vendorizado em `static/vendor/echarts.min.js`. O relatório **funciona
  offline** — não há CDN nem requisição de rede.
- **Dados dos gráficos**: embutidos no HTML como JSON e desenhados no
  navegador, com tooltip, zoom, troca de tema claro/escuro e tabela de dados
  por gráfico.
- **Paleta**: validada para daltonismo e contraste nos dois temas. A cor segue
  a entidade (Geladeira é sempre azul, Lavadora sempre laranja, etc.), nunca a
  posição no ranking.
- **Impressão**: o CSS tem regras `@media print` — `Ctrl+P` gera um PDF
  apresentável, com os gráficos redesenhados e as tabelas abertas.

## Como estender

Para acrescentar uma seção ao relatório:

1. calcule os números em `relatorio/estatistica.py` e exponha-os no dicionário
   de `analisar()`, em `relatorio/analise.py`;
2. monte as séries em `construir_graficos()`, em `relatorio/graficos.py`,
   usando a chave `secao` para direcionar o gráfico;
3. registre a seção em `config.SECOES` (ela aparece na navegação do topo);
4. escreva o HTML em `templates/index.html`, reaproveitando o macro
   `cartao_grafico()` de `templates/partials/grafico.html`.

Os tipos de gráfico aceitos pelo motor JavaScript são `histograma`, `barras`,
`barras-agrupadas`, `barras-empilhadas`, `linhas`, `area`, `boxplot`,
`dispersao`, `donut`, `heatmap` e `pareto`.

## Publicação

`dist/` não é versionado. Para entregar o relatório, basta a pasta `dist/`
inteira (o HTML depende de `dist/static/`). Para publicar no GitHub Pages,
remova `dist/` do `.gitignore` e aponte o Pages para essa pasta.
