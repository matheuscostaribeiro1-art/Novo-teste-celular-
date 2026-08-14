---
description: Roda a fila do dia e dispara as cobranças pendentes
---

Toque a rotina de cobrança de hoje.

1. `./corresp hoje --textos`.

2. Antes de mandar, dê uma passada de realidade em cada item:
   - já respondeu por outro canal? confira o Gmail antes de cobrar de novo;
   - o gerente pediu prazo? então adie em vez de cobrar;
   - o parceiro recebeu a mesma cobrança ontem? junte tudo numa mensagem só.

3. Para cada cobrança que sobrar, ajuste o texto ao histórico daquela relação
   (`eventos` no JSON da empresa mostra quantas vezes já cobramos) e mande pelo
   canal indicado. Cobrança do terceiro lembrete não pode ter o mesmo tom do
   primeiro — seja mais direta sobre a consequência, sem ser grosseira.

4. Depois de mandar, `./corresp cobrar <empresa> --registrar` para não repetir
   amanhã.

5. Regenere o painel com `./corresp painel` e me dê um resumo curto: o que saiu,
   o que ficou parado por decisão minha e o que está travado esperando terceiro.

$ARGUMENTS
