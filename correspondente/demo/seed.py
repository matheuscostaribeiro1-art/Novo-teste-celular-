#!/usr/bin/env python3
"""Popula o protótipo com uma esteira de exemplo.

Cria empresas em estágios diferentes, envios já feitos, calls marcadas e —
o mais importante — uma caixa de entrada real, com os anexos bagunçados do
jeito que chegam por e-mail, para você rodar a triagem de verdade.

    python3 demo/seed.py            # cria tudo
    python3 demo/seed.py --limpar   # apaga e recria
"""

from __future__ import annotations

import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config, store  # noqa: E402
from core.util import iso  # noqa: E402

HOJE = date.today()


def d(dias: int) -> str:
    return iso(HOJE - timedelta(days=dias))


# ------------------------------------------------------------------ PDF cru


def pdf(caminho: Path, linhas: list[str]) -> None:
    """PDF mínimo, texto não comprimido — o extrator lê sem biblioteca externa."""
    conteudo = ["BT", "/F1 10 Tf", "40 800 Td", "14 TL"]
    for linha in linhas:
        seguro = linha.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        conteudo.append(f"({seguro}) Tj T*")
    conteudo.append("ET")
    fluxo = "\n".join(conteudo).encode("latin-1", errors="replace")

    objetos = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]"
        b"/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
        b"<</Length " + str(len(fluxo)).encode() + b">>\nstream\n" + fluxo + b"\nendstream",
    ]

    saida = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objetos, start=1):
        offsets.append(len(saida))
        saida += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"

    inicio_xref = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n".encode()
    saida += b"0000000000 65535 f \n"
    for off in offsets:
        saida += f"{off:010d} 00000 n \n".encode()
    saida += (
        f"trailer\n<</Size {len(objetos) + 1}/Root 1 0 R>>\nstartxref\n{inicio_xref}\n%%EOF\n".encode()
    )

    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(bytes(saida))


def br(dias_atras: int) -> str:
    return (HOJE - timedelta(days=dias_atras)).strftime("%d/%m/%Y")


# -------------------------------------------------------------- caixa de entrada


def caixa_acme(slug_empresa: str) -> None:
    """Anexos como chegam de verdade: nome ruim, ordem aleatória, um vencido,
    um documento defasado e um arquivo que não dá para identificar."""
    p = config.INBOX / slug_empresa
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True, exist_ok=True)

    pdf(p / "doc1.pdf", [
        "REPUBLICA FEDERATIVA DO BRASIL",
        "COMPROVANTE DE INSCRICAO E DE SITUACAO CADASTRAL",
        "CNPJ: 21.345.678/0001-90",
        "NOME EMPRESARIAL: ACME LOGISTICA E TRANSPORTES LTDA",
        f"Emitido em: {br(64)}",
    ])
    pdf(p / "CONTRATO SOCIAL ATUALIZADO (1).pdf", [
        "INSTRUMENTO PARTICULAR DE ALTERACAO CONTRATUAL",
        "ACME LOGISTICA E TRANSPORTES LTDA",
        "Registrado na Junta Comercial do Estado de Sao Paulo",
        f"Data do registro: {br(420)}",
    ])
    pdf(p / "faturamento acme.pdf", [
        "RELACAO DE FATURAMENTO - ULTIMOS 12 MESES",
        "ACME LOGISTICA E TRANSPORTES LTDA",
        "Receita bruta acumulada: R$ 12.480.000,00",
        "Competencia final: 06/2026",
        "Contador responsavel - CRC 1SP123456/O-4",
        f"Emitido em: {br(45)}",
    ])
    pdf(p / "extrato itau abril.pdf", [
        "ITAU UNIBANCO S.A.",
        "EXTRATO DE CONTA CORRENTE",
        "Agencia 1234 Conta 56789-0",
        "Periodo: 04/2026",
        "Saldo final: R$ 310.442,18",
    ])
    pdf(p / "extrato itau maio.pdf", [
        "ITAU UNIBANCO S.A.",
        "EXTRATO DE CONTA CORRENTE",
        "Periodo: 05/2026",
        "Saldo final: R$ 287.115,02",
    ])
    pdf(p / "bradesco extrato 06.pdf", [
        "BANCO BRADESCO S.A.",
        "EXTRATO DE CONTA CORRENTE",
        "Periodo: 06/2026",
        "Saldo final: R$ 96.730,44",
    ])
    pdf(p / "balanco 2025 acme.pdf", [
        "BALANCO PATRIMONIAL",
        "Exercicio encerrado em 31/12/2025",
        "ACME LOGISTICA E TRANSPORTES LTDA",
        "Ativo total: R$ 8.114.220,00",
    ])
    pdf(p / "DRE.pdf", [
        "DEMONSTRACAO DO RESULTADO DO EXERCICIO",
        "Exercicio 2025",
        "Receita liquida: R$ 11.902.330,00",
        "Lucro liquido: R$ 1.284.900,00",
    ])
    pdf(p / "cnh socio.pdf", [
        "CARTEIRA NACIONAL DE HABILITACAO",
        "NOME: MARCELO AUGUSTO PEREIRA",
        "CPF: 123.456.789-00",
    ])
    pdf(p / "IR marcelo.pdf", [
        "DECLARACAO DE AJUSTE ANUAL - IRPF",
        "Exercicio 2026 ano-calendario 2025",
        "MARCELO AUGUSTO PEREIRA",
        "Recibo de entrega numero 12.34.56.78.90",
    ])
    pdf(p / "conta de luz.pdf", [
        "ENEL DISTRIBUICAO SAO PAULO",
        "COMPROVANTE DE ENDERECO",
        "ACME LOGISTICA E TRANSPORTES LTDA",
        "AV DAS INDUSTRIAS 1200 - GALPAO 3",
        f"Vencimento: {br(140)}",
    ])
    pdf(p / "serasa.pdf", [
        "SERASA EXPERIAN - RELATORIO CONCENTRE",
        "ACME LOGISTICA E TRANSPORTES LTDA",
        "Score: 712 - Nenhuma pendencia financeira",
        f"Emitido em: {br(58)}",
    ])
    pdf(p / "scan0042.pdf", [
        "Anotacoes internas",
        "Contato do cliente e valores conversados por telefone",
    ])
    (p / "observacoes do indicador.txt").write_text(
        "Rodrigo: o cliente precisa de 1,5mi pra capital de giro, tem 2 galpoes proprios.\n"
        "Falta o Registrato, ele vai puxar amanha.\n",
        encoding="utf-8",
    )


# ------------------------------------------------------------------ empresas


def doc(tipo: str, arquivo: str, comp: str | None = None, emissao: str | None = None,
        alertas: list[str] | None = None, leva: str = "primeira_leva") -> dict:
    return {
        "tipo": tipo, "arquivo": arquivo, "origem": arquivo, "leva": leva,
        "competencia": comp, "emissao": emissao, "fonte_data": "documento",
        "confianca": 9, "alertas": alertas or [], "triado_em": d(10),
    }


DOSSIE_COMPLETO = [
    doc("FICHA_CADASTRAL", "01-FICHA-CADASTRAL_X.pdf", emissao=d(20)),
    doc("CONTRATO_SOCIAL", "02-CONTRATO-SOCIAL_X.pdf", emissao=d(400)),
    doc("CARTAO_CNPJ", "03-CARTAO-CNPJ_X.pdf", emissao=d(12)),
    doc("FATURAMENTO_12M", "05-FATURAMENTO-12M_X_2026-06.pdf", comp="2026-06", emissao=d(20)),
    doc("BALANCO", "06-BALANCO_X_2025.pdf", comp="2025", emissao=d(120)),
    doc("DRE", "07-DRE_X_2025.pdf", comp="2025", emissao=d(120)),
    doc("EXTRATO_BANCARIO", "11-EXTRATO-BANCARIO_X_ITAU_2026-04.pdf", comp="2026-04", emissao=d(100)),
    doc("EXTRATO_BANCARIO", "11-EXTRATO-BANCARIO_X_ITAU_2026-05.pdf", comp="2026-05", emissao=d(70)),
    doc("EXTRATO_BANCARIO", "11-EXTRATO-BANCARIO_X_ITAU_2026-06.pdf", comp="2026-06", emissao=d(40)),
    doc("ENDIVIDAMENTO", "12-ENDIVIDAMENTO_X.pdf", emissao=d(25)),
    doc("DOC_SOCIO", "19-DOC-SOCIO_X_SOCIO-1.pdf", emissao=d(300)),
    doc("DOC_SOCIO", "19-DOC-SOCIO_X_SOCIO-2.pdf", emissao=d(300)),
    doc("IRPF_SOCIO", "20-IRPF-SOCIO_X_SOCIO-1_2026.pdf", comp="2026", emissao=d(90)),
    doc("IRPF_SOCIO", "20-IRPF-SOCIO_X_SOCIO-2_2026.pdf", comp="2026", emissao=d(90)),
    doc("COMPROVANTE_ENDERECO", "21-COMPROVANTE-ENDERECO_X.pdf", emissao=d(35)),
]


def materializa(empresa: dict) -> None:
    """Escreve um PDF de exemplo para cada documento já registrado, para que o
    dossiê anexado nos envios seja um arquivo de verdade."""
    destino = config.EMPRESAS / empresa["slug"] / "01-primeira-leva"
    for d in empresa.get("documentos", []):
        alvo = destino / d["arquivo"]
        if alvo.exists():
            continue
        pdf(alvo, [
            d["arquivo"],
            empresa["razao_social"],
            "Documento de exemplo gerado pelo protótipo.",
        ])


def cria() -> None:
    config.garante_pastas()

    # 1. Acme — acabou de chegar, documentação crua na inbox
    acme = store.nova(
        "Acme Logística e Transportes Ltda", cnpj="21345678000190", setor="logistica",
        faturamento_anual=12_480_000, necessidade=1_500_000, produto="capital_giro",
        garantia="imovel", parceiro="esc_lima", qtd_socios=1,
        contato_empresa={"nome": "Marcelo Pereira", "email": "marcelo@exemplo-acme.com.br",
                         "whatsapp": "+55 11 92000-0001"},
        observacoes="Dois galpões próprios, um pode entrar como garantia.",
    )
    acme["criado_em"] = d(2) + "T09:12:00"
    acme["status_desde"] = d(2)
    store.salva(acme)
    caixa_acme(acme["slug"])

    # 2. Brasa Alimentos — enviada a 3 gerentes, ninguém respondeu
    brasa = store.nova(
        "Brasa Alimentos Indústria Ltda", cnpj="33456789000121", setor="industria",
        faturamento_anual=42_000_000, necessidade=3_000_000, produto="capital_giro",
        garantia="recebiveis", parceiro="esc_vertice", qtd_socios=2,
        contato_empresa={"nome": "Helena Sartori", "email": "helena@exemplo-brasa.com.br",
                         "whatsapp": "+55 11 92000-0002"},
    )
    brasa["documentos"] = [dict(x, arquivo=x["arquivo"].replace("_X_", "_BRASA_").replace("_X.", "_BRASA."))
                           for x in DOSSIE_COMPLETO]
    brasa["envios"] = [
        {"gerente": g, "tipo": "primeira_leva", "enviado_em": d(7), "status_envio": "enviado",
         "resposta": None, "respondido_em": None, "ultimo_followup": None, "notas": []}
        for g in ("bruno_itau", "diego_btg", "marcos_daycoval")
    ]
    store.muda_status(brasa, "em_analise", "dossiê enviado")
    brasa["status_desde"] = d(7)
    brasa["proximo_passo"] = "Cobrar retorno dos três gerentes"
    store.salva(brasa)

    # 3. Nordeste Têxtil — parceiro fraco, documentação capenga e vencida
    tex = store.nova(
        "Nordeste Têxtil Comércio Ltda", cnpj="44567890000132", setor="varejo",
        faturamento_anual=6_200_000, necessidade=800_000, produto="capital_giro",
        garantia="aval", parceiro="cons_tavares", qtd_socios=2,
        contato_empresa={"nome": "Jussara Belmiro", "email": "jussara@exemplo-nordestetextil.com.br",
                         "whatsapp": "+55 81 92000-0003"},
    )
    tex["documentos"] = [
        doc("CONTRATO_SOCIAL", "02-CONTRATO-SOCIAL_NORDESTE.pdf", emissao=d(900)),
        doc("CARTAO_CNPJ", "03-CARTAO-CNPJ_NORDESTE.pdf", emissao=d(97),
            alertas=[f"VENCIDO há 67 dia(s) — emitido em {br(97)}, validade de 30 dias. Precisa reemitir."]),
        doc("FATURAMENTO_12M", "05-FATURAMENTO-12M_NORDESTE_2025-11.pdf", comp="2025-11", emissao=d(240),
            alertas=["defasado: competência 2025-11 tem 9 meses — pedir atualizado"]),
        doc("EXTRATO_BANCARIO", "11-EXTRATO-BANCARIO_NORDESTE_BRADESCO_2026-06.pdf", comp="2026-06", emissao=d(40)),
        doc("DOC_SOCIO", "19-DOC-SOCIO_NORDESTE_JUSSARA.pdf", emissao=d(500)),
    ]
    store.muda_status(tex, "pendente_documentos", "triagem apontou 6 pendências")
    tex["status_desde"] = d(9)
    tex["proximo_passo"] = "Cobrar Eduardo Tavares — falta metade do dossiê"
    store.salva(tex)

    # 4. Metalúrgica Kuhn — pré-aprovada, banco pediu segunda leva
    kuhn = store.nova(
        "Metalúrgica Kuhn S/A", cnpj="55678901000143", setor="industria",
        faturamento_anual=88_000_000, necessidade=6_000_000, produto="capital_giro",
        garantia="imovel", parceiro="cont_horizonte", qtd_socios=3,
        contato_empresa={"nome": "Otávio Kuhn", "email": "otavio@exemplo-kuhn.com.br",
                         "whatsapp": "+55 47 92000-0004"},
    )
    kuhn["documentos"] = [dict(x, arquivo=x["arquivo"].replace("_X_", "_KUHN_").replace("_X.", "_KUHN."))
                          for x in DOSSIE_COMPLETO]
    kuhn["envios"] = [
        {"gerente": "diego_btg", "tipo": "primeira_leva", "enviado_em": d(14), "status_envio": "enviado",
         "resposta": "pre_aprovado", "respondido_em": d(6),
         "notas": [{"data": d(6), "texto": "Pré-aprovado 6mi em 36x, condicionado às certidões e ao ECF"}]},
        {"gerente": "bruno_itau", "tipo": "primeira_leva", "enviado_em": d(14), "status_envio": "enviado",
         "resposta": "recusado", "respondido_em": d(9),
         "notas": [{"data": d(9), "texto": "Recusou por concentração no setor"}]},
    ]
    kuhn["pendencias"] = [
        "Certidão negativa federal (RFB/PGFN)",
        "Certidão de regularidade do FGTS",
        "CNDT trabalhista",
        "ECF do último exercício",
        "Matrícula atualizada do imóvel dado em garantia",
    ]
    kuhn["solicitante_complementar"] = "Diego Ferraz"
    kuhn["checklist_pacote"] = "primeira_leva_padrao"
    store.muda_status(kuhn, "pendente_complementar", "Diego Ferraz pediu segunda leva")
    kuhn["status_desde"] = d(6)
    kuhn["proximo_passo"] = "Cobrar Otávio as 5 certidões pedidas pelo BTG"
    kuhn["calls"] = [{
        "data": iso(HOJE + timedelta(days=2)), "hora": "14:30", "gerente": "diego_btg",
        "responsavel": "Rafael (comercial)", "status": "agendada",
        "preparo": "mandar resumo da operação e o balanço 2025 para o Rafael na véspera",
    }]
    store.salva(kuhn)

    # 5. Clínica Vitalis — proposta na mesa
    vit = store.nova(
        "Clínica Vitalis Serviços Médicos Ltda", cnpj="66789012000154", setor="saude",
        faturamento_anual=9_800_000, necessidade=1_200_000, produto="antecipacao_recebiveis",
        garantia="recebiveis", parceiro="esc_vertice", qtd_socios=2,
        contato_empresa={"nome": "Dra. Camila Rezende", "email": "camila@exemplo-vitalis.com.br",
                         "whatsapp": "+55 31 92000-0005"},
    )
    vit["documentos"] = [dict(x, arquivo=x["arquivo"].replace("_X_", "_VITALIS_").replace("_X.", "_VITALIS."))
                         for x in DOSSIE_COMPLETO]
    vit["envios"] = [
        {"gerente": "carla_santander", "tipo": "primeira_leva", "enviado_em": d(18), "status_envio": "enviado",
         "resposta": "proposta", "respondido_em": d(3),
         "notas": [{"data": d(3), "texto": "Proposta: 1,2mi antecipação, taxa 1,49% a.m."}]},
        {"gerente": "renata_fundo_atlas", "tipo": "primeira_leva", "enviado_em": d(18), "status_envio": "enviado",
         "resposta": "pre_aprovado", "respondido_em": d(5), "notas": []},
    ]
    store.muda_status(vit, "proposta_emitida", "Santander emitiu proposta")
    vit["status_desde"] = d(3)
    vit["proximo_passo"] = "Levar as duas condições para a Dra. Camila comparar"
    vit["calls"] = [{
        "data": iso(HOJE + timedelta(days=1)), "hora": "10:00", "gerente": "carla_santander",
        "responsavel": "Rafael (comercial)", "status": "agendada",
        "preparo": "comparativo das duas propostas em uma página",
    }]
    store.salva(vit)

    # 6. Transportes Duarte — assinando
    dua = store.nova(
        "Transportes Duarte Ltda", cnpj="77890123000165", setor="transporte",
        faturamento_anual=23_000_000, necessidade=2_200_000, produto="capital_giro",
        garantia="aval", parceiro="esc_lima", qtd_socios=1,
        contato_empresa={"nome": "Sérgio Duarte", "email": "sergio@exemplo-duarte.com.br",
                         "whatsapp": "+55 11 92000-0006"},
    )
    dua["documentos"] = [dict(x, arquivo=x["arquivo"].replace("_X_", "_DUARTE_").replace("_X.", "_DUARTE."))
                         for x in DOSSIE_COMPLETO]
    dua["envios"] = [
        {"gerente": "marcos_daycoval", "tipo": "primeira_leva", "enviado_em": d(28), "status_envio": "enviado",
         "resposta": "proposta", "respondido_em": d(11), "notas": []},
    ]
    store.muda_status(dua, "em_formalizacao", "contrato em assinatura")
    dua["status_desde"] = d(8)
    dua["proximo_passo"] = "Cobrar Marcos a data de liberação"
    store.salva(dua)

    # 7. Studio Belle — encerrada
    belle = store.nova(
        "Studio Belle Estética Ltda", cnpj="88901234000176", setor="servicos",
        faturamento_anual=1_400_000, necessidade=250_000, produto="capital_giro",
        garantia="aval", parceiro="cons_tavares", qtd_socios=1,
    )
    belle["restricoes"] = {"serasa": True, "protestos": True}
    belle["envios"] = [
        {"gerente": "paulo_sicoob", "tipo": "primeira_leva", "enviado_em": d(40), "status_envio": "enviado",
         "resposta": "recusado", "respondido_em": d(31), "notas": [{"data": d(31), "texto": "Restritivo ativo"}]},
        {"gerente": "renata_fundo_atlas", "tipo": "primeira_leva", "enviado_em": d(40), "status_envio": "enviado",
         "resposta": "recusado", "respondido_em": d(29), "notas": [{"data": d(29), "texto": "Sem recebível para lastrear"}]},
    ]
    store.muda_status(belle, "recusado", "duas recusas, sem alternativa no momento")
    belle["status_desde"] = d(29)
    belle["proximo_passo"] = "Retomar quando limpar o restritivo"
    store.salva(belle)

    for e in store.todas():
        materializa(e)

    print(f"✓ {len(list(store.todas()))} empresas criadas em pipeline/")
    inbox_acme = config.INBOX / "acme-logistica-transportes"
    print(f"✓ caixa de entrada de exemplo em inbox/{inbox_acme.name}/ "
          f"({len(list(inbox_acme.iterdir()))} arquivos)")
    print("\nComece por:  ./corresp hoje")


def limpa() -> None:
    for pasta in (config.PIPELINE, config.EMPRESAS, config.INBOX, config.SAIDA):
        if pasta.exists():
            shutil.rmtree(pasta)
    config.garante_pastas()


if __name__ == "__main__":
    if "--limpar" in sys.argv:
        limpa()
    cria()
