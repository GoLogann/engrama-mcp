> Export do doc de design feito na sessão web: https://claude.ai/artifact/5cdvQN7TAECrvttMNejRrG (rev 14, 27/10/2026). Os três diagramas ficam só no doc original.

# Cérebro de conhecimento em grafo — fundamentação e plano

2026-10-27 · Logan Cardoso

## Resumo executivo

A proposta é um cérebro em grafo com três camadas: estrutura do código, documentação e experiência do time. Ele é exposto como um servidor MCP para devs, no Claude Code, e para os demais colaboradores, no Claude app e web. A literatura sustenta cada peça, mas separadamente; nas buscas feitas, nenhum trabalho junta as três com acesso pela organização inteira, e o mais próximo é o Code Digital Twin (PENG; WANG, 2025).

Quatro recomendações saem da revisão:

1. Arestas estruturais vêm de extração determinística, e o LLM só resume e liga conceitos. Agentes LLM que reconstruíram microsserviços chegaram a F1 de 0,604, e as conexões entre serviços foram o ponto mais fraco (LILJAS et al., 2026).
2. O LLM consulta o grafo por tools curadas, com Cypher somente leitura como reserva. Grafos de repositório melhoram agentes (OUYANG et al., 2025; LIU et al., 2025), e os erros restantes vêm do raciocínio do LLM (ABEDU; KHATOONABADI; SHIHAB, 2025).
3. Aprendizados entram como episódios datados e ligados ao código. Uma reflexão periódica os consolida, e os superados são invalidados, não apagados (RASMUSSEN et al., 2025; XU et al., 2025; PARK et al., 2023).
4. O porquê das decisões é capturado de pessoas, no momento em que acontece. LLMs não recuperam bem o rationale a partir de commits (VAIDHYANATHAN et al., 2026), e 63% dos ADRs em código aberto já nascem aceitos, sem a deliberação (SANTANA JUNIOR et al., 2026).

A PoC usa quatro repositórios do LABit-UFPA (PhishForge API e web, Phishing Quest API e app) e leva de 4 a 5 semanas para uma pessoa.

## Visão e objetivos

Qualquer colaborador deve perguntar sobre os projetos e receber uma resposta correta, com a fonte, sem abrir o GitHub. O mesmo cérebro guarda o que o time aprende enquanto desenvolve, para que esse conhecimento não saia junto com as pessoas.

O problema é medido na literatura. Quando desenvolvedores saem, projetos ficam expostos a perdas de conhecimento mais de três vezes maiores que o esperado (RIGBY et al., 2016). Quem fica passa a depender de documentação, de colegas ou de recriar o que se perdeu (ROBILLARD, 2021).

| Camada | O que guarda | De onde vem | Quem mais usa |
| --- | --- | --- | --- |
| Estrutura | Repositórios, módulos, rotas, chamadas, bancos, infraestrutura | Extração determinística do código | Devs |
| Documentação | READMEs, docs, ADRs, análises, resumos em linguagem simples | Indexação e resumos por LLM | Todos |
| Experiência | Decisões, aprendizados, problemas e reflexões, com autor e data | Pessoas, nos momentos de captura | Todos |

Os dois públicos fazem perguntas diferentes:

- **Devs:** impacto de uma mudança, quem chama o quê, por que algo foi feito assim.
- **Demais colaboradores** (pesquisa, gestão, quem está chegando): o que cada projeto faz, como os projetos se conectam, o que já foi aprendido.

## Princípios de design derivados da literatura

Doze princípios saem da revisão, e cada um muda uma decisão concreta do sistema.

| # | Princípio | Evidência | Como entra no sistema |
| --- | --- | --- | --- |
| 1 | Arestas estruturais por extração determinística | Agentes LLM reconstruindo 17 sistemas de microsserviços: F1 de 0,604 com GPT-4o; conexões entre serviços foram o ponto mais fraco (LILJAS et al., 2026) | Parsers por stack geram `CALLS`, `EXPOSES` e `STORES_IN`; o LLM não cria arestas estruturais |
| 2 | Contexto de dependência melhora o LLM | ArchAgent: F1 de 0,966 contra 0,860 do DeepWiki; o contexto de dependência aumentou o F1 (PAN et al., 2026) | Resumos por LLM recebem a vizinhança do nó no grafo |
| 3 | Grafo como navegação, não só como busca | RepoGraph melhorou quatro métodos no SWE-bench (OUYANG et al., 2025); CodexGraph consulta o repositório em linguagem de grafo (LIU et al., 2025) | Tools de navegação, com Cypher somente leitura como reserva |
| 4 | Reduzir o raciocínio exigido do LLM | 84% de acerto com few-shot e chain-of-thought; os erros vinham do raciocínio do LLM (ABEDU; KHATOONABADI; SHIHAB, 2025) | Tools curadas de alto nível, com exemplos na skill |
| 5 | Resumos por comunidade para perguntas globais | GraphRAG melhorou abrangência e diversidade das respostas a perguntas globais (EDGE et al., 2024) | Comunidades do grafo com resumo pré-gerado, base das respostas para não devs |
| 6 | Conhecimento com validade no tempo | Modelo bitemporal com invalidação de fatos, com ganho de acurácia e latência em memória longa (RASMUSSEN et al., 2025) | `valid_from`, `valid_to` e `ingested_at` em fatos e episódios |
| 7 | Aprendizados como notas ligadas que evoluem | Notas no estilo Zettelkasten, ligadas por similaridade; notas novas revisam as antigas (XU et al., 2025) | Episódios com contexto e palavras-chave, ligados a nós do código |
| 8 | Reflexão periódica | Sintetizar memórias em reflexões contribuiu para o comportamento dos agentes (PARK et al., 2023) | Job semanal consolida episódios em sínteses por tema |
| 9 | O porquê vem de pessoas, no momento | Rationale extraído de commits sai verboso e sem o porquê (VAIDHYANATHAN et al., 2026); 63% dos ADRs nascem aceitos (SANTANA JUNIOR et al., 2026); LLMs redigem decisões abaixo do nível humano (DHAR; VAIDHYANATHAN; VARMA, 2024) | Pergunta curta no PR, no fim da sessão e no ADR, registrando também as alternativas descartadas |
| 10 | O cérebro pode perguntar | Um agente que entrevista pessoas recuperou 94,9% do conhecimento-alvo em simulação (ZUIN et al., 2025) | Ao achar uma lacuna, como um módulo sem rationale, o cérebro pergunta ao autor |
| 11 | Curadoria e lugar central | Experience Factory: uma organização de apoio empacota a experiência (BASILI; LINDVALL; COSTA, [2001?]); onde a documentação fica afeta sua utilidade (AHMETI et al., 2024); humanos no loop (PENG; WANG, 2025) | Papel de curador; cérebro central com links para os repos |
| 12 | Controle de dados e superfície de ataque | Preocupação com LLMs de terceiros no onboarding (AZANZA et al., 2024); 833 servidores MCP vulneráveis entre 67.057 analisados (LI; GAO, 2025) | Servidor interno, escrita só de episódios, descrições de tools revisadas |

## Arquitetura proposta

Três fontes alimentam três camadas do mesmo grafo, e um único servidor MCP atende devs e demais colaboradores.

> Diagrama no doc original: arquitetura · 3 fontes, 3 camadas, 1 servidor MCP.

A coluna da direita é o que muda em relação ao plano anterior: pessoas registram episódios, e uma reflexão semanal os consolida e invalida os superados.

- **Extração determinística:** um parser leve por stack, cobrindo os decorators do FastAPI, o `Group`/`GET` do Gin, o `request()` dos services React e o `buildUrl` com a base URL no Flutter. Também lê migrations Flyway, compose, manifests Kubernetes e arquivos de dependência, e casa chamadas com rotas normalizando parâmetros (princípio 1).
- **Resumo e conceitos:** o LLM recebe o nó e sua vizinhança, gera resumos simples e técnicos, liga conceitos e resume comunidades (princípios 2 e 5).
- **Captura de episódios:** detalhada na próxima seção (princípios 7, 9 e 10).
- **Grafo:** Neo4j, ou Neptune numa stack AWS, com busca híbrida sobre documentos e episódios. O Graphiti é candidato para a camada de experiência por já ser bitemporal (princípio 6).
- **Atualização:** um webhook de push reextrai só o repositório alterado.

## Modelo de dados

O grafo tem uma família de nós por camada, e toda aresta carrega origem, evidência e validade no tempo.

| Nó | Camada | Exemplos nos quatro repos |
| --- | --- | --- |
| `Project`, `Repo` | Estrutura | PhishForge, Phishing Quest; `phishforge-api` |
| `Module` | Estrutura | `app/domain/services`, `src/modules/evaluation` |
| `Endpoint` | Estrutura | `POST /api/v1/generate`, `GET /api/v1/rankings` |
| `DataStore` | Estrutura | Postgres de cada API, coleção Qdrant `phishing_articles` |
| `Concept` | Documentação | Pista (cue), dificuldade, canal, rodada de avaliação |
| `Doc`, `Decision` | Documentação | `docs/integracao_api.md`, decisão 0001 da Quest API |
| `Episode` | Experiência | Aprendizado, decisão, problema, reflexão |
| `Person` | Experiência | Autor de episódios, responsável por um módulo |

Arestas principais: `EXPOSES`, `CALLS`, `STORES_IN`, `PART_OF`, `DOCUMENTED_IN`, `MENTIONS_CONCEPT`, `REFERENCES_ISSUE`, `ABOUT` (episódio para nó), `AUTHORED_BY` e `SUPERSEDES` (episódio para episódio).

Propriedades obrigatórias em toda aresta e episódio:

- `source`: extração, documento, LLM ou pessoa.
- `evidence`: repo, arquivo, linha e commit, ou o link do documento.
- `confidence`: alta para extração determinística, menor para inferência por LLM.
- `valid_from`, `valid_to` e `ingested_at`: o modelo bitemporal de Rasmussen et al. (2025).
- `author`: apenas em episódios.

## Ciclo de captura de aprendizados e reflexões

O porquê é registrado por quem decidiu, no momento em que decidiu. É exatamente o que um LLM não recupera depois a partir do código ou dos commits (VAIDHYANATHAN et al., 2026).

> Diagrama no doc original: ciclo de captura · 5 momentos, revisão semanal.

Episódios entram por cinco momentos naturais do trabalho, sempre com uma pergunta curta, e uma reflexão semanal os transforma em sínteses que um curador aprova.

| Momento | O que o cérebro pergunta | Tipo de episódio |
| --- | --- | --- |
| PR mergeado | O que mudou e por que este caminho, e não outro? | Decisão |
| Fim de sessão no Claude Code | O que aprendemos que vale para a próxima pessoa? | Aprendizado |
| ADR | Quais alternativas foram descartadas, e por quê? | Decisão |
| Retro ou experimento | O que funcionou, o que não funcionou e o que muda? | Reflexão |
| Lacuna achada no grafo | Por que este módulo existe, ou por que esta rota não tem cliente? | Problema ou decisão |

Formato de um episódio:

```yaml
tipo: aprendizado
sobre: [phishforge-api/pipeline-de-geracao]
texto: o que aprendemos e por quê
autor: preenchido pelo login
data: preenchida pelo sistema
substitui: episódio anterior, se houver
```

Regras do ciclo:

- Um episódio nunca é editado. Quando deixa de valer, um novo o substitui e o antigo ganha `valid_to` (RASMUSSEN et al., 2025).
- A reflexão semanal agrupa episódios por nó e por conceito e escreve uma síntese, como as reflexões de Park et al. (2023) e as notas que evoluem do A-Mem (XU et al., 2025).
- O curador aprova a síntese antes que ela vire a resposta padrão, no papel da organização de experiência de Basili, Lindvall e Costa ([2001?]).
- No fim da sessão, um hook do Claude Code sugere o registro, e a pessoa decide se registra.

## Servidor MCP

O servidor expõe tools de leitura para todos e uma única tool de escrita, que só acrescenta episódios. O grafo do código nunca é escrito pelo MCP; ele vem apenas da extração.

| Tool | Tipo | Para que serve |
| --- | --- | --- |
| `project_overview(projeto, nível)` | Leitura | Resumo `simples` ou `técnico` de um projeto |
| `find(texto)` | Leitura | Busca híbrida que resolve um nome para o nó certo |
| `how_it_connects(a, b)` | Leitura | Caminho entre dois nós, com a evidência de cada aresta |
| `who_uses(nó)` | Leitura | Quem chama uma rota ou usa um conceito |
| `impact_of_change(nó)` | Leitura | O que depende de um nó, nas duas direções |
| `search_knowledge(pergunta)` | Leitura | Busca em documentos, resumos e episódios |
| `lessons_about(nó ou tema)` | Leitura | Episódios e reflexões sobre o assunto, do mais recente ao mais antigo |
| `cypher_readonly(query)` | Leitura | Reserva para perguntas que as tools não cobrem |
| `record_episode(tipo, texto, sobre)` | Escrita | Registra um aprendizado, decisão, problema ou reflexão |

Regras do servidor:

- Toda resposta traz a fonte: arquivo e linha, documento, ou episódio com autor e data.
- `record_episode` exige autor autenticado e liga o episódio a pelo menos um nó.
- O que vem do grafo é tratado como dado, nunca como instrução, o que reduz o risco de injeção por documentos e episódios.

Distribuição:

- **Devs:** Claude Code, via `.mcp.json` no repositório ou configuração gerenciada pela organização, com transporte HTTP e login.
- **Demais colaboradores:** o mesmo servidor como conector personalizado no Claude (app e web), conforme o plano da organização permitir.
- **Skill de uso:** orienta o Claude a responder no nível de quem pergunta, citar a fonte e sugerir o registro de um episódio ao fim de uma tarefa.

## Decisão de stack

A PoC é feita em Python: as peças centrais do sistema nascem nesse ecossistema, e o gargalo está nas chamadas de LLM e nas consultas ao grafo, não em CPU.

| Critério | Python | Go |
| --- | --- | --- |
| Camada temporal (Graphiti) | Nativa | Reimplementar ou chamar de fora |
| GraphRAG e resumos por comunidade | Biblioteca da Microsoft | Reimplementar |
| SDK de MCP | Oficial | Oficial ([go-sdk](https://github.com/modelcontextprotocol/go-sdk)) |
| Driver do Neo4j | Sim | Sim |
| Parsers para Go, TypeScript, Dart e Python | tree-sitter | tree-sitter |
| Performance de ingestão | Suficiente para a PoC | Melhor em escala |
| Continuidade no LABit | `phishforge-api` já é Python | `phishing-quest-api` é Go |

Escolhas da PoC:

- Servidor MCP em Python, com o SDK oficial e transporte HTTP.
- Neo4j como banco e Graphiti para a camada de experiência.
- tree-sitter para a extração estrutural das quatro stacks.
- Poetry para dependências, como na `phishforge-api`.

Gatilho para rever: se a ingestão virar gargalo com centenas de repositórios, o extrator estrutural pode migrar para Go, com o núcleo mantido em Python.

## PoC com os quatro repositórios

A PoC usa os quatro repositórios públicos do LABit-UFPA, lidos em 27/10/2026, e uma leitura rápida já mostra conexões que nenhum repo revela sozinho.

| Achado | Repos envolvidos | Tipo de conexão |
| --- | --- | --- |
| O app chama 6 rotas da Quest API: categorias, perguntas, respostas, `game/answer`, login e registro | `phishing_quest` → `phishing-quest-api` | Chamada direta |
| O frontend chama as rotas de geração, curadoria, especialista e pesquisador, via proxy nginx em produção | `phishforge-frontend` → `phishforge-api` | Chamada direta |
| A doc da PhishForge API aponta o backend Go como único cliente das rotas de geração, mas o Go ainda gera rascunhos por template | `phishing-quest-api` → `phishforge-api` | Integração só documentada |
| `GET /api/v1/rankings` existe na API, mas o ranking do app ainda é mockado | `phishing_quest` e `phishing-quest-api` | Funcionalidade não usada |
| `/api/v1/evaluate/user-answer` não tem chamada encontrada nos outros três repos | `phishforge-api` | Rota sem cliente |
| O Postgres da PhishForge não publica a porta 5432 para conviver com o da Quest API | `phishforge-api` e `phishing-quest-api` | Restrição operacional |
| Pistas, dificuldade estimada, canais e o shape de `links` aparecem nas duas APIs | `phishforge-api` e `phishing-quest-api` | Conceito compartilhado |

Sementes para a camada de experiência, já presentes nos repos:

- `docs/analise_rag_vs_no_rag.md`, `docs/analise_zero_shot_vs_cot.md` e `docs/analise_alinhamento_artigo.md`, na `phishforge-api`: aprendizados de experimentos.
- `docs/decisoes/0001-path-registro-usuario.md` e `0002-estrategia-testes-e-ci.md`, na Quest API: decisões.
- `PLANO_EXECUCAO.md` e as referências a issues nos comentários do código: problemas e decisões em andamento.

Exemplos de perguntas de ouro:

| Pergunta | Público | Onde está a resposta |
| --- | --- | --- |
| O que é o PhishForge e para que serve? | Não técnico | README e resumo da `phishforge-api` |
| Qual a diferença entre o Phishing Quest e o PhishForge? | Não técnico | Resumos dos dois projetos |
| Como um especialista avalia um exemplo gerado? | Não técnico | Módulo de avaliação do frontend e rotas `/api/v1/expert` |
| Quais rotas o app chama, e quais a Quest API tem que o app não usa? | Técnico | Extração do Flutter e do Gin |
| Se o shape de `links` mudar, o que quebra? | Técnico | `item_draft_service.go` e o contrato da `phishforge-api` |
| Por que o Postgres da PhishForge não publica a porta? | Técnico | README da `phishforge-api` |
| O que aprendemos comparando geração com e sem RAG? | Ambos | `docs/analise_rag_vs_no_rag.md` |

> Diagrama no doc original: roadmap da PoC · 6 fases, 2 portões.

O primeiro portão garante a base estrutural antes de gastar com LLM; o segundo libera o estudo com usuários.

- **Fase 0:** ontologia, 40 perguntas de ouro e o filtro de segredos definido.
- **Fase 1:** grafo estrutural dos quatro repos, com rotas e chamadas casadas e evidência por arquivo e linha.
- **Fase 2:** docs indexados, resumos simples e técnicos por projeto e módulo, e comunidades resumidas.
- **Fase 3:** episódios semeados com as análises e decisões existentes, `record_episode` funcionando e a primeira reflexão semanal.
- **Fase 4:** servidor MCP remoto com login, configurado no Claude Code e como conector no Claude, mais a skill de uso.
- **Fase 5:** perguntas de ouro medidas, estudo com 6 a 10 pessoas e relatório de desalinhamento entre docs e código.

## Avaliação

A PoC é avaliada com perguntas de ouro e um estudo curto com usuários, no formato de Abedu, Khatoonabadi e Shihab (2025). As metas abaixo são propostas, a confirmar depois da primeira medição.

| Métrica | Como medir | Meta proposta |
| --- | --- | --- |
| Acerto | 40 perguntas de ouro, metade não técnica, corrigidas contra o código e os docs | 80% ou mais |
| Fonte correta | A citação aponta para o arquivo, documento ou episódio que sustenta a resposta | 90% ou mais |
| Cobertura estrutural | Rotas expostas e chamadas casadas, conferidas à mão nos quatro repos | 100% |
| Tarefas com usuários | 6 a 10 pessoas resolvem tarefas com o cérebro e só com o GitHub; tempo e acerto | Mais rápido e com mais acertos |
| Captura de experiência | Episódios por semana e fração ligada a nós do código | Observar na fase 5 |
| Frescor | Tempo entre um push e o grafo atualizado | Menos de 10 minutos |

Amostras pequenas limitam a generalização: o Onboarding Buddy foi avaliado com 8 pessoas, e os autores registram esse limite (IONESCU; TITOV; IZADI, 2025).

## Riscos e mitigações

O maior risco novo é a escrita: com episódios, o cérebro deixa de ser somente leitura e passa a poder ser envenenado.

| Risco | Mitigação |
| --- | --- |
| Envenenamento da memória via `record_episode` | Autor autenticado, só acréscimo, revisão do curador, `SUPERSEDES` em vez de edição |
| Injeção de instruções por documentos ou descrições de tools | Conteúdo lido é dado; descrições de tools revisadas (LI; GAO, 2025) |
| Segredos commitados, como credenciais de desenvolvimento no compose e no plano de execução | Filtro na ingestão; o cérebro nunca devolve credenciais |
| Dados pessoais, como o export do console do pesquisador | O cérebro lê código e docs, nunca os bancos |
| Grafo desatualizado respondendo com confiança | Webhook de push e `ingested_at` visível na resposta |
| Episódios que ninguém registra | Captura nos momentos naturais, com uma pergunta curta, nunca um formulário longo |
| LLM de terceiros com dados internos | Avaliar modelo hospedado na própria nuvem ou aberto (AZANZA et al., 2024) |
| Permissões numa empresa real | Herdar as permissões do GitHub, ou mostrar só o nível de resumo a quem não tem acesso ao código |

## Lacuna de pesquisa e oportunidades

Nas buscas feitas, nenhum trabalho combina grafo do código entre repositórios, memória da experiência do time ao longo do desenvolvimento e acesso por toda a organização via MCP. O Code Digital Twin é o mais próximo: une artefatos e conhecimento tácito, com sincronização incremental (PENG; WANG, 2025). O foco dele é dar esse conhecimento a LLMs no desenvolvimento; o acesso para não devs e o registro ativo de reflexões pelo time ficam como espaço de contribuição.

Perguntas que a PoC pode responder com dados:

- Episódios capturados no momento respondem melhor às perguntas de porquê do que rationale extraído de commits?
- Colaboradores não técnicos respondem perguntas sobre os projetos mais rápido com o cérebro do que com o GitHub?
- Quanto do desalinhamento entre documentação e código o grafo detecta, como uma integração documentada sem chamada no código?

## Referências

ABEDU, Samuel; KHATOONABADI, SayedHassan; SHIHAB, Emad. Synergizing LLMs and knowledge graphs: a novel approach to software repository-related question answering. arXiv, 2025. DOI: 10.1145/3796510. Disponível em: [https://arxiv.org/abs/2412.03815](https://arxiv.org/abs/2412.03815v2). Acesso em: 27 out. 2026.

AHMETI, Bardha et al. Introducing architecture decision records in practice: an action research study. In: EUROPEAN CONFERENCE ON SOFTWARE ARCHITECTURE, 18., 2024, Luxemburgo. Disponível em: [conf.researchr.org](https://conf.researchr.org/details/ecsa-2024/ecsa-2024-research-papers/9/Introducing-Architecture-Decision-Records-in-Practice-An-Action-Research-Study). Acesso em: 27 out. 2026.

AZANZA, Maider et al. Can LLMs facilitate onboarding software developers? An ongoing industrial case study. In: CONFERENCE ON SOFTWARE ENGINEERING EDUCATION AND TRAINING, 2024, Würzburg. Disponível em: [conf.researchr.org](https://conf.researchr.org/details/cseet-2024/cseet-2024-industry-track/4/Can-LLMs-Facilitate-Onboarding-Software-Developers-An-Ongoing-Industrial-Case-Study). Acesso em: 27 out. 2026.

BASILI, Victor R.; LINDVALL, Mikael; COSTA, Patricia. Implementing the experience factory concepts as a set of experience bases. College Park: Fraunhofer Center for Experimental Software Engineering Maryland, [2001?]. Disponível em: [https://www.cs.umd.edu/users/basili/publications/proceedings/P90.pdf](https://www.cs.umd.edu/users/basili/publications/proceedings/P90.pdf). Acesso em: 27 out. 2026.

DHAR, Rudra; VAIDHYANATHAN, Karthik; VARMA, Vasudeva. Can LLMs generate architectural design decisions? An exploratory empirical study. In: INTERNATIONAL CONFERENCE ON SOFTWARE ARCHITECTURE, 2024. Disponível em: [https://arxiv.org/abs/2403.01709](https://arxiv.org/abs/2403.01709v1). Acesso em: 27 out. 2026.

EDGE, Darren et al. From local to global: a graph RAG approach to query-focused summarization. arXiv, 2024. Disponível em: [https://arxiv.org/abs/2404.16130](https://arxiv.org/html/2404.16130v2). Acesso em: 27 out. 2026.

IONESCU, Andrei-Cristian; TITOV, Sergey; IZADI, Maliheh. A multi-agent onboarding assistant based on large language models, retrieval augmented generation, and chain-of-thought. In: ACM INTERNATIONAL CONFERENCE ON THE FOUNDATIONS OF SOFTWARE ENGINEERING, 2025, Trondheim. Disponível em: [https://arxiv.org/abs/2503.23421](https://arxiv.org/html/2503.23421v1). Acesso em: 27 out. 2026.

LI, Xiaofan; GAO, Xing. A first look at the security issues in the Model Context Protocol ecosystem. arXiv, 2025. Disponível em: [https://arxiv.org/abs/2510.16558](https://arxiv.org/abs/2510.16558v1). Acesso em: 27 out. 2026.

LILJAS, Venla et al. Can agents reconstruct microservice architecture? In: INTERNATIONAL SYMPOSIUM ON EMPIRICAL SOFTWARE ENGINEERING AND MEASUREMENT, 20., 2026. Leibniz International Proceedings in Informatics, v. 394, p. 62:1-62:13. DOI: [10.4230/LIPIcs.ESEM.2026.62](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ESEM.2026.62).

LIU, Xiangyan et al. CodexGraph: bridging large language models and code repositories via code graph databases. In: CONFERENCE OF THE NATIONS OF THE AMERICAS CHAPTER OF THE ASSOCIATION FOR COMPUTATIONAL LINGUISTICS, 2025. Disponível em: [https://aclanthology.org/2025.naacl-long.7/](https://aclanthology.org/2025.naacl-long.7/). Acesso em: 27 out. 2026.

OUYANG, Siru et al. RepoGraph: enhancing AI software engineering with repository-level code graph. In: INTERNATIONAL CONFERENCE ON LEARNING REPRESENTATIONS, 2025. Disponível em: [proceedings.iclr.cc](https://proceedings.iclr.cc/paper_files/paper/2025/hash/4a4a3c197deac042461c677219efd36c-Abstract-Conference.html). Acesso em: 27 out. 2026.

PAN, Rusheng et al. ArchAgent: scalable legacy software architecture recovery with LLMs. arXiv, 2026. Disponível em: [https://arxiv.org/pdf/2601.13007](https://arxiv.org/pdf/2601.13007). Acesso em: 27 out. 2026.

PARK, Joon Sung et al. Generative agents: interactive simulacra of human behavior. arXiv, 2023. Disponível em: [https://arxiv.org/abs/2304.03442](https://huggingface.co/papers/2304.03442). Acesso em: 27 out. 2026.

PENG, Xin; WANG, Chong. Code digital twin: empowering LLMs with tacit knowledge for complex software development. arXiv, 2025. Disponível em: [https://arxiv.org/pdf/2510.16395](https://arxiv.org/pdf/2510.16395). Acesso em: 27 out. 2026.

RASMUSSEN, Preston et al. Zep: a temporal knowledge graph architecture for agent memory. arXiv, 2025. Disponível em: [https://arxiv.org/abs/2501.13956](https://arxiv.org/html/2501.13956v1). Acesso em: 27 out. 2026.

RIGBY, Peter C. et al. Quantifying and mitigating turnover-induced knowledge loss. In: INTERNATIONAL CONFERENCE ON SOFTWARE ENGINEERING, 38., 2016, Austin. Resumo disponível em: [neverworkintheory.org](https://neverworkintheory.org/2021/09/30/quantifying-and-mitigating-turnover-induced-knowledge-loss.html). Acesso em: 27 out. 2026.

ROBILLARD, Martin P. Turnover-induced knowledge loss in practice. In: ACM JOINT EUROPEAN SOFTWARE ENGINEERING CONFERENCE AND SYMPOSIUM ON THE FOUNDATIONS OF SOFTWARE ENGINEERING, 29., 2021, Atenas. Disponível em: [https://www.cs.mcgill.ca/~martin/papers/esecfse2021.pdf](https://www.cs.mcgill.ca/~martin/papers/esecfse2021.pdf). Acesso em: 27 out. 2026.

SANTANA JUNIOR, Enio Garcia de et al. Architecture decision records: adoption, impact, and developer engagement in open-source software. In: INTERNATIONAL CONFERENCE ON SOFTWARE ARCHITECTURE, 2026, Amsterdã. Disponível em: [conf.researchr.org](https://conf.researchr.org/details/icsa-2026/icsa-2026-papers/34/Architecture-Decision-Records-Adoption-Impact-and-Developer-Engagement-in-Open-Sou). Acesso em: 27 out. 2026.

VAIDHYANATHAN, Karthik et al. Can LLMs extract architectural design decisions from source code commits? A preliminary exploratory study. arXiv:2609.03721, 2026. Disponível em: [tldr.takara.ai](https://tldr.takara.ai/p/2609.03721). Acesso em: 27 out. 2026.

XU, Wujiang et al. A-Mem: agentic memory for LLM agents. In: ADVANCES IN NEURAL INFORMATION PROCESSING SYSTEMS, 38., 2025. DOI: 10.52202/085713-0593. Disponível em: [proceedings.neurips.cc](https://proceedings.neurips.cc/paper_files/paper/2025/hash/19909c36f51abc4856b4560aff3d36d6-Abstract-Conference.html). Acesso em: 27 out. 2026.

ZUIN, Gianlucca et al. Leveraging large language models for tacit knowledge discovery in organizational contexts. arXiv, 2025. Disponível em: [https://arxiv.org/pdf/2507.03811](https://arxiv.org/pdf/2507.03811). Acesso em: 27 out. 2026.

### Documentação técnica e repositórios consultados

- [Backstage — MCP Actions Backend](https://backstage.io/docs/ai/mcp-actions)
- [Spotify Portal — Creating the Catalog Graph](https://backstage.spotify.com/docs/portal/core-features-and-plugins/catalog/creating-the-catalog-graph)
- [Neo4j MCP server (Docker Hub)](https://hub.docker.com/r/mcp/neo4j)
- [Graphiti MCP server](https://help.getzep.com/graphiti/getting-started/mcp-server)
- Repositórios do LABit-UFPA, lidos em 27/10/2026: [phishforge-api](https://github.com/LABit-UFPA/phishforge-api) (commit 815bd3a), [phishforge-frontend](https://github.com/LABit-UFPA/phishforge-frontend) (73b7b83), [phishing-quest-api](https://github.com/LABit-UFPA/phishing-quest-api) (1141d44) e [phishing_quest](https://github.com/LABit-UFPA/phishing_quest) (43ed8ff)
