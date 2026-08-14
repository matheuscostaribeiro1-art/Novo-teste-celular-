"""Motor de cobrança: olha há quantos dias úteis cada coisa está parada,
compara com o SLA do status e devolve a lista do dia com o texto já escrito.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from . import checklist, config, envios, store, tipos_doc
from .util import competencia_legivel, dias_uteis_entre, iso, moeda, parse_data, plural


@dataclass
class Acao:
    empresa: str
    empresa_nome: str
    tipo: str                    # cobrar_gerente | cobrar_parceiro | cobrar_empresa | interno | call | documento
    titulo: str
    alvo_nome: str = ""
    alvo_codigo: str = ""
    canal: str = "email"
    para: str = ""
    whatsapp: str = ""
    assunto: str = ""
    mensagem: str = ""
    prioridade: str = "media"    # alta | media | baixa
    dias: int = 0
    contexto: str = ""
    chave: str = ""

    @property
    def peso(self) -> int:
        return {"alta": 0, "media": 1, "baixa": 2}[self.prioridade]


def _prioridade(dias: int, sla: int) -> str:
    if dias >= sla * 2:
        return "alta"
    if dias >= sla:
        return "media"
    return "baixa"


def _dias_parado(referencia: str | None, fallback: str | None = None) -> int:
    d = parse_data(referencia) or parse_data(fallback)
    if not d:
        return 0
    return dias_uteis_entre(d, date.today())


def _ultimo_followup(empresa: dict, chave: str) -> str | None:
    return (empresa.get("followups") or {}).get(chave)


def marca_followup(empresa: dict, chave: str) -> None:
    empresa.setdefault("followups", {})[chave] = iso(date.today())
    store.registra_evento(empresa, "cobranca", f"Cobrança registrada: {chave}")


def _msg(template: str, valores: dict) -> tuple[str, str]:
    bruto = config.template(template)
    texto = envios.preenche(bruto, valores)
    linhas = texto.splitlines()
    if linhas and linhas[0].startswith("ASSUNTO:"):
        return linhas[0].replace("ASSUNTO:", "").strip(), "\n".join(linhas[1:]).strip() + "\n"
    return "", texto


def _base(empresa: dict) -> dict:
    op = config.operador()
    return {
        "razao_social": empresa["razao_social"],
        "operador_nome": op.get("nome", ""),
        "assinatura": op.get("assinatura", ""),
        "data": date.today().strftime("%d/%m/%Y"),
        "necessidade": moeda(empresa.get("necessidade")),
    }


# ------------------------------------------------------------------ regras


def acoes_da_empresa(empresa: dict) -> list[Acao]:
    acoes: list[Acao] = []
    status = empresa.get("status", "recebido")
    regra = config.sla().get(status, {})
    sla_dias = regra.get("dias", 3)
    nome = empresa["razao_social"]

    # 1) Gerentes que receberam e não voltaram
    if status in {"em_analise", "pre_aprovado", "em_formalizacao", "proposta_emitida"}:
        for env in empresa.get("envios", []):
            if env.get("resposta") not in (None, "", "pendente", "sem_retorno"):
                continue
            chave = f"gerente:{env['gerente']}"
            dias = _dias_parado(_ultimo_followup(empresa, chave) or env.get("enviado_em"))
            if dias < sla_dias:
                continue
            g = config.gerentes().get(env["gerente"], {"nome": env["gerente"]})
            valores = _base(empresa) | {
                "gerente_primeiro_nome": g["nome"].split()[0],
                "gerente_nome": g["nome"],
                "instituicao": g.get("instituicao", ""),
                "dias": plural(dias, "dia útil", "dias úteis"),
                "enviado_em": (parse_data(env.get("enviado_em")) or date.today()).strftime("%d/%m"),
            }
            assunto, corpo = _msg("cobranca_gerente", valores)
            acoes.append(Acao(
                empresa=empresa["slug"], empresa_nome=nome, tipo="cobrar_gerente",
                titulo=f"Cobrar retorno de {g['nome']} ({g.get('instituicao', '')})",
                alvo_nome=g["nome"], alvo_codigo=env["gerente"], canal="email",
                para=g.get("email", ""), whatsapp=g.get("whatsapp", ""),
                assunto=assunto, mensagem=corpo,
                prioridade=_prioridade(dias, sla_dias), dias=dias,
                contexto=f"Enviado em {env.get('enviado_em')} · sem retorno",
                chave=chave,
            ))

    # 2) Documentação faltando com o parceiro indicador
    if status in {"recebido", "em_triagem", "pendente_documentos"}:
        itens = checklist.avalia(empresa)
        res = checklist.resumo(itens)
        if res["bloqueios"]:
            chave = "parceiro:documentos"
            dias = _dias_parado(_ultimo_followup(empresa, chave) or store.status_desde(empresa))
            if dias >= config.sla().get("pendente_documentos", {}).get("dias", 2):
                p = config.parceiros().get(empresa.get("parceiro", ""), {})
                valores = _base(empresa) | {
                    "parceiro_primeiro_nome": (p.get("nome", "") or "você").split()[0],
                    "parceiro_nome": p.get("nome", ""),
                    "pendencias": checklist.texto_pendencias(itens),
                    "qtd": len(res["pendentes"]),
                    "percentual": res["percentual"],
                }
                assunto, corpo = _msg("cobranca_parceiro", valores)
                acoes.append(Acao(
                    empresa=empresa["slug"], empresa_nome=nome, tipo="cobrar_parceiro",
                    titulo=f"Cobrar {len(res['bloqueios'])} documento(s) de {p.get('nome', 'parceiro')}",
                    alvo_nome=p.get("nome", "parceiro não cadastrado"),
                    alvo_codigo=empresa.get("parceiro", ""), canal=p.get("canal_preferido", "whatsapp"),
                    para=p.get("email", ""), whatsapp=p.get("whatsapp", ""),
                    assunto=assunto, mensagem=corpo,
                    prioridade=_prioridade(dias, 2), dias=dias,
                    contexto=f"Checklist em {res['percentual']}% · trava o envio",
                    chave=chave,
                ))

    # 3) Documentação complementar pedida por gerente após pré-aprovação
    if status == "pendente_complementar":
        chave = "empresa:complementar"
        dias = _dias_parado(_ultimo_followup(empresa, chave) or store.status_desde(empresa))
        if dias >= config.sla().get("pendente_complementar", {}).get("dias", 2):
            pedidos = empresa.get("pendencias", [])
            contato = empresa.get("contato_empresa", {})
            valores = _base(empresa) | {
                "contato_primeiro_nome": (contato.get("nome", "") or "você").split()[0],
                "pendencias": "\n".join(f"{i}. {p}" for i, p in enumerate(pedidos, 1)) or "—",
                "gerente_nome": empresa.get("solicitante_complementar", "o banco"),
            }
            assunto, corpo = _msg("cobranca_empresa", valores)
            acoes.append(Acao(
                empresa=empresa["slug"], empresa_nome=nome, tipo="cobrar_empresa",
                titulo=f"Cobrar documentação complementar — {contato.get('nome', 'dono')}",
                alvo_nome=contato.get("nome", ""), canal="whatsapp",
                para=contato.get("email", ""), whatsapp=contato.get("whatsapp", ""),
                assunto=assunto, mensagem=corpo,
                prioridade=_prioridade(dias, 2), dias=dias,
                contexto=f"{len(pedidos)} item(ns) pedidos pelo banco",
                chave=chave,
            ))

    # 4) Ações internas: parado num status que depende só de você
    if status in {"recebido", "em_triagem", "pronto_envio"}:
        dias = _dias_parado(store.status_desde(empresa))
        if dias >= config.sla().get(status, {}).get("dias", 1):
            proximo = {
                "recebido": "Rodar a triagem dos documentos recebidos",
                "em_triagem": "Fechar a triagem e resolver os não identificados",
                "pronto_envio": "Escolher gerentes e disparar os envios individuais",
            }[status]
            acoes.append(Acao(
                empresa=empresa["slug"], empresa_nome=nome, tipo="interno",
                titulo=proximo, prioridade=_prioridade(dias, 1), dias=dias,
                contexto=f"parada há {plural(dias, 'dia útil', 'dias úteis')} em '{status}'",
                chave=f"interno:{status}",
            ))

    # 5) Documentos vencendo/vencidos que vão travar o envio.
    # Se já existe uma cobrança aberta que carrega essas pendências no texto,
    # não repete o alerta — a fila do dia é para agir, não para ler duas vezes.
    ja_cobrado = any(a.tipo in {"cobrar_parceiro", "cobrar_empresa"} for a in acoes)
    for d in [] if ja_cobrado else empresa.get("documentos", []):
        criticos = [a for a in d.get("alertas", []) if a.startswith("VENCIDO") or "vence em" in a or "defasado" in a]
        if not criticos:
            continue
        resumo, _, explicacao = criticos[0].partition(" — ")
        detalhes = [explicacao.strip().rstrip(".")] if explicacao else []
        if d.get("competencia"):
            detalhes.insert(0, competencia_legivel(d["competencia"]))
        acoes.append(Acao(
            empresa=empresa["slug"], empresa_nome=nome, tipo="documento",
            titulo=f"{tipos_doc.nome(d['tipo'])} — {resumo.lower()}",
            prioridade="alta" if criticos[0].startswith("VENCIDO") else "media",
            contexto=" · ".join(detalhes),
            chave=f"doc:{d['arquivo']}",
        ))

    return acoes


def calls(dias_a_frente: int = 7) -> list[dict]:
    """Calls de gerente com o dono da empresa — quem acompanha é outra pessoa,
    então aqui só interessa o que precisa ser preparado e confirmado."""
    limite = date.today() + timedelta(days=dias_a_frente)
    saida = []
    for e in store.todas():
        for c in e.get("calls", []):
            d = parse_data(c.get("data"))
            if not d or d < date.today() or d > limite:
                continue
            g = config.gerentes().get(c.get("gerente", ""), {})
            saida.append({
                "empresa": e["slug"],
                "empresa_nome": e["razao_social"],
                "data": iso(d),
                "hora": c.get("hora", ""),
                "gerente": g.get("nome", c.get("gerente", "")),
                "instituicao": g.get("instituicao", ""),
                "responsavel": c.get("responsavel", "—"),
                "status": c.get("status", "agendada"),
                "preparo": c.get("preparo", ""),
                "dias_ate": (d - date.today()).days,
            })
    saida.sort(key=lambda c: (c["data"], c["hora"]))
    return saida


def brief() -> dict:
    """O que fazer hoje, em ordem."""
    acoes: list[Acao] = []
    for e in store.ativas():
        acoes.extend(acoes_da_empresa(e))
    acoes.sort(key=lambda a: (a.peso, a.tipo == "documento", -a.dias))

    por_tipo: dict[str, list[Acao]] = {}
    for a in acoes:
        por_tipo.setdefault(a.tipo, []).append(a)

    empresas = list(store.todas())
    return {
        "data": iso(date.today()),
        "acoes": acoes,
        "por_tipo": por_tipo,
        "calls": calls(),
        "total_ativas": len([e for e in empresas if e.get("status") not in store.STATUS_ENCERRADOS]),
        "total": len(empresas),
        "urgentes": [a for a in acoes if a.prioridade == "alta"],
    }
