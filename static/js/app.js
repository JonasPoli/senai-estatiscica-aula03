/* ===========================================================
   EletroTech - Relatório estatístico one-page
   Motor de gráficos ECharts (AGENTE D).

   Entrada: duas tags JSON no HTML
     <script type="application/json" id="dados-graficos"> -> lista de gráficos
     <script type="application/json" id="dados-meta">     -> metadados / paleta

   Dependência única: o global `echarts` (ECharts 5.5.1 vendorizado em
   static/vendor/echarts.min.js). Nada de rede: o relatório roda offline.

   Exigência central da disciplina: TODO gráfico mostra média (linha
   tracejada), mediana (pontilhada), moda (sólida fina), Q1/Q3 (tracejado
   curto, cinza), a faixa de +-1 desvio-padrão e, na faixa de estatísticas
   do cartão, variância, desvio-padrão, CV e IQR.
   =========================================================== */

(function () {
  "use strict";

  /* =========================================================
     1. Paleta validada (item 3 do contrato)
     ========================================================= */

  /** Cores categóricas, ordem fixa, nunca ciclar além do slot 8. */
  var SLOTS = {
    claro: [
      "#2a78d6", // 1 azul
      "#eb6834", // 2 laranja
      "#1baf7a", // 3 aqua
      "#eda100", // 4 amarelo
      "#e87ba4", // 5 magenta
      "#008300", // 6 verde
      "#6250d6", // 7 violeta
      "#e34948"  // 8 vermelho
    ],
    escuro: [
      "#3987e5",
      "#d95926",
      "#199e70",
      "#c98500",
      "#d55181",
      "#0ca30c",
      "#9085e9",
      "#e66767"
    ]
  };

  /** Cores de status: fixas, iguais nos dois temas. */
  var STATUS = {
    bom: "#0ca30c",
    atencao: "#fab219",
    grave: "#ec835a",
    critico: "#d03b3b"
  };

  /** Escala sequencial (azul 100 -> 700), usada em heatmaps de intensidade. */
  var SEQUENCIAL = [
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
    "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"
  ];

  /** Escala divergente (azul <-> vermelho) com ponto neutro cinza por tema. */
  var DIVERGENTE = {
    claro: [
      "#104281", "#1c5cab", "#2a78d6", "#5598e7", "#9ec5f4",
      "#f0efec",
      "#f6c0bf", "#ee9593", "#e34948", "#c9312f", "#9d2321"
    ],
    escuro: [
      "#104281", "#1c5cab", "#2a78d6", "#5598e7", "#86b6ef",
      "#383835",
      "#ea8a89", "#e66767", "#e34948", "#c9312f", "#9d2321"
    ]
  };

  /** Superfícies, texto, grade e cores dos marcadores por tema. */
  var TEMAS = {
    claro: {
      nome: "claro",
      superficie: "#fcfcfb",
      texto: "#0b0b0b",
      textoFraco: "#52514e",
      neutro: "#f0efec",
      grade: "rgba(11, 11, 11, 0.10)",
      eixo: "rgba(11, 11, 11, 0.28)",
      marcadorForte: "#0b0b0b",
      marcadorFraco: "#52514e",
      marcadorCinza: "#7a7975",
      areaDp: "rgba(11, 11, 11, 0.055)",
      tooltipFundo: "rgba(252, 252, 251, 0.97)",
      tooltipBorda: "rgba(11, 11, 11, 0.16)",
      rotuloFundo: "rgba(252, 252, 251, 0.82)"
    },
    escuro: {
      nome: "escuro",
      superficie: "#1a1a19",
      texto: "#f0efec",
      textoFraco: "#c3c2b7",
      neutro: "#383835",
      grade: "rgba(240, 239, 236, 0.12)",
      eixo: "rgba(240, 239, 236, 0.30)",
      marcadorForte: "#f0efec",
      marcadorFraco: "#c3c2b7",
      marcadorCinza: "#9a998f",
      areaDp: "rgba(240, 239, 236, 0.07)",
      tooltipFundo: "rgba(26, 26, 25, 0.97)",
      tooltipBorda: "rgba(240, 239, 236, 0.20)",
      rotuloFundo: "rgba(26, 26, 25, 0.82)"
    }
  };

  /* =========================================================
     2. Constantes de marcação (ids e classes esperados no HTML)
     ========================================================= */

  var ID_DADOS_GRAFICOS = "dados-graficos";
  var ID_DADOS_META = "dados-meta";
  var ID_BOTAO_TEMA = "alternar-tema";
  // O template do AGENTE E emite <button id="voltar-topo" class="voltar-topo">.
  // Os demais seletores ficam como alternativa.
  var SELETORES_BOTAO_TOPO = [
    "#voltar-topo",
    ".voltar-topo",
    "#voltar-ao-topo",
    "[data-voltar-topo]",
    ".botao-topo"
  ];
  // O rótulo do botão de tema pode vir com qualquer um destes nomes de classe.
  var SELETORES_TEXTO_TEMA = [".botao--tema__texto", ".alternar-tema__texto"];

  /** Primeiro elemento encontrado entre vários seletores alternativos. */
  function primeiro(seletores, raiz) {
    var base = raiz || document;
    for (var i = 0; i < seletores.length; i += 1) {
      var achado = base.querySelector(seletores[i]);
      if (achado) return achado;
    }
    return null;
  }
  var CHAVE_TEMA = "eletrotech:tema";

  var PREFIXO_TELA = "g-";   // <div class="grafico__tela" id="g-{{id}}">
  var PREFIXO_CARD = "card-"; // <figure class="grafico" id="card-{{id}}">

  /* =========================================================
     3. Preferências do usuário e utilidades de DOM
     ========================================================= */

  var SEM_MOVIMENTO = (function () {
    try {
      return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    } catch (erro) {
      return false;
    }
  })();

  /** localStorage pode lançar (modo privado, cookies bloqueados) ou vir vazio. */
  function lerArmazenado(chave) {
    try {
      var valor = window.localStorage.getItem(chave);
      return valor ? String(valor) : null;
    } catch (erro) {
      return null;
    }
  }

  function gravarArmazenado(chave, valor) {
    try {
      window.localStorage.setItem(chave, String(valor));
      return true;
    } catch (erro) {
      return false;
    }
  }

  function criar(tag, classe, texto) {
    var el = document.createElement(tag);
    if (classe) el.className = classe;
    if (texto !== undefined && texto !== null) el.textContent = String(texto);
    return el;
  }

  function limpar(el) {
    if (!el) return;
    while (el.firstChild) el.removeChild(el.firstChild);
  }

  function ehNumero(v) {
    return typeof v === "number" && isFinite(v);
  }

  /* =========================================================
     4. Formatação pt-BR
     ========================================================= */

  var cacheFormatadores = {};

  function formatador(minimo, maximo) {
    var chave = minimo + ":" + maximo;
    if (!cacheFormatadores[chave]) {
      cacheFormatadores[chave] = new Intl.NumberFormat("pt-BR", {
        minimumFractionDigits: minimo,
        maximumFractionDigits: maximo
      });
    }
    return cacheFormatadores[chave];
  }

  function fmtInt(v) {
    return formatador(0, 0).format(v);
  }

  function fmtNum(v, casas) {
    var c = casas === undefined ? 2 : casas;
    return formatador(c, c).format(v);
  }

  /**
   * Formata um valor conforme o formato declarado pelo gerador Python.
   *   "int" -> inteiro
   *   "num" -> 2 casas (mais casas quando o valor é muito pequeno)
   *   "pct" -> fração 0-1 convertida em percentual
   * `unidade` é opcional e vira sufixo (exceto em "pct", que já usa "%").
   */
  function formatarValor(valor, formato, unidade, semUnidade) {
    if (valor === null || valor === undefined || !isFinite(valor)) return "—";
    var texto;
    var abs = Math.abs(valor);
    if (formato === "pct") {
      texto = fmtNum(valor * 100, abs < 0.001 ? 3 : abs < 0.01 ? 2 : 1) + "%";
      return texto;
    }
    if (formato === "int") {
      texto = Math.abs(valor - Math.round(valor)) < 1e-9 ? fmtInt(valor) : fmtNum(valor, 1);
    } else {
      // "num" e qualquer formato desconhecido.
      if (abs !== 0 && abs < 0.01) texto = fmtNum(valor, 4);
      else if (abs < 1) texto = fmtNum(valor, 3);
      else if (abs >= 10000) texto = fmtNum(valor, 1);
      else texto = fmtNum(valor, 2);
    }
    if (unidade && !semUnidade) texto += " " + unidade;
    return texto;
  }

  /** Formatação curta para rótulo de eixo (sem unidade, sem ruído). */
  function formatarEixo(valor, formato) {
    if (!ehNumero(valor)) return "";
    if (formato === "pct") {
      return formatador(0, Math.abs(valor) < 0.01 ? 2 : 1).format(valor * 100) + "%";
    }
    var abs = Math.abs(valor);
    if (formato === "int" || Math.abs(valor - Math.round(valor)) < 1e-9) {
      if (abs >= 1000000) return formatador(0, 1).format(valor / 1000000) + " mi";
      if (abs >= 10000) return formatador(0, 0).format(valor / 1000) + " mil";
      return fmtInt(valor);
    }
    if (abs !== 0 && abs < 0.01) return formatador(0, 4).format(valor);
    if (abs < 1) return formatador(0, 3).format(valor);
    return formatador(0, 2).format(valor);
  }

  /**
   * Coeficiente de variação: o gerador pode entregar fração (0,42) ou
   * percentual (42,0). Heurística defensiva: CV acima de 3 já está em %.
   */
  function formatarCV(valor) {
    if (!ehNumero(valor)) return "—";
    var pct = Math.abs(valor) <= 3 ? valor * 100 : valor;
    return fmtNum(pct, 1) + "%";
  }

  /** Variância: unidade ao quadrado; em formato percentual fica como fração. */
  function formatarVariancia(valor, formato, unidade) {
    if (!ehNumero(valor)) return "—";
    if (formato === "pct") return formatador(0, 6).format(valor);
    var abs = Math.abs(valor);
    var texto = abs >= 1000 ? fmtNum(valor, 1) : abs < 0.01 ? formatador(0, 6).format(valor) : fmtNum(valor, 2);
    if (unidade) texto += " " + unidade + "²";
    return texto;
  }

  /** Desvio-padrão de uma fração é lido em pontos percentuais. */
  function formatarDesvio(valor, formato, unidade) {
    if (!ehNumero(valor)) return "—";
    if (formato === "pct") return fmtNum(valor * 100, 2) + " p.p.";
    return formatarValor(valor, formato, unidade);
  }

  /** Formata qualquer célula de tabela vinda do Python. */
  function formatarCelula(valor) {
    if (valor === null || valor === undefined) return "—";
    if (typeof valor === "boolean") return valor ? "Sim" : "Não";
    if (typeof valor === "number") {
      if (!isFinite(valor)) return "—";
      if (Math.abs(valor - Math.round(valor)) < 1e-9 && Math.abs(valor) < 1e15) return fmtInt(valor);
      var abs = Math.abs(valor);
      if (abs !== 0 && abs < 0.01) return formatador(0, 4).format(valor);
      if (abs < 1) return fmtNum(valor, 3);
      return fmtNum(valor, 2);
    }
    return String(valor);
  }

  /* =========================================================
     5. Resolução de cores
     ========================================================= */

  function escalaDe(especificacao, tema) {
    if (especificacao === "sequencial") return SEQUENCIAL.slice();
    if (especificacao === "divergente") return (DIVERGENTE[tema] || DIVERGENTE.claro).slice();
    return null;
  }

  /**
   * Resolve "slot1".."slot8", "status:bom|atencao|grave|critico",
   * "sequencial", "divergente" ou um hexadecimal literal.
   * `indice` é a posição da série, usada como reserva.
   */
  function resolverCor(especificacao, tema, indice) {
    var slots = SLOTS[tema] || SLOTS.claro;
    var i = ehNumero(indice) ? Math.abs(Math.round(indice)) % slots.length : 0;
    if (!especificacao || typeof especificacao !== "string") return slots[i];
    var spec = especificacao.trim().toLowerCase();

    var slot = /^slot\s*([1-8])$/.exec(spec);
    if (slot) return slots[parseInt(slot[1], 10) - 1];

    var st = /^status\s*[:\-]\s*(.+)$/.exec(spec);
    if (st) {
      var nome = st[1]
        .replace(/[áàâã]/g, "a")
        .replace(/[éèê]/g, "e")
        .replace(/[íì]/g, "i")
        .replace(/[óòôõ]/g, "o")
        .replace(/[úù]/g, "u")
        .replace(/ç/g, "c")
        .replace(/\s+/g, "");
      if (STATUS[nome]) return STATUS[nome];
      return slots[i];
    }

    // Escalas: fora de heatmap, usa-se um ponto representativo da escala.
    if (spec === "sequencial") return SEQUENCIAL[7];
    if (spec === "divergente") return (DIVERGENTE[tema] || DIVERGENTE.claro)[8];

    if (/^#[0-9a-f]{3,8}$/.test(spec) || /^rgba?\(/.test(spec)) return especificacao;
    return slots[i];
  }

  /* =========================================================
     6. Leitura dos dados embutidos no HTML
     ========================================================= */

  function lerJson(id) {
    var tag = document.getElementById(id);
    if (!tag) return null;
    try {
      var bruto = tag.textContent || "";
      if (!bruto.trim()) return null;
      return JSON.parse(bruto);
    } catch (erro) {
      console.error('Não foi possível interpretar o JSON de "#' + id + '":', erro);
      return null;
    }
  }

  function lerGraficos() {
    var dados = lerJson(ID_DADOS_GRAFICOS);
    if (!dados) return [];
    if (Array.isArray(dados)) return dados;
    if (Array.isArray(dados.graficos)) return dados.graficos;
    return [];
  }

  function lerMeta() {
    var dados = lerJson(ID_DADOS_META);
    return dados && typeof dados === "object" ? dados : {};
  }

  /* =========================================================
     7. Tema vigente
     ========================================================= */

  var temaAtual = "claro";

  function temaPreferidoDoSistema() {
    try {
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "escuro" : "claro";
    } catch (erro) {
      return "claro";
    }
  }

  function normalizarTema(valor) {
    return valor === "escuro" || valor === "dark" ? "escuro" : "claro";
  }

  function tema() {
    return TEMAS[temaAtual] || TEMAS.claro;
  }

  /* =========================================================
     8. Marcadores estatísticos (média, mediana, moda, Q1, Q3, +-1 DP)
     ========================================================= */

  /** Definição visual de cada marcador, conforme item 4 do contrato. */
  function estilosMarcadores(t) {
    return {
      media: {
        chave: "media",
        sigla: "x̄",
        rotulo: "Média (tracejada)",
        cor: t.marcadorForte,
        largura: 1.7,
        tipo: [8, 6]
      },
      mediana: {
        chave: "mediana",
        sigla: "Md",
        rotulo: "Mediana (pontilhada)",
        cor: t.marcadorForte,
        largura: 1.5,
        tipo: [2, 4]
      },
      moda: {
        chave: "moda",
        sigla: "Mo",
        rotulo: "Moda (sólida fina)",
        cor: t.marcadorFraco,
        largura: 1,
        tipo: "solid"
      },
      q1: {
        chave: "q1",
        sigla: "Q1",
        rotulo: "Q1 e Q3 (tracejado curto)",
        cor: t.marcadorCinza,
        largura: 1,
        tipo: [4, 4]
      },
      q3: {
        chave: "q3",
        sigla: "Q3",
        rotulo: null, // a legenda de Q1 cobre os dois
        cor: t.marcadorCinza,
        largura: 1,
        tipo: [4, 4]
      }
    };
  }

  /**
   * Posição de cada marcador no eixo. Em eixo de categorias (histogramas)
   * usa-se `marcadores.pos`, que traz o índice fracionário.
   */
  function posicaoMarcador(marc, chave, eixoCategoria) {
    if (eixoCategoria) {
      if (!marc.pos) return null;
      var p = marc.pos[chave];
      return ehNumero(p) ? p : null;
    }
    return ehNumero(marc[chave]) ? marc[chave] : null;
  }

  /**
   * Rótulos alternam posição e alinhamento para não se sobrepor.
   * Em linhas verticais (eixo x) "end" é o topo; em horizontais (eixo y)
   * "end" é a borda direita.
   */
  function rotuloMarcador(chave, vertical) {
    if (vertical) {
      switch (chave) {
        case "media": return { position: "end", align: "left", offset: [3, -1] };
        case "mediana": return { position: "end", align: "right", offset: [-3, 12] };
        case "moda": return { position: "end", align: "left", offset: [3, 25] };
        case "q1": return { position: "start", align: "right", offset: [-3, 1] };
        default: return { position: "start", align: "left", offset: [3, 1] };
      }
    }
    switch (chave) {
      case "media": return { position: "end", align: "right", offset: [-2, -9] };
      case "mediana": return { position: "start", align: "left", offset: [2, -9] };
      case "moda": return { position: "end", align: "right", offset: [-2, 10] };
      case "q1": return { position: "start", align: "left", offset: [2, 10] };
      default: return { position: "end", align: "right", offset: [-2, 10] };
    }
  }

  /**
   * Monta markLine + markArea para o gráfico. Devolve `null` quando não há
   * marcadores aplicáveis (ex.: donut sem eixos).
   */
  function construirMarcadores(g, t, formatoEixo) {
    var marc = g && g.marcadores;
    if (!marc || typeof marc !== "object") return null;

    var eixo = marc.eixo === "x" ? "x" : "y";
    var vertical = eixo === "x"; // linha vertical quando ancorada no eixo x
    var eixoCategoria = vertical
      ? !!(g.eixo_x && g.eixo_x.tipo === "category")
      : !!(g.eixo_y && g.eixo_y.tipo === "category");

    var estilos = estilosMarcadores(t);
    var ordem = ["q1", "q3", "moda", "mediana", "media"];
    var itens = [];

    ordem.forEach(function (chave) {
      var estilo = estilos[chave];
      var posicao = posicaoMarcador(marc, chave, eixoCategoria);
      var valorReal = ehNumero(marc[chave]) ? marc[chave] : null;
      if (posicao === null || valorReal === null) return;
      var rot = rotuloMarcador(chave, vertical);
      var item = {
        name: estilo.sigla,
        lineStyle: {
          color: estilo.cor,
          width: estilo.largura,
          type: estilo.tipo,
          opacity: 0.95
        },
        label: {
          show: true,
          formatter: estilo.sigla + " " + formatarEixo(valorReal, formatoEixo),
          position: rot.position,
          align: rot.align,
          offset: rot.offset,
          color: estilo.cor,
          fontSize: 10,
          fontWeight: chave === "media" || chave === "mediana" ? 600 : 400,
          backgroundColor: t.rotuloFundo,
          padding: [2, 3, 1, 3],
          borderRadius: 2
        },
        emphasis: { disabled: true }
      };
      if (vertical) item.xAxis = posicao;
      else item.yAxis = posicao;
      itens.push(item);
    });

    // Faixa de +-1 desvio-padrão em torno da média.
    var area = null;
    var inf = null;
    var sup = null;
    if (eixoCategoria && marc.pos) {
      inf = ehNumero(marc.pos.dp_inf) ? marc.pos.dp_inf : null;
      sup = ehNumero(marc.pos.dp_sup) ? marc.pos.dp_sup : null;
    } else if (ehNumero(marc.media) && ehNumero(marc.desvio_padrao)) {
      inf = marc.media - marc.desvio_padrao;
      sup = marc.media + marc.desvio_padrao;
    }
    if (inf !== null && sup !== null && sup > inf) {
      var p1 = {};
      var p2 = {};
      if (vertical) {
        p1.xAxis = inf;
        p2.xAxis = sup;
      } else {
        p1.yAxis = inf;
        p2.yAxis = sup;
      }
      p1.name = "±1 σ";
      p1.itemStyle = { color: t.areaDp };
      p1.label = {
        show: true,
        position: vertical ? "insideTop" : "insideTopRight",
        formatter: "±1 σ",
        color: t.marcadorCinza,
        fontSize: 10,
        padding: [2, 4, 2, 4]
      };
      area = { silent: true, data: [[p1, p2]] };
    }

    if (!itens.length && !area) return null;
    return {
      markLine: itens.length
        ? {
            silent: true,
            symbol: "none",
            animation: !SEM_MOVIMENTO,
            emphasis: { disabled: true },
            data: itens
          }
        : null,
      markArea: area
    };
  }

  /** Aplica os marcadores na primeira série cartesiana, evitando duplicatas. */
  function aplicarMarcadores(series, marcadores) {
    if (!marcadores || !series || !series.length) return;
    var alvo = null;
    for (var i = 0; i < series.length; i += 1) {
      var tipo = series[i].type;
      if (tipo === "bar" || tipo === "line" || tipo === "scatter" || tipo === "boxplot") {
        alvo = series[i];
        break;
      }
    }
    if (!alvo) alvo = series[0];
    if (marcadores.markLine) alvo.markLine = marcadores.markLine;
    if (marcadores.markArea) alvo.markArea = marcadores.markArea;
  }

  /* =========================================================
     9. Peças comuns da option
     ========================================================= */

  function textoBase(t) {
    return {
      color: t.textoFraco,
      fontFamily:
        '"Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif',
      fontSize: 11
    };
  }

  function tooltipBase(t, gatilho, ponteiro) {
    var tip = {
      trigger: gatilho || "item",
      confine: true,
      backgroundColor: t.tooltipFundo,
      borderColor: t.tooltipBorda,
      borderWidth: 1,
      padding: [8, 10, 8, 10],
      textStyle: { color: t.texto, fontSize: 12 },
      extraCssText: "box-shadow: 0 6px 20px rgba(0,0,0,0.14); max-width: 280px;"
    };
    if (gatilho === "axis") {
      tip.axisPointer = {
        type: ponteiro || "shadow",
        label: { backgroundColor: t.marcadorFraco, color: t.superficie },
        lineStyle: { color: t.eixo, width: 1, type: "dashed" },
        crossStyle: { color: t.eixo, width: 1, type: "dashed" },
        shadowStyle: { color: t.grade }
      };
    }
    return tip;
  }

  function legendaBase(t, quantidade) {
    if (quantidade < 2) return { show: false };
    return {
      show: true,
      type: "scroll",
      top: 0,
      left: "center",
      itemWidth: 12,
      itemHeight: 8,
      itemGap: 14,
      icon: "roundRect",
      textStyle: { color: t.textoFraco, fontSize: 11 },
      pageIconColor: t.textoFraco,
      pageIconInactiveColor: t.grade,
      pageTextStyle: { color: t.textoFraco }
    };
  }

  function precisaRotacionar(rotulos) {
    if (!rotulos || !rotulos.length) return 0;
    var maior = 0;
    rotulos.forEach(function (r) {
      var n = String(r === null || r === undefined ? "" : r).length;
      if (n > maior) maior = n;
    });
    if (rotulos.length > 16 && maior > 3) return 45;
    if (rotulos.length > 9 && maior > 5) return 35;
    if (rotulos.length > 6 && maior > 11) return 25;
    return 0;
  }

  function eixoCategoriaBase(t, cfg, rotulos) {
    var rot = precisaRotacionar(rotulos);
    return {
      type: "category",
      data: (rotulos || []).map(function (r) {
        return r === null || r === undefined ? "" : String(r);
      }),
      name: (cfg && cfg.nome) || "",
      nameLocation: "middle",
      nameGap: rot ? 46 : 28,
      nameTextStyle: { color: t.textoFraco, fontSize: 11, fontWeight: 600 },
      boundaryGap: true,
      axisLine: { lineStyle: { color: t.eixo } },
      axisTick: { show: false },
      axisLabel: {
        color: t.textoFraco,
        fontSize: 10,
        rotate: rot,
        hideOverlap: true,
        interval: "auto"
      },
      splitLine: { show: false }
    };
  }

  function eixoValorBase(t, cfg, vertical) {
    var formato = (cfg && cfg.formato) || "num";
    return {
      type: "value",
      name: (cfg && cfg.nome) || "",
      nameLocation: vertical ? "end" : "middle",
      nameGap: vertical ? 12 : 30,
      nameTextStyle: {
        color: t.textoFraco,
        fontSize: 11,
        fontWeight: 600,
        align: vertical ? "left" : "center"
      },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: t.textoFraco,
        fontSize: 10,
        hideOverlap: true,
        formatter: function (valor) {
          return formatarEixo(valor, formato);
        }
      },
      splitLine: { show: true, lineStyle: { color: t.grade, width: 1 } },
      scale: !vertical
    };
  }

  function gradeBase(t, temLegenda, temZoom, rotacionado) {
    return {
      left: 10,
      right: 22,
      top: temLegenda ? 36 : 22,
      bottom: (temZoom ? 46 : 8) + (rotacionado ? 16 : 0),
      containLabel: true
    };
  }

  function zoomBase(t, eixos) {
    var lista = [
      {
        type: "inside",
        xAxisIndex: 0,
        filterMode: "none",
        zoomOnMouseWheel: "shift",
        moveOnMouseWheel: false
      },
      {
        type: "slider",
        xAxisIndex: 0,
        filterMode: "none",
        height: 18,
        bottom: 6,
        borderColor: t.grade,
        fillerColor: t.areaDp,
        handleStyle: { color: t.marcadorFraco, borderColor: t.marcadorFraco },
        moveHandleStyle: { color: t.grade },
        dataBackground: {
          lineStyle: { color: t.eixo },
          areaStyle: { color: t.grade }
        },
        selectedDataBackground: {
          lineStyle: { color: t.marcadorFraco },
          areaStyle: { color: t.areaDp }
        },
        textStyle: { color: t.textoFraco, fontSize: 10 }
      }
    ];
    if (eixos === "xy") {
      lista.push({
        type: "inside",
        yAxisIndex: 0,
        filterMode: "none",
        zoomOnMouseWheel: "shift",
        moveOnMouseWheel: false
      });
    }
    return lista;
  }

  /* =========================================================
     10. Normalização das séries vindas do Python
     ========================================================= */

  function valorDe(ponto) {
    if (ponto === null || ponto === undefined) return null;
    if (typeof ponto === "number") return isFinite(ponto) ? ponto : null;
    if (typeof ponto === "object" && "value" in ponto) {
      return ehNumero(ponto.value) ? ponto.value : null;
    }
    return null;
  }

  /** Converte números ou dicts {name, value, cor|status} em itens do ECharts. */
  function pontosCartesianos(serie, corBase, t) {
    var bruto = Array.isArray(serie.dados) ? serie.dados : [];
    return bruto.map(function (ponto, i) {
      if (ponto === null || ponto === undefined) return null;
      if (typeof ponto === "number") return isFinite(ponto) ? ponto : null;
      if (Array.isArray(ponto)) return ponto;
      if (typeof ponto === "object") {
        var item = { value: ehNumero(ponto.value) ? ponto.value : null };
        if (ponto.name !== undefined && ponto.name !== null) item.name = String(ponto.name);
        var corPonto = ponto.cor || (ponto.status ? "status:" + ponto.status : null);
        if (corPonto) item.itemStyle = { color: resolverCor(corPonto, t.nome, i) };
        return item;
      }
      return null;
    });
  }

  /** Lista de cores por ponto quando a série traz `cores` ou `status`. */
  function coresPorPonto(serie, t) {
    if (Array.isArray(serie.cores) && serie.cores.length) {
      return serie.cores.map(function (c, i) {
        return resolverCor(c, t.nome, i);
      });
    }
    if (Array.isArray(serie.status) && serie.status.length) {
      return serie.status.map(function (s, i) {
        return resolverCor("status:" + s, t.nome, i);
      });
    }
    return null;
  }

  function temDados(serie) {
    if (!serie) return false;
    var d = serie.dados;
    if (!Array.isArray(d) || !d.length) return false;
    return d.some(function (p) {
      if (p === null || p === undefined) return false;
      if (Array.isArray(p)) return p.length > 0;
      if (typeof p === "number") return isFinite(p);
      if (typeof p === "object") return p.value !== null && p.value !== undefined;
      return false;
    });
  }

  function seriesValidas(g) {
    var lista = Array.isArray(g.series) ? g.series : [];
    return lista.filter(temDados);
  }

  function rotuloDireto(serie, t, formato, vertical) {
    if (!serie.rotulo_direto) return { show: false };
    return {
      show: true,
      position: vertical ? "right" : "top",
      distance: 4,
      color: t.texto,
      fontSize: 10,
      fontWeight: 600,
      formatter: function (p) {
        var v = ehNumero(p.value) ? p.value : valorDe(p.data);
        return formatarEixo(v, formato);
      }
    };
  }

  /* =========================================================
     11. Construtores de option por tipo
     ========================================================= */

  function construirCartesiano(g, t, opcoes) {
    var cfg = opcoes || {};
    var series = seriesValidas(g);
    if (!series.length) throw new Error("sem séries com dados");

    var formatoY = (g.eixo_y && g.eixo_y.formato) || "num";
    var rotulos = (g.eixo_x && g.eixo_x.rotulos) || [];
    var xCategoria = !(g.eixo_x && g.eixo_x.tipo === "value");
    var temZoom = !!cfg.zoom;
    var rot = xCategoria ? precisaRotacionar(rotulos) : 0;

    var echSeries = series.map(function (s, i) {
      var cor = resolverCor(s.cor, t.nome, i);
      var porPonto = coresPorPonto(s, t);
      var tipo = cfg.tipoSerie || s.tipo || "bar";
      if (tipo === "pie" || tipo === "heatmap" || tipo === "boxplot") tipo = "bar";

      var item = {
        name: s.nome || "Série " + (i + 1),
        type: tipo,
        data: pontosCartesianos(s, cor, t),
        label: rotuloDireto(s, t, formatoY, false),
        labelLayout: { hideOverlap: true },
        animation: !SEM_MOVIMENTO,
        animationDuration: SEM_MOVIMENTO ? 0 : 450
      };

      if (tipo === "bar") {
        item.itemStyle = {
          color: porPonto
            ? function (p) {
                return porPonto[p.dataIndex % porPonto.length];
              }
            : cor,
          borderRadius: cfg.histograma ? [2, 2, 0, 0] : [3, 3, 0, 0]
        };
        item.barMaxWidth = cfg.histograma ? 40 : 54;
        if (cfg.histograma) item.barCategoryGap = "6%";
        if (cfg.empilhado) item.stack = "total";
        item.emphasis = { focus: "series" };
      } else if (tipo === "line") {
        item.lineStyle = { color: cor, width: 2 };
        item.itemStyle = { color: cor };
        item.symbol = "circle";
        item.symbolSize = rotulos.length > 30 ? 0 : 5;
        item.showSymbol = rotulos.length <= 30;
        item.smooth = false;
        item.connectNulls = false;
        item.emphasis = { focus: "series" };
        if (cfg.area) {
          item.areaStyle = { color: cor, opacity: series.length > 1 ? 0.14 : 0.22 };
          if (cfg.empilhado) item.stack = "total";
        }
      } else if (tipo === "scatter") {
        item.itemStyle = { color: cor, opacity: 0.72 };
        item.symbolSize = s.tamanho || 7;
      }
      return item;
    });

    var temLegenda = echSeries.length >= 2;
    var gatilho = cfg.tooltipEixo ? "axis" : "item";
    var ponteiro = cfg.crosshair ? "cross" : "shadow";

    var option = {
      backgroundColor: "transparent",
      textStyle: textoBase(t),
      animation: !SEM_MOVIMENTO,
      grid: gradeBase(t, temLegenda, temZoom, rot),
      legend: legendaBase(t, echSeries.length),
      tooltip: tooltipBase(t, gatilho, ponteiro),
      xAxis: xCategoria
        ? eixoCategoriaBase(t, g.eixo_x, rotulos)
        : eixoValorBase(t, g.eixo_x, false),
      yAxis: eixoValorBase(t, g.eixo_y, true),
      series: echSeries
    };

    if (temZoom) option.dataZoom = zoomBase(t, cfg.zoom === "xy" ? "xy" : "x");

    // Tooltip com formatação pt-BR.
    var unidade = (g.estatisticas && g.estatisticas.unidade) || "";
    option.tooltip.formatter = criarFormatadorTooltip(g, formatoY, unidade, gatilho, xCategoria);

    aplicarMarcadores(echSeries, construirMarcadores(g, t, formatoY));
    return option;
  }

  function criarFormatadorTooltip(g, formato, unidade, gatilho, xCategoria) {
    return function (parametros) {
      var lista = Array.isArray(parametros) ? parametros : [parametros];
      if (!lista.length) return "";
      var partes = [];
      var titulo = lista[0].name;
      if (!xCategoria) {
        var v0 = lista[0].value;
        titulo = Array.isArray(v0) ? formatarEixo(v0[0], (g.eixo_x && g.eixo_x.formato) || "num") : titulo;
      }
      if (titulo) partes.push("<strong>" + escaparHtml(titulo) + "</strong>");
      lista.forEach(function (p) {
        var valor = Array.isArray(p.value) ? p.value[p.value.length - 1] : p.value;
        if (p.value && typeof p.value === "object" && !Array.isArray(p.value)) {
          valor = p.value.value;
        }
        var linha = (p.marker || "") + escaparHtml(p.seriesName || "") + ": <strong>" +
          formatarValor(valor, formato, unidade) + "</strong>";
        partes.push(linha);
      });
      return partes.join("<br>");
    };
  }

  function escaparHtml(texto) {
    return String(texto === null || texto === undefined ? "" : texto)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function construirBoxplot(g, t) {
    var series = seriesValidas(g);
    if (!series.length) throw new Error("sem séries com dados");
    var principal = series[0];
    var rotulos = (g.eixo_x && g.eixo_x.rotulos) || [];
    var formatoY = (g.eixo_y && g.eixo_y.formato) || "num";
    var unidade = (g.estatisticas && g.estatisticas.unidade) || "";
    var cor = resolverCor(principal.cor, t.nome, 0);
    var porPonto = coresPorPonto(principal, t);

    var caixas = (principal.dados || []).map(function (d, i) {
      var v = Array.isArray(d) ? d.slice(0, 5) : null;
      var item = { value: v };
      if (porPonto) item.itemStyle = { color: porPonto[i % porPonto.length] };
      return item;
    });

    var echSeries = [
      {
        name: principal.nome || "Distribuição",
        type: "boxplot",
        data: caixas,
        boxWidth: ["20%", "54%"],
        itemStyle: {
          color: porPonto ? undefined : cor,
          opacity: 0.55,
          borderColor: porPonto ? undefined : cor,
          borderWidth: 1.4
        },
        emphasis: { itemStyle: { opacity: 0.85, borderWidth: 2 } },
        animation: !SEM_MOVIMENTO,
        tooltip: {
          formatter: function (p) {
            var v = p.value || [];
            var nomes = ["mínimo", "Q1", "mediana", "Q3", "máximo"];
            var linhas = ["<strong>" + escaparHtml(p.name) + "</strong>"];
            for (var i = 1; i <= 5; i += 1) {
              linhas.push(nomes[i - 1] + ": <strong>" + formatarValor(v[i], formatoY, unidade) + "</strong>");
            }
            return linhas.join("<br>");
          }
        }
      }
    ];

    // Outliers vêm como [[indice_categoria, valor], ...].
    var atipicos = [];
    series.forEach(function (s) {
      if (Array.isArray(s.outliers)) atipicos = atipicos.concat(s.outliers);
    });
    if (atipicos.length) {
      echSeries.push({
        name: "Valores atípicos",
        type: "scatter",
        data: atipicos,
        symbolSize: 6,
        itemStyle: { color: t.marcadorFraco, opacity: 0.7 },
        animation: !SEM_MOVIMENTO,
        tooltip: {
          formatter: function (p) {
            var v = p.value || [];
            return "Atípico: <strong>" + formatarValor(v[1], formatoY, unidade) + "</strong>";
          }
        }
      });
    }

    var temLegenda = echSeries.length >= 2;
    var rot = precisaRotacionar(rotulos);
    var option = {
      backgroundColor: "transparent",
      textStyle: textoBase(t),
      animation: !SEM_MOVIMENTO,
      grid: gradeBase(t, temLegenda, false, rot),
      legend: legendaBase(t, echSeries.length),
      tooltip: tooltipBase(t, "item"),
      xAxis: eixoCategoriaBase(t, g.eixo_x, rotulos),
      yAxis: eixoValorBase(t, g.eixo_y, true),
      series: echSeries
    };
    aplicarMarcadores(echSeries, construirMarcadores(g, t, formatoY));
    return option;
  }

  function construirDonut(g, t) {
    var series = seriesValidas(g);
    if (!series.length) throw new Error("sem séries com dados");
    var principal = series[0];
    var rotulos = (g.eixo_x && g.eixo_x.rotulos) || [];
    var formato = (g.eixo_y && g.eixo_y.formato) || (g.estatisticas && g.estatisticas.formato) || "num";
    var unidade = (g.estatisticas && g.estatisticas.unidade) || "";
    var porPonto = coresPorPonto(principal, t);

    var dados = (principal.dados || []).map(function (d, i) {
      var nome = rotulos[i] !== undefined && rotulos[i] !== null ? String(rotulos[i]) : "Item " + (i + 1);
      var valor = null;
      if (typeof d === "number") valor = isFinite(d) ? d : null;
      else if (d && typeof d === "object") {
        valor = ehNumero(d.value) ? d.value : null;
        if (d.name !== undefined && d.name !== null) nome = String(d.name);
      }
      var corPonto = porPonto
        ? porPonto[i % porPonto.length]
        : d && typeof d === "object" && (d.cor || d.status)
        ? resolverCor(d.cor || "status:" + d.status, t.nome, i)
        : resolverCor(principal.cor && /^slot/.test(String(principal.cor)) ? null : principal.cor, t.nome, i);
      return { name: nome, value: valor, itemStyle: { color: corPonto } };
    });

    return {
      backgroundColor: "transparent",
      textStyle: textoBase(t),
      animation: !SEM_MOVIMENTO,
      tooltip: Object.assign(tooltipBase(t, "item"), {
        formatter: function (p) {
          return "<strong>" + escaparHtml(p.name) + "</strong><br>" +
            formatarValor(p.value, formato, unidade) +
            " (" + fmtNum(p.percent, 1) + "%)";
        }
      }),
      legend: Object.assign(legendaBase(t, Math.max(2, dados.length)), {
        orient: "horizontal",
        bottom: 0,
        top: "auto",
        left: "center"
      }),
      series: [
        {
          name: principal.nome || "Composição",
          type: "pie",
          radius: ["48%", "72%"],
          center: ["50%", "46%"],
          avoidLabelOverlap: true,
          itemStyle: { borderColor: t.superficie, borderWidth: 2 },
          label: {
            show: true,
            color: t.texto,
            fontSize: 10,
            formatter: function (p) {
              return p.name + "\n" + fmtNum(p.percent, 1) + "%";
            }
          },
          labelLine: { length: 8, length2: 8, lineStyle: { color: t.eixo } },
          labelLayout: { hideOverlap: true },
          data: dados,
          animation: !SEM_MOVIMENTO
        }
      ]
    };
  }

  function construirHeatmap(g, t) {
    var series = seriesValidas(g);
    if (!series.length) throw new Error("sem séries com dados");
    var principal = series[0];
    var rotulosX = (g.eixo_x && g.eixo_x.rotulos) || [];
    var rotulosY = (g.eixo_y && g.eixo_y.rotulos) || [];
    var formato = (g.eixo_y && g.eixo_y.formato) || (g.estatisticas && g.estatisticas.formato) || "num";
    var unidade = (g.estatisticas && g.estatisticas.unidade) || "";

    var dados = (principal.dados || []).filter(function (d) {
      return Array.isArray(d) && d.length >= 3;
    });
    if (!dados.length) throw new Error("heatmap sem células");

    var valores = dados
      .map(function (d) {
        return ehNumero(d[2]) ? d[2] : null;
      })
      .filter(function (v) {
        return v !== null;
      });
    var minimo = Math.min.apply(null, valores);
    var maximo = Math.max.apply(null, valores);

    var escala = escalaDe(String(principal.cor || "sequencial").toLowerCase(), t.nome) || SEQUENCIAL.slice();
    var divergente = String(principal.cor || "").toLowerCase() === "divergente";
    if (divergente) {
      var limite = Math.max(Math.abs(minimo), Math.abs(maximo));
      if (limite <= 1.001) limite = 1;
      minimo = -limite;
      maximo = limite;
    }
    if (minimo === maximo) {
      minimo = minimo - 1;
      maximo = maximo + 1;
    }

    var celulas = rotulosX.length * Math.max(1, rotulosY.length);
    var mostrarRotulo = celulas > 0 && celulas <= 120;
    var rot = precisaRotacionar(rotulosX);

    return {
      backgroundColor: "transparent",
      textStyle: textoBase(t),
      animation: !SEM_MOVIMENTO,
      grid: {
        left: 10,
        right: 16,
        top: 18,
        bottom: 56 + (rot ? 16 : 0),
        containLabel: true
      },
      tooltip: Object.assign(tooltipBase(t, "item"), {
        formatter: function (p) {
          var v = p.value || [];
          var rx = rotulosX[v[0]] !== undefined ? rotulosX[v[0]] : v[0];
          var ry = rotulosY[v[1]] !== undefined ? rotulosY[v[1]] : v[1];
          return "<strong>" + escaparHtml(rx) + " · " + escaparHtml(ry) + "</strong><br>" +
            escaparHtml(principal.nome || "Valor") + ": <strong>" +
            formatarValor(v[2], formato, unidade) + "</strong>";
        }
      }),
      visualMap: {
        type: "continuous",
        min: minimo,
        max: maximo,
        calculable: true,
        orient: "horizontal",
        left: "center",
        bottom: 2,
        itemWidth: 12,
        itemHeight: 110,
        precision: formato === "pct" ? 3 : 2,
        inRange: { color: escala },
        textStyle: { color: t.textoFraco, fontSize: 10 },
        formatter: function (valor) {
          return formatarEixo(valor, formato);
        }
      },
      xAxis: Object.assign(eixoCategoriaBase(t, g.eixo_x, rotulosX), {
        splitArea: { show: true, areaStyle: { color: ["transparent"] } },
        boundaryGap: true
      }),
      yAxis: Object.assign(eixoCategoriaBase(t, g.eixo_y, rotulosY), {
        nameLocation: "end",
        nameGap: 12,
        boundaryGap: true
      }),
      series: [
        {
          name: principal.nome || "Intensidade",
          type: "heatmap",
          data: dados,
          label: {
            show: mostrarRotulo,
            color: t.texto,
            fontSize: 9,
            formatter: function (p) {
              return formatarEixo(p.value[2], formato);
            }
          },
          itemStyle: { borderColor: t.superficie, borderWidth: 1 },
          emphasis: { itemStyle: { borderColor: t.texto, borderWidth: 1.6 } },
          progressive: 0,
          animation: !SEM_MOVIMENTO
        }
      ]
    };
  }

  /**
   * Pareto: barras + linha acumulada. O contrato proíbe eixo y duplo, então,
   * quando as escalas são incompatíveis (ex.: contagens x fração 0-1), a linha
   * é desenhada reescalada para o eixo das barras e os rótulos/tooltip mostram
   * sempre o valor verdadeiro.
   */
  function construirPareto(g, t) {
    var series = seriesValidas(g);
    if (!series.length) throw new Error("sem séries com dados");
    var rotulos = (g.eixo_x && g.eixo_x.rotulos) || [];
    var formatoY = (g.eixo_y && g.eixo_y.formato) || "num";
    var unidade = (g.estatisticas && g.estatisticas.unidade) || "";

    var barras = [];
    var linhas = [];
    series.forEach(function (s) {
      if ((s.tipo || "bar") === "line") linhas.push(s);
      else barras.push(s);
    });
    if (!barras.length) barras = [series[0]];

    function maximoDe(s) {
      var m = 0;
      (s.dados || []).forEach(function (d) {
        var v = valorDe(d);
        if (v !== null && Math.abs(v) > m) m = Math.abs(v);
      });
      return m;
    }

    var maxBarras = 0;
    barras.forEach(function (s) {
      maxBarras = Math.max(maxBarras, maximoDe(s));
    });

    var echSeries = [];

    barras.forEach(function (s, i) {
      var cor = resolverCor(s.cor || "slot1", t.nome, i);
      var porPonto = coresPorPonto(s, t);
      echSeries.push({
        name: s.nome || "Contagem",
        type: "bar",
        data: pontosCartesianos(s, cor, t),
        barMaxWidth: 54,
        itemStyle: {
          color: porPonto
            ? function (p) {
                return porPonto[p.dataIndex % porPonto.length];
              }
            : cor,
          borderRadius: [3, 3, 0, 0]
        },
        label: rotuloDireto(s, t, formatoY, false),
        labelLayout: { hideOverlap: true },
        emphasis: { focus: "series" },
        animation: !SEM_MOVIMENTO,
        tooltip: {
          valueFormatter: function (v) {
            return formatarValor(v, formatoY, unidade);
          }
        }
      });
    });

    linhas.forEach(function (s, i) {
      var cor = resolverCor(s.cor || "slot2", t.nome, barras.length + i);
      var reais = (s.dados || []).map(valorDe);
      var maxLinha = maximoDe(s);
      var escala = 1;
      if (maxLinha > 0 && maxBarras > 0 && maxBarras / maxLinha > 8) {
        escala = (maxBarras / maxLinha) * 0.98;
      }
      var formatoLinha = s.formato || (maxLinha <= 1.001 ? "pct" : formatoY);
      echSeries.push({
        name: s.nome || "Acumulado",
        type: "line",
        data: reais.map(function (v) {
          return v === null ? null : v * escala;
        }),
        lineStyle: { color: cor, width: 2 },
        itemStyle: { color: cor },
        symbol: "circle",
        symbolSize: 5,
        z: 5,
        label: {
          show: true,
          position: "top",
          distance: 6,
          color: t.texto,
          fontSize: 10,
          fontWeight: 600,
          formatter: function (p) {
            return formatarEixo(reais[p.dataIndex], formatoLinha);
          }
        },
        labelLayout: { hideOverlap: true },
        animation: !SEM_MOVIMENTO,
        __reais: reais,
        __formato: formatoLinha
      });
    });

    var rot = precisaRotacionar(rotulos);
    var option = {
      backgroundColor: "transparent",
      textStyle: textoBase(t),
      animation: !SEM_MOVIMENTO,
      grid: gradeBase(t, echSeries.length >= 2, false, rot),
      legend: legendaBase(t, echSeries.length),
      tooltip: Object.assign(tooltipBase(t, "axis", "shadow"), {
        formatter: function (parametros) {
          var lista = Array.isArray(parametros) ? parametros : [parametros];
          if (!lista.length) return "";
          var partes = ["<strong>" + escaparHtml(lista[0].name) + "</strong>"];
          lista.forEach(function (p) {
            var serie = echSeries[p.seriesIndex];
            var valor = p.value;
            var formato = formatoY;
            if (serie && serie.__reais) {
              valor = serie.__reais[p.dataIndex];
              formato = serie.__formato;
              partes.push((p.marker || "") + escaparHtml(p.seriesName) + ": <strong>" +
                formatarValor(valor, formato, "") + "</strong>");
              return;
            }
            partes.push((p.marker || "") + escaparHtml(p.seriesName) + ": <strong>" +
              formatarValor(valor, formato, unidade) + "</strong>");
          });
          return partes.join("<br>");
        }
      }),
      xAxis: eixoCategoriaBase(t, g.eixo_x, rotulos),
      yAxis: eixoValorBase(t, g.eixo_y, true),
      series: echSeries
    };
    aplicarMarcadores(echSeries, construirMarcadores(g, t, formatoY));
    return option;
  }

  var CONSTRUTORES = {
    histograma: function (g, t) {
      return construirCartesiano(g, t, {
        tipoSerie: "bar",
        histograma: true,
        tooltipEixo: false
      });
    },
    barras: function (g, t) {
      return construirCartesiano(g, t, { tipoSerie: "bar", tooltipEixo: false });
    },
    "barras-agrupadas": function (g, t) {
      return construirCartesiano(g, t, { tipoSerie: "bar", tooltipEixo: true });
    },
    "barras-empilhadas": function (g, t) {
      return construirCartesiano(g, t, {
        tipoSerie: "bar",
        empilhado: true,
        tooltipEixo: true
      });
    },
    linhas: function (g, t) {
      return construirCartesiano(g, t, {
        tipoSerie: "line",
        tooltipEixo: true,
        crosshair: true,
        zoom: "x"
      });
    },
    area: function (g, t) {
      return construirCartesiano(g, t, {
        tipoSerie: "line",
        area: true,
        tooltipEixo: true,
        crosshair: true,
        zoom: "x"
      });
    },
    dispersao: function (g, t) {
      return construirCartesiano(g, t, {
        tipoSerie: "scatter",
        tooltipEixo: false,
        zoom: "xy"
      });
    },
    boxplot: construirBoxplot,
    donut: construirDonut,
    heatmap: construirHeatmap,
    pareto: construirPareto
  };

  /** Dispersão precisa de tooltip com x e y; sobrescreve o formatador. */
  function ajustarDispersao(g, option) {
    var formatoX = (g.eixo_x && g.eixo_x.formato) || "num";
    var formatoY = (g.eixo_y && g.eixo_y.formato) || "num";
    var nomeX = (g.eixo_x && g.eixo_x.nome) || "x";
    var nomeY = (g.eixo_y && g.eixo_y.nome) || "y";
    option.tooltip.formatter = function (p) {
      var v = Array.isArray(p.value) ? p.value : [null, p.value];
      return "<strong>" + escaparHtml(p.seriesName) + "</strong><br>" +
        escaparHtml(nomeX) + ": <strong>" + formatarEixo(v[0], formatoX) + "</strong><br>" +
        escaparHtml(nomeY) + ": <strong>" + formatarEixo(v[1], formatoY) + "</strong>";
    };
    return option;
  }

  function construirOption(g, t) {
    var tipo = String(g.tipo || "").toLowerCase();
    var construtor = CONSTRUTORES[tipo];
    if (!construtor) throw new Error('tipo de gráfico desconhecido: "' + g.tipo + '"');
    var option = construtor(g, t);
    if (tipo === "dispersao") ajustarDispersao(g, option);
    return option;
  }

  /* =========================================================
     12. Faixa de estatísticas (.grafico__stats)
     ========================================================= */

  var AMOSTRAS_SVG = {
    media: '<svg class="grafico__amostra" width="26" height="8" viewBox="0 0 26 8" aria-hidden="true" focusable="false"><line x1="0" y1="4" x2="26" y2="4" stroke="currentColor" stroke-width="1.8" stroke-dasharray="8 6"/></svg>',
    mediana: '<svg class="grafico__amostra" width="26" height="8" viewBox="0 0 26 8" aria-hidden="true" focusable="false"><line x1="0" y1="4" x2="26" y2="4" stroke="currentColor" stroke-width="1.8" stroke-dasharray="2 4"/></svg>',
    moda: '<svg class="grafico__amostra" width="26" height="8" viewBox="0 0 26 8" aria-hidden="true" focusable="false"><line x1="0" y1="4" x2="26" y2="4" stroke="currentColor" stroke-width="1" stroke-dasharray="none"/></svg>',
    quartis: '<svg class="grafico__amostra" width="26" height="8" viewBox="0 0 26 8" aria-hidden="true" focusable="false"><line x1="0" y1="4" x2="26" y2="4" stroke="currentColor" stroke-width="1.2" stroke-dasharray="4 4" opacity="0.75"/></svg>',
    dp: '<svg class="grafico__amostra" width="26" height="8" viewBox="0 0 26 8" aria-hidden="true" focusable="false"><rect x="0" y="1" width="26" height="6" fill="currentColor" opacity="0.18"/></svg>'
  };

  function itemEstatistica(rotulo, valor, titulo) {
    var li = criar("li", "grafico__stat");
    if (titulo) li.title = titulo;
    li.appendChild(criar("span", "grafico__stat-rotulo", rotulo));
    li.appendChild(criar("span", "grafico__stat-valor", valor));
    return li;
  }

  function itemLegendaLinha(amostraSvg, texto) {
    var li = criar("li", "grafico__linha-legenda");
    var marca = criar("span", "grafico__amostra-caixa");
    marca.innerHTML = amostraSvg;
    li.appendChild(marca);
    li.appendChild(criar("span", "grafico__linha-texto", texto));
    return li;
  }

  /** Renderiza os sete indicadores obrigatórios + CV, IQR e a legenda das linhas. */
  function renderizarEstatisticas(faixa, g) {
    if (!faixa) return;
    limpar(faixa);
    var est = g && g.estatisticas;
    if (!est || typeof est !== "object") {
      faixa.appendChild(
        criar("p", "grafico__stats-aviso", "Estatísticas não informadas para este gráfico.")
      );
      return;
    }

    var fmt = est.formato || "num";
    var un = est.unidade || "";

    var cabecalho = criar("p", "grafico__stats-variavel");
    var variavel = est.variavel || (g.estatisticas && g.estatisticas.variavel) || g.titulo || "";
    cabecalho.appendChild(criar("span", "grafico__stats-titulo", "Medidas de " + variavel));
    var complemento = "";
    if (ehNumero(est.n)) complemento = "n = " + fmtInt(est.n);
    if (un) complemento += (complemento ? " · " : "") + "unidade: " + un;
    if (complemento) {
      // Separador explícito: a faixa não depende do espaçamento do CSS.
      cabecalho.appendChild(criar("span", "grafico__stats-sep", " · "));
      cabecalho.appendChild(criar("span", "grafico__stats-n", complemento));
    }
    faixa.appendChild(cabecalho);

    var lista = criar("ul", "grafico__stats-lista");
    lista.appendChild(
      itemEstatistica("x̄ média", formatarValor(est.media, fmt, un), "Média aritmética")
    );
    lista.appendChild(
      itemEstatistica("mediana", formatarValor(est.mediana, fmt, un), "Valor central (Q2)")
    );
    lista.appendChild(
      itemEstatistica(
        "moda",
        est.moda === null || est.moda === undefined ? "amodal" : formatarValor(est.moda, fmt, un),
        "Valor mais frequente"
      )
    );
    lista.appendChild(
      itemEstatistica("σ² variância", formatarVariancia(est.variancia, fmt, un), "Variância amostral")
    );
    lista.appendChild(
      itemEstatistica("σ desvio-padrão", formatarDesvio(est.desvio_padrao, fmt, un), "Desvio-padrão amostral")
    );
    lista.appendChild(
      itemEstatistica("CV", formatarCV(est.coef_variacao), "Coeficiente de variação (σ / x̄)")
    );
    lista.appendChild(itemEstatistica("Q1", formatarValor(est.q1, fmt, un), "1º quartil"));
    lista.appendChild(itemEstatistica("Q3", formatarValor(est.q3, fmt, un), "3º quartil"));
    lista.appendChild(
      itemEstatistica("IQR", formatarValor(est.iqr, fmt, un), "Amplitude interquartil (Q3 - Q1)")
    );
    if (ehNumero(est.minimo)) {
      lista.appendChild(itemEstatistica("mínimo", formatarValor(est.minimo, fmt, un), "Menor valor"));
    }
    if (ehNumero(est.maximo)) {
      lista.appendChild(itemEstatistica("máximo", formatarValor(est.maximo, fmt, un), "Maior valor"));
    }
    faixa.appendChild(lista);

    // Legenda visual dos estilos de linha desenhados sobre o gráfico.
    var marc = g.marcadores;
    var legenda = criar("ul", "grafico__legenda-linhas");
    legenda.setAttribute("aria-label", "Legenda dos marcadores estatísticos");
    legenda.appendChild(itemLegendaLinha(AMOSTRAS_SVG.media, "Média (tracejada)"));
    legenda.appendChild(itemLegendaLinha(AMOSTRAS_SVG.mediana, "Mediana (pontilhada)"));
    legenda.appendChild(itemLegendaLinha(AMOSTRAS_SVG.moda, "Moda (sólida fina)"));
    legenda.appendChild(itemLegendaLinha(AMOSTRAS_SVG.quartis, "Q1 e Q3 (tracejado curto, cinza)"));
    legenda.appendChild(itemLegendaLinha(AMOSTRAS_SVG.dp, "Faixa ±1 desvio-padrão"));
    if (!marc) {
      legenda.appendChild(
        itemLegendaLinha("", "Neste gráfico as medidas aparecem apenas na faixa acima.")
      );
    }
    faixa.appendChild(legenda);
  }

  /* =========================================================
     13. Tabela de dados (details.grafico__tabela)
     ========================================================= */

  function renderizarTabela(details, g) {
    if (!details) return;
    // Preserva o <summary> escrito pelo template.
    var sumario = details.querySelector("summary");
    limpar(details);
    if (sumario) details.appendChild(sumario);
    else details.appendChild(criar("summary", "grafico__tabela-botao", "Ver tabela de dados"));

    var tab = g && g.tabela;
    if (!tab || !Array.isArray(tab.colunas) || !Array.isArray(tab.linhas) || !tab.linhas.length) {
      details.appendChild(criar("p", "grafico__aviso", "Tabela de dados não disponível para este gráfico."));
      return;
    }

    var rolagem = criar("div", "tabela-rolagem");
    var tabela = criar("table", "tabela tabela--grafico");
    var legenda = criar("caption", "tabela__legenda", "Dados de: " + (g.titulo || g.id || ""));
    tabela.appendChild(legenda);

    var thead = criar("thead");
    var trCab = criar("tr");
    tab.colunas.forEach(function (col, i) {
      var th = criar("th", i === 0 ? "tabela__th" : "tabela__th tabela__th--num", String(col));
      th.setAttribute("scope", "col");
      trCab.appendChild(th);
    });
    thead.appendChild(trCab);
    tabela.appendChild(thead);

    var tbody = criar("tbody");
    tab.linhas.forEach(function (linha) {
      var tr = criar("tr");
      var celulas = Array.isArray(linha) ? linha : [linha];
      celulas.forEach(function (celula, i) {
        var numerica = typeof celula === "number";
        if (i === 0) {
          var th = criar("th", "tabela__th-linha", formatarCelula(celula));
          th.setAttribute("scope", "row");
          tr.appendChild(th);
        } else {
          tr.appendChild(criar("td", numerica ? "tabela__td tabela__td--num" : "tabela__td", formatarCelula(celula)));
        }
      });
      tbody.appendChild(tr);
    });
    tabela.appendChild(tbody);
    rolagem.appendChild(tabela);
    details.appendChild(rolagem);
  }

  /* =========================================================
     14. Registro e ciclo de vida dos gráficos
     ========================================================= */

  var registros = new Map();   // id -> registro
  var instancias = new Map();  // id -> instância ECharts

  function mostrarAviso(tela, mensagem) {
    if (!tela) return;
    limpar(tela);
    var aviso = criar("p", "grafico__aviso", mensagem);
    aviso.setAttribute("role", "note");
    tela.appendChild(aviso);
  }

  function echartsDisponivel() {
    return typeof window.echarts !== "undefined" && window.echarts && typeof window.echarts.init === "function";
  }

  function desenhar(registro) {
    var g = registro.grafico;
    var tela = registro.tela;
    if (!tela) return;

    if (!echartsDisponivel()) {
      mostrarAviso(tela, "Biblioteca de gráficos não carregada; consulte a tabela de dados abaixo.");
      registro.erro = true;
      return;
    }

    try {
      var option = construirOption(g, tema());
      var instancia = instancias.get(registro.id);
      if (!instancia || instancia.isDisposed()) {
        // O aviso anterior, se houver, precisa sair antes de inicializar.
        if (registro.erro) limpar(tela);
        instancia = window.echarts.init(tela, null, {
          renderer: "svg",
          useDirtyRect: false
        });
        instancias.set(registro.id, instancia);
      }
      instancia.setOption(option, { notMerge: true, lazyUpdate: false });
      registro.erro = false;
      registro.desenhado = true;
    } catch (erro) {
      registro.erro = true;
      registro.desenhado = true; // não tentar de novo em laço
      console.warn('Gráfico "' + registro.id + '" não pôde ser desenhado:', erro);
      var instanciaAntiga = instancias.get(registro.id);
      if (instanciaAntiga && !instanciaAntiga.isDisposed()) {
        try {
          instanciaAntiga.dispose();
        } catch (e) {
          /* ignorado */
        }
      }
      instancias.delete(registro.id);
      mostrarAviso(
        tela,
        "Não foi possível desenhar este gráfico. Os dados estão na tabela abaixo."
      );
    }
  }

  function preparar(g) {
    if (!g || !g.id) return null;
    var id = String(g.id);
    var tela = document.getElementById(PREFIXO_TELA + id);
    var cartao = document.getElementById(PREFIXO_CARD + id) ||
      document.querySelector('[data-grafico="' + id.replace(/"/g, '\\"') + '"]');
    if (!tela && cartao) tela = cartao.querySelector(".grafico__tela");
    if (!cartao && tela) cartao = tela.closest(".grafico");
    if (!tela) return null;

    var registro = {
      id: id,
      grafico: g,
      tela: tela,
      cartao: cartao,
      desenhado: false,
      erro: false
    };

    if (ehNumero(g.altura) && g.altura > 80) {
      tela.style.minHeight = Math.round(g.altura) + "px";
      if (!tela.style.height) tela.style.height = Math.round(g.altura) + "px";
    } else if (!tela.style.height && !tela.offsetHeight) {
      tela.style.height = "340px";
    }

    // Faixa de estatísticas e tabela são independentes do ECharts:
    // renderizam de imediato, para o conteúdo existir mesmo sem gráfico.
    try {
      var faixa = cartao ? cartao.querySelector(".grafico__stats") : null;
      renderizarEstatisticas(faixa, g);
    } catch (erro) {
      console.warn('Faixa de estatísticas de "' + id + '" falhou:', erro);
    }
    try {
      var details = cartao ? cartao.querySelector("details.grafico__tabela") : null;
      renderizarTabela(details, g);
    } catch (erro) {
      console.warn('Tabela de "' + id + '" falhou:', erro);
    }

    registros.set(id, registro);
    return registro;
  }

  function observarEntradaNaViewport() {
    var lista = Array.from(registros.values());
    if (!lista.length) return;

    if (typeof window.IntersectionObserver !== "function") {
      lista.forEach(desenhar);
      return;
    }

    var observador = new IntersectionObserver(
      function (entradas) {
        entradas.forEach(function (entrada) {
          if (!entrada.isIntersecting) return;
          var id = entrada.target.getAttribute("data-grafico-id");
          var registro = registros.get(id);
          observador.unobserve(entrada.target);
          if (registro && !registro.desenhado) desenhar(registro);
        });
      },
      { root: null, rootMargin: "240px 0px 240px 0px", threshold: 0 }
    );

    lista.forEach(function (registro) {
      var alvo = registro.cartao || registro.tela;
      alvo.setAttribute("data-grafico-id", registro.id);
      observador.observe(alvo);
    });
  }

  function observarRedimensionamento() {
    if (typeof window.ResizeObserver !== "function") {
      window.addEventListener("resize", function () {
        redimensionarTodos();
      });
      return;
    }
    var agendado = false;
    var pendentes = new Set();
    var observador = new ResizeObserver(function (entradas) {
      entradas.forEach(function (entrada) {
        var id = entrada.target.getAttribute("data-grafico-id-tela");
        if (id) pendentes.add(id);
      });
      if (agendado) return;
      agendado = true;
      window.requestAnimationFrame(function () {
        agendado = false;
        pendentes.forEach(function (id) {
          var instancia = instancias.get(id);
          if (instancia && !instancia.isDisposed()) {
            try {
              instancia.resize();
            } catch (erro) {
              /* ignorado */
            }
          }
        });
        pendentes.clear();
      });
    });
    registros.forEach(function (registro) {
      registro.tela.setAttribute("data-grafico-id-tela", registro.id);
      observador.observe(registro.tela);
    });
  }

  function redimensionarTodos() {
    instancias.forEach(function (instancia) {
      if (instancia && !instancia.isDisposed()) {
        try {
          instancia.resize();
        } catch (erro) {
          /* ignorado */
        }
      }
    });
  }

  function desenharTodos() {
    registros.forEach(function (registro) {
      if (!registro.desenhado) desenhar(registro);
    });
  }

  /** Redesenha o que já está na tela (troca de tema). Gráficos que já
      falharam não são tentados de novo: o aviso discreto permanece. */
  function redesenharTodos() {
    registros.forEach(function (registro) {
      if (registro.erro) return;
      if (registro.desenhado || instancias.has(registro.id)) desenhar(registro);
    });
  }

  /* =========================================================
     15. Alternância de tema
     ========================================================= */

  function aplicarTema(novo, gravar) {
    temaAtual = normalizarTema(novo);
    try {
      document.documentElement.dataset.tema = temaAtual;
    } catch (erro) {
      document.documentElement.setAttribute("data-tema", temaAtual);
    }
    if (gravar) gravarArmazenado(CHAVE_TEMA, temaAtual);
    atualizarBotaoTema();
    redesenharTodos();
  }

  function atualizarBotaoTema() {
    var botao = document.getElementById(ID_BOTAO_TEMA);
    if (!botao) return;
    var escuro = temaAtual === "escuro";
    botao.setAttribute("aria-pressed", escuro ? "true" : "false");
    botao.setAttribute(
      "aria-label",
      escuro ? "Mudar para o tema claro" : "Mudar para o tema escuro"
    );
    botao.setAttribute("title", escuro ? "Tema escuro ativo" : "Tema claro ativo");
    var texto = primeiro(SELETORES_TEXTO_TEMA, botao);
    if (texto) texto.textContent = escuro ? "Tema claro" : "Tema escuro";
  }

  function iniciarTema() {
    var gravado = lerArmazenado(CHAVE_TEMA);
    var atributo = document.documentElement.getAttribute("data-tema");
    var inicial = gravado || atributo || temaPreferidoDoSistema();
    temaAtual = normalizarTema(inicial);
    try {
      document.documentElement.dataset.tema = temaAtual;
    } catch (erro) {
      document.documentElement.setAttribute("data-tema", temaAtual);
    }
    atualizarBotaoTema();

    var botao = document.getElementById(ID_BOTAO_TEMA);
    if (botao) {
      botao.addEventListener("click", function () {
        aplicarTema(temaAtual === "escuro" ? "claro" : "escuro", true);
      });
    }

    // Sem preferência gravada, acompanhar o sistema.
    if (!gravado) {
      try {
        var consulta = window.matchMedia("(prefers-color-scheme: dark)");
        var reagir = function (evento) {
          if (lerArmazenado(CHAVE_TEMA)) return;
          aplicarTema(evento.matches ? "escuro" : "claro", false);
        };
        if (typeof consulta.addEventListener === "function") {
          consulta.addEventListener("change", reagir);
        } else if (typeof consulta.addListener === "function") {
          consulta.addListener(reagir);
        }
      } catch (erro) {
        /* ignorado */
      }
    }
  }

  /* =========================================================
     16. Navegação, voltar ao topo e impressão
     ========================================================= */

  function ativarNavegacao() {
    var secoes = Array.prototype.slice.call(document.querySelectorAll(".secao[id]"));
    var itens = new Map();
    Array.prototype.forEach.call(document.querySelectorAll(".navegacao__item"), function (a) {
      var href = a.getAttribute("href") || "";
      if (href.charAt(0) === "#" && href.length > 1) itens.set(href.slice(1), a);
    });
    if (!secoes.length || !itens.size) return;

    function marcar(id) {
      itens.forEach(function (item, chave) {
        var ativo = chave === id;
        item.classList.toggle("is-ativo", ativo);
        if (ativo) item.setAttribute("aria-current", "true");
        else item.removeAttribute("aria-current");
      });
    }

    if (typeof window.IntersectionObserver !== "function") {
      marcar(secoes[0].id);
      return;
    }

    var visiveis = new Set();
    var observador = new IntersectionObserver(
      function (entradas) {
        entradas.forEach(function (entrada) {
          if (entrada.isIntersecting) visiveis.add(entrada.target.id);
          else visiveis.delete(entrada.target.id);
        });
        // Entre as seções visíveis, destacar a primeira na ordem do documento.
        for (var i = 0; i < secoes.length; i += 1) {
          if (visiveis.has(secoes[i].id)) {
            marcar(secoes[i].id);
            return;
          }
        }
      },
      { rootMargin: "-20% 0px -60% 0px", threshold: 0 }
    );
    secoes.forEach(function (s) {
      observador.observe(s);
    });
  }

  function ativarVoltarAoTopo() {
    var botao = primeiro(SELETORES_BOTAO_TOPO);
    if (!botao) return;
    botao.addEventListener("click", function (evento) {
      evento.preventDefault();
      try {
        window.scrollTo({ top: 0, behavior: SEM_MOVIMENTO ? "auto" : "smooth" });
      } catch (erro) {
        window.scrollTo(0, 0);
      }
      var alvo = document.querySelector("h1") || document.body;
      if (alvo && typeof alvo.focus === "function") {
        alvo.setAttribute("tabindex", "-1");
        alvo.focus({ preventScroll: true });
      }
    });

    var agendado = false;
    function atualizar() {
      agendado = false;
      var visivel = (window.pageYOffset || document.documentElement.scrollTop || 0) > 600;
      botao.classList.toggle("is-visivel", visivel);
      botao.setAttribute("aria-hidden", visivel ? "false" : "true");
    }
    window.addEventListener(
      "scroll",
      function () {
        if (agendado) return;
        agendado = true;
        window.requestAnimationFrame(atualizar);
      },
      { passive: true }
    );
    atualizar();
  }

  function prepararImpressao() {
    function antes() {
      // Gráficos ainda não desenhados ficariam em branco no PDF.
      desenharTodos();
      redimensionarTodos();
    }
    window.addEventListener("beforeprint", antes);
    window.addEventListener("afterprint", function () {
      redimensionarTodos();
    });
    try {
      var consulta = window.matchMedia("print");
      var reagir = function (evento) {
        if (evento.matches) antes();
        else redimensionarTodos();
      };
      if (typeof consulta.addEventListener === "function") consulta.addEventListener("change", reagir);
      else if (typeof consulta.addListener === "function") consulta.addListener(reagir);
    } catch (erro) {
      /* ignorado */
    }
  }

  /* =========================================================
     17. Inicialização
     ========================================================= */

  var graficos = [];
  var meta = {};

  function iniciar() {
    graficos = lerGraficos();
    meta = lerMeta();

    iniciarTema();
    ativarNavegacao();
    ativarVoltarAoTopo();

    var ignorados = [];
    graficos.forEach(function (g) {
      try {
        var registro = preparar(g);
        if (!registro) ignorados.push(g && g.id ? g.id : "(sem id)");
      } catch (erro) {
        console.warn("Falha ao preparar o cartão de gráfico:", erro);
        ignorados.push(g && g.id ? g.id : "(sem id)");
      }
    });
    if (ignorados.length) {
      console.info("Cartões não encontrados no HTML para: " + ignorados.join(", "));
    }

    observarEntradaNaViewport();
    observarRedimensionamento();
    prepararImpressao();

    // Se o navegador abrir direto num hash, garantir o gráfico daquela seção.
    if (window.location.hash) {
      var alvo = document.querySelector(window.location.hash);
      if (alvo) {
        registros.forEach(function (registro) {
          if (alvo.contains(registro.cartao || registro.tela) && !registro.desenhado) {
            desenhar(registro);
          }
        });
      }
    }

    window.RELATORIO.graficos = graficos;
    window.RELATORIO.meta = meta;
    window.RELATORIO.pronto = true;
  }

  // Objeto de inspeção no console, disponível desde o início.
  window.RELATORIO = {
    versao: "1.0",
    pronto: false,
    graficos: graficos,
    meta: meta,
    registros: registros,
    instancias: instancias,
    paleta: {
      slots: SLOTS,
      status: STATUS,
      sequencial: SEQUENCIAL,
      divergente: DIVERGENTE,
      temas: TEMAS
    },
    get tema() {
      return temaAtual;
    },
    cor: function (especificacao, indice) {
      return resolverCor(especificacao, temaAtual, indice || 0);
    },
    formatar: formatarValor,
    definirTema: function (novo) {
      aplicarTema(novo, true);
      return temaAtual;
    },
    option: function (id) {
      var registro = registros.get(String(id));
      if (!registro) return null;
      try {
        return construirOption(registro.grafico, tema());
      } catch (erro) {
        return { erro: String(erro) };
      }
    },
    desenhar: function (id) {
      var registro = registros.get(String(id));
      if (registro) desenhar(registro);
      return registro || null;
    },
    desenharTodos: desenharTodos,
    redesenharTodos: redesenharTodos,
    redimensionarTodos: redimensionarTodos,
    tiposSuportados: Object.keys(CONSTRUTORES)
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      try {
        iniciar();
      } catch (erro) {
        console.error("Falha na inicialização do relatório:", erro);
      }
    });
  } else {
    try {
      iniciar();
    } catch (erro) {
      console.error("Falha na inicialização do relatório:", erro);
    }
  }
})();
