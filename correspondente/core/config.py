"""Caminhos do projeto e carregamento dos arquivos de configuração."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

INBOX = RAIZ / "inbox"
EMPRESAS = RAIZ / "empresas"
PIPELINE = RAIZ / "pipeline"
SAIDA = RAIZ / "saida"
CONFIG = RAIZ / "config"
TEMPLATES = RAIZ / "templates"

QUARENTENA = "_nao-identificados"


def garante_pastas() -> None:
    for p in (INBOX, EMPRESAS, PIPELINE, SAIDA, SAIDA / "envios", SAIDA / "cobrancas"):
        p.mkdir(parents=True, exist_ok=True)


def _carrega(nome: str) -> dict:
    caminho = CONFIG / nome
    if not caminho.exists():
        return {}
    return json.loads(caminho.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def gerentes() -> dict[str, dict]:
    return {g["codigo"]: g for g in _carrega("gerentes.json").get("gerentes", [])}


@lru_cache(maxsize=None)
def parceiros() -> dict[str, dict]:
    return {p["codigo"]: p for p in _carrega("parceiros.json").get("parceiros", [])}


@lru_cache(maxsize=None)
def checklists() -> dict[str, dict]:
    return _carrega("checklists.json").get("pacotes", {})


@lru_cache(maxsize=None)
def regras() -> dict:
    return _carrega("regras.json")


def sla() -> dict[str, dict]:
    return regras().get("sla", {})


def status_def() -> dict[str, dict]:
    return regras().get("status", {})


def operador() -> dict:
    return regras().get("operador", {"nome": "Correspondente", "email": "", "assinatura": ""})


def template(nome: str) -> str:
    caminho = TEMPLATES / f"{nome}.md"
    if not caminho.exists():
        raise FileNotFoundError(f"template ausente: {caminho}")
    return caminho.read_text(encoding="utf-8")
