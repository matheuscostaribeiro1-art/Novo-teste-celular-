# Mesa do correspondente bancário — protótipo

Ferramenta de esteira para quem recebe empresas de parceiros indicadores, monta o
dossiê de crédito PJ e envia para gerentes de bancos e fundos **um a um**.

Resolve os quatro gargalos do dia a dia:

| Gargalo | O que a ferramenta faz |
|---|---|
| Conferir e renomear a documentação que chega por e-mail | Lê o conteúdo de cada anexo, identifica o tipo, extrai competência e data de emissão, checa validade e renomeia tudo no padrão do dossiê |
| Parceiro que manda documentação incompleta ou defasada | Confronta com o checklist do produto e devolve a lista de pendências já escrita para cobrar |
| Envio um a um para não cruzar gerentes | Ranqueia gerentes por apetite real e gera um e-mail separado por gerente, cada um com o dossiê anexado — nunca em cópia |
| Perder o fio do que está com quem | SLA por etapa em dias úteis, fila diária de cobrança com o texto pronto, e painel HTML da esteira |

Tudo roda local, sem servidor e sem dependência externa: Python 3.11+ da máquina.
O estado fica em JSON legível, versionável em git.

## Começando

```bash
cd correspondente
python3 demo/seed.py          # popula uma esteira de exemplo (opcional)
./corresp hoje                # a fila do dia
./corresp painel --abrir      # o painel no navegador
```

Para começar do zero, apague `pipeline/`, `empresas/`, `inbox/` e `saida/`, e
edite os quatro arquivos de `config/`.

## O ciclo completo

```bash
# 1. entrou empresa nova
./corresp nova "Acme Logística e Transportes Ltda" \
    --cnpj 21345678000190 --setor logistica \
    --faturamento 12480000 --necessidade 1500000 \
    --parceiro esc_lima --socios 1

# 2. jogue os anexos do e-mail em inbox/acme-logistica-transportes/ e triage
./corresp triagem acme                 # simulação: mostra o que entendeu
./corresp triagem acme --aplicar       # move e renomeia

# 3. o que falta, com texto pronto para cobrar o indicador
./corresp checklist acme --texto

# 4. para quem vale mandar
./corresp gerentes acme

# 5. um e-mail por gerente, sem cópia
./corresp enviar acme -g bruno_itau,carla_santander,renata_fundo_atlas

# 6. o que o gerente respondeu
./corresp resposta acme bruno_itau pediu_documento --pendencia "CND federal; FGTS; ECF"

# 7. call do gerente com o dono (quem acompanha é outra pessoa)
./corresp call acme --data 2026-08-20 --hora 14:30 --gerente bruno_itau \
    --responsavel "Rafael (comercial)" --preparo "resumo da operação na véspera"

# 8. rotina
./corresp hoje --textos
./corresp cobrar acme --registrar
./corresp painel
```

## Triagem: o que ela reconhece

23 tipos de documento de crédito PJ (`./corresp tipos`), com regra de validade e
de competência para cada um. A leitura usa o nome do arquivo **e** o texto de
dentro do PDF — funciona com `foto123.pdf` e `scan0042.pdf`.

O que ela devolve por arquivo:

- tipo do documento e nome novo no padrão `NN-TIPO_EMPRESA[_EXTRA][_COMPETENCIA].pdf`,
  numerado na ordem em que o gerente espera ler o dossiê;
- competência (mês/ano de referência) e data de emissão;
- alerta de vencido, de "vence em X dias" e de competência defasada;
- banco identificado, no caso de extrato, e nome do sócio, no caso de documento pessoal;
- o que não deu para identificar vai para `_nao-identificados/`, para conferência
  manual — nunca é chutado para dentro do dossiê.

PDF escaneado sem camada de texto não é lido por regra — cai em não identificado.
Se instalar `pypdf` ou `poppler-utils` a extração melhora; com OCR (`ocrmypdf`)
passa a ler escaneado também.

## Envio individual

`./corresp gerentes <empresa>` ranqueia cada gerente cadastrado por faturamento,
ticket, setor, produto, garantia, tolerância a restritivo, tempo médio de retorno
e quantas propostas suas já estão paradas com ele. Mostra **impeditivos**, não só
score — "não trabalha construção civil" vale mais que qualquer nota.

`./corresp enviar` gera, por gerente:

- `NN_<gerente>.md` — assunto e corpo, para o Claude enviar pelo Gmail;
- `NN_<gerente>.eml` — o mesmo e-mail já com o dossiê zipado anexado, é só abrir;
- e uma linha no `manifest.json` do lote.

Um arquivo por gerente. Nenhum deles aparece para o outro.

## Fila do dia

`./corresp hoje` percorre a esteira e devolve o que venceu o SLA da etapa, em
dias úteis (feriados nacionais fixos já descontados), ordenado por urgência:

- gerente que recebeu e não voltou;
- parceiro indicador com documento pendente que trava o envio;
- dono de empresa com a segunda leva pedida pelo banco;
- o que depende só de você (triagem parada, dossiê pronto sem envio);
- documento vencendo ou defasado.

Com `--textos`, cada item já vem com a mensagem escrita, no canal certo.
Os prazos de cada etapa estão em `config/regras.json`.

## Com o Claude Code

O `CLAUDE.md` na raiz ensina o Claude a operar a mesa, e há quatro comandos em
`.claude/commands/`:

| Comando | O que faz |
|---|---|
| `/entrada` | varre o Gmail, cadastra a empresa, baixa os anexos, tria e resolve os não identificados lendo o conteúdo |
| `/enviar` | escolhe os gerentes com você, personaliza cada e-mail e dispara um a um |
| `/retornos` | lê as respostas dos gerentes e atualiza status, pendências e calls |
| `/cobrar` | roda a fila do dia, confere se já houve resposta, manda e registra |

A divisão é proposital: o CLI faz o que precisa ser sempre igual (classificar,
conferir validade, contar prazo, gerar arquivo); o Claude faz o que precisa de
julgamento (ler o e-mail, decidir o tom da terceira cobrança, escolher entre dois
gerentes parecidos).

## Estrutura

```
config/     gerentes, parceiros, checklists e SLA — é aqui que você configura
core/       motor: triagem, checklist, envios, cobrança, painel
templates/  textos de e-mail e cobrança
pipeline/   um JSON por empresa (o estado)
inbox/      anexos crus por empresa
empresas/   dossiês renomeados
saida/      envios gerados e painel.html
```

## Limites deste protótipo

- Não lê e-mail sozinho: quem faz isso é o Claude, pelos comandos acima.
- Não lê PDF escaneado sem OCR instalado.
- Não valida se o documento é verdadeiro nem se o balanço fecha — confere tipo,
  competência e validade.
- Os gerentes, parceiros e empresas do `demo/` são fictícios.
