"""Seleção de gerentes e geração dos envios — sempre um a um, nunca em cópia.

Para cada gerente escolhido gera:
  - um `.md` com assunto + corpo (é o que o Claude Code manda pelo Gmail)
  - um `.eml` já com o dossiê anexado (é só dar duplo clique)
  - uma linha no `manifest.json` do lote
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from . import checklist, config, store, tipos_doc
from .util import competencia_legivel, formata_cnpj, iso, moeda, slug


@dataclass
class Sugestao:
    codigo: str
    gerente: dict
    score: int
    motivos: list[str] = field(default_factory=list)
    impeditivos: list[str] = field(default_factory=list)
    ja_enviado: str | None = None

    @property
    def recomendado(self) -> bool:
        return not self.impeditivos and self.ja_enviado is None


def carga_atual(codigo_gerente: str) -> int:
    """Quantas propostas esse gerente já tem em análise agora."""
    total = 0
    for e in store.ativas():
        for env in e.get("envios", []):
            if env.get("gerente") == codigo_gerente and env.get("resposta") in (None, "", "pendente"):
                total += 1
    return total


def ranqueia(empresa: dict) -> list[Sugestao]:
    faturamento = empresa.get("faturamento_anual")
    necessidade = empresa.get("necessidade")
    setor = slug(empresa.get("setor", ""))
    restricoes = empresa.get("restricoes", {}) or {}
    produto = empresa.get("produto", "")
    garantia = empresa.get("garantia", "")

    sugestoes: list[Sugestao] = []
    for codigo, g in config.gerentes().items():
        ap = g.get("apetite", {})
        score, motivos, impeditivos = 0, [], []

        fmin, fmax = ap.get("faturamento_min_anual"), ap.get("faturamento_max_anual")
        if faturamento is not None:
            if fmin and faturamento < fmin:
                impeditivos.append(f"faturamento abaixo do mínimo ({moeda(fmin)}/ano)")
            elif fmax and faturamento > fmax:
                impeditivos.append(f"faturamento acima do teto ({moeda(fmax)}/ano)")
            else:
                score += 25
                motivos.append("faturamento dentro da faixa")

        tmin, tmax = ap.get("ticket_min"), ap.get("ticket_max")
        if necessidade is not None:
            if tmin and necessidade < tmin:
                impeditivos.append(f"ticket abaixo do mínimo ({moeda(tmin)})")
            elif tmax and necessidade > tmax:
                impeditivos.append(f"ticket acima do teto ({moeda(tmax)})")
            else:
                score += 20
                motivos.append("ticket dentro da faixa")

        evitados = [slug(s) for s in ap.get("setores_evitados", [])]
        preferidos = [slug(s) for s in ap.get("setores_preferidos", [])]
        if setor and setor in evitados:
            impeditivos.append(f"não opera com {empresa.get('setor')}")
        elif setor and setor in preferidos:
            score += 20
            motivos.append(f"tem apetite para {empresa.get('setor')}")

        if restricoes.get("serasa") and not ap.get("aceita_serasa", False):
            impeditivos.append("empresa com restrição e o gerente não aceita")
        elif restricoes.get("serasa") and ap.get("aceita_serasa"):
            score += 15
            motivos.append("aceita empresa com restrição")

        produtos = ap.get("produtos", [])
        if produto and produtos:
            if produto in produtos:
                score += 15
                motivos.append(f"trabalha {produto.replace('_', ' ')}")
            else:
                impeditivos.append(f"não trabalha {produto.replace('_', ' ')}")

        garantias = ap.get("garantias", [])
        if garantia and garantias and garantia in garantias:
            score += 10
            motivos.append(f"aceita garantia por {garantia}")

        carga = carga_atual(codigo)
        if carga >= ap.get("limite_simultaneo", 6):
            impeditivos.append(f"já está com {carga} propostas suas em análise")
        else:
            score += max(0, 8 - carga * 2)

        prazo = ap.get("prazo_retorno_dias")
        if prazo and prazo <= 3:
            score += 5
            motivos.append(f"costuma responder em {prazo} dias úteis")

        ja = next(
            (env.get("enviado_em") for env in empresa.get("envios", []) if env.get("gerente") == codigo),
            None,
        )
        sugestoes.append(Sugestao(codigo, g, score, motivos, impeditivos, ja))

    sugestoes.sort(key=lambda s: (s.recomendado, s.score), reverse=True)
    return sugestoes


# ------------------------------------------------------------- montagem


def resumo_operacao(empresa: dict) -> str:
    linhas = [
        f"Empresa: {empresa['razao_social']} — CNPJ {formata_cnpj(empresa.get('cnpj', ''))}",
        f"Setor: {empresa.get('setor') or '—'}",
        f"Faturamento anual: {moeda(empresa.get('faturamento_anual'))}",
        f"Necessidade: {moeda(empresa.get('necessidade'))} · {empresa.get('produto', '').replace('_', ' ')}",
        f"Garantia oferecida: {empresa.get('garantia') or '—'}",
    ]
    r = empresa.get("restricoes", {}) or {}
    marcas = [k for k, v in r.items() if v is True]
    linhas.append("Restritivos: " + (", ".join(marcas) if marcas else "nada apontado"))
    if empresa.get("observacoes"):
        linhas.append(f"Observações: {empresa['observacoes']}")
    return "\n".join(linhas)


def lista_documentos(empresa: dict, leva: str | None = None) -> str:
    """Uma linha por tipo — várias vias do mesmo documento viram uma só,
    com as competências entre parênteses."""
    docs = empresa.get("documentos", [])
    if leva:
        docs = [d for d in docs if d.get("leva") == leva]

    agrupado: dict[str, list[str]] = {}
    for d in docs:
        comp = competencia_legivel(d.get("competencia"))
        extra = comp or ""
        agrupado.setdefault(d["tipo"], []).append(extra)

    linhas = []
    for codigo in sorted(agrupado, key=lambda cod: tipos_doc.tipo(cod).ordem):
        marcas = [m for m in agrupado[codigo] if m]
        detalhe = ""
        if marcas:
            detalhe = " — " + ", ".join(dict.fromkeys(marcas))
        elif len(agrupado[codigo]) > 1:
            detalhe = f" — {len(agrupado[codigo])} arquivos"
        linhas.append(f"• {tipos_doc.nome(codigo)}{detalhe}")
    return "\n".join(linhas) or "—"


def preenche(texto: str, valores: dict) -> str:
    def troca(m: re.Match) -> str:
        return str(valores.get(m.group(1).strip(), ""))

    corpo = re.sub(r"\{\{([^}]+)\}\}", troca, texto)
    return re.sub(r"\n{3,}", "\n\n", corpo).strip() + "\n"


def monta_mensagem(empresa: dict, gerente: dict, tipo: str = "primeira_leva", pedido: str = "") -> dict:
    nome_template = "email_gerente" if tipo == "primeira_leva" else "email_gerente_complementar"
    bruto = config.template(nome_template)
    op = config.operador()
    valores = {
        "gerente_primeiro_nome": gerente["nome"].split()[0],
        "gerente_nome": gerente["nome"],
        "instituicao": gerente.get("instituicao", ""),
        "razao_social": empresa["razao_social"],
        "cnpj": formata_cnpj(empresa.get("cnpj", "")),
        "resumo": resumo_operacao(empresa),
        "documentos": lista_documentos(empresa, None if tipo != "primeira_leva" else "primeira_leva"),
        "pedido": pedido,
        "operador_nome": op.get("nome", ""),
        "assinatura": op.get("assinatura", ""),
        "observacao_gerente": gerente.get("observacoes", ""),
        "data": date.today().strftime("%d/%m/%Y"),
        "necessidade": moeda(empresa.get("necessidade")),
        "faturamento": moeda(empresa.get("faturamento_anual")),
    }
    corpo = preenche(bruto, valores)
    linhas = corpo.splitlines()
    assunto = linhas[0].replace("ASSUNTO:", "").strip() if linhas and linhas[0].startswith("ASSUNTO:") else (
        f"{empresa['razao_social']} — {moeda(empresa.get('necessidade'))} — {empresa.get('produto', '').replace('_', ' ')}"
    )
    corpo = "\n".join(linhas[1:]).strip() + "\n"
    return {"assunto": assunto, "corpo": corpo, "para": gerente.get("email", "")}


def monta_dossie(empresa: dict, destino: Path, leva: str | None = None) -> Path | None:
    pasta = config.EMPRESAS / empresa["slug"]
    arquivos: list[Path] = []
    subpastas = ["01-primeira-leva", "02-complementar"] if leva is None else [
        {"primeira_leva": "01-primeira-leva", "complementar": "02-complementar"}[leva]
    ]
    for sub in subpastas:
        p = pasta / sub
        if p.exists():
            arquivos.extend(sorted(x for x in p.iterdir() if x.is_file()))
    if not arquivos:
        return None
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for a in arquivos:
            z.write(a, arcname=a.name)
    return destino


def gera_lote(
    empresa: dict,
    codigos: list[str],
    tipo: str = "primeira_leva",
    pedido: str = "",
    registrar: bool = True,
) -> dict:
    config.garante_pastas()
    dia = date.today().isoformat()
    pasta = config.SAIDA / "envios" / empresa["slug"] / f"{dia}_{tipo}"
    pasta.mkdir(parents=True, exist_ok=True)

    leva = "primeira_leva" if tipo == "primeira_leva" else None
    zip_path = monta_dossie(empresa, pasta / f"dossie_{empresa['slug']}.zip", leva)

    itens = []
    for idx, codigo in enumerate(codigos, start=1):
        g = config.gerentes().get(codigo)
        if not g:
            raise KeyError(f"gerente '{codigo}' não está em config/gerentes.json")
        msg = monta_mensagem(empresa, g, tipo, pedido)
        base = f"{idx:02d}_{codigo}"

        (pasta / f"{base}.md").write_text(
            f"PARA: {msg['para']}\nASSUNTO: {msg['assunto']}\n"
            f"ANEXO: {zip_path.name if zip_path else '—'}\n\n---\n\n{msg['corpo']}",
            encoding="utf-8",
        )

        eml = EmailMessage()
        eml["To"] = msg["para"]
        eml["From"] = config.operador().get("email", "")
        eml["Subject"] = msg["assunto"]
        eml.set_content(msg["corpo"])
        if zip_path:
            eml.add_attachment(
                zip_path.read_bytes(), maintype="application", subtype="zip", filename=zip_path.name
            )
        (pasta / f"{base}.eml").write_bytes(bytes(eml))

        itens.append({
            "gerente": codigo,
            "nome": g["nome"],
            "instituicao": g.get("instituicao", ""),
            "para": msg["para"],
            "assunto": msg["assunto"],
            "arquivo_md": str((pasta / f"{base}.md").relative_to(config.RAIZ)),
            "arquivo_eml": str((pasta / f"{base}.eml").relative_to(config.RAIZ)),
        })

        if registrar:
            empresa.setdefault("envios", []).append({
                "gerente": codigo,
                "tipo": tipo,
                "enviado_em": dia,
                "status_envio": "gerado",
                "resposta": None,
                "respondido_em": None,
                "ultimo_followup": None,
                "notas": [],
            })

    manifest = {
        "empresa": empresa["slug"],
        "razao_social": empresa["razao_social"],
        "tipo": tipo,
        "gerado_em": dia,
        "anexo": zip_path.name if zip_path else None,
        "envios": itens,
    }
    (pasta / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    if registrar:
        store.registra_evento(
            empresa, "envio",
            f"Gerado envio {tipo} para {len(itens)} gerente(s): "
            + ", ".join(i["nome"] for i in itens),
        )
        if tipo == "primeira_leva":
            store.muda_status(empresa, "em_analise", "dossiê enviado")
        empresa["proximo_passo"] = "Confirmar leitura e cobrar retorno dos gerentes"
        store.salva(empresa)

    manifest["pasta"] = str(pasta.relative_to(config.RAIZ))
    return manifest


def registra_resposta(empresa: dict, codigo_gerente: str, resposta: str, nota: str = "") -> None:
    validas = {"pendente", "pre_aprovado", "pediu_documento", "recusado", "proposta", "sem_retorno"}
    if resposta not in validas:
        raise ValueError(f"resposta inválida: {resposta}. Válidas: {', '.join(sorted(validas))}")
    envio = next((e for e in empresa.get("envios", []) if e["gerente"] == codigo_gerente), None)
    if envio is None:
        raise KeyError(f"não há envio registrado para '{codigo_gerente}' nessa empresa")
    envio["resposta"] = resposta
    envio["respondido_em"] = iso(date.today())
    if nota:
        envio.setdefault("notas", []).append({"data": iso(date.today()), "texto": nota})

    g = config.gerentes().get(codigo_gerente, {"nome": codigo_gerente})
    store.registra_evento(empresa, "resposta", f"{g['nome']}: {resposta}" + (f" · {nota}" if nota else ""))

    if resposta == "pre_aprovado":
        store.muda_status(empresa, "pre_aprovado", g["nome"])
        empresa["proximo_passo"] = f"Confirmar próximos passos com {g['nome']}"
    elif resposta == "pediu_documento":
        store.muda_status(empresa, "pendente_complementar", g["nome"])
        empresa["proximo_passo"] = f"Cobrar documentação complementar pedida por {g['nome']}"
    elif resposta == "proposta":
        store.muda_status(empresa, "proposta_emitida", g["nome"])
        empresa["proximo_passo"] = "Levar proposta ao dono e comparar com as demais"

    if all(e.get("resposta") == "recusado" for e in empresa.get("envios", [])) and empresa["envios"]:
        empresa["proximo_passo"] = "Todos recusaram — reavaliar praça/produto ou buscar novos gerentes"
