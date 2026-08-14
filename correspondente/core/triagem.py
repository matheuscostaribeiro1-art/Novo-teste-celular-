"""Triagem: lê os anexos crus, identifica o que é cada documento, confere
validade e renomeia tudo no padrão do dossiê.

Não depende de biblioteca externa: tenta `pypdf`, depois `pdftotext`, e cai
para uma leitura direta dos streams de texto do PDF.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import unicodedata
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config, tipos_doc
from .util import MESES, iso, parse_data, slug, slug_arquivo

EXTENSOES_SUPORTADAS = {".pdf", ".txt", ".docx", ".xlsx", ".jpg", ".jpeg", ".png", ".zip", ".xml", ".csv"}

BANCOS = [
    "itau", "bradesco", "santander", "banco do brasil", "caixa", "sicredi", "sicoob",
    "safra", "btg", "inter", "c6", "nubank", "banrisul", "daycoval", "abc brasil",
    "pine", "sofisa", "original", "brb", "banestes", "stone", "cielo", "getnet", "pagseguro",
]


def _norm(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto or "")
    base = "".join(c for c in base if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", base).strip()


# ---------------------------------------------------------------- extração


def extrai_texto(caminho: Path, limite: int = 20000) -> str:
    ext = caminho.suffix.lower()
    try:
        if ext == ".pdf":
            return _texto_pdf(caminho)[:limite]
        if ext in {".txt", ".csv", ".xml"}:
            return caminho.read_text(encoding="utf-8", errors="ignore")[:limite]
        if ext in {".docx", ".xlsx"}:
            return _texto_ooxml(caminho)[:limite]
    except Exception:
        return ""
    return ""


def _texto_pdf(caminho: Path) -> str:
    try:
        import pypdf  # type: ignore

        leitor = pypdf.PdfReader(str(caminho))
        return "\n".join((p.extract_text() or "") for p in leitor.pages[:12])
    except ImportError:
        pass
    except Exception:
        pass

    if shutil.which("pdftotext"):
        try:
            saida = subprocess.run(
                ["pdftotext", "-l", "12", "-q", str(caminho), "-"],
                capture_output=True, timeout=30,
            )
            if saida.stdout:
                return saida.stdout.decode("utf-8", errors="ignore")
        except Exception:
            pass

    return _texto_pdf_cru(caminho)


def _texto_pdf_cru(caminho: Path) -> str:
    """Último recurso: extrai literais de texto de streams não comprimidos."""
    dados = caminho.read_bytes()
    pedacos = re.findall(rb"\(((?:[^()\\]|\\.)*)\)\s*Tj", dados)
    if not pedacos:
        return ""
    linhas = []
    for p in pedacos:
        txt = p.replace(rb"\(", b"(").replace(rb"\)", b")").replace(rb"\\", b"\\")
        linhas.append(txt.decode("latin-1", errors="ignore"))
    return "\n".join(linhas)


def _texto_ooxml(caminho: Path) -> str:
    partes: list[str] = []
    with zipfile.ZipFile(caminho) as z:
        alvos = [n for n in z.namelist() if n.endswith(".xml") and ("document" in n or "sharedStrings" in n or "sheet" in n)]
        for nome in alvos[:8]:
            bruto = z.read(nome).decode("utf-8", errors="ignore")
            partes.append(re.sub(r"<[^>]+>", " ", bruto))
    return " ".join(partes)


# ------------------------------------------------------------ classificação


@dataclass
class Analise:
    origem: Path
    tipo: str = "OUTROS"
    confianca: int = 0
    competencia: str | None = None
    emissao: date | None = None
    fonte_data: str = "desconhecida"
    extra: str = ""
    alertas: list[str] = field(default_factory=list)
    nome_final: str = ""

    @property
    def legivel(self) -> str:
        return tipos_doc.nome(self.tipo)


def classifica(nome_arquivo: str, texto: str) -> tuple[str, int]:
    nome_n = _norm(nome_arquivo)
    texto_n = _norm(texto[:6000])
    melhor, melhor_score, melhor_nome, melhor_forte = "OUTROS", 0, 0, False
    for t in tipos_doc.CATALOGO:
        if t.codigo == "OUTROS":
            continue
        por_nome = 0
        por_texto = 0
        forte = False
        for p in t.padroes_fortes:
            pn = _norm(p)
            if pn and pn in nome_n:
                por_nome += 5
                forte = True
            if pn and pn in texto_n:
                por_texto += 4
                forte = True
        for p in t.padroes:
            pn = _norm(p)
            if pn and pn in nome_n:
                por_nome += 3
            if pn and pn in texto_n:
                por_texto += 1
        if por_nome + por_texto > melhor_score:
            melhor, melhor_score, melhor_nome, melhor_forte = (
                t.codigo, por_nome + por_texto, por_nome, forte)

    # Bilhete solto, anotação do indicador, print de conversa: texto curto que
    # cita um termo de passagem não é o documento em si.
    if melhor_nome == 0 and not melhor_forte and len(texto.strip()) < 400:
        return "OUTROS", melhor_score
    if melhor_score < 3:
        return "OUTROS", melhor_score
    return melhor, melhor_score


def detecta_competencia(nome_arquivo: str, texto: str) -> str | None:
    fontes = [nome_arquivo, texto[:4000]]
    for fonte in fontes:
        f = _norm(fonte)
        m = re.search(r"\b(20\d{2})\s*(0[1-9]|1[0-2])\b", f)
        if m:
            return f"{m.group(1)}-{m.group(2)}"
        m = re.search(r"\b(0?[1-9]|1[0-2])\s*(20\d{2})\b", f)
        if m:
            return f"{m.group(2)}-{int(m.group(1)):02d}"
        for abrev, num in MESES.items():
            m = re.search(rf"\b{abrev}[a-z]*\s*(?:de\s*)?(20\d{{2}}|\d{{2}})\b", f)
            if m:
                ano = m.group(1)
                ano = ano if len(ano) == 4 else f"20{ano}"
                return f"{ano}-{num:02d}"
        m = re.search(r"\b(20\d{2})\b", f)
        if m and re.search(r"exercicio|anual|ano base|ano calendario", f):
            return m.group(1)
    return None


def detecta_emissao(texto: str, caminho: Path) -> tuple[date | None, str]:
    marcadores = r"(?:emitid[ao] em|data de emissao|emissao|expedida em|gerado em|valida ate|emitida as)"
    achado = re.search(rf"{marcadores}[^0-9]{{0,20}}(\d{{2}}[/-]\d{{2}}[/-]\d{{4}})", _norm(texto)[:6000])
    if achado:
        d = parse_data(achado.group(1).replace("-", "/"))
        if d:
            return d, "documento"
    qualquer = re.search(r"\b(\d{2}/\d{2}/20\d{2})\b", texto[:6000])
    if qualquer:
        d = parse_data(qualquer.group(1))
        if d and d <= date.today() + timedelta(days=1):
            return d, "documento (data solta)"
    try:
        return datetime.fromtimestamp(caminho.stat().st_mtime).date(), "arquivo"
    except OSError:
        return None, "desconhecida"


def detecta_banco(nome_arquivo: str, texto: str) -> str:
    alvo = _norm(nome_arquivo) + " " + _norm(texto[:2500])
    for banco in BANCOS:
        if _norm(banco) in alvo:
            return banco.replace(" ", "-")
    return ""


def detecta_pessoa(nome_arquivo: str) -> str:
    """Tenta achar o nome do sócio no nome do arquivo (tokens que sobram)."""
    base = _norm(Path(nome_arquivo).stem)
    ruido = {
        "rg", "cnh", "cpf", "doc", "documento", "socio", "identidade", "irpf", "ir",
        "imposto", "de", "renda", "declaracao", "completa", "recibo", "pdf", "scan",
        "digitalizado", "img", "novo", "final", "1", "2", "3", "copia", "frente", "verso",
    }
    tokens = [t for t in base.split() if t not in ruido and not t.isdigit() and len(t) > 2]
    return "-".join(tokens[:3]).upper()


# --------------------------------------------------------------- validade


def avalia_validade(a: Analise) -> list[str]:
    t = tipos_doc.tipo(a.tipo)
    alertas: list[str] = []
    hoje_ = date.today()

    if t.validade_dias and a.emissao:
        vence = a.emissao + timedelta(days=t.validade_dias)
        dias = (vence - hoje_).days
        if dias < 0:
            alertas.append(
                f"VENCIDO há {abs(dias)} dia(s) — emitido em {a.emissao.strftime('%d/%m/%Y')}, "
                f"validade de {t.validade_dias} dias. Precisa reemitir."
            )
        elif dias <= 7:
            alertas.append(f"vence em {dias} dia(s) ({vence.strftime('%d/%m/%Y')}) — reemitir antes de enviar")
        if a.fonte_data == "arquivo":
            alertas.append("data de emissão inferida pela data do arquivo — conferir no documento")

    if t.competencia and not a.competencia:
        alertas.append("competência não identificada — confirmar mês/ano de referência")

    if t.competencia and a.competencia and len(a.competencia) == 7:
        ano, mes = int(a.competencia[:4]), int(a.competencia[5:])
        idade_meses = (hoje_.year - ano) * 12 + (hoje_.month - mes)
        limite = {"FATURAMENTO_12M": 2, "EXTRATO_BANCARIO": 3, "BALANCETE": 4, "RECEBIVEIS": 2}.get(a.tipo)
        if limite and idade_meses > limite:
            alertas.append(f"defasado: competência {a.competencia} tem {idade_meses} meses — pedir atualizado")

    if a.tipo == "OUTROS":
        alertas.append("não identificado — classificar manualmente")
    elif a.confianca < 6:
        alertas.append("classificação com baixa confiança — conferir")

    return alertas


# --------------------------------------------------------------- renomeação


def nome_padrao(a: Analise, slug_empresa: str) -> str:
    t = tipos_doc.tipo(a.tipo)
    partes = [f"{t.ordem:02d}-{a.tipo.replace('_', '-')}", slug_arquivo(slug_empresa)]
    if a.extra:
        partes.append(a.extra)
    if a.competencia:
        partes.append(a.competencia)
    return "_".join(partes) + a.origem.suffix.lower()


def analisa_arquivo(caminho: Path, slug_empresa: str) -> Analise:
    texto = extrai_texto(caminho)
    if caminho.suffix.lower() in {".txt", ".csv"}:
        # Recado do indicador, corpo de e-mail salvo, planilha solta: nunca é
        # o documento em si — vai para conferência manual.
        codigo, score = "OUTROS", 0
    else:
        codigo, score = classifica(caminho.name, texto)
    a = Analise(origem=caminho, tipo=codigo, confianca=score)
    t = tipos_doc.tipo(codigo)

    if t.competencia:
        a.competencia = detecta_competencia(caminho.name, texto)
    a.emissao, a.fonte_data = detecta_emissao(texto, caminho)

    if t.por_banco:
        a.extra = detecta_banco(caminho.name, texto).upper()
    elif t.por_socio:
        a.extra = detecta_pessoa(caminho.name)

    a.alertas = avalia_validade(a)
    a.nome_final = nome_padrao(a, slug_empresa)
    return a


def pasta_destino(slug_empresa: str, leva: str) -> Path:
    sub = {"primeira_leva": "01-primeira-leva", "complementar": "02-complementar"}.get(leva, leva)
    return config.EMPRESAS / slug_empresa / sub


def triagem_pasta(
    origem: Path,
    slug_empresa: str,
    leva: str = "primeira_leva",
    aplicar: bool = False,
) -> list[Analise]:
    """Analisa todos os arquivos de `origem`. Com `aplicar=True`, move e renomeia."""
    if not origem.exists():
        raise FileNotFoundError(f"pasta de origem não existe: {origem}")

    arquivos = sorted(
        p for p in origem.rglob("*")
        if p.is_file() and p.suffix.lower() in EXTENSOES_SUPORTADAS and not p.name.startswith(".")
    )
    resultado: list[Analise] = []
    usados: set[str] = set()

    for arq in arquivos:
        a = analisa_arquivo(arq, slug_empresa)
        final = a.nome_final
        if final in usados:
            raiz, ext = final.rsplit(".", 1)
            contador = 2
            while f"{raiz}-{contador}.{ext}" in usados:
                contador += 1
            final = f"{raiz}-{contador}.{ext}"
        usados.add(final)
        a.nome_final = final
        resultado.append(a)

    if aplicar:
        destino_ok = pasta_destino(slug_empresa, leva)
        destino_quar = config.EMPRESAS / slug_empresa / config.QUARENTENA
        destino_ok.mkdir(parents=True, exist_ok=True)
        for a in resultado:
            alvo_dir = destino_quar if a.tipo == "OUTROS" else destino_ok
            alvo_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(a.origem), str(alvo_dir / a.nome_final))

    return resultado


def para_registro(a: Analise, leva: str) -> dict:
    return {
        "tipo": a.tipo,
        "arquivo": a.nome_final,
        "origem": a.origem.name,
        "leva": leva,
        "competencia": a.competencia,
        "emissao": iso(a.emissao),
        "fonte_data": a.fonte_data,
        "confianca": a.confianca,
        "alertas": a.alertas,
        "triado_em": iso(date.today()),
    }
