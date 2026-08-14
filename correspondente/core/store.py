"""Persistência do pipeline.

Um arquivo JSON por empresa em `pipeline/<slug>.json`. Formato legível e
versionável em git — o Claude Code lê e edita direto quando precisa.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from . import config
from .util import hoje, iso, slug, slug_empresa

STATUS_ORDEM = [
    "recebido",
    "em_triagem",
    "pendente_documentos",
    "pronto_envio",
    "em_analise",
    "pre_aprovado",
    "pendente_complementar",
    "call_agendada",
    "proposta_emitida",
    "em_formalizacao",
    "liberado",
    "recusado",
    "standby",
]

STATUS_ENCERRADOS = {"liberado", "recusado", "standby"}


def caminho(slug_empresa: str) -> Path:
    return config.PIPELINE / f"{slug_empresa}.json"


def existe(slug_empresa: str) -> bool:
    return caminho(slug_empresa).exists()


def carrega(slug_empresa: str) -> dict[str, Any]:
    p = caminho(slug_empresa)
    if not p.exists():
        raise KeyError(f"empresa não encontrada no pipeline: {slug_empresa}")
    return json.loads(p.read_text(encoding="utf-8"))


def salva(empresa: dict[str, Any]) -> None:
    config.garante_pastas()
    empresa["atualizado_em"] = datetime.now().isoformat(timespec="seconds")
    p = caminho(empresa["slug"])
    p.write_text(json.dumps(empresa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def todas() -> Iterator[dict[str, Any]]:
    config.garante_pastas()
    for p in sorted(config.PIPELINE.glob("*.json")):
        yield json.loads(p.read_text(encoding="utf-8"))


def ativas() -> list[dict[str, Any]]:
    return [e for e in todas() if e.get("status") not in STATUS_ENCERRADOS]


def resolve(termo: str) -> dict[str, Any]:
    """Aceita slug, pedaço do nome ou CNPJ."""
    termo_norm = slug(termo)
    if existe(termo_norm):
        return carrega(termo_norm)
    from .util import so_digitos

    digitos = so_digitos(termo)
    candidatos = []
    for e in todas():
        if digitos and len(digitos) >= 8 and so_digitos(e.get("cnpj", "")).startswith(digitos):
            return e
        if termo_norm in e["slug"] or termo_norm in slug(e.get("razao_social", "")):
            candidatos.append(e)
    if len(candidatos) == 1:
        return candidatos[0]
    if not candidatos:
        raise KeyError(f"nenhuma empresa casa com '{termo}'")
    nomes = ", ".join(c["slug"] for c in candidatos)
    raise KeyError(f"'{termo}' é ambíguo: {nomes}")


def nova(razao_social: str, **campos: Any) -> dict[str, Any]:
    s = campos.pop("slug", None) or slug_empresa(razao_social)
    if existe(s):
        raise ValueError(f"já existe empresa com slug '{s}'")
    empresa: dict[str, Any] = {
        "slug": s,
        "razao_social": razao_social,
        "cnpj": campos.pop("cnpj", ""),
        "setor": campos.pop("setor", ""),
        "faturamento_anual": campos.pop("faturamento_anual", None),
        "necessidade": campos.pop("necessidade", None),
        "produto": campos.pop("produto", "capital_giro"),
        "garantia": campos.pop("garantia", "aval"),
        "restricoes": campos.pop("restricoes", {"serasa": False, "protestos": False}),
        "parceiro": campos.pop("parceiro", ""),
        "contato_empresa": campos.pop("contato_empresa", {}),
        "checklist_pacote": campos.pop("checklist_pacote", "primeira_leva_padrao"),
        "status": "recebido",
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        "atualizado_em": "",
        "documentos": [],
        "envios": [],
        "calls": [],
        "eventos": [],
        "pendencias": [],
        "proximo_passo": "Rodar triagem da primeira leva",
        "observacoes": campos.pop("observacoes", ""),
    }
    empresa.update(campos)
    registra_evento(empresa, "criada", f"Empresa cadastrada (parceiro: {empresa['parceiro'] or '—'})")
    salva(empresa)
    return empresa


def registra_evento(empresa: dict, tipo: str, texto: str, data: str | None = None) -> None:
    empresa.setdefault("eventos", []).append(
        {"data": data or iso(hoje()), "tipo": tipo, "texto": texto}
    )


def muda_status(empresa: dict, novo: str, nota: str = "") -> None:
    if novo not in STATUS_ORDEM:
        raise ValueError(f"status inválido: {novo}. Válidos: {', '.join(STATUS_ORDEM)}")
    anterior = empresa.get("status")
    if anterior == novo:
        return
    empresa["status"] = novo
    empresa["status_desde"] = iso(hoje())
    registra_evento(empresa, "status", f"{anterior} → {novo}" + (f" · {nota}" if nota else ""))


def status_desde(empresa: dict) -> str:
    return empresa.get("status_desde") or empresa.get("criado_em", "")[:10] or iso(hoje())
