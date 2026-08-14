"""Confronta o que chegou com o que o pacote exige e devolve as pendências."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import config, tipos_doc


@dataclass
class ItemChecklist:
    tipo: str
    nome: str
    obrigatorio: bool
    qtd_min: int
    qtd_ok: int
    observacao: str
    situacao: str  # ok | faltando | insuficiente | problema
    problemas: list[str] = field(default_factory=list)

    @property
    def pendente(self) -> bool:
        return self.situacao != "ok"

    @property
    def bloqueia_envio(self) -> bool:
        return self.obrigatorio and self.situacao in {"faltando", "insuficiente", "problema"}


def pacote(nome: str) -> dict:
    pacotes = config.checklists()
    if nome not in pacotes:
        disponiveis = ", ".join(pacotes) or "nenhum"
        raise KeyError(f"pacote '{nome}' não existe. Disponíveis: {disponiveis}")
    return pacotes[nome]


def avalia(empresa: dict, nome_pacote: str | None = None) -> list[ItemChecklist]:
    nome_pacote = nome_pacote or empresa.get("checklist_pacote", "primeira_leva_padrao")
    definicao = pacote(nome_pacote)
    docs = empresa.get("documentos", [])
    itens: list[ItemChecklist] = []

    for regra in definicao.get("itens", []):
        codigo = regra["tipo"]
        qtd_min = regra.get("qtd_min", 1)
        if regra.get("por_socio") and empresa.get("qtd_socios"):
            qtd_min = max(qtd_min, int(empresa["qtd_socios"]))

        encontrados = [d for d in docs if d.get("tipo") == codigo]
        problemas: list[str] = []
        validos = []
        for d in encontrados:
            criticos = [a for a in d.get("alertas", []) if _critico(a)]
            if criticos:
                problemas.extend(f"{d['arquivo']}: {a}" for a in criticos)
            else:
                validos.append(d)

        if len(validos) >= qtd_min:
            situacao = "ok" if not problemas else "ok"
        elif encontrados and problemas:
            situacao = "problema"
        elif encontrados:
            situacao = "insuficiente"
        else:
            situacao = "faltando"

        itens.append(
            ItemChecklist(
                tipo=codigo,
                nome=tipos_doc.nome(codigo),
                obrigatorio=regra.get("obrigatorio", True),
                qtd_min=qtd_min,
                qtd_ok=len(validos),
                observacao=regra.get("observacao", "") or tipos_doc.tipo(codigo).nota,
                situacao=situacao,
                problemas=problemas,
            )
        )

    itens.sort(key=lambda i: tipos_doc.tipo(i.tipo).ordem)
    return itens


def _critico(alerta: str) -> bool:
    a = alerta.lower()
    return a.startswith("vencido") or "defasado" in a or "não identificado" in a


def resumo(itens: list[ItemChecklist]) -> dict:
    obrig = [i for i in itens if i.obrigatorio]
    ok = [i for i in obrig if i.situacao == "ok"]
    return {
        "total_obrigatorios": len(obrig),
        "ok": len(ok),
        "pendentes": [i for i in itens if i.pendente],
        "bloqueios": [i for i in itens if i.bloqueia_envio],
        "percentual": round(100 * len(ok) / len(obrig)) if obrig else 100,
        "pronto": not any(i.bloqueia_envio for i in itens),
    }


def texto_pendencias(itens: list[ItemChecklist], numerado: bool = True,
                     apenas_bloqueios: bool = False) -> str:
    """Lista de pendências pronta para colar em e-mail/WhatsApp."""
    linhas: list[str] = []
    n = 1
    for i in itens:
        if not i.pendente or (apenas_bloqueios and not i.bloqueia_envio):
            continue
        marcador = f"{n}. " if numerado else "• "
        if i.situacao == "faltando":
            detalhe = f"{i.nome}" + (f" ({i.qtd_min} arquivos)" if i.qtd_min > 1 else "")
        elif i.situacao == "insuficiente":
            detalhe = f"{i.nome} — recebi {i.qtd_ok} de {i.qtd_min}"
        else:
            detalhe = f"{i.nome} — {'; '.join(p.split(': ', 1)[-1] for p in i.problemas[:2])}"
        if not i.obrigatorio:
            detalhe += " (opcional)"
        if i.observacao:
            detalhe += f" · {i.observacao}"
        linhas.append(marcador + detalhe)
        n += 1
    return "\n".join(linhas) if linhas else "Nada pendente."
