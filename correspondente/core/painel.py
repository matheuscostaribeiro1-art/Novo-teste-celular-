"""Painel HTML da esteira — o que está com quem, há quanto tempo, e o que
precisa sair hoje. Gera um arquivo único, sem dependência externa.
"""

from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path

from . import checklist, config, followup, store, tipos_doc
from .util import competencia_legivel, formata_cnpj, moeda, parse_data, plural

COLUNAS = [
    ("Entrada", ["recebido", "em_triagem"], "Chegou do parceiro, ainda não triado"),
    ("Falta documento", ["pendente_documentos"], "Trava o envio — cobrança com o indicador"),
    ("Pronto para enviar", ["pronto_envio"], "Dossiê fechado, falta escolher gerentes"),
    ("Com os gerentes", ["em_analise"], "Enviado, aguardando retorno"),
    ("Pré-aprovado", ["pre_aprovado", "pendente_complementar"], "Banco avançou e pediu mais coisa"),
    ("Call e proposta", ["call_agendada", "proposta_emitida"], "Dono na mesa com o gerente"),
    ("Formalização", ["em_formalizacao"], "Assinatura e liberação"),
]

ROTULOS = {
    "recebido": "Recebido",
    "em_triagem": "Em triagem",
    "pendente_documentos": "Falta documento",
    "pronto_envio": "Pronto p/ envio",
    "em_analise": "Com os gerentes",
    "pre_aprovado": "Pré-aprovado",
    "pendente_complementar": "Falta complementar",
    "call_agendada": "Call agendada",
    "proposta_emitida": "Proposta emitida",
    "em_formalizacao": "Formalização",
    "liberado": "Liberado",
    "recusado": "Recusado",
    "standby": "Standby",
}

CSS = """
:root {
  --papel: #EDEFEA;
  --superficie: #F8F9F5;
  --superficie-2: #E3E7DF;
  --tinta: #131A16;
  --tinta-2: #4A554E;
  --tinta-3: #74807A;
  --linha: #CDD4CB;
  --cofre: #1E4636;
  --cofre-suave: #DCE8E0;
  --latao: #8A6B26;
  --critico: #9E2A1E;
  --critico-fundo: #F6DFDB;
  --atencao: #7A5600;
  --atencao-fundo: #F5E9CE;
  --ok: #24614A;
  --ok-fundo: #DBEBE1;
  --sombra: 0 1px 2px rgba(19, 26, 22, .06), 0 6px 18px -12px rgba(19, 26, 22, .28);
  --display: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
  --ui: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
  --dados: ui-monospace, "SF Mono", "Cascadia Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --papel: #0E1311;
    --superficie: #161D19;
    --superficie-2: #1E2721;
    --tinta: #E7EBE5;
    --tinta-2: #A9B4AC;
    --tinta-3: #7C877F;
    --linha: #2A342D;
    --cofre: #79B899;
    --cofre-suave: #1B2C24;
    --latao: #C7A45C;
    --critico: #E9887A;
    --critico-fundo: #34211D;
    --atencao: #DDB65E;
    --atencao-fundo: #322A1C;
    --ok: #7BC3A2;
    --ok-fundo: #16291F;
    --sombra: 0 1px 2px rgba(0,0,0,.4), 0 8px 20px -14px rgba(0,0,0,.8);
  }
}
:root[data-theme="dark"] {
  --papel: #0E1311;
  --superficie: #161D19;
  --superficie-2: #1E2721;
  --tinta: #E7EBE5;
  --tinta-2: #A9B4AC;
  --tinta-3: #7C877F;
  --linha: #2A342D;
  --cofre: #79B899;
  --cofre-suave: #1B2C24;
  --latao: #C7A45C;
  --critico: #E9887A;
  --critico-fundo: #34211D;
  --atencao: #DDB65E;
  --atencao-fundo: #322A1C;
  --ok: #7BC3A2;
  --ok-fundo: #16291F;
  --sombra: 0 1px 2px rgba(0,0,0,.4), 0 8px 20px -14px rgba(0,0,0,.8);
}

* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--papel);
  color: var(--tinta);
  font-family: var(--ui);
  font-size: 15px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
.envelope { max-width: 1180px; margin: 0 auto; padding: 32px 20px 96px; }

.cabecalho { display: flex; flex-wrap: wrap; gap: 20px; align-items: flex-end; justify-content: space-between;
  padding-bottom: 20px; border-bottom: 2px solid var(--cofre); }
.marca { display: flex; flex-direction: column; gap: 2px; }
.marca .eyebrow { font-size: 11px; letter-spacing: .16em; text-transform: uppercase; color: var(--latao); font-weight: 600; }
h1 { font-family: var(--display); font-size: clamp(28px, 4vw, 40px); margin: 0; letter-spacing: -.01em; text-wrap: balance; }
.carimbo { font-family: var(--dados); font-size: 12px; color: var(--tinta-3); }

.placar { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 1px;
  background: var(--linha); border: 1px solid var(--linha); margin: 24px 0 0; }
.placar .celula { background: var(--superficie); padding: 14px 16px; }
.placar .n { font-family: var(--dados); font-size: 30px; font-variant-numeric: tabular-nums; line-height: 1.1; }
.placar .rot { font-size: 11px; letter-spacing: .1em; text-transform: uppercase; color: var(--tinta-3); margin-top: 4px; }
.placar .celula.alerta .n { color: var(--critico); }
.placar .celula.destaque .n { color: var(--cofre); }

section { margin-top: 44px; }
.titulo-secao { display: flex; align-items: baseline; gap: 12px; margin-bottom: 4px; }
h2 { font-family: var(--display); font-size: 22px; margin: 0; font-weight: 600; }
.sub { color: var(--tinta-3); font-size: 13px; margin: 0 0 16px; }

.fila { display: flex; flex-direction: column; gap: 10px; }
.acao { background: var(--superficie); border: 1px solid var(--linha); border-left: 4px solid var(--tinta-3);
  border-radius: 2px; box-shadow: var(--sombra); }
.acao.alta { border-left-color: var(--critico); }
.acao.media { border-left-color: var(--atencao); }
.acao.baixa { border-left-color: var(--tinta-3); }
.acao > summary { list-style: none; cursor: pointer; padding: 12px 16px; display: grid;
  grid-template-columns: 1fr auto; gap: 4px 16px; align-items: center; }
.acao > summary::-webkit-details-marker { display: none; }
.acao > summary:hover { background: var(--superficie-2); }
.acao .linha1 { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.acao .quem { font-weight: 600; }
.acao .empresa { color: var(--tinta-2); font-size: 13px; }
.acao .meta { font-family: var(--dados); font-size: 12px; color: var(--tinta-3); text-align: right; white-space: nowrap; }
.acao .corpo { padding: 0 16px 16px; border-top: 1px dashed var(--linha); margin-top: 4px; padding-top: 12px; }
.acao pre { font-family: var(--ui); font-size: 13.5px; white-space: pre-wrap; background: var(--papel);
  border: 1px solid var(--linha); padding: 12px 14px; margin: 8px 0 0; border-radius: 2px; overflow-x: auto; }
.acao .assunto { font-family: var(--dados); font-size: 12px; color: var(--tinta-2); }

.pill { font-size: 11px; letter-spacing: .06em; text-transform: uppercase; font-weight: 600;
  padding: 2px 8px; border-radius: 999px; border: 1px solid transparent; white-space: nowrap; }
.pill.critico { background: var(--critico-fundo); color: var(--critico); border-color: var(--critico); }
.pill.atencao { background: var(--atencao-fundo); color: var(--atencao); border-color: var(--atencao); }
.pill.ok { background: var(--ok-fundo); color: var(--ok); border-color: var(--ok); }
.pill.neutro { background: var(--superficie-2); color: var(--tinta-2); border-color: var(--linha); }
.pill.canal { background: transparent; color: var(--tinta-3); border-color: var(--linha); }

.botao { font: inherit; font-size: 12px; padding: 5px 12px; border: 1px solid var(--cofre); color: var(--cofre);
  background: transparent; border-radius: 2px; cursor: pointer; }
.botao:hover { background: var(--cofre-suave); }
.botao:focus-visible { outline: 2px solid var(--latao); outline-offset: 2px; }

.esteira { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(198px, 1fr);
  gap: 12px; overflow-x: auto; padding-bottom: 10px; }
.coluna { background: var(--superficie); border: 1px solid var(--linha); border-radius: 2px; padding: 10px;
  display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.coluna h3 { font-size: 12px; letter-spacing: .09em; text-transform: uppercase; margin: 0; color: var(--tinta-2);
  display: flex; justify-content: space-between; gap: 8px; }
.coluna h3 .cont { font-family: var(--dados); color: var(--latao); }
.coluna .dica { font-size: 11.5px; color: var(--tinta-3); margin: -4px 0 2px; line-height: 1.35; }
.card { background: var(--papel); border: 1px solid var(--linha); border-radius: 2px; padding: 10px; }
.card .nome { font-weight: 600; font-size: 13.5px; line-height: 1.3; }
.card .valor { font-family: var(--dados); font-size: 12px; color: var(--cofre); margin-top: 2px; }
.card .rodape { display: flex; justify-content: space-between; align-items: center; gap: 6px; margin-top: 8px;
  font-family: var(--dados); font-size: 11px; color: var(--tinta-3); }
.barra { height: 4px; background: var(--superficie-2); margin-top: 8px; border-radius: 2px; overflow: hidden; }
.barra i { display: block; height: 100%; background: var(--cofre); }
.vazio { color: var(--tinta-3); font-size: 12px; font-style: italic; padding: 4px 0; }

.tabela-caixa { overflow-x: auto; border: 1px solid var(--linha); background: var(--superficie); }
table { border-collapse: collapse; width: 100%; font-size: 13.5px; min-width: 780px; }
th { text-align: left; font-size: 11px; letter-spacing: .09em; text-transform: uppercase; color: var(--tinta-3);
  padding: 10px 12px; border-bottom: 1px solid var(--linha); font-weight: 600; white-space: nowrap; }
td { padding: 10px 12px; border-bottom: 1px solid var(--linha); vertical-align: top; }
tr:last-child td { border-bottom: none; }
td.num { font-family: var(--dados); font-variant-numeric: tabular-nums; white-space: nowrap; }
td .secundario { color: var(--tinta-3); font-size: 12px; }
.parada { color: var(--critico); font-weight: 600; }

.agenda { display: flex; flex-direction: column; gap: 8px; }
.agenda .item { display: grid; grid-template-columns: 88px 1fr auto; gap: 14px; align-items: center;
  background: var(--superficie); border: 1px solid var(--linha); padding: 10px 14px; }
.agenda .quando { font-family: var(--dados); font-size: 12px; color: var(--cofre); font-weight: 600; }
.agenda .quem { font-size: 12px; color: var(--tinta-2); }

footer { margin-top: 56px; padding-top: 18px; border-top: 1px solid var(--linha); color: var(--tinta-3); font-size: 12px; }
footer code { font-family: var(--dados); color: var(--tinta-2); }
@media (max-width: 620px) {
  .acao > summary { grid-template-columns: 1fr; }
  .acao .meta { text-align: left; }
  .agenda .item { grid-template-columns: 1fr; gap: 4px; }
}
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
"""

JS = """
document.addEventListener('click', function (ev) {
  var b = ev.target.closest('[data-copiar]');
  if (!b) return;
  var alvo = document.getElementById(b.getAttribute('data-copiar'));
  if (!alvo || !navigator.clipboard) return;
  navigator.clipboard.writeText(alvo.textContent).then(function () {
    var antes = b.textContent;
    b.textContent = 'Copiado';
    setTimeout(function () { b.textContent = antes; }, 1600);
  });
});
"""


def _e(texto) -> str:
    return html.escape(str(texto if texto is not None else ""))


def _pct(empresa: dict) -> int:
    try:
        return checklist.resumo(checklist.avalia(empresa))["percentual"]
    except Exception:
        return 0


def _dias_parada(empresa: dict) -> int:
    from .util import dias_uteis_entre

    d = parse_data(store.status_desde(empresa))
    return dias_uteis_entre(d, date.today()) if d else 0


def _card(empresa: dict) -> str:
    pct = _pct(empresa)
    dias = _dias_parada(empresa)
    classe = "parada" if dias >= 5 else ""
    return f"""<div class="card">
  <div class="nome">{_e(empresa['razao_social'])}</div>
  <div class="valor">{_e(moeda(empresa.get('necessidade')))}</div>
  <div class="barra"><i style="width:{pct}%"></i></div>
  <div class="rodape"><span>{pct}% doc</span><span class="{classe}">{dias}d parada</span></div>
</div>"""


def _acao(a: followup.Acao, indice: int) -> str:
    tem_texto = bool(a.mensagem)
    ident = f"msg{indice}"
    canal = {"email": "e-mail", "whatsapp": "WhatsApp"}.get(a.canal, a.canal)
    pill = {"alta": "critico", "media": "atencao", "baixa": "neutro"}[a.prioridade]
    rot = {"cobrar_gerente": "Gerente", "cobrar_parceiro": "Parceiro", "cobrar_empresa": "Empresa",
           "interno": "Sua mesa", "documento": "Documento"}.get(a.tipo, a.tipo)
    corpo = ""
    if tem_texto:
        contato = a.whatsapp if a.canal == "whatsapp" else a.para
        corpo = f"""<div class="corpo">
  <div class="assunto">{_e(canal)} · {_e(contato)}{(' · ' + _e(a.assunto)) if a.assunto else ''}</div>
  <pre id="{ident}">{_e(a.mensagem)}</pre>
  <p style="margin:10px 0 0"><button class="botao" type="button" data-copiar="{ident}">Copiar mensagem</button></p>
</div>"""
    else:
        corpo = f'<div class="corpo"><p class="sub" style="margin:0">{_e(a.contexto)}</p></div>'

    return f"""<details class="acao {a.prioridade}">
  <summary>
    <span class="linha1">
      <span class="pill {pill}">{_e(rot)}</span>
      <span class="quem">{_e(a.titulo)}</span>
      <span class="empresa">· {_e(a.empresa_nome)}</span>
    </span>
    <span class="meta">{_e(a.contexto)}</span>
  </summary>
  {corpo}
</details>"""


def _tabela(empresas: list[dict]) -> str:
    linhas = []
    for e in sorted(empresas, key=lambda x: (-_dias_parada(x), x["razao_social"])):
        pct = _pct(e)
        dias = _dias_parada(e)
        gerentes = [config.gerentes().get(v["gerente"], {}).get("nome", v["gerente"]) for v in e.get("envios", [])]
        parceiro = config.parceiros().get(e.get("parceiro", ""), {}).get("nome", "—")
        status = e.get("status", "")
        pill = "ok" if status in {"liberado", "proposta_emitida", "em_formalizacao"} else (
            "critico" if status in {"recusado", "pendente_documentos"} else "neutro")
        linhas.append(f"""<tr>
  <td><strong>{_e(e['razao_social'])}</strong><div class="secundario">{_e(formata_cnpj(e.get('cnpj', '')))} · {_e(e.get('setor') or '—')}</div></td>
  <td><span class="pill {pill}">{_e(ROTULOS.get(status, status))}</span></td>
  <td class="num">{_e(moeda(e.get('necessidade')))}</td>
  <td class="num">{pct}%</td>
  <td class="num {'parada' if dias >= 5 else ''}">{dias}d</td>
  <td>{_e(', '.join(gerentes) or '—')}<div class="secundario">indicou: {_e(parceiro)}</div></td>
  <td>{_e(e.get('proximo_passo') or '—')}</td>
</tr>""")
    return f"""<div class="tabela-caixa"><table>
<thead><tr><th>Empresa</th><th>Status</th><th>Necessidade</th><th>Doc</th><th>Parada</th>
<th>Gerentes acionados</th><th>Próximo passo</th></tr></thead>
<tbody>{''.join(linhas) or '<tr><td colspan="7" class="vazio">Nenhuma empresa no pipeline.</td></tr>'}</tbody>
</table></div>"""


def monta(titulo: str = "Mesa de Crédito") -> tuple[str, str, str]:
    """Devolve (titulo, css+js, corpo) para compor arquivo local ou artifact."""
    b = followup.brief()
    empresas = list(store.todas())
    ativas = [e for e in empresas if e.get("status") not in store.STATUS_ENCERRADOS]
    acoes = b["acoes"]
    urgentes = b["urgentes"]
    aguardando_gerente = sum(
        1 for e in ativas for v in e.get("envios", []) if v.get("resposta") in (None, "", "pendente")
    )
    volume = sum(e.get("necessidade") or 0 for e in ativas)
    hoje_fmt = date.today().strftime("%d/%m/%Y")

    placar = f"""<div class="placar">
  <div class="celula"><div class="n">{len(ativas)}</div><div class="rot">Empresas na esteira</div></div>
  <div class="celula {'alerta' if urgentes else ''}"><div class="n">{len(urgentes)}</div><div class="rot">Atrasos críticos</div></div>
  <div class="celula"><div class="n">{len(acoes)}</div><div class="rot">Ações hoje</div></div>
  <div class="celula"><div class="n">{aguardando_gerente}</div><div class="rot">Aguardando gerente</div></div>
  <div class="celula destaque"><div class="n">{_e(moeda(volume))}</div><div class="rot">Volume em análise</div></div>
</div>"""

    fila = "".join(_acao(a, i) for i, a in enumerate(acoes)) or '<p class="vazio">Nada vencido hoje. Esteira em dia.</p>'

    colunas = []
    for nome, estados, dica in COLUNAS:
        na_coluna = [e for e in ativas if e.get("status") in estados]
        cards = "".join(_card(e) for e in na_coluna) or '<p class="vazio">—</p>'
        colunas.append(f"""<div class="coluna">
  <h3><span>{_e(nome)}</span><span class="cont">{len(na_coluna)}</span></h3>
  <p class="dica">{_e(dica)}</p>
  {cards}
</div>""")

    agenda = []
    for c in b["calls"]:
        quando = parse_data(c["data"])
        rotulo = "hoje" if c["dias_ate"] == 0 else ("amanhã" if c["dias_ate"] == 1 else f"em {c['dias_ate']}d")
        agenda.append(f"""<div class="item">
  <span class="quando">{quando.strftime('%d/%m')} {_e(c['hora'])}</span>
  <span><strong>{_e(c['empresa_nome'])}</strong> com {_e(c['gerente'])} ({_e(c['instituicao'])})
    <div class="quem">acompanha: {_e(c['responsavel'])}{(' · ' + _e(c['preparo'])) if c['preparo'] else ''}</div></span>
  <span class="pill neutro">{_e(rotulo)}</span>
</div>""")
    agenda_html = "".join(agenda) or '<p class="vazio">Nenhuma call marcada nos próximos 7 dias.</p>'

    corpo = f"""<div class="envelope">
<header class="cabecalho">
  <div class="marca">
    <span class="eyebrow">Correspondente bancário · crédito PJ</span>
    <h1>{_e(titulo)}</h1>
  </div>
  <div class="carimbo">Fechamento de {hoje_fmt}</div>
</header>

{placar}

<section>
  <div class="titulo-secao"><h2>Sai hoje</h2></div>
  <p class="sub">Cobrança vencida pelo SLA de cada etapa. Abra o item e o texto já está escrito — um a um, nunca em cópia.</p>
  <div class="fila">{fila}</div>
</section>

<section>
  <div class="titulo-secao"><h2>Esteira</h2></div>
  <p class="sub">Cada cartão mostra o quanto do dossiê está completo e há quantos dias úteis a empresa não anda.</p>
  <div class="esteira">{''.join(colunas)}</div>
</section>

<section>
  <div class="titulo-secao"><h2>Calls da semana</h2></div>
  <p class="sub">Quem conduz a call é outra pessoa — aqui fica só o que você precisa preparar e confirmar antes.</p>
  <div class="agenda">{agenda_html}</div>
</section>

<section>
  <div class="titulo-secao"><h2>Todas as empresas</h2></div>
  <p class="sub">{plural(len(empresas), 'empresa cadastrada', 'empresas cadastradas')}, ordenadas pelo tempo parado.</p>
  {_tabela(empresas)}
</section>

<footer>
  Gerado por <code>corresp painel</code> a partir dos arquivos em <code>pipeline/</code>.
  Rode <code>corresp hoje</code> no terminal para a mesma fila em texto.
</footer>
</div>"""

    return titulo, f"<style>{CSS}</style>", corpo


def gera(destino: Path | None = None, artifact: Path | None = None, titulo: str = "Mesa de Crédito") -> Path:
    titulo_, estilo, corpo = monta(titulo)
    script = f"<script>{JS}</script>"

    if artifact:
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(
            f"<title>{_e(titulo_)}</title>\n{estilo}\n{corpo}\n{script}\n", encoding="utf-8"
        )

    destino = destino or (config.SAIDA / "painel.html")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        "<!doctype html>\n<html lang=\"pt-BR\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{_e(titulo_)}</title>\n{estilo}\n</head>\n<body>\n{corpo}\n{script}\n</body>\n</html>\n",
        encoding="utf-8",
    )
    return destino
