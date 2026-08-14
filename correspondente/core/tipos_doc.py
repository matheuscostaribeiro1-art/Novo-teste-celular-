"""Catálogo de tipos de documento de crédito PJ.

Cada tipo carrega:
  - `ordem`: posição no dossiê entregue ao gerente (vira prefixo do arquivo)
  - `padroes`: expressões que identificam o documento pelo nome do arquivo ou pelo texto
  - `validade_dias`: janela de aceitação a partir da data de emissão (None = não vence)
  - `competencia`: se o documento é mensal/anual e precisa de competência no nome
  - `por_socio` / `por_banco`: se pode haver várias vias legítimas do mesmo tipo
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TipoDoc:
    codigo: str
    nome: str
    ordem: int
    padroes: list[str] = field(default_factory=list)
    padroes_fortes: list[str] = field(default_factory=list)
    validade_dias: int | None = None
    competencia: bool = False
    por_socio: bool = False
    por_banco: bool = False
    nota: str = ""


CATALOGO: list[TipoDoc] = [
    TipoDoc(
        "FICHA_CADASTRAL", "Ficha cadastral / proposta assinada", 1,
        padroes=["ficha cadastral", "ficha de cadastro", "proposta assinada", "formulario cadastral"],
        padroes_fortes=["ficha cadastral"],
        validade_dias=90,
    ),
    TipoDoc(
        "CONTRATO_SOCIAL", "Contrato social / última alteração", 2,
        padroes=["contrato social", "alteracao contratual", "consolidacao contratual",
                 "estatuto social", "requerimento de empresario", "ato constitutivo"],
        padroes_fortes=["contrato social", "alteracao contratual", "estatuto social"],
        nota="Precisa ser a ÚLTIMA alteração, registrada na Junta.",
    ),
    TipoDoc(
        "CARTAO_CNPJ", "Cartão CNPJ", 3,
        padroes=["cartao cnpj", "comprovante de inscricao e de situacao cadastral", "qsa cnpj"],
        padroes_fortes=["comprovante de inscricao e de situacao cadastral", "cartao cnpj"],
        validade_dias=30,
        nota="Emitir novo na Receita — banco recusa cartão com mais de 30 dias.",
    ),
    TipoDoc(
        "CERTIDAO_SIMPLIFICADA", "Certidão simplificada da Junta", 4,
        padroes=["certidao simplificada", "certidao da junta", "jucesp", "jucemg", "jucerja", "junta comercial"],
        padroes_fortes=["certidao simplificada"],
        validade_dias=90,
    ),
    TipoDoc(
        "FATURAMENTO_12M", "Relação de faturamento 12 meses", 5,
        padroes=["faturamento", "relacao de faturamento", "receita bruta", "faturamento 12", "faturamento mensal"],
        padroes_fortes=["relacao de faturamento", "faturamento 12"],
        validade_dias=60,
        competencia=True,
        nota="Assinada pelo contador, com CRC. Precisa fechar até o mês anterior.",
    ),
    TipoDoc(
        "BALANCO", "Balanço patrimonial", 6,
        padroes=["balanco", "balanco patrimonial", "demonstracoes contabeis"],
        padroes_fortes=["balanco patrimonial"],
        competencia=True,
    ),
    TipoDoc(
        "DRE", "DRE", 7,
        padroes=["dre", "demonstracao do resultado", "demonstrativo de resultado"],
        padroes_fortes=["demonstracao do resultado", "dre"],
        competencia=True,
    ),
    TipoDoc(
        "BALANCETE", "Balancete do exercício corrente", 8,
        padroes=["balancete"],
        padroes_fortes=["balancete"],
        validade_dias=120,
        competencia=True,
    ),
    TipoDoc(
        "SPED_ECF", "SPED / ECF", 9,
        padroes=["sped", "ecf", "escrituracao contabil fiscal", "ecd"],
        padroes_fortes=["escrituracao contabil fiscal", "sped"],
        competencia=True,
    ),
    TipoDoc(
        "PGDAS", "PGDAS / Simples Nacional", 10,
        padroes=["pgdas", "simples nacional", "das ", "extrato do simples"],
        padroes_fortes=["pgdas"],
        competencia=True,
    ),
    TipoDoc(
        "EXTRATO_BANCARIO", "Extrato bancário", 11,
        padroes=["extrato", "extrato bancario", "conta corrente", "movimentacao bancaria",
                 "saldo final", "agencia conta"],
        padroes_fortes=["extrato bancario", "extrato de conta corrente", "extrato conta corrente"],
        validade_dias=75,
        competencia=True,
        por_banco=True,
        nota="Mínimo 3 meses fechados, um arquivo por banco/mês.",
    ),
    TipoDoc(
        "ENDIVIDAMENTO", "Relação de endividamento bancário", 12,
        padroes=["endividamento", "relacao de dividas", "relacao de emprestimos", "posicao de dividas",
                 "scr", "registrato"],
        padroes_fortes=["endividamento", "registrato"],
        validade_dias=60,
    ),
    TipoDoc(
        "RECEBIVEIS", "Relação de recebíveis / vendas cartão", 13,
        padroes=["recebiveis", "duplicatas", "vendas cartao", "agenda de recebiveis", "cielo", "getnet", "stone"],
        padroes_fortes=["agenda de recebiveis", "relacao de recebiveis"],
        validade_dias=45,
        competencia=True,
    ),
    TipoDoc(
        "CND_FEDERAL", "Certidão negativa federal (RFB/PGFN)", 14,
        padroes=["certidao negativa", "cnd federal", "receita federal", "pgfn", "certidao conjunta"],
        padroes_fortes=["certidao conjunta", "pgfn"],
        validade_dias=180,
    ),
    TipoDoc(
        "CND_FGTS", "Certidão FGTS (CRF)", 15,
        padroes=["fgts", "crf", "certificado de regularidade do fgts", "caixa economica"],
        padroes_fortes=["certificado de regularidade do fgts", "crf fgts"],
        validade_dias=30,
    ),
    TipoDoc(
        "CND_TRABALHISTA", "Certidão negativa trabalhista (CNDT)", 16,
        padroes=["cndt", "trabalhista", "tribunal superior do trabalho", "debitos trabalhistas"],
        padroes_fortes=["cndt", "debitos trabalhistas"],
        validade_dias=180,
    ),
    TipoDoc(
        "CND_ESTADUAL_MUNICIPAL", "Certidão estadual / municipal", 17,
        padroes=["certidao estadual", "certidao municipal", "sefaz", "prefeitura", "iss", "icms"],
        validade_dias=90,
    ),
    TipoDoc(
        "SERASA", "Relatório de crédito (Serasa/Boa Vista)", 18,
        padroes=["serasa", "boa vista", "spc", "relatorio de credito", "concentre", "score"],
        padroes_fortes=["serasa", "boa vista"],
        validade_dias=30,
    ),
    TipoDoc(
        "DOC_SOCIO", "Documento pessoal do sócio (RG/CNH)", 19,
        padroes=["rg", "cnh", "identidade", "carteira nacional", "documento socio", "cpf"],
        padroes_fortes=["carteira nacional de habilitacao", "registro geral"],
        por_socio=True,
    ),
    TipoDoc(
        "IRPF_SOCIO", "Imposto de renda do sócio", 20,
        padroes=["irpf", "imposto de renda", "declaracao de ajuste", "recibo de entrega"],
        padroes_fortes=["declaracao de ajuste anual", "irpf"],
        competencia=True,
        por_socio=True,
        nota="Declaração completa + recibo de entrega do último exercício.",
    ),
    TipoDoc(
        "COMPROVANTE_ENDERECO", "Comprovante de endereço", 21,
        padroes=["comprovante de endereco", "conta de luz", "conta de energia", "conta de agua",
                 "fatura enel", "cpfl", "sabesp", "telefone fixo"],
        padroes_fortes=["comprovante de endereco"],
        validade_dias=90,
    ),
    TipoDoc(
        "MATRICULA_IMOVEL", "Matrícula de imóvel (garantia)", 22,
        padroes=["matricula", "registro de imoveis", "certidao de matricula", "iptu", "avaliacao do imovel"],
        padroes_fortes=["certidao de matricula", "registro de imoveis"],
        validade_dias=30,
    ),
    TipoDoc(
        "PROCURACAO", "Procuração / autorização de consulta", 23,
        padroes=["procuracao", "autorizacao de consulta", "autorizacao scr", "termo de autorizacao"],
        padroes_fortes=["procuracao"],
        validade_dias=365,
    ),
    TipoDoc(
        "OUTROS", "Não identificado", 99,
        padroes=[],
    ),
]

POR_CODIGO: dict[str, TipoDoc] = {t.codigo: t for t in CATALOGO}


def tipo(codigo: str) -> TipoDoc:
    return POR_CODIGO.get(codigo, POR_CODIGO["OUTROS"])


def nome(codigo: str) -> str:
    return tipo(codigo).nome
