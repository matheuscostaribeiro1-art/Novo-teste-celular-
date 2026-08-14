---
description: Varre o Gmail, baixa os anexos das indicações novas e roda a triagem
---

Processe a documentação que chegou por e-mail.

1. Busque no Gmail as threads não lidas dos parceiros indicadores cadastrados em
   `config/parceiros.json` (procure pelos e-mails deles) e também qualquer thread
   com anexo cujo assunto cite CNPJ, "crédito", "análise", "capital de giro" ou o
   nome de uma empresa. Considere os últimos 7 dias, salvo se eu pedir outro período.

2. Para cada thread, identifique de que empresa se trata. Se ela já existe em
   `pipeline/`, é documentação adicional. Se não existe, leia o corpo do e-mail e
   cadastre com `./corresp nova`, preenchendo o que der para extrair: CNPJ, setor,
   faturamento anual, necessidade, produto, garantia, número de sócios, contato do
   dono e o código do parceiro que indicou. O que não estiver no e-mail, deixe em
   branco e me pergunte no fim — não invente.

3. Baixe todos os anexos para `inbox/<slug>/`, preservando o nome original.

4. Rode `./corresp triagem <slug>` (sem `--aplicar`) e me mostre a leitura.
   Se estiver coerente, rode com `--aplicar`.

5. Abra cada arquivo que caiu em `empresas/<slug>/_nao-identificados/`, leia o
   conteúdo e classifique manualmente: renomeie no padrão do dossiê, mova para
   `01-primeira-leva/` e acrescente a entrada correspondente no array `documentos`
   do JSON da empresa. Se realmente não for documento de crédito (recado, print,
   assinatura de e-mail), deixe onde está e diga que descartou.

6. Feche com o checklist de cada empresa processada e, quando faltar coisa, o
   texto de cobrança pronto para o parceiro — mas **não envie ainda**, me mostre.

$ARGUMENTS
