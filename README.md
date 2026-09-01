# Sistema Integrado de Atendimento e Execução de Serviços

Back-end da oficina mecânica — Tech Challenge Fase 1, Pós-Tech Software Architecture (FIAP), turma 15SOAT.

API REST que cobre o ciclo da Ordem de Serviço (abertura, diagnóstico, orçamento, aprovação do cliente,
execução, finalização e entrega), os cadastros de apoio (clientes, veículos, serviços) e o controle de
estoque de peças e insumos, com reserva e baixa amarradas ao fluxo da OS.

Monolito em camadas, Django + Django REST Framework, autenticação JWT e autorização por papel.

## Índice

- [Como rodar](#como-rodar) — o caminho rápido, com ou sem Docker
- [Stack](#stack) e [escolha do banco de dados](#escolha-do-banco-de-dados)
- [Configuração](#configuração-o-arquivo-env) — o `.env`, para quando for preciso
- [Rodando em Docker](#rodando-em-docker)
- [Autenticação](#autenticação) e [papéis e permissões](#papéis-e-permissões) — quem pode o quê
- [Fluxo de uma OS](#fluxo-de-uma-os-do-começo-ao-fim) — do cadastro do cliente à entrega do veículo
- [Estoque](#estoque) e [notificações](#notificações)
- [Endpoints](#endpoints) e [códigos de erro](#erros)
- [Testes](#testes), [estrutura do código](#estrutura) e [documentação de domínio](#documentação-de-domínio)

## Como rodar

Com Docker, um comando sobe o ambiente inteiro — banco, migrations, dados de exemplo e API:

```bash
docker compose up --build
```

Sem Docker, com Python 3.11+:

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_users
python manage.py seed_demo
python manage.py runserver
```

Nos dois casos não é preciso criar arquivo de configuração nem informar credencial nenhuma. Quando
terminar:

| | |
|---|---|
| Documentação da API | http://localhost:8000/api/docs/ |
| Usuário para entrar | `admin`, senha `oficina123` |
| Obter o token | `POST /api/token/` com esse usuário e senha |
| Usar o token | cabeçalho `Authorization: Bearer <access>` |

Os cinco papéis do sistema — atendente, mecânico, estoquista, admin e cliente — usam a mesma senha e
estão descritos em [Autenticação](#autenticação). O banco já vem com clientes, veículos, serviços e peças
de exemplo.

Para percorrer o ciclo completo de uma Ordem de Serviço, da identificação do cliente até a entrega do
veículo, siga o roteiro em [Fluxo de uma OS](#fluxo-de-uma-os-do-começo-ao-fim) ou importe o
`postman_collection.json`, que traz a sequência pronta e na ordem certa.

Além do Swagger, a documentação está em `/api/redoc/` e o schema OpenAPI cru em `/api/schema/`.
O `.env` só entra se quiser apontar para outro banco ou enviar e-mail de verdade; sem ele, as
notificações são registradas em log e nenhuma operação de negócio é interrompida.

## Stack

| | |
|---|---|
| Linguagem | Python 3.11 |
| Framework | Django 4.2 + Django REST Framework 3.15 |
| Autenticação | SimpleJWT |
| Documentação | drf-spectacular (Swagger / Redoc) |
| Banco | PostgreSQL — em contêiner no Docker, ou no Neon (SQLite ao rodar sem Docker) |
| Testes | `unittest` do Django + coverage |
| Container | Docker e Docker Compose |

## Escolha do banco de dados

PostgreSQL, por três motivos que vêm do domínio e não de preferência:

1. **O modelo é relacional de verdade.** São 9 tabelas e 11 chaves estrangeiras cuja regra de exclusão
   carrega significado: item de OS é `CASCADE` porque é parte do agregado; cliente, veículo, serviço e
   peça são `PROTECT` porque a OS os referencia mas não os possui. Deixar essa integridade no banco, e
   não só na aplicação, é o que garante que ninguém apague um cadastro com histórico vinculado.
2. **A reserva de estoque depende de bloqueio de linha.** O `EstoqueService` usa `select_for_update()`
   para conferir e reservar o saldo de cada peça sem que duas aprovações simultâneas reservem a mesma
   unidade. O Postgres bloqueia linha a linha; o SQLite serializa o banco inteiro e não sustenta esse
   cenário.
3. **Há invariante que só o banco fecha.** A unicidade da sequência do orçamento dentro da mesma OS é
   uma `UniqueConstraint` composta (`orcamento_sequencia_unica_por_os`), e CPF/CNPJ e placa são únicos
   por constraint. Validação em serializer não impede corrida.

A instância roda no **Neon**, um Postgres gerenciado. Para um MVP tocado por um grupo, resolve o que
interessa: todo mundo aponta para o mesmo banco sem ninguém manter servidor, o provisionamento é imediato
e o plano gratuito aguenta a carga da demonstração. Como é Postgres de verdade, nada no código muda por
causa disso — o mesmo `manage.py migrate` e os mesmos models valem para os dois.

O SQLite continua sendo o padrão quando `DB_HOST` não está definido. É a saída para clonar o repositório
e rodar a suíte de testes sem depender de rede — não é o alvo de produção.

## Configuração: o arquivo `.env`

Toda a configuração vive num `.env` na raiz do projeto, lido na subida da aplicação. Banco e e-mail
seguem o mesmo caminho: preencheu, funciona; deixou de fora, o projeto usa o padrão.

Crie o arquivo com este conteúdo e troque pelos valores de vocês:

```ini
# Banco — preencha para usar o Neon. DB_HOST vazio ou ausente = SQLite local.
DB_NAME=neondb
DB_USER=neondb_owner
DB_PASSWORD=sua-senha-do-neon
DB_HOST=ep-nome-do-projeto-123456.sa-east-1.aws.neon.tech
DB_PORT=5432

# E-mail — remetente das notificações da OS e dos alertas de estoque
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=oficina@gmail.com
EMAIL_HOST_PASSWORD=senha-de-app-do-gmail
DEFAULT_FROM_EMAIL=oficina@gmail.com
EMAIL_OPERACAO=operacao@oficina.com

# Django
SECRET_KEY=troque-esta-chave
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

Sem aspas e sem espaço em volta do `=`. Se algum valor tiver `#` no meio, aí sim ponha entre aspas duplas.

### De onde vêm os valores do Neon

O painel do Neon entrega tudo numa string só. Ela se quebra assim:

```
postgresql://neondb_owner:npg_AbC123@ep-nome-do-projeto-123456.sa-east-1.aws.neon.tech/neondb?sslmode=require
             └── DB_USER ─┘└DB_PASSWORD┘└──────────────── DB_HOST ─────────────────────┘ └DB_NAME┘
```

O que vem depois do `?` você descarta: o driver negocia TLS sozinho, porque o Neon só aceita conexão
criptografada. `DB_PORT` é sempre `5432`.

### Trocando de banco

A troca é automática e não envolve mexer no código. A aplicação olha o `DB_HOST` na subida e decide
sozinha: preenchido, usa o Postgres; vazio ou ausente, usa o SQLite. Nenhuma migration muda, nenhum model
muda, nenhum arquivo `.py` é tocado.

Depois de mexer no `.env`:

1. **Reinicie o servidor** — o arquivo é lido uma vez, na subida.
2. **Rode as migrations**, porque o banco do Neon começa vazio:
   `python manage.py migrate && python manage.py seed_users && python manage.py seed_demo`.

Os dados do SQLite não vão junto: `db.sqlite3` fica onde está, intacto, e volta a valer se você comentar
o `DB_HOST` de novo. É assim que se roda a suíte de testes localmente sem criar um banco de teste remoto.

Para confirmar em qual banco você está de verdade, em vez de supor:

```bash
python -c "import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','So_PosTech.settings');django.setup();from django.db import connection;print(connection.settings_dict['ENGINE'], connection.settings_dict['HOST'] or '(sqlite local)')"
```

Uma observação sobre o Neon: ele suspende a instância depois de um tempo ocioso, e a primeira consulta
depois disso acorda o banco e demora alguns segundos. Antes de uma demonstração, faça uma chamada
qualquer para aquecer.

### Referência das variáveis

| Variável | Padrão | Para que serve |
|---|---|---|
| `SECRET_KEY` | chave de desenvolvimento | Obrigatória fora do ambiente local |
| `DEBUG` | `True` | Deixe `False` em qualquer ambiente exposto |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Lista separada por vírgula |
| `DB_HOST` | vazio | Vazio = SQLite. Preenchido = Postgres |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_PORT` | `sopostech` / `postgres` / `postgres` / `5432` | Conexão do Postgres |
| `EMAIL_BACKEND` | SMTP | Use o de console para desenvolver |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_USE_TLS` | `smtp.gmail.com` / `587` / `True` | Servidor de envio |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | vazio | Credenciais do remetente |
| `DEFAULT_FROM_EMAIL` | `EMAIL_HOST_USER` | Remetente das mensagens |
| `EMAIL_OPERACAO` | vazio | Caixa da oficina, que recebe os alertas de estoque |

O `.env` está no `.gitignore` e não vai para o repositório — as credenciais do Neon e do e-mail ficam
com cada um.

## Rodando em Docker

Um comando sobe o ambiente inteiro:

```bash
docker compose up --build
```

Isso levanta dois contêineres — o Postgres e a aplicação — e faz o resto sozinho: espera o banco aceitar
conexão, aplica as migrations, roda os dois seeds e sobe a API com gunicorn. Ao terminar, o Swagger está
em `http://localhost:8000/api/docs/` e dá para entrar com qualquer um dos cinco usuários.

Não é preciso criar `.env` nem configurar nada antes. Sem SMTP configurado, as notificações são impressas
no log em vez de enviadas, o que na verdade ajuda na demonstração — dá para ver cada e-mail da OS
acontecendo:

```bash
docker compose logs -f api
```

Para derrubar tudo, incluindo o volume com os dados do banco:

```bash
docker compose down -v
```

### Apontando para o Neon em vez do Postgres local

Se existir um `.env` na raiz, os valores dele têm precedência sobre os padrões do `docker-compose.yml`.
Com o `DB_HOST` preenchido, a aplicação fala direto com o Neon e o contêiner de banco fica sem uso. Nada
mais muda: mesmo comando, mesma imagem.

### Detalhes que valem saber

O compose sobe com `DEBUG=False`, que é o certo para algo empacotado, mas isso significa que o Django não
serve os arquivos estáticos do `/admin/` — a área administrativa aparece sem estilo. A API, o Swagger e o
Redoc não dependem disso e funcionam normalmente. Para desenvolver com a página de erro detalhada:

```bash
DEBUG=True docker compose up
```

Os seeds rodam a cada subida. Como usam `update_or_create`, atualizam o que já existe em vez de duplicar,
então subir o ambiente várias vezes é seguro. O banco fica no volume `postgres_data` e sobrevive a um
`docker compose down` comum.

## Autenticação

Toda a API exige JWT. Ficam abertas apenas as rotas que não teriam como exigi-lo: `POST /api/token/`
e `/api/token/refresh/`, o cadastro em `POST /api/users/`, o `GET /api/health/` e a documentação
(`/api/docs/`, `/api/redoc/` e `/api/schema/`).

```bash
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"atendente\", \"password\": \"oficina123\"}"
```

A resposta traz `access` e `refresh`. Mande o access nas demais chamadas em `Authorization: Bearer
<token>`. O access vale 60 minutos; o refresh, 1 dia, e é rotacionado a cada `POST /api/token/refresh/`.

O `seed_users` cria um usuário por papel, todos com a senha `oficina123`:

| Usuário | Papel |
|---|---|
| `atendente` | Atendente |
| `mecanico` | Mecânico |
| `estoquista` | Estoquista |
| `admin` | Admin (também `is_staff`) |
| `cliente` | Sem papel — é o login de cliente |

Quem se cadastra sozinho pelo `POST /api/users/` nasce sem papel, ou seja, como cliente. Atribuir `type`
no cadastro exige um admin autenticado.

## Papéis e permissões

São cinco papéis, cada um com o seu pedaço do atendimento:

| Papel | O que faz na oficina |
|---|---|
| **Atendente** | Recebe o cliente, cadastra o veículo, abre a OS, envia o orçamento e registra a entrega |
| **Mecânico** | Faz o diagnóstico, inclui os serviços e as peças, executa os reparos e finaliza a OS |
| **Estoquista** | Cadastra peças e registra a entrada delas no estoque |
| **Admin** | Cuida do catálogo de serviços e dos usuários, e passa em qualquer operação dos demais |
| **Cliente** | Aprova ou recusa o orçamento e acompanha as próprias ordens de serviço |

Repare que reserva e baixa de estoque não aparecem em papel nenhum: são automáticas, disparadas pela
aprovação do orçamento e pela entrega do veículo. O estoquista repõe; quem consome é o fluxo da OS.

O papel de cada usuário fica em `UserModel.type` e é aplicado por ação nos viewsets, via
`PermissoesPorAcaoMixin`. O admin passa em qualquer operação de papel específico.

| Recurso | Consulta | Escrita |
|---|---|---|
| `/api/clientes/` | Autenticado (cliente vê só o próprio cadastro) | Atendente |
| `/api/veiculos/` | Autenticado (cliente vê só os seus) | Atendente |
| `/api/servicos/` | Autenticado | Admin |
| `/api/pecas/` | Operador (cliente não acessa) | Estoquista |
| `/api/ordens-servico/` | Autenticado (cliente vê só as suas) | Criar e editar: atendente. Excluir: admin |
| `/api/ordens-servico/{id}/diagnosticar/` e `/finalizar/` | — | Mecânico |
| `/api/ordens-servico/{id}/entregar/` e `/encerrar/` | — | Atendente |
| `/api/itens-servico/` | Operador | Mecânico ou atendente |
| `/api/itens-peca/` | Operador | Mecânico |
| `/api/orcamentos/` | Autenticado (cliente vê só os seus) | Gerar: mecânico. Enviar: atendente |
| `/api/orcamentos/{id}/aprovar/` e `/recusar/` | — | Cliente ou atendente |
| `/api/relatorios/tempo-medio-execucao/` | Operador | — |

Item de serviço pode ser incluído pelo atendente porque é item de catálogo e não move estoque. Item de
peça fica só com o mecânico, que é quem sabe se a peça serve naquele veículo.

O cliente aprova ou recusa o próprio orçamento; o atendente também pode registrar essa resposta, para o
caso de ela chegar por telefone ou balcão.

## Fluxo de uma OS, do começo ao fim

1. **Identificar o cliente.** `GET /api/clientes/?cpf_cnpj=529.982.247-25` — a busca compara só os
   dígitos, então acha com ou sem pontuação. Não achou, `POST /api/clientes/`.
2. **Cadastrar o veículo.** `POST /api/veiculos/`. A placa aceita o padrão antigo (`ABC1234`) e o
   Mercosul (`ABC1D23`), e é normalizada para maiúscula sem hífen antes de gravar.
3. **Abrir a OS.** `POST /api/ordens-servico/` com `cliente`, `veiculo` e `descricao`, que é a queixa do
   cliente. Nasce em **Recebida**. A API recusa se o veículo não pertencer ao cliente informado.
4. **Diagnosticar.** `POST /api/ordens-servico/{id}/diagnosticar/` com o parecer do mecânico.
   → **Em diagnóstico**. Chamar de novo com a OS já em diagnóstico apenas revisa o parecer.
5. **Incluir itens.** `POST /api/itens-servico/` e `POST /api/itens-peca/`. Cada item copia para si o
   preço vigente do catálogo, e o orçamento é gerado e recalculado sozinho a cada inclusão — não existe
   passo manual de montar orçamento. Incluir peça **não** reserva estoque.
6. **Enviar ao cliente.** `POST /api/orcamentos/{id}/enviar/` → **Aguardando aprovação**. A partir daqui
   os itens desse orçamento ficam travados: para mexer na proposta, registre a recusa e remonte.
7. **Resposta do cliente.**
   - `POST /api/orcamentos/{id}/aprovar/` reserva as peças e leva a OS para **Em execução**.
   - `POST /api/orcamentos/{id}/recusar/` tira os itens recusados da OS e devolve para **Em diagnóstico**,
     onde o mecânico refaz a proposta. O orçamento recusado fica no histórico, com o que foi proposto e
     por quanto.
8. **Reparo adicional.** Item incluído com a OS em execução nasce sem orçamento e abre o orçamento
   seguinte. Enviar leva a OS de volta para **Aguardando aprovação**; aprovar devolve para **Em execução**.
   Recusar o adicional descarta só os itens dele — o que já foi aprovado continua.
9. **Finalizar.** `POST /api/ordens-servico/{id}/finalizar/` → **Finalizada**.
10. **Entregar.** `POST /api/ordens-servico/{id}/entregar/` → **Entregue**, e é aqui que as peças
    reservadas saem definitivamente do estoque. Estado terminal.

O cliente acompanha tudo isso com o próprio login: `GET /api/ordens-servico/` já vem filtrado pelas OS
dele, com os itens e os orçamentos embutidos na resposta.

### Estados e transições

```
Recebida → Em diagnóstico → Aguardando aprovação → Em execução → Finalizada → Entregue
                  ^                     |               ^             |
                  +--- orçamento -------+               +-- reparo ---+
                       recusado                            adicional
```

Transição fora desse mapa devolve 400 com o motivo. O status nunca é escrito direto por `PATCH`: ele é
resultado de um comando de negócio.

### Encerrar não é um status

Uma OS pode morrer sem virar serviço — o cliente sumiu, desistiu, ou a ordem foi aberta por engano.
`POST /api/ordens-servico/{id}/encerrar/` marca `is_active=false`, libera as peças reservadas e avisa o
cliente, **sem mexer no status**. O status continua registrando até onde o atendimento chegou, o que
mostra onde a oficina perde atendimento: uma OS encerrada em Aguardando aprovação conta uma história
diferente de uma encerrada em Recebida.

OS já entregue não se encerra — o serviço foi prestado.

A listagem esconde as encerradas por padrão. `?is_active=false` traz só elas; `?is_active=todas`, tudo.

## Estoque

O saldo de uma peça tem três números: `quantidade` (o que existe), `quantidade_reservada` (o que já está
comprometido com alguma OS aprovada) e o disponível, que é a diferença.

- **Reserva** acontece na aprovação do orçamento, nunca na inclusão do item. É tudo ou nada: o serviço
  confere o saldo de todas as peças antes de reservar qualquer uma, somando as ocorrências repetidas.
- **Estoque insuficiente** devolve **409** com a lista do que faltou (peça, solicitado, disponível),
  dispara um e-mail para a caixa da oficina e deixa a OS parada em Aguardando aprovação. A resposta do
  cliente não é gravada, de propósito: reposto o estoque, alguém aprova de novo. A retomada não é
  automática.
- **Editar item já aprovado** ajusta a reserva pela diferença; remover libera o total.
- **Baixa** acontece na entrega do veículo.
- Depois de cada reserva e de cada baixa, as peças que ficaram abaixo do `estoque_minimo` geram alerta por
  e-mail. `GET /api/pecas/alertas/` lista as que precisam de reposição a qualquer momento.

Entrada de peças não tem rota própria: é um `PATCH /api/pecas/{id}/` no campo `quantidade`, restrito ao
estoquista.

## Notificações

O app `notifications` envia e-mail em quatro situações, com template HTML e texto para cada uma:

- **ao cliente**, a cada mudança de status da OS (em diagnóstico, aguardando aprovação, em execução,
  finalizada, entregue) e no encerramento. A abertura não gera aviso — Recebida é o estado inicial, não
  uma mudança;
- **à oficina** (`EMAIL_OPERACAO`), quando a aprovação esbarra em estoque insuficiente e quando uma peça
  cai abaixo do mínimo.

O envio é acessório: falha vira log e não desfaz a operação de negócio nem impede a mudança de status.

## Endpoints

| Método | Rota | O que faz |
|---|---|---|
| `POST` | `/api/token/` | Autentica e devolve access + refresh |
| `POST` | `/api/token/refresh/` | Renova o access |
| `GET` | `/api/health/` | Liveness, sem autenticação |
| `GET` | `/api/profile/` | Dados do usuário logado |
| `GET` `POST` | `/api/users/` | Cadastro de usuário; listagem só para staff |
| CRUD | `/api/clientes/` | Cadastro de clientes. Filtro `?cpf_cnpj=` |
| CRUD | `/api/veiculos/` | Cadastro de veículos |
| CRUD | `/api/servicos/` | Catálogo de serviços |
| CRUD | `/api/pecas/` | Catálogo de peças e saldo de estoque |
| `GET` | `/api/pecas/alertas/` | Peças abaixo do estoque mínimo |
| CRUD | `/api/ordens-servico/` | Ordens de serviço. Filtros `?cliente=`, `?veiculo=`, `?is_active=` |
| `POST` | `/api/ordens-servico/{id}/diagnosticar/` | Registra o parecer e transita |
| `POST` | `/api/ordens-servico/{id}/finalizar/` | Conclui os serviços |
| `POST` | `/api/ordens-servico/{id}/entregar/` | Devolve o veículo e baixa o estoque |
| `POST` | `/api/ordens-servico/{id}/encerrar/` | Dá baixa no atendimento e libera reservas |
| CRUD | `/api/itens-servico/` | Itens de serviço da OS |
| CRUD | `/api/itens-peca/` | Itens de peça da OS |
| `GET` `POST` | `/api/orcamentos/` | Orçamentos da OS |
| `POST` | `/api/orcamentos/{id}/enviar/` | Encaminha ao cliente |
| `POST` | `/api/orcamentos/{id}/aprovar/` | Autoriza, reserva peças e inicia a execução |
| `POST` | `/api/orcamentos/{id}/recusar/` | Não autoriza e descarta os itens |
| `GET` | `/api/relatorios/tempo-medio-execucao/` | Tempo médio entre início da execução e finalização |

O relatório aceita `?de=` e `?ate=` em ISO 8601 e filtra pela data de finalização. Data sem fuso é lida no
fuso do projeto (America/Sao_Paulo).

Os filtros `?cliente=` e `?veiculo=` aceitam tanto o `id` quanto o `uuid`, porque o serializer expõe os
dois. Valor que não é nenhum dos dois devolve lista vazia, não erro — é consulta, e consulta que não achou
nada não achou nada.

## Erros

| Código | Quando |
|---|---|
| `400` | Transição de status inválida, regra de negócio violada, payload inválido |
| `401` | Sem token, ou token expirado |
| `403` | O papel do usuário não executa aquela operação |
| `404` | Recurso inexistente — ou de outro cliente, no caso do login de cliente |
| `409` | Estoque insuficiente na aprovação, ou exclusão de cadastro com vínculo (`PROTECT`) |

## Testes

```bash
python manage.py test
```

Com cobertura:

```bash
coverage run --source=. manage.py test
coverage report
coverage html          # relatório navegável em htmlcov/
```

São 149 testes sobre os fluxos críticos: máquina de estados e transições inválidas, geração automática e
recálculo do orçamento, envio, aprovação, recusa inicial e recusa de adicional, reserva e baixa de
estoque, tudo ou nada com estoque insuficiente, alerta de mínimo, proteção do orçamento já enviado,
validação de CPF/CNPJ e placa, permissão por papel, isolamento do cliente logado, histórico por cliente e
por veículo, exclusão protegida e relatório de tempo médio.

O CI (`.github/workflows/ci-sonarqube.yml`) roda a suíte com coverage a cada push em `main` e publica o
resultado no SonarCloud.

## Estrutura

```
So_PosTech/     configuração do projeto: urls, settings e o handler de exceções da API
accounts/       usuário, papéis, permissões e JWT
cadastros/      cliente, veículo, serviço e os validadores de CPF/CNPJ e placa
estoque/        peça, saldo e o EstoqueService (reserva, liberação e baixa)
so/             ordem de serviço, orçamento, itens e o relatório de tempo médio
notifications/  serviços de e-mail e templates
```

Cada app segue a mesma divisão: `models/`, `serializers/`, `views/`, `urls.py`, `tests.py`. Regra de
negócio mora no modelo ou no serviço de aplicação; a view traduz HTTP em comando de domínio, e domínio em
HTTP.

Os três contextos delimitados do desenho DDD estão mapeados nos apps: Atendimento e Execução em `so/`,
Gestão de Peças e Insumos em `estoque/`, Gestão Administrativa em `cadastros/` e `accounts/`. A única
travessia de escrita entre atendimento e estoque passa pelo `EstoqueService`.

## Documentação de domínio

Fica em `../documentacao-postech`:

- **Event Storming** (Miro) — os dois fluxos exigidos na fase: criação e acompanhamento da OS, e gestão de
  peças e insumos. Link em `link-miro.txt`.
- **Linguagem Ubíqua** (`Linguagem_Ubiqua_v12.pdf`) — contextos, agregados e invariantes, atores, eventos,
  comandos, políticas, estados, e a tabela que liga cada conceito do negócio ao ponto do código onde ele
  vive.
- **Diagrama ER** (`Diagrama-ER.pdf`) — as 9 tabelas, as 11 relações e o que cada regra de exclusão
  significa.
- **Diagramas C4** (`diagrama-c4/`) — contexto, contêineres e componentes.

Os nomes do negócio aparecem sem tradução no código: `OrdemServico`, `Orcamento`, `Peca`, `transitar_para`,
`aprovar`, `recusar`, `encerrar`. Termo novo entra primeiro na Linguagem Ubíqua e só depois no código.
