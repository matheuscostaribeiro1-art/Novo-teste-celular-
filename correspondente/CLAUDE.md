# Mesa do correspondente bancário

Este projeto é a mesa de operação de uma correspondente bancária de crédito PJ.
Ela recebe empresas de parceiros indicadores, monta o dossiê, envia para gerentes
de bancos e fundos **um a um**, e acompanha até a liberação.

Você (Claude) é a operação: lê e-mail, tria documento, escreve cobrança, dispara
envio e atualiza o pipeline. O CLI `./corresp` é a ferramenta determinística —
use-o em vez de reimplementar a lógica.

## Comandos

```bash
./corresp hoje [--textos]        # fila do dia, com as mensagens prontas
./corresp lista [--ativas]       # visão geral do pipeline
./corresp ver <empresa>          # ficha, envios, calls, histórico
./corresp nova "Razão Social" --cnpj ... --parceiro ... --necessidade ...
./corresp triagem <empresa> [--aplicar] [--leva complementar]
./corresp checklist <empresa> [--texto]
./corresp gerentes <empresa>     # ranking por apetite, com impeditivos
./corresp enviar <empresa> -g cod1,cod2 [--tipo complementar --pedido "..."]
./corresp resposta <empresa> <gerente> <pre_aprovado|pediu_documento|recusado|proposta> [--nota] [--pendencia "a; b"]
./corresp call <empresa> --data AAAA-MM-DD --hora 14:30 --gerente cod --responsavel "Rafael"
./corresp cobrar <empresa> [--registrar]
./corresp status <empresa> <status> [--proximo "..."]
./corresp painel [--abrir]
./corresp tipos                  # catálogo de documentos reconhecidos
```

## Onde ficam as coisas

| Caminho | O que é |
|---|---|
| `pipeline/<empresa>.json` | estado de cada empresa — leia e edite direto quando o CLI não cobrir |
| `inbox/<empresa>/` | anexos crus, do jeito que chegaram no e-mail |
| `empresas/<empresa>/01-primeira-leva/` | dossiê renomeado e conferido |
| `empresas/<empresa>/_nao-identificados/` | o que a triagem não reconheceu — **resolva isso lendo o arquivo** |
| `saida/envios/<empresa>/<data>_<tipo>/` | e-mails individuais + dossiê zipado + `manifest.json` |
| `config/gerentes.json` | gerentes, contatos e apetite de crédito |
| `config/parceiros.json` | parceiros indicadores e a qualidade documental de cada um |
| `config/checklists.json` | o que cada pacote de documentação exige |
| `config/regras.json` | SLA por status e dados do operador |
| `templates/*.md` | textos de e-mail e cobrança (`{{campo}}` é substituído) |

## Regras da casa

1. **Nunca mande um e-mail com cópia para mais de um gerente.** O relacionamento
   com cada um é individual e um gerente saber que a operação está com outros
   queima a mesa. `corresp enviar` já gera um e-mail por gerente — envie um a um.
2. **Não envie dossiê incompleto** sem avisar. `corresp enviar` trava quando um
   item obrigatório falta; só use `--forcar` se a pessoa pedir explicitamente.
3. **Documento vencido é retrabalho garantido.** Cartão CNPJ (30 dias), FGTS
   (30 dias) e Serasa (30 dias) vencem rápido — deixe para emitir por último.
4. **A call é de outra pessoa.** O gerente conversa com o dono, quem acompanha é
   o comercial. Sua parte é registrar a call, preparar o material e cobrar o
   resultado depois — não tente conduzir.
5. **Registre a cobrança** com `corresp cobrar <empresa> --registrar` depois de
   mandar, senão o mesmo item volta na fila amanhã.

## Fluxos

### Chegou documentação nova por e-mail
1. Busque a thread no Gmail e baixe os anexos para `inbox/<slug>/`.
2. `./corresp nova "..."` se a empresa ainda não existir (pegue CNPJ, faturamento,
   necessidade e parceiro do corpo do e-mail).
3. `./corresp triagem <slug>` para ver a leitura, depois `--aplicar`.
4. Abra cada arquivo em `_nao-identificados/` e classifique você mesmo: renomeie
   no padrão `NN-TIPO_SLUG[_EXTRA][_COMPETENCIA].ext`, mova para
   `01-primeira-leva/` e acrescente a entrada em `documentos` no JSON da empresa.
5. `./corresp checklist <slug> --texto` e mande a lista de pendências ao parceiro.

### Enviar para os gerentes
1. `./corresp gerentes <slug>` — leia os impeditivos, não só o score.
2. `./corresp enviar <slug> -g cod1,cod2,cod3`.
3. Envie cada `.md` da pasta gerada como um e-mail separado, anexando o zip do
   dossiê. **Um envio por vez, sem cópia, sem cco.**
4. Confirme o que foi enviado e para quem.

### Gerente respondeu
- Pré-aprovou: `./corresp resposta <slug> <gerente> pre_aprovado --nota "..."`
- Pediu mais documento: `./corresp resposta <slug> <gerente> pediu_documento --pendencia "CND federal; FGTS; ECF"`
- Recusou: `./corresp resposta <slug> <gerente> recusado --nota "motivo"`
- Emitiu proposta: `./corresp resposta <slug> <gerente> proposta --nota "valor, prazo, taxa"`

### Rotina do dia
`./corresp hoje --textos`, e para cada item: mande a mensagem pelo canal indicado,
depois `./corresp cobrar <slug> --registrar`. Feche com `./corresp painel`.

## Como escrever as mensagens

Português brasileiro, direto, sem formalidade de circular. Frases curtas. Nunca
prometa prazo de banco. Com gerente, o tom é de par: você traz operação boa, ele
responde. Com parceiro indicador que atrasa, seja específico sobre o custo do
atraso — não genérico. Com dono de empresa, explique o porquê de cada documento.

Os templates em `templates/` são o ponto de partida; adapte ao caso, mas mantenha
o formato `ASSUNTO:` na primeira linha.
