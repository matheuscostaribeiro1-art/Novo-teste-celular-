---
description: Lê as respostas dos gerentes no Gmail e atualiza o pipeline
---

Atualize o pipeline com o que os gerentes responderam.

1. Para cada empresa com envio sem resposta (`./corresp lista --ativas` e o campo
   `envios` de cada JSON), procure no Gmail a thread com aquele gerente.

2. Classifique a resposta:
   - avançou / gostou / mandou para o comitê → `pre_aprovado`
   - pediu documento → `pediu_documento`, com `--pendencia "item; item"` exatamente
     como ele escreveu
   - declinou → `recusado`, com `--nota` explicando o motivo real (isso alimenta o
     apetite do gerente e evita mandar caso parecido de novo)
   - mandou condições → `proposta`, com `--nota "valor, prazo, taxa, garantia"`
   - marcou call com o dono → registre com `./corresp call`

3. Registre com `./corresp resposta ...` e, quando o gerente pediu documentos que
   a empresa já mandou na primeira leva, me avise em vez de cobrar de novo o dono.

4. Se a resposta abriu segunda leva, monte o checklist complementar
   (`./corresp checklist <empresa> --pacote segunda_leva_padrao --texto`) e prepare
   a cobrança para quem tem o documento — o dono ou o contador, não o parceiro.

5. Se algum gerente respondeu algo que muda a leitura da operação (ex.: apontou um
   risco que não tínhamos visto), me diga explicitamente — isso vale mais que o
   status.

$ARGUMENTS
