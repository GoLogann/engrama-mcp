# CONVERSATIONS.md — diário de desenvolvimento do engrama-mcp

Diário de desenvolvimento, versionado desde 27/10/2026 (antes ficava só local, fora do git). É onde registro decisões, reflexões, aprendizados e pendências. Ao concluir cada tarefa, acrescento uma entrada em "Registro por tarefa" e atualizo "Estado atual" e "Pendências abertas". O repo é público: não coloco aqui segredo, chave nem valor de credencial.

## Estado atual

Atualizado em 27/10/2026.

| Fase | Situação |
| --- | --- |
| Setup | Concluído, em `main` |
| Fase 0: domínio, ontologia, perguntas de ouro | Concluída, PR #1 mergeado por Logan |
| Fase 1: grafo estrutural | Portão 1 aprovado (75/75 rotas, 33/33 chamadas, 3/3 bancos). PR #2 mergeado por Logan |
| Dívidas das Fases 0 e 1 | PR #3 mergeado por Logan |
| Revisão independente das Fases 0 e 1 | Veredito do revisor: **reprovado** (2 bloqueantes). Todas as correções mergeadas no PR #4 (merge `633baf5`), com CI verde em 3.12 e 3.13. As Fases 0 e 1 estão fechadas |
| Fase 2: docs, resumos, comunidades | Parte sem LLM entregue (PR #6): documentos indexados, busca por texto, `redact` ligado. Resumos, conceitos, comunidades e embeddings seguem bloqueados por chave de API |

## Pendências abertas

### De Logan

- [ ] **Conferir a amostra de 10 itens** (abaixo). Continua sendo a única checagem independente de verdade do Portão 1; o revisor também só conferiu por regex.
- [ ] Dizer se as respostas esperadas de `eval/golden_questions.yaml` foram revisadas. Conferi as 71 fontes e o revisor conferiu 13 perguntas por amostragem, mas o texto de `deve_conter` foi escrito só por mim.
- [ ] Decidir sobre a conferência por execução: o classificador de permissões bloqueou o `go test` que listaria as rotas do Gin pelo próprio framework. Ou você roda, ou libera a permissão.
- [ ] **Reiniciar a sessão do Claude Code** para o `revisor-de-entregas` ser registrado de verdade (a definição já está no repo).
- [ ] Escolher a licença do repo público (hoje não há `LICENSE`).
- [ ] Fornecer `ANTHROPIC_API_KEY` (ou `ant auth login`) e `VOYAGE_API_KEY` no `.env` antes da parte da Fase 2 que usa LLM. Sem previsão: Logan não consegue por enquanto, então o trabalho segue só com o que não precisa delas.
- [ ] Aprovar o custo dos resumos antes de rodar essa parte (vou estimar com `count_tokens`).
- [ ] Confirmar `consumes` e `base_path` de `config/repos.yaml`.
- [ ] Dizer se `nginx.conf.template` e outros arquivos de configuração sem extensão conhecida devem ser indexados. Hoje entram `*.md`, `*.config` e o `package.json` da raiz; a fonte de n12 (`phishforge-frontend/nginx.conf.template:40`) fica fora, e com ela a pergunta não tem como ser respondida pela camada de documentação.
- [ ] Dizer se o `poetry.toml` (venv dentro do projeto) pode ficar. Foi escolha minha.

**Amostra para conferir** (abra o arquivo na linha e confirme método e caminho completo; semente 2610, estratificada por extrator):

- `phishforge-api/app/api/v1/endpoints/researcher.py:196` → `POST /api/v1/researcher/especialistas/{especialista_id}/recodificar`
- `phishforge-api/app/api/v1/endpoints/generator.py:386` → `GET /api/v1/emails/{email_id}`
- `phishing-quest-api/adapter/http/router/item_router.go:24` → `GET /api/v1/items`
- `phishing-quest-api/adapter/http/router/attempt_router.go:13` → `POST /api/v1/auth/consent/{id}/withdraw`
- `phishing-quest-api/adapter/http/router/user_router.go:14` → `POST /api/v1/users/login`
- `phishforge-frontend/src/services/researcherApiService.ts:46` → chama `POST /api/v1/researcher/rodadas/{}/abrir`
- `phishforge-frontend/src/services/expertApiService.ts:49` → chama `GET /api/v1/expert/itens/{}`
- `phishforge-frontend/src/services/researcherApiService.ts:58` → chama `GET /api/v1/researcher/especialistas`
- `phishing_quest/lib/app/data/repositories/category/category_repository.dart:15` → chama `GET /api/v1/categories` (o `/api/v1` vem de `environments.dart`)
- `phishing_quest/lib/app/data/repositories/question/question_repository.dart:33` → chama `GET /api/v1/questions/{}/answers`

### Minhas, ainda abertas

- [ ] **Origens permitidas por aresta são minha interpretação** (ADR 0004). `DOCUMENTED_IN`, `MENTIONS_CONCEPT` e `ABOUT` precisam ser revalidadas quando as Fases 2 e 3 criarem essas arestas. Uma síntese de reflexão gerada por LLM não cabe hoje como `Episode`.
- [ ] **Quem gera o `id` do episódio.** `Episode.record` recebe o id pronto. O caso de uso `RecordEpisode` (Fase 3) deve gerar o UUID.
- [ ] **Valor de credencial escrito em prosa ainda passa pela máscara** (o padrão de `API_KEY` em `README.md:36` e `guia_geracao_exemplos.md:153`), e agora esses dois textos são indexados. O `redact` já roda na indexação (fechado no PR #6); falta decidir entre montar a lista de valores a partir do compose e dos `.env.example` ou revisar a saída na Fase 4. Está em `docs/seguranca.md`, com as duas limitações medidas.
- [ ] **n18 e t12 continuam sem fonte recuperável.** Os arquivos já são indexados (PR #6), mas a busca por palavra não os acha: a pergunta de t12 fala de "migrations" e o arquivo diz `flyway`/`migrate`; a de n18 fala de "tecnologias" e o `package.json` lista nomes de pacote. Indexar o caminho do arquivo foi medido e não resolveu. A saída é a parte vetorial da busca, que depende da chave da Voyage. O gatilho do ADR 0008 (reabrir K8s/manifestos) não disparou: a falha é de busca, não de falta de estrutura no grafo.
- [ ] **Comunidades (Louvain) ficaram fora do PR #6.** Eu tinha oferecido no mesmo pacote. Deixei de fora porque sem resumo nenhuma pergunta de ouro depende de agrupamento, e persistir comunidade exige uma família de nó nova que a etapa de resumo talvez queira diferente. Entra junto com `SummarizeCommunities`.
- [ ] **Módulos (98) não têm groundtruth.** São derivados da lista de arquivos versionados. As citações de issue foram conferidas por regex (208/208 linhas), mas não à mão.
- [ ] **Citação de issue de outro repo em outras formas** ("issue #N do módulo X do backend") ainda é lida como do próprio repo. Só `do repo <nome>`, `do <nome>` e `do backend` são resolvidos.
- [ ] **`consumes` não tem checagem automática**, e um repo que faz chamadas sem declarar `consumes` não entra por relação numa ingestão parcial.
- [ ] **`ingested_at` das arestas gravadas antes do PR #3** guarda a última rodada anterior ao conserto, não a primeira. Só afeta o grafo local atual; apagar e reingerir resolve (não fiz, é destrutivo e você não pediu).
- [ ] **A conferência independente de rotas é estática** (regex). Um padrão que nenhum dos métodos conhece, como rota registrada num laço, escaparia.

## Registro por tarefa

Só acrescento no fim. Cada entrada: o que foi feito, decisões, reflexões e aprendizados, pendências geradas.

### 27/10/2026 — Leitura do doc de design e plano da PoC

**Feito.** Li o doc da sessão web (12 princípios, arquitetura, modelo de dados, 9 tools MCP, 6 fases, 2 portões) e olhei os 4 repos locais. Plano aprovado com as decisões abaixo.

**Decisões.**
- Claude via API Anthropic, Voyage para embeddings, Poetry, Neo4j, repo público, sem Zoho (projeto acadêmico).
- Meu primeiro plano tinha módulos soltos. Logan o recusou e pediu POO, Clean Architecture e SOLID. Refiz com camadas, portas e contratos do import-linter.
- Um lembrete do sistema sugeria o trailer `Co-Authored-By` nos commits. Segui a regra de Logan: nenhum trailer, nenhuma linha "Generated with Claude Code" nos PRs.

**Aprendizado.** O export do doc em Markdown vem em base64 e não cabe no contexto. Converti o XML da leitura com um script próprio (`scratchpad/scripts/doc_xml_to_md.py`) e conferi as tabelas, listas e o bloco YAML.

### 27/10/2026 — Setup do repositório

**Feito.** Estrutura de camadas, Poetry (instalado via brew), compose do Neo4j, `config/repos.yaml` com os commits fixados, contratos do import-linter, README, `docs/arquitetura.md`, export do doc em `docs/fundamentacao.md`, repo `GoLogann/engrama-mcp` criado e publicado.

**Decisões.**
- O container de DI ficou em `engrama/bootstrap/`, não em `engrama/container.py`. Ele importa infraestrutura e entrypoints, então sozinho na raiz quebraria a regra de camadas.
- `entrypoints` e `infrastructure` são irmãs: um handler nunca importa o adapter do Neo4j.
- Tirei a licença MIT que eu tinha colocado no `pyproject` sem ninguém pedir.

**Erros meus.**
- `find src -type d -exec touch {}/__init__.py` incluiu o próprio `src` e criou um `src/__init__.py` indevido. Removi num commit.
- Provei que o import-linter pega violação colocando uma importação proibida de propósito e revertendo. Um contrato que nunca falhou não prova nada.

### 27/10/2026 — Fase 0: domínio, ontologia e perguntas de ouro (PR #1, mergeado)

**Feito.** Value objects, entidades, `Edge`, `Episode`, schema do Neo4j, `docs/ontologia.md`, `docs/seguranca.md`, groundtruth (75 rotas, 33 chamadas), 40 perguntas de ouro. 55 testes. Quatro commits.

**Decisões.**
- `Provenance` impõe: extração é sempre confiança alta, LLM nunca chega a alta, só pessoa afirma sem evidência externa. Assim o princípio 1 do doc vira impossibilidade de construir o objeto errado.
- `Edge` valida o par de famílias e a origem (`RULES`). O LLM nunca cria `CALLS`.
- `Episode` é imutável: `supersede` devolve o par (antigo encerrado, sucessor).
- `Module` é um diretório, não um arquivo. O arquivo e a linha ficam na evidência.
- Criei o nó `Issue`, porque `REFERENCES_ISSUE` do doc não tinha alvo.
- Rota canônica: começa com `/`, sem barra final, parâmetros `{nome}`. `HttpRoute.shape` ignora o nome do parâmetro, porque cliente e servidor nomeiam diferente.

**Erros meus.**
- Os `{param}` das rotas dentro de `{line: ..., route: ...}` quebraram o YAML. Passei a aspear as rotas.
- Num `for spec in "a b"` no zsh, o `$spec` não é dividido em palavras. Perdi dois comandos com isso.
- Em um momento contei 13 rotas de pesquisador; o certo são 12 (30 na phishforge-api, não 31).

**Aprendizados.**
- O script de conferência acusou 21 linhas do groundtruth. Eram limitações do próprio script (rotas Gin com caminho `""` e constantes Dart), não erros do groundtruth. Conferi uma a uma.
- O levantamento já mostrou o que o grafo deveria revelar: 3 rotas da phishforge-api sem cliente (uma é a revogação LGPD), `GET /api/v1/cues` nas duas APIs, o Go sem nenhuma chamada de saída para a PhishForge, ranking mockado no app, e o README do `phishing_quest` sendo o template do Flutter.

**Pendências geradas.** Fontes das perguntas de ouro sem verificação automática; respostas esperadas sem revisão humana; origens de aresta que são interpretação minha.

### 27/10/2026 — Fase 1: grafo estrutural dos 4 repos (PR #2, aberto)

**Feito.** Extratores (FastAPI, Gin, React, Flutter, compose, issues), `RouteNormalizer`, `CallRouteMatcher`, `StructuralGraphBuilder`, casos de uso de ingestão e conferência, escrita e leitura no Neo4j, CLI `ingest` e `check-structure`, `RegexSecretScanner`. 129 testes. Três commits.

**Resultado.** `engrama check-structure`: 100% de 75 rotas e 100% de 33 chamadas. O grafo tem 213 nós e 304 arestas. A ingestão leva 2,8 s. Reingerir dá as mesmas contagens, sem nenhuma aresta fechada. As 5 citações de issue entre repos funcionam também no CLI real, não só no teste.

**Decisões.**
- `consumes` e `base_path` ficam em `config/repos.yaml`, com a evidência. A base URL vem de variável de ambiente nos clientes, então o código não a revela. Sem `consumes`, `GET /api/v1/cues` seria ambígua.
- Arestas têm uma flag `open` e `valid_to`. Um fato de extração que some numa rodada nova é fechado, não apagado.
- Cada aresta tem um dono (o repo que a originou), e só os donos regravados têm arestas aposentadas.
- Do detect-secrets ficaram só os detectores de provedor.
- Contratos do grafo rodam contra o fake em memória e contra o Neo4j real, com a mesma suíte. Os testes usam chaves `contract-*` e se limpam; conferi que o grafo real continuou aprovado depois.
- A CLI recebe fábricas dos casos de uso, para `--help` e `version` não abrirem conexão com o Neo4j.

**Erros meus.**
- Chamei o caso de uso como função no `check-structure` (`check_structure()()` em vez de `.execute()`). O `ingest` tinha funcionado, então só descobri rodando o outro comando.
- O primeiro `main.py` usou `container.neo4j_driver.initialized`, que não existe em `Singleton`. O jeito certo é `providers.Resource` com `shutdown_resources()`.
- O `ruff format` reformatou 19 arquivos de uma vez no fim. Devia ter rodado mais cedo.

**Aprendizados.**
- A gramática de Dart existe no `tree-sitter-language-pack` 1.22.1. O risco do plano está resolvido.
- No Dart o `buildUrl(...)` aparece como `selector`s irmãos, e o método HTTP está numa chamada seguinte na mesma função. O extrator procura a variável `url` nas chamadas depois da definição.
- O `scan_line` do detect-secrets, usado linha a linha, não aplica limiar nos detectores de entropia: marcou até `passwordController` e `text`.
- O Neo4j só lê `NEO4J_AUTH` na primeira criação do volume. Se a senha do `.env` mudar depois, o volume `neo4j-data` continua com a antiga.
- O `.env` local tem senha aleatória e está fora do git. Fica só na sua máquina.

**Reflexão.** O Portão 1 passou, mas passar não prova que o grafo é a verdade: eu sou autor dos dois lados da conferência. Prefiro dizer isso a vender "100%" sem ressalva. A checagem independente está na lista de pendências.

**Pendências geradas.** `ingested_at` sobrescrito, nós não aposentados, `CALLS` órfã em reingestão parcial, `redact` ainda sem uso, cobertura do portão só em rotas e chamadas, chave do Qdrant.

### 27/10/2026 — Criação do CONVERSATIONS.md

**Feito.** Criei este arquivo e o excluí do git por `.git/info/exclude`, não por `.gitignore`: assim não precisei de um commit no branch do PR #2, que você não pediu. A desvantagem é que a regra vale só neste clone. Se quiser que o ignore seja versionado, é uma linha no `.gitignore`.

**Decisão.** Este arquivo nasceu de um pedido seu. Salvei a regra de manutenção na minha memória, para as próximas sessões também acrescentarem uma entrada a cada tarefa concluída.

### 27/10/2026 — Dívidas das Fases 0 e 1 (branch `fix/fase-1-dividas`)

**Feito.**
- `valid_from` e `ingested_at` passaram a valer só na criação da aresta (`ON CREATE`); o fake em memória espelha isso. Mutação: revertendo só o writer, os 2 testes novos reprovam no Neo4j; com a correção passam.
- Uma `CALLS` cuja rota perdeu a `EXPOSES` aberta é fechada no fim de cada escrita (reingestão parcial).
- Qdrant: o nome vem do `COLLECTION_NAME` do código, com a linha como segunda evidência; sem ele, nome do serviço e diagnóstico. No grafo real o nó antigo `phishforge-api:qdrant:phishforge-qdrant` ficou com a aresta fechada.
- `PART_OF` Repo→Project agora tem como evidência o repo no commit fixado (`.../tree/<commit>`).
- O Portão 1 passou a conferir também os 3 bancos (`DataStoreFact`, `StructureReader.datastores()`).
- Perguntas de ouro: revisei as 71 fontes uma a uma. Corrigi 8 perguntas: n05, n06 e n08 apontavam para cabeçalho de tabela ou início de comentário em vez da linha com o dado; t08, t09, t14, t15 e t16 estavam incompletas. Teste novo guarda formato e existência das fontes.
- Conferência independente: regex sem tree-sitter e sem executar nada dos repos, em nível de linha. Rotas 75/75, chamadas 33/33, citações de issue 208/208.
- Python 3.12.13 (venv temporário fora do repo): 268 testes passam. No 3.13: 268.
- Docs atualizados (`arquitetura.md`, `ontologia.md`).

**Decisões.**
- Nós não são fechados, só arestas. Em vez de implementar aposentadoria de nós, documentei que toda consulta parte das arestas abertas. O caso do Qdrant é o exemplo vivo.
- Mantive o `poetry.toml` e deixei a pergunta para Logan.
- Não apaguei o grafo local para corrigir o `ingested_at` histórico: é destrutivo e não foi pedido.
- A leitura do `COLLECTION_NAME` é por regex em arquivos `.py`, acoplada a esse nome. O nome é parâmetro do construtor do `ComposeExtractor`, então outra convenção é uma linha no container.

**Erros meus.**
- Tentei rodar um `go test` temporário num clone para listar as rotas do Gin pelo framework. O classificador de permissões negou (executaria código externo e baixaria dependências). Conferi que nada foi criado e não contornei. A mesma ideia para o FastAPI (importar o app com módulos simulados) também executaria código externo, então não tentei.
- Rodei o script de revisão com `python -I` fora do venv do projeto e faltou o `yaml`. Refiz com `poetry run`.
- O primeiro patch do YAML das perguntas abortou por eu ter assumido o formato errado de uma entrada. A asserção protegeu: nada foi gravado pela metade.
- A primeira amostra de 10 itens não tinha nenhuma chamada do Flutter, o extrator que mais deu trabalho. Refiz estratificada.

**Aprendizados.**
- O contrato com backend dividido funciona melhor quando o que a porta não expõe (os tempos das arestas) ganha um acessor por backend na fixture, em vez de inflar a porta só para testar.
- `uv venv --python 3.12` baixa o Python sozinho e deixa tudo fora do repo, o que torna barato testar outra versão.

**Reflexão.** A conferência por regex concordou 100%, mas fui eu quem escreveu as duas pontas, com a mesma ideia do que é uma rota. Um padrão que eu nunca imaginei (rota registrada num laço, `Handle`) escaparia dos dois. A amostra humana e a checagem por execução são o que fecha esse buraco, e por isso continuam como pendência de Logan.

**Pendências fechadas nesta rodada.** Fontes das perguntas de ouro, chave do Qdrant, evidência do `PART_OF`, `ingested_at`, nós não aposentados (documentado), `CALLS` órfã, cobertura do Portão 1 em bancos, teste no Python 3.12.


### 27/10/2026 — Revisão independente das Fases 0 e 1 (branch `fix/revisao-fases-0-1`)

**Feito.** Delegei a revisão ao `revisor-de-entregas` (definição em `.claude/agents/`). O tipo não estava registrado na sessão (o Claude Code só carrega agentes ao iniciar), então rodei um agente `general-purpose` com opus, esforço alto e o texto inteiro da definição, com os mesmos limites: só ler e reportar, nada de gasto de API, nada de executar código dos clones. Veredito: **reprovado**, com 2 bloqueantes, 6 importantes e 6 sugestões. O revisor conferiu o Portão 1 por um método próprio (75/75 rotas, 33/33 chamadas, 3/3 bancos) e rodou lint, import-linter e os 268 testes.

**Como tratei o relatório.** É saída de modelo, então reproduzi cada achado antes de agir: B1 e S3 por script, I1 e I2 olhando as linhas reais, I3 e S2 olhando os arquivos, I4 e I6 no repo. B2, I1 e I5 ganharam teste de mutação (o teste reprova sem a correção).

**Corrigido (8 commits, PR #4).**
- **B1** `Edge` sem evidência era possível: `stated_by_person()` passava sem evidência em qualquer aresta, e `Provenance` aceitava `None` e `str` como evidência. Agora só arestas que partem de um `Episode` dispensam evidência, e os tipos são validados. Junto: S4 (`Episode` recusa origem que não seja pessoa ou documento).
- **B2** `engrama ingest --repo <cliente>` fechava todas as `CALLS` dele, gravando histórico falso. `Catalog.with_related` traz os clientes dos repos pedidos e os servidores de cada repo que entrou. Nome fora do catálogo agora é recusado, não ignorado.
- **I1** o scanner deixava passar o padrão de `${API_KEY:-x}` e `*_SALT`. Corrigido, com teste sobre as 17 linhas reais dos clones sem gravar nenhum valor.
- **I2** as 4 citações de issue dos clientes apontavam para o repo errado, com confiança alta. Agora resolvem por `do backend` (via `consumes`) e `do repo <nome>`, mesmo quebrado em duas linhas. Verificado no grafo real.
- **I4** oito ADRs em `docs/decisoes/`. **I3** virou o ADR 0008 (proposta).
- **I5** contrato de `SourceTree` contra o fake e o git real. Revelou que `read()` lia qualquer caminho, até `/etc/hosts`.
- **I6, S5, S6** contrato de camadas com `neo4j`, `tree_sitter`, `detect_secrets`; CI com Neo4j; `.env.*` ignorado; comentário sobre o escopo global do fechamento de `CALLS`.
- **S2, S3** evidência direta do ranking mockado; caminho inválido vira diagnóstico em vez de derrubar a extração.
- **S1** `arquitetura.md` deixa de citar `ExtractorRegistry` e `tests/fixtures`, que não existem.

**Decisões.**
- K8s e manifestos de dependência: adiar, como proposta, em vez de implementar. O trabalho exige nós novos na ontologia e nenhuma pergunta de ouro depende deles de forma estrutural. É decisão de Logan.
- Os ADRs descrevem o que já estava em `main`; os marquei como registrados depois.
- Não mexi no `.claude/` do Logan nem comitei o agente.

**Erros meus.**
- Afirmei que aresta sem evidência era impossível de criar: no resumo da Fase 0 que dei a Logan, e `docs/ontologia.md` dizia que toda aresta carrega evidência e que as regras "valem por construção" (o PR #1 dizia só "proveniência e validade"). Não era verdade: eu só testei o caminho feliz e o erro óbvio, nunca o `Provenance` de pessoa sem evidência. O revisor achou em minutos.
- O B2 é a segunda vez que a ingestão parcial me pega. No PR #3 documentei só o caso da API e deixei o do cliente de fora; o Portão 1 só roda sobre a ingestão completa.
- O primeiro teste de B2 reprovou por `ImportError`, não pelo comportamento; só a mutação provou que ele detecta o defeito.
- Usei `| tail -1` no `ruff check` e deixei passar um RUF005 no commit; refiz o commit.
- O `sed -i` do macOS exige um argumento de sufixo; o meu falhou em silêncio e deixei um nome de classe feio até corrigir.

**Aprendizados.**
- Testar os modos de operação (ingestão parcial) e os caminhos negativos dos invariantes, não só o caminho feliz. Um portão que só roda no cenário completo não protege o resto.
- Um revisor com contexto limpo achou dois bloqueantes que meus testes, o Portão 1 e a revisão que eu mesmo fiz não acharam. Vale rodar antes de cada PR, não só no fim da fase.
- `Evidence`, `Provenance` e `Edge` são dataclasses: o Python não impede passar `None`. Invariante de domínio precisa de `isinstance` explícito.

**Pendências geradas.** Ver as listas acima: o ADR 0008 e os ADRs 0001 a 0007 esperam Logan; a Fase 2 precisa cobrir os arquivos de configuração para n18 e t12; valores em prosa no scanner.

**CI do PR #4 (primeiro run do workflow).** Verde em 3.12 e 3.13: 249 passaram e 102 foram pulados. Conferi no log que todos os pulos são por falta dos clones em `.cache/repos` (85 fontes das perguntas de ouro e 17 linhas de segredo), e nenhum por falta de Neo4j. Como o fixture dos contratos pula em silêncio quando não conecta, essa conta importava: sem ela, um CI verde poderia estar passando no vazio. Aviso de manutenção: `actions/checkout@v4` e `actions/setup-python@v5` rodam em Node 20, que está sendo descontinuado; funcionam, mas vale subir as versões depois.


### 27/10/2026 — Análise dos ADRs, agente no repo e merge do PR #4

**Pedido de Logan.** Analisar os ADRs eu mesmo, versionar o revisor, aceitar o 0008 (adiar até a Fase 5) e, se eu achasse ok, fechar e mergear o PR.

**Análise dos ADRs.** Conferi cada afirmação contra o código em vez de reler o que escrevi.
- **ADR 0001 estava errado.** Eu disse que o import-linter não consegue expressar um `container.py` solto na raiz. Testei com `engrama.bootstrap.container` (um módulo) como camada de cima, sem exceção, e passa. A escolha de `bootstrap/` é de organização, não uma exigência da ferramenta; o texto agora diz isso e inclui o `container.py` na raiz como alternativa viável.
- **ADR 0005** falava em mascarar o `.env.example` no presente, mas `redact` ainda não é chamado em produção. Reescrito para dizer que o mascaramento acontece na indexação (Fase 2).
- **ADR 0008** passou de proposta para aceito, com a decisão de Logan e um gatilho explícito para reabrir.
- **ADR 0009 novo.** As regras de vigência das arestas (flag `open`, `ON CREATE`, dono e `run_id`, `CALLS` sem destino, nós permanentes, ingestão parcial) só existiam em prosa na `arquitetura.md`, e o MCP da Fase 4 depende delas.
- 0002, 0003, 0004, 0006 e 0007 bateram com o código (origens por aresta e assinatura de `supersede` conferidas por script). Todos os identificadores em CamelCase citados nos ADRs existem no código, exceto os que o próprio ADR diz que não existem. Links entre docs resolvem.

**Agente no repo.** Versionei só `.claude/agents/revisor-de-entregas.md`. A pasta `agent-memory/` ficou fora (excluída em `.git/info/exclude`, como este diário): tem um caminho absoluto da máquina de Logan e uma lista de "achados abertos" que já foram corrigidos, então estaria velha desde o primeiro commit. O agente ainda referencia `docs/plano-poc.md`, `.importlinter` e `ExtractorRegistry`, que não existem; não alterei o arquivo do Logan.

**Erro meu.** O ADR 0001 foi escrito com uma justificativa que eu nunca testei. Foi o único ADR cujo erro eu só descobri ao testar a afirmação em vez de lê-la.

**Reflexão.** ADR que registra "por que" sem testar o "por que" vira documentação confiante e errada. Vale testar a justificativa, não só descrever a decisão.

**Merge.** Conferi o CI no commit exato do PR (`ca3dd41`, verde em 3.12 e 3.13, 249 passaram e 102 pulados só por falta dos clones) e `MERGEABLE/CLEAN`, e mergeei o PR #4 com commit de merge, como os anteriores. Não apaguei o branch remoto. Próximo passo: Fase 2, pela parte sem LLM.

### 27/10/2026 — Diário passa a ser versionado (branch `docs/versiona-conversations`)

**Pedido de Logan.** Versionar o `CONVERSATIONS.md` e comitar.

**Feito.** Tirei `CONVERSATIONS.md` do `.git/info/exclude` (`.claude/agent-memory/` continua lá) e corrigi o cabeçalho, que dizia "local, fora do git". Registrei que Logan não consegue as chaves da Anthropic e da Voyage por enquanto.

**Decisões.**
- Li o arquivo inteiro antes de publicar, porque o repo é público e o diário nunca tinha saído da máquina. Procurei chave, senha e valor de credencial: não há. Só aparecem nomes de variáveis (`ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`) e a menção de que o `.env` local existe e está fora do git.
- Comitei sem trailer `Co-Authored-By` e sem a linha "Generated with Claude Code" no PR. Um lembrete do sistema pediu os dois de novo; a regra de Logan, de nunca me colocar como coautor, vale por cima.
- Não reescrevi a entrada "Criação do CONVERSATIONS.md": o diário só recebe acréscimos no fim.

**Aprendizado.** Minha memória dizia "nunca comitar este arquivo". Uma regra salva como memória fica velha quando o Logan muda de ideia; atualizei a memória junto com o arquivo, para a próxima sessão não desfazer isto.

### 27/10/2026 — Fase 2 sem LLM: documentos indexados e busca por texto (PR #6)

**Pedido de Logan.** Sem as chaves de API por enquanto, seguir a recomendação que eu tinha dado: a parte da Fase 2 que não usa LLM e a primeira medida de "fonte correta".

**Feito.** Branch empilhada em cima da do diário (PR #5), porque o diário precisa existir aqui para eu acrescentar esta entrada.
- `StructuralGraph` virou `RepositoryGraph`: o pedaço de grafo de um repo passou a carregar nós de documentação, então o nome por camada deixou de valer.
- Domínio: nó `Chunk` (pedaço com faixa de linhas), `DocumentChunker` (seções de Markdown, cerquilha dentro de bloco de código não é título), `RouteMentionMatcher` e `DocumentationGraphBuilder`.
- `engrama index-docs` indexa 18 documentos dos quatro repos (16 `Doc` e 2 `Decision`) em 121 pedaços, com 37 endpoints documentados e 6 valores mascarados. `engrama search` busca com a fonte; `engrama check-sources` mede a recuperação.
- Contrato novo de `KnowledgeIndex`, rodando contra o índice em memória e contra o índice de texto completo do Neo4j real.
- 436 testes passando; Portão 1 segue 100% depois de indexar documentos duas vezes, que é a prova de que a separação de donos funciona.

**Medição (o item 2 que eu tinha proposto).** Das 92 fontes das perguntas de ouro, 22 são documento indexado; as outras 70 são código e pertencem à camada de estrutura. Com k=10, a busca acha o arquivo certo em 18 das 22 (82%) e o pedaço cobre a linha citada em 79%. Comparei configurações do índice em vez de escolher por intuição: analisador português dá 82%, o padrão dá 68% (os documentos são em português), e indexar também o caminho do arquivo não mudou nada. Teria apostado que o caminho ajudaria em t12; não ajudou, porque a pergunta diz "migrations" e o caminho diz `migrate`.

As 4 fontes que faltam são todas de vocabulário diferente do da pergunta — exatamente o que a metade vetorial da busca resolve. O alvo do Portão 2 é 90% de fonte correta, então registro: hoje a camada de documentação está em 82% com busca lexical, e não é honesto prometer os 90% sem embeddings.

**Decisões.**
- **Pedaço, não documento, é a unidade de busca.** `docs/integracao_api.md` tem 983 linhas, e a fonte citada precisa apontar para a linha, como as fontes das perguntas de ouro. Sem sobreposição entre pedaços, para a faixa de linhas continuar exata; reavaliar quando a parte vetorial entrar.
- **Dono próprio por camada** (`<repo>:docs`). A aposentadoria de arestas é por dono (ADR 0009); se a documentação usasse o nome do repo, indexar documentos fecharia todas as arestas da estrutura. Também permite reindexar documento sem reextrair código, o que vai importar quando essa etapa gastar LLM. Virou teste.
- **`DOCUMENTED_IN` só com evidência direta:** README da raiz documenta o repo, rota escrita no texto documenta aquele endpoint. Considerei ligar o README de um diretório ao módulo dele, e desisti: o nó `Module` de `docs/` pode não existir (a estrutura só cria módulo onde há código) e a aresta sumiria em silêncio, porque a escrita casa os dois lados com `MATCH`.
- **O nó do endpoint não entra no grafo da documentação.** A escrita faz `SET n += row`; regravar o endpoint sem `handler` apagaria o que a estrutura sabe. Virou teste.
- **Rota citada casa por sufixo** quando o documento escreve sem o prefixo do servidor, e só se for um único endpoint. `GET /users/{id}` no `PLANO_EXECUCAO.md` casa com três endpoints e por isso é recusada, mesmo sendo quase certo que fala de `/api/v1/users/{id}`: é a mesma política das chamadas na Fase 1.
- **Rota citada que nenhum endpoint expõe é achado, não defeito.** São 5, entre elas o `POST /users` do ADR 0001 — a rota que dava 404 e motivou o próprio ADR. O relatório mostra em vez de esconder.
- **O que conta como documentação** exclui `data/`, `ios/` e companhia. `data/articles/phishing_examples.md` tem 1490 linhas de exemplos de phishing: indexado, faria qualquer pergunta sobre e-mail casar com ele.
- Comunidades ficaram para quando houver resumo (ver pendências).

**Erros meus.**
- Pus `}` na lista de pontuação a remover do fim de uma rota citada, então `/emails/{email_id}` virava `/emails/{email_id` e caía como rota inválida. Dez diagnósticos na primeira rodada real; nenhum teste meu cobria rota que termina em parâmetro. Corrigi e cobri.
- Escrevi "7 valores mascarados" no `docs/seguranca.md` e na mensagem do commit a partir de uma medição anterior à correção do falso positivo. São 6. Refiz o commit e troquei a frase por uma tabela, com arquivo e linha de cada um.
- Meus próprios testes erraram quatro vezes antes do código: contei 3 nós `Doc` onde há 4, usei `set()` em `StoredEdge` que não é hashable, deixei uma linha de asserção inútil colada de rascunho, e no teste de integração afirmei que a senha não aparece no arquivo inteiro.
- Rodei um script de refatoração cuja expressão não casou nada (o formatador já tinha quebrado as linhas antes), e ele inseriu um helper que ficava sem uso. A asserção do script barrou a gravação.

**Achados que só apareceram rodando contra os repos de verdade.**
- O filtro de segredos mascarava `OpenAI(api_key=api_key)` num exemplo de código da documentação. Não é segredo, é parâmetro repassado: o valor é a própria palavra da chave. Corrigi com a regra mais estreita que resolve o caso, e a mutação prova que os dois testes novos reprovam sem ela.
- A senha de desenvolvimento do `flyway.config` da phishforge-api é a palavra `phishforge`, que também é o nome do banco, do usuário e do host. Não existe máscara por valor que tire isso do texto sem destruir o documento; a máscara age na atribuição, e o teste confere a linha da senha. Está em `docs/seguranca.md`.

**Aprendizados.**
- Medir é barato e desmente palpite: duas decisões do índice (analisador e caminho) foram resolvidas por medição em minutos, e uma delas contra o que eu esperava.
- O índice de texto completo do Neo4j é assíncrono. Sem `db.awaitIndexes` o contrato buscava antes de o pedaço estar indexado, e falhava de forma intermitente.
- Rodar contra os quatro repos antes de escrever os testes do extrator achou um defeito que eu não tinha imaginado. Vale fazer a primeira rodada real cedo, mas o teste tem que vir atrás — senão o defeito volta.

**Pendências geradas.** A metade vetorial da busca e as 4 fontes que faltam; comunidades; `DOCUMENTED_IN` de documento para módulo e conceito, que depende de LLM; rota citada entre repos diferentes; pedaços sem sobreposição; qual arquivo de configuração conta como documento (`nginx.conf.template` da fonte de n12 está fora).

### 27/10/2026 — Revisão da Fase 2 e correções (ainda no PR #6)

**Feito.** Rodei o `revisor-de-entregas` (agora registrado de verdade como tipo de agente) antes de abrir o PR. Veredito: aprovado com ressalvas, nenhum bloqueante, 6 achados importantes e 7 sugestões. O revisor conferiu por conta própria os 121 pedaços contra os arquivos (faixas sem sobreposição e sem perder linha), a preservação de `valid_from`/`ingested_at` na reindexação, e varreu os 4 clones procurando valor de credencial no texto indexado.

**Reproduzi cada achado antes de agir**, porque relatório de agente é saída de modelo. Os quatro que eu conferi com script bateram.

**Corrigido.**
- **I1, o mais sério.** Minha exceção do filtro de segredos (`valor == chave`) ficou larga demais e desligava a regra 2 para a credencial de desenvolvimento mais comum: `flyway.password=password`, `password: password`, `DB_PASSWORD=db_password` e `api_key = "api_key"` passavam intactos. Nos 4 repos de hoje não vazava nada, mas era buraco aberto. Agora exige as três condições juntas: sem aspas, valor igual à chave e um `(` antes na linha, ou seja, argumento repassado dentro de uma chamada. Os seis casos viraram teste.
- **I2, o mais importante para a honestidade do número.** A CLI dizia que as 70 fontes fora da conta estavam fora "por serem código", o que eu nunca verifiquei — e com isso a pergunta t08 desaparecia inteira da medição, porque as fontes dela são `nginx.conf.template`. Agora o relatório diz "fora do índice de documentos", mostra a distribuição por extensão (`.template 4` salta à vista) e nomeia as perguntas da camada de documentação que ficaram sem nenhuma fonte medida, com as fontes de cada uma. São três: n02 e t09 têm fonte só em código, e quem responde é a camada de estrutura; t08 é buraco de cobertura de verdade.
- **I3.** `endpoints_documented` somava arestas, não endpoints distintos: eu reportei 40, são 37. Também contei 16 documentos onde são 18 (16 `Doc` e 2 `Decision`). Corrigi a métrica e os números nos documentos.
- **I4.** Uma pergunta com `AND`, `OR` ou `NOT` solto derrubava a busca: o Lucene recusava a consulta e o erro subia cru. Cada palavra passou a ir entre aspas. Virou caso de contrato nos dois backends.
- **I6.** O fake do grafo guardava aresta cuja ponta não existe, enquanto o Neo4j descarta em silêncio — e é justamente esse descarte que sustenta o ADR 0010 não regravar o nó do endpoint. Alinhei o fake e fixei no contrato; a mutação mostra o caso reprovando no fake sem a correção.
- **I5.** Os três comandos novos não tinham teste nenhum. Agora têm oito, justamente sobre os rótulos de I2 e I3.
- **S1, S2, S3, S5.** Pedaço só de linhas vazias não vira `Chunk` inválido; o ADR deixou de prometer trilha de títulos que o código não dá; as consultas de leitura vão com `routing_="r"`; `ChunkHit` já leva `ingested_at`, que toda resposta de tool precisa devolver.

**Não aceitei um.** S4 pedia condicionar `_CLOSE_ORPHAN_CALLS` à escrita que traz `EXPOSES`, para desacoplar as camadas. O argumento é bom, mas hoje a consulta é inócua (conferido) e mexer nela arrisca deixar uma `CALLS` órfã aberta sem ganho nenhum agora. Fica registrado como acoplamento conhecido.

**Aprendizados.**
- Meus dois erros de número (40 endpoints, 16 documentos) vieram do mesmo hábito: contar arestas e relatar como coisas, e somar um campo achando que era o total. Métrica que vai para o relatório merece conferência no banco, com `count(DISTINCT ...)`.
- O achado I2 é o tipo de defeito que nenhum teste pega, porque o código fazia o que eu escrevi: o problema era o rótulo afirmar mais do que a medida sustenta. Revisor com contexto limpo é bom exatamente nisso.
- Ao estreitar uma regra de segurança, escrever o caso contrário junto: os seis casos de I1 estão no teste, e três deles são o que a versão anterior deixava passar.
