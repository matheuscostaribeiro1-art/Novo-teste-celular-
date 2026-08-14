"""Utilidades comuns: datas, slugs, formatação e dias úteis."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta

MESES = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}

FERIADOS_FIXOS = {(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (12, 25)}


def hoje() -> date:
    return date.today()


def iso(d: date | datetime | None) -> str | None:
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.date().isoformat()
    return d.isoformat()


def parse_data(valor: str | date | None) -> date | None:
    if valor is None or isinstance(valor, date):
        return valor
    valor = valor.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(valor, fmt).date()
        except ValueError:
            continue
    return None


def sem_acento(texto: str) -> str:
    norm = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in norm if not unicodedata.combining(c))


def slug(texto: str, sep: str = "-") -> str:
    base = sem_acento(texto).lower()
    base = re.sub(r"[^a-z0-9]+", sep, base).strip(sep)
    return base or "sem-nome"


SUFIXOS_JURIDICOS = {"ltda", "sa", "s", "a", "me", "epp", "eireli", "eirl", "mei", "cia"}
CONECTIVOS = {"e", "de", "da", "do", "das", "dos", "em"}


def slug_empresa(razao_social: str) -> str:
    """Slug curto e reconhecível: sem forma jurídica, sem conectivos, 3 palavras."""
    palavras = slug(razao_social, sep=" ").split()
    while palavras and palavras[-1] in SUFIXOS_JURIDICOS:
        palavras.pop()
    uteis = [p for p in palavras if p not in CONECTIVOS] or palavras
    return "-".join(uteis[:3]) or "sem-nome"


def slug_arquivo(texto: str) -> str:
    """Slug em caixa alta usado nos nomes de arquivo entregues aos gerentes."""
    return slug(texto).upper()


def so_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def formata_cnpj(cnpj: str) -> str:
    d = so_digitos(cnpj)
    if len(d) != 14:
        return cnpj
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def valida_cnpj(cnpj: str) -> bool:
    d = so_digitos(cnpj)
    if len(d) != 14 or d == d[0] * 14:
        return False
    for tamanho in (12, 13):
        pesos = list(range(tamanho - 7, 1, -1)) + list(range(9, 1, -1))
        soma = sum(int(d[i]) * pesos[i] for i in range(tamanho))
        resto = soma % 11
        digito = 0 if resto < 2 else 11 - resto
        if int(d[tamanho]) != digito:
            return False
    return True


def dia_util(d: date) -> bool:
    return d.weekday() < 5 and (d.month, d.day) not in FERIADOS_FIXOS


def dias_uteis_entre(inicio: date, fim: date) -> int:
    """Conta dias úteis de `inicio` (exclusivo) até `fim` (inclusivo)."""
    if fim <= inicio:
        return 0
    total, cursor = 0, inicio
    while cursor < fim:
        cursor += timedelta(days=1)
        if dia_util(cursor):
            total += 1
    return total


def proximo_dia_util(d: date) -> date:
    cursor = d
    while not dia_util(cursor):
        cursor += timedelta(days=1)
    return cursor


def moeda(valor: float | int | None) -> str:
    if valor is None:
        return "—"
    inteiro = f"{valor:,.0f}".replace(",", ".")
    return f"R$ {inteiro}"


def competencia_legivel(comp: str | None) -> str:
    """'2026-06' -> 'jun/2026'."""
    if not comp:
        return ""
    m = re.match(r"^(\d{4})-(\d{2})$", comp)
    if not m:
        return comp
    ano, mes = m.group(1), int(m.group(2))
    nomes = list(MESES.keys())
    return f"{nomes[mes - 1]}/{ano}"


def plural(n: int, singular: str, plural_: str) -> str:
    return f"{n} {singular if n == 1 else plural_}"
