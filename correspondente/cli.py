#!/usr/bin/env python3
"""corresp — mesa de operação do correspondente bancário.

Uso rápido:
    ./corresp hoje                       o que precisa sair agora
    ./corresp triagem acme --aplicar     confere e renomeia os anexos
    ./corresp gerentes acme              para quem vale mandar
    ./corresp enviar acme -g bruno_itau,carla_santander
    ./corresp painel                     gera o painel HTML
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import checklist, config, envios, followup, painel, store, tipos_doc, triagem  # noqa: E402
from core.util import competencia_legivel, formata_cnpj, moeda, plural, slug  # noqa: E402

CORES = {
    "reset": "\033[0m", "forte": "\033[1m", "apagado": "\033[2m",
    "vermelho": "\033[31m", "verde": "\033[32m", "amarelo": "\033[33m",
    "azul": "\033[36m", "roxo": "\033[35m",
}


def c(texto: str, cor: str) -> str:
    if not sys.stdout.isatty():
        return texto
    return f"{CORES.get(cor, '')}{texto}{CORES['reset']}"


def titulo(texto: str) -> None:
    print(f"\n{c(texto, 'forte')}\n{c('─' * min(len(texto), 72), 'apagado')}")


def marca(situacao: str) -> str:
    return {
        "ok": c("✓", "verde"),
        "faltando": c("✗", "vermelho"),
        "insuficiente": c("!", "amarelo"),
        "problema": c("!", "amarelo"),
    }.get(situacao, "·")


# ------------------------------------------------------------------ comandos


def cmd_nova(args) -> None:
    empresa = store.nova(
        args.razao_social,
        cnpj=args.cnpj or "",
        setor=args.setor or "",
        faturamento_anual=args.faturamento,
        necessidade=args.necessidade,
        produto=args.produto,
        garantia=args.garantia,
        parceiro=args.parceiro or "",
        checklist_pacote=args.pacote,
        qtd_socios=args.socios,
        contato_empresa={"nome": args.contato or "", "email": args.contato_email or "",
                         "whatsapp": args.contato_whatsapp or ""},
        restricoes={"serasa": bool(args.serasa), "protestos": False},
    )
    print(f"{c('✓', 'verde')} {empresa['razao_social']} cadastrada como {c(empresa['slug'], 'azul')}")
    print(f"  Próximo passo: {empresa['proximo_passo']}")
    pasta = f"inbox/{empresa['slug']}/"
    print(f"  Jogue os anexos em {c(pasta, 'azul')} e rode: corresp triagem {empresa['slug']} --aplicar")


def cmd_lista(args) -> None:
    empresas = list(store.todas())
    if args.ativas:
        empresas = [e for e in empresas if e.get("status") not in store.STATUS_ENCERRADOS]
    if not empresas:
        print("Nenhuma empresa no pipeline. Use: corresp nova \"Razão Social\"")
        return
    titulo(f"{plural(len(empresas), 'empresa', 'empresas')} no pipeline")
    for e in sorted(empresas, key=lambda x: x.get("status", "")):
        pct = checklist.resumo(checklist.avalia(e))["percentual"]
        cor = "verde" if pct == 100 else ("amarelo" if pct >= 60 else "vermelho")
        print(f"  {c(e['slug'].ljust(26), 'azul')} {painel.ROTULOS.get(e.get('status'), '').ljust(18)} "
              f"{c(str(pct).rjust(3) + '%', cor)} doc   {moeda(e.get('necessidade'))}")


def cmd_ver(args) -> None:
    e = store.resolve(args.empresa)
    titulo(f"{e['razao_social']}  ({e['slug']})")
    print(f"  CNPJ           {formata_cnpj(e.get('cnpj', '')) or '—'}")
    print(f"  Setor          {e.get('setor') or '—'}")
    print(f"  Faturamento    {moeda(e.get('faturamento_anual'))}/ano")
    print(f"  Necessidade    {moeda(e.get('necessidade'))} · {e.get('produto', '')}")
    print(f"  Status         {c(painel.ROTULOS.get(e.get('status'), ''), 'roxo')} desde {store.status_desde(e)}")
    print(f"  Parceiro       {config.parceiros().get(e.get('parceiro', ''), {}).get('nome', '—')}")
    print(f"  Próximo passo  {e.get('proximo_passo') or '—'}")

    if e.get("envios"):
        titulo("Envios")
        for v in e["envios"]:
            g = config.gerentes().get(v["gerente"], {"nome": v["gerente"], "instituicao": ""})
            resposta = v.get("resposta") or "sem retorno"
            cor = {"pre_aprovado": "verde", "proposta": "verde", "recusado": "vermelho"}.get(resposta, "amarelo")
            print(f"  {v['enviado_em']}  {g['nome'].ljust(24)} {g.get('instituicao', '').ljust(18)} "
                  f"{c(resposta, cor)}")
            for n in v.get("notas", []):
                print(f"      {c('↳ ' + n['texto'], 'apagado')}")

    if e.get("calls"):
        titulo("Calls")
        for call in e["calls"]:
            g = config.gerentes().get(call.get("gerente", ""), {})
            print(f"  {call.get('data')} {call.get('hora', '')}  {g.get('nome', '')} "
                  f"· acompanha: {call.get('responsavel', '—')}")

    titulo("Histórico")
    for ev in e.get("eventos", [])[-12:]:
        print(f"  {c(ev['data'], 'apagado')}  {ev['texto']}")


def cmd_triagem(args) -> None:
    e = store.resolve(args.empresa)
    origem = Path(args.inbox) if args.inbox else config.INBOX / e["slug"]
    if not origem.exists():
        print(f"{c('✗', 'vermelho')} pasta não encontrada: {origem}")
        print(f"  Crie e jogue os anexos do e-mail lá: mkdir -p {origem}")
        return

    resultados = triagem.triagem_pasta(origem, e["slug"], args.leva, aplicar=args.aplicar)
    if not resultados:
        print("Nenhum arquivo suportado encontrado em " + str(origem))
        return

    titulo(f"Triagem — {e['razao_social']} ({len(resultados)} arquivos)")
    for a in resultados:
        cabeca = c("?", "vermelho") if a.tipo == "OUTROS" else (
            c("!", "amarelo") if a.alertas else c("✓", "verde"))
        print(f"\n  {cabeca} {c(a.origem.name, 'apagado')}")
        print(f"      → {c(a.nome_final, 'azul')}")
        detalhe = a.legivel
        if a.competencia:
            detalhe += f" · {competencia_legivel(a.competencia)}"
        if a.emissao:
            detalhe += f" · emitido {a.emissao.strftime('%d/%m/%Y')}"
        print(f"      {detalhe}")
        for alerta in a.alertas:
            cor = "vermelho" if alerta.startswith("VENCIDO") or "não identificado" in alerta else "amarelo"
            print(f"      {c('▲ ' + alerta, cor)}")

    if args.aplicar:
        registros = [triagem.para_registro(a, args.leva) for a in resultados if a.tipo != "OUTROS"]
        existentes = {d["arquivo"] for d in e.get("documentos", [])}
        novos = [r for r in registros if r["arquivo"] not in existentes]
        e.setdefault("documentos", []).extend(novos)
        store.registra_evento(e, "triagem", f"Triagem: {len(novos)} documento(s) classificados e renomeados")

        itens = checklist.avalia(e)
        res = checklist.resumo(itens)
        store.muda_status(e, "pronto_envio" if res["pronto"] else "pendente_documentos")
        e["proximo_passo"] = (
            "Escolher gerentes e enviar" if res["pronto"]
            else f"Cobrar {len(res['bloqueios'])} documento(s) com o parceiro"
        )
        store.salva(e)
        destino = triagem.pasta_destino(e["slug"], args.leva)
        print(f"\n{c('✓', 'verde')} {len(novos)} arquivo(s) renomeados em {c(str(destino.relative_to(config.RAIZ)), 'azul')}")
        _imprime_checklist(e, itens)
    else:
        print(f"\n{c('Simulação.', 'amarelo')} Rode de novo com --aplicar para mover e renomear.")


def _imprime_checklist(e: dict, itens=None) -> None:
    itens = itens if itens is not None else checklist.avalia(e)
    res = checklist.resumo(itens)
    titulo(f"Checklist — {res['ok']}/{res['total_obrigatorios']} obrigatórios ({res['percentual']}%)")
    for i in itens:
        opcional = "" if i.obrigatorio else c(" (opcional)", "apagado")
        qtd = f" [{i.qtd_ok}/{i.qtd_min}]" if i.qtd_min > 1 else ""
        print(f"  {marca(i.situacao)} {i.nome}{qtd}{opcional}")
        for p in i.problemas[:2]:
            print(f"      {c('▲ ' + p, 'amarelo')}")
        if i.situacao == "faltando" and i.observacao:
            print(f"      {c(i.observacao, 'apagado')}")
    if res["pronto"]:
        print(f"\n{c('✓ Dossiê fechado — pode enviar.', 'verde')}")
    else:
        print(f"\n{c('✗ ' + plural(len(res['bloqueios']), 'item trava', 'itens travam') + ' o envio.', 'vermelho')}")


def cmd_checklist(args) -> None:
    e = store.resolve(args.empresa)
    itens = checklist.avalia(e, args.pacote)
    _imprime_checklist(e, itens)
    if args.texto:
        titulo("Texto para cobrar")
        print(checklist.texto_pendencias(itens))


def cmd_gerentes(args) -> None:
    e = store.resolve(args.empresa)
    sugestoes = envios.ranqueia(e)
    titulo(f"Gerentes para {e['razao_social']}")
    for s in sugestoes:
        if s.ja_enviado:
            cabeca, nota = c("↺", "apagado"), c(f"já enviado em {s.ja_enviado}", "apagado")
        elif s.recomendado:
            cabeca, nota = c("✓", "verde"), c(f"score {s.score}", "verde")
        else:
            cabeca, nota = c("✗", "vermelho"), c("não indicado", "vermelho")
        print(f"\n  {cabeca} {c(s.gerente['nome'], 'forte')} — {s.gerente.get('instituicao', '')}  {nota}")
        print(f"      {c(s.codigo, 'azul')}")
        for m in s.motivos:
            print(f"      + {m}")
        for i in s.impeditivos:
            print(f"      {c('− ' + i, 'vermelho')}")
        if s.gerente.get("observacoes"):
            print(f"      {c(s.gerente['observacoes'], 'apagado')}")

    recomendados = [s.codigo for s in sugestoes if s.recomendado]
    if recomendados:
        print(f"\n  Enviar para os indicados:\n  {c('corresp enviar ' + e['slug'] + ' -g ' + ','.join(recomendados), 'azul')}")


def cmd_enviar(args) -> None:
    e = store.resolve(args.empresa)
    itens = checklist.avalia(e)
    res = checklist.resumo(itens)
    if not res["pronto"] and not args.forcar and args.tipo == "primeira_leva":
        print(f"{c('✗ Dossiê incompleto', 'vermelho')} — {plural(len(res['bloqueios']), 'item trava', 'itens travam')} o envio:")
        print(checklist.texto_pendencias(itens, apenas_bloqueios=True))
        print("\nUse --forcar para enviar mesmo assim.")
        return

    codigos = [g.strip() for g in args.gerentes.split(",") if g.strip()]
    if not codigos:
        codigos = [s.codigo for s in envios.ranqueia(e) if s.recomendado]
        if not codigos:
            print("Nenhum gerente recomendado. Passe -g explicitamente.")
            return
        print(f"{c('Usando os recomendados:', 'amarelo')} {', '.join(codigos)}")

    manifest = envios.gera_lote(e, codigos, args.tipo, args.pedido or "")
    titulo(f"{len(manifest['envios'])} envios individuais gerados")
    for i in manifest["envios"]:
        print(f"  {c('→', 'verde')} {i['nome'].ljust(24)} {i['para']}")
        print(f"      {c(i['assunto'], 'apagado')}")
    print(f"\n  Pasta: {c(manifest['pasta'], 'azul')}")
    print(f"  Anexo: {manifest['anexo'] or '—'}")
    print(f"\n  Cada arquivo .eml abre no seu cliente de e-mail já com o dossiê anexado.")
    print(f"  Ou peça ao Claude: {c('envie os e-mails da pasta ' + manifest['pasta'] + ' um a um', 'azul')}")


def cmd_resposta(args) -> None:
    e = store.resolve(args.empresa)
    envios.registra_resposta(e, args.gerente, args.resposta, args.nota or "")
    if args.pendencia:
        e.setdefault("pendencias", []).extend(p.strip() for p in args.pendencia.split(";") if p.strip())
        e["solicitante_complementar"] = config.gerentes().get(args.gerente, {}).get("nome", args.gerente)
    store.salva(e)
    print(f"{c('✓', 'verde')} {e['razao_social']}: {args.gerente} → {args.resposta}")
    print(f"  Status agora: {c(painel.ROTULOS.get(e['status'], e['status']), 'roxo')}")
    print(f"  Próximo passo: {e.get('proximo_passo')}")


def cmd_status(args) -> None:
    e = store.resolve(args.empresa)
    store.muda_status(e, args.status, args.nota or "")
    if args.proximo:
        e["proximo_passo"] = args.proximo
    store.salva(e)
    print(f"{c('✓', 'verde')} {e['razao_social']} → {painel.ROTULOS.get(args.status, args.status)}")


def cmd_call(args) -> None:
    e = store.resolve(args.empresa)
    e.setdefault("calls", []).append({
        "data": args.data, "hora": args.hora or "", "gerente": args.gerente,
        "responsavel": args.responsavel or "—", "status": "agendada", "preparo": args.preparo or "",
    })
    store.muda_status(e, "call_agendada", f"call em {args.data}")
    store.registra_evento(e, "call", f"Call marcada para {args.data} {args.hora or ''} com {args.gerente}")
    e["proximo_passo"] = f"Preparar {args.responsavel or 'quem acompanha'} para a call de {args.data}"
    store.salva(e)
    print(f"{c('✓', 'verde')} Call registrada — {args.data} {args.hora or ''} · acompanha: {args.responsavel or '—'}")


def cmd_pendencia(args) -> None:
    e = store.resolve(args.empresa)
    e.setdefault("pendencias", []).extend(p.strip() for p in args.itens.split(";") if p.strip())
    store.registra_evento(e, "pendencia", f"Pendências registradas: {args.itens}")
    store.salva(e)
    print(f"{c('✓', 'verde')} {len(e['pendencias'])} pendência(s) na {e['razao_social']}")


def _imprime_acao(a: followup.Acao, numero: int) -> None:
    cor = {"alta": "vermelho", "media": "amarelo", "baixa": "apagado"}[a.prioridade]
    etiqueta = {"cobrar_gerente": "GERENTE", "cobrar_parceiro": "PARCEIRO", "cobrar_empresa": "EMPRESA",
                "interno": "SUA MESA", "documento": "DOCUMENTO"}.get(a.tipo, a.tipo.upper())
    print(f"\n {c(str(numero).rjust(2) + '.', 'apagado')} {c('[' + etiqueta + ']', cor)} {c(a.titulo, 'forte')}")
    print(f"     {a.empresa_nome} · {a.contexto}")
    if a.mensagem:
        contato = a.whatsapp if a.canal == "whatsapp" else a.para
        print(f"     {c(a.canal + ': ' + contato, 'azul')}")


def cmd_hoje(args) -> None:
    b = followup.brief()
    titulo(f"Fila de {date.today().strftime('%d/%m/%Y')} — "
           f"{plural(len(b['acoes']), 'ação', 'ações')} · {b['total_ativas']} empresas ativas")

    if not b["acoes"]:
        print("\n  Nada vencido. Esteira em dia.")
    for n, a in enumerate(b["acoes"], 1):
        _imprime_acao(a, n)
        if args.textos and a.mensagem:
            print()
            for linha in a.mensagem.strip().splitlines():
                print(f"     {c('│ ' + linha, 'apagado')}")

    if b["calls"]:
        titulo("Calls dos próximos 7 dias")
        for call in b["calls"]:
            quando = "hoje" if call["dias_ate"] == 0 else f"em {call['dias_ate']}d"
            print(f"  {call['data']} {call['hora'].ljust(6)} {call['empresa_nome'].ljust(28)} "
                  f"{call['gerente']} · acompanha: {c(call['responsavel'], 'roxo')} ({quando})")

    if not args.textos and b["acoes"]:
        print(f"\n  {c('corresp hoje --textos', 'azul')} mostra as mensagens já escritas.")


def cmd_cobrar(args) -> None:
    e = store.resolve(args.empresa)
    acoes = [a for a in followup.acoes_da_empresa(e) if a.mensagem]
    if args.alvo:
        acoes = [a for a in acoes if args.alvo in (a.alvo_codigo, a.tipo)]
    if not acoes:
        print("Nada a cobrar nessa empresa hoje (ou nenhuma cobrança venceu o SLA).")
        return
    for n, a in enumerate(acoes, 1):
        _imprime_acao(a, n)
        print()
        if a.assunto:
            print(f"     {c('Assunto: ' + a.assunto, 'apagado')}")
        for linha in a.mensagem.strip().splitlines():
            print(f"     {linha}")
        if args.registrar:
            followup.marca_followup(e, a.chave)
    if args.registrar:
        store.salva(e)
        print(f"\n{c('✓ Cobranças registradas — só voltam à fila quando vencer o SLA de novo.', 'verde')}")


def cmd_painel(args) -> None:
    destino = painel.gera(Path(args.saida) if args.saida else None)
    print(f"{c('✓', 'verde')} Painel gerado: {c(str(destino), 'azul')}")
    if args.abrir:
        import webbrowser

        webbrowser.open(destino.as_uri())


def cmd_tipos(args) -> None:
    titulo("Catálogo de documentos")
    for t in sorted(tipos_doc.CATALOGO, key=lambda x: x.ordem):
        if t.codigo == "OUTROS":
            continue
        validade = f"vale {t.validade_dias}d" if t.validade_dias else "sem validade"
        print(f"  {str(t.ordem).rjust(2)}  {c(t.codigo.ljust(26), 'azul')} {t.nome}")
        print(f"      {c(validade + (' · mensal' if t.competencia else ''), 'apagado')}"
              + (f"  {c(t.nota, 'apagado')}" if t.nota else ""))


# --------------------------------------------------------------------- main


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="corresp", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="comando", required=True)

    n = sub.add_parser("nova", help="cadastra uma empresa")
    n.add_argument("razao_social")
    n.add_argument("--cnpj")
    n.add_argument("--setor")
    n.add_argument("--faturamento", type=float, help="faturamento anual em R$")
    n.add_argument("--necessidade", type=float, help="crédito pretendido em R$")
    n.add_argument("--produto", default="capital_giro")
    n.add_argument("--garantia", default="aval")
    n.add_argument("--parceiro", help="código do parceiro indicador")
    n.add_argument("--pacote", default="primeira_leva_padrao")
    n.add_argument("--socios", type=int, default=1)
    n.add_argument("--contato")
    n.add_argument("--contato-email", dest="contato_email")
    n.add_argument("--contato-whatsapp", dest="contato_whatsapp")
    n.add_argument("--serasa", action="store_true", help="empresa tem restrição")
    n.set_defaults(func=cmd_nova)

    l = sub.add_parser("lista", help="lista o pipeline")
    l.add_argument("--ativas", action="store_true")
    l.set_defaults(func=cmd_lista)

    v = sub.add_parser("ver", help="ficha completa da empresa")
    v.add_argument("empresa")
    v.set_defaults(func=cmd_ver)

    t = sub.add_parser("triagem", help="classifica, confere validade e renomeia os anexos")
    t.add_argument("empresa")
    t.add_argument("--inbox", help="pasta de origem (padrão: inbox/<empresa>)")
    t.add_argument("--leva", default="primeira_leva", choices=["primeira_leva", "complementar"])
    t.add_argument("--aplicar", action="store_true", help="move e renomeia de verdade")
    t.set_defaults(func=cmd_triagem)

    ch = sub.add_parser("checklist", help="o que falta")
    ch.add_argument("empresa")
    ch.add_argument("--pacote")
    ch.add_argument("--texto", action="store_true", help="mostra o texto pronto para cobrar")
    ch.set_defaults(func=cmd_checklist)

    g = sub.add_parser("gerentes", help="para quem vale mandar essa empresa")
    g.add_argument("empresa")
    g.set_defaults(func=cmd_gerentes)

    en = sub.add_parser("enviar", help="gera os e-mails individuais (um por gerente)")
    en.add_argument("empresa")
    en.add_argument("-g", "--gerentes", default="", help="códigos separados por vírgula")
    en.add_argument("--tipo", default="primeira_leva", choices=["primeira_leva", "complementar"])
    en.add_argument("--pedido", help="o que o gerente pediu (envio complementar)")
    en.add_argument("--forcar", action="store_true")
    en.set_defaults(func=cmd_enviar)

    r = sub.add_parser("resposta", help="registra o retorno de um gerente")
    r.add_argument("empresa")
    r.add_argument("gerente")
    r.add_argument("resposta", choices=["pendente", "pre_aprovado", "pediu_documento", "recusado",
                                        "proposta", "sem_retorno"])
    r.add_argument("--nota")
    r.add_argument("--pendencia", help="itens pedidos, separados por ';'")
    r.set_defaults(func=cmd_resposta)

    s = sub.add_parser("status", help="muda o status manualmente")
    s.add_argument("empresa")
    s.add_argument("status", choices=store.STATUS_ORDEM)
    s.add_argument("--nota")
    s.add_argument("--proximo", help="próximo passo")
    s.set_defaults(func=cmd_status)

    ca = sub.add_parser("call", help="registra call do gerente com o dono")
    ca.add_argument("empresa")
    ca.add_argument("--data", required=True, help="AAAA-MM-DD")
    ca.add_argument("--hora")
    ca.add_argument("--gerente", required=True)
    ca.add_argument("--responsavel", help="quem acompanha a call")
    ca.add_argument("--preparo", help="o que precisa estar pronto antes")
    ca.set_defaults(func=cmd_call)

    pe = sub.add_parser("pendencia", help="registra o que o banco pediu")
    pe.add_argument("empresa")
    pe.add_argument("itens", help="separados por ';'")
    pe.set_defaults(func=cmd_pendencia)

    h = sub.add_parser("hoje", help="a fila do dia")
    h.add_argument("--textos", action="store_true", help="inclui as mensagens prontas")
    h.set_defaults(func=cmd_hoje)

    co = sub.add_parser("cobrar", help="mostra as cobranças de uma empresa")
    co.add_argument("empresa")
    co.add_argument("--alvo", help="código do gerente ou tipo (cobrar_parceiro, cobrar_empresa)")
    co.add_argument("--registrar", action="store_true", help="marca como cobrado hoje")
    co.set_defaults(func=cmd_cobrar)

    pa = sub.add_parser("painel", help="gera o painel HTML")
    pa.add_argument("--saida")
    pa.add_argument("--abrir", action="store_true")
    pa.set_defaults(func=cmd_painel)

    ti = sub.add_parser("tipos", help="catálogo de documentos reconhecidos")
    ti.set_defaults(func=cmd_tipos)

    return p


def main(argv: list[str] | None = None) -> int:
    config.garante_pastas()
    args = parser().parse_args(argv)
    try:
        args.func(args)
    except (KeyError, ValueError, FileNotFoundError) as erro:
        print(f"{c('✗', 'vermelho')} {erro}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
