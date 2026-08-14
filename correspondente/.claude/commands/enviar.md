---
description: Escolhe os gerentes de uma empresa e dispara os e-mails um a um
---

Envie a empresa indicada em $ARGUMENTS para os gerentes.

1. `./corresp checklist <empresa>`. Se algum item obrigatório trava o envio, pare
   e me mostre o que falta — não force.

2. `./corresp gerentes <empresa>`. Leia os impeditivos, não só o score, e me
   proponha a lista final com uma linha de justificativa por gerente. Considere:
   - quem já está com muita coisa sua parada na mesa;
   - quem tem apetite real para o setor e o ticket;
   - se vale segurar um gerente para uma segunda rodada, caso os primeiros recusem.
   Espere eu confirmar a lista.

3. `./corresp enviar <empresa> -g <lista>` para gerar os e-mails.

4. Antes de disparar, leia cada `.md` gerado e personalize o corpo com o que você
   sabe daquele gerente (campo `observacoes` em `config/gerentes.json`) e com o que
   há de forte nessa operação especificamente. Não mande o mesmo texto para todos.

5. Envie **um e-mail por gerente, separadamente, sem cópia e sem cco**, anexando o
   zip do dossiê que está na pasta do lote. Confirme cada envio antes do próximo.

6. No fim: liste o que saiu, para quem, e o que o `corresp` registrou no pipeline.
