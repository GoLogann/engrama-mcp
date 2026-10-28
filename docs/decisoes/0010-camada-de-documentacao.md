# ADR 0010 — Camada de documentação: o que é documento, pedaços e busca

- **Status:** aceita
- **Data:** 27/10/2026

## Contexto

A Fase 2 do plano indexa a documentação dos repos (READMEs, `docs/`, ADRs) para a busca híbrida. A parte que usa LLM (resumos, conceitos, comunidades) e os embeddings dependem de chave de API, que não está disponível; a parte determinística não depende de nada disso e já responde perguntas da camada de documentação.

Três decisões não estavam no plano e precisam de registro: o que conta como documento, em que granularidade o texto entra no grafo, e como a nova camada conviva com a vigência das arestas do ADR 0009.

## Decisão

1. **O que é documento.** Entram `*.md`, `*.config`, `*.conf`, `*.conf.template` e o `package.json` da raiz. *(Emenda de 28/10/2026: `*.conf` e `*.conf.template` entraram depois. Três das quatro fontes da pergunta t08 e uma das duas de n12 estão em `phishforge-frontend/nginx.conf.template`, que descreve como o frontend chega na API em produção — é documentação de operação, não dado. Medida antes de adotar: a regra traz exatamente um arquivo nos quatro repos, então não há ruído. `*.cfg` e `*.ini` ficaram de fora por não existirem em nenhum deles.)* Ficam fora os diretórios de dados e de plataforma (`data/`, `assets/`, `ios/`, `android/`, `macos/`, `windows/`, `linux/`, `web/`) e os de teste. `data/articles/phishing_examples.md` tem 1490 linhas de exemplos de phishing: indexar isso faria qualquer pergunta sobre e-mail casar com ele. `migrate/flyway.config` e `package.json` entram porque duas perguntas de ouro (t12 e n18) têm a resposta neles.

2. **Decisão (ADR) pelo diretório.** `docs/decisoes/`, `docs/decisions/`, `adr/` e `adrs/` viram nós `Decision`; o resto vira `Doc`. O critério é o caminho, não o conteúdo: é determinístico e é a convenção dos repos do LABit. O `status` sai da linha "Status:" do próprio documento, e o título, do primeiro título do arquivo (ou do nome dele).

3. **Pedaço (`Chunk`) é o que entra no índice**, com a faixa de linhas de onde saiu. Um documento inteiro não serve como unidade de busca: `docs/integracao_api.md` tem 983 linhas, e a fonte que o MCP cita precisa apontar para a linha, que é o formato das fontes das perguntas de ouro (`repo/caminho:linha`). O corte segue as seções do Markdown: seções curtas seguidas são juntadas até 1500 caracteres, e seção maior que isso é cortada em limite de linha. Cada pedaço carrega a trilha de títulos da seção em que ele começa (`Instalação > Docker`).

4. **`DOCUMENTED_IN` só com evidência que não exige interpretação.** Duas formas: o `README.md` da raiz documenta o repo, e uma rota escrita no texto (`POST /api/v1/generate`) documenta aquele endpoint. Dizer que um documento qualquer documenta determinado módulo é leitura de conteúdo, não extração: fica para a parte com LLM, com origem e confiança próprias (princípio 1 do doc de fundamentação).

5. **Rota citada casa por forma, e por sufixo quando precisa.** Documento costuma escrever a rota sem o prefixo com que o servidor a registra: o ADR 0001 da Quest API fala de `POST /users/register`, e o grafo tem `POST /api/v1/users/register`. Quando nada casa exatamente, vale o endpoint cujo caminho termina na citação, e só se for um único; com dois ou mais, a citação é ignorada. A citação só vale para endpoints do mesmo repo, e só para endpoints que já existem no grafo, para a aresta nunca apontar para um nó que não existe.

6. **Dono próprio por camada:** as arestas da documentação de um repo têm `owner = "<repo>:docs"`. A aposentadoria do ADR 0009 é por dono, então indexar documentos não pode encerrar as arestas da estrutura do mesmo repo, nem o contrário. Também permite reindexar documentos sem reextrair código, o que importa quando essa etapa passar a gastar chamada de LLM.

7. **O nó do endpoint não é regravado pela documentação.** A escrita faz `SET n += row`: incluir o `Endpoint` no grafo da documentação apagaria o `handler` que a estrutura gravou.

8. **A máscara de segredos roda na indexação**, antes de o texto virar nó, como o ADR 0005 previu.

9. **Busca por texto com analisador português.** Medido contra as fontes das perguntas de ouro: o analisador português acha o arquivo certo em 82% das fontes de documento (k=10), contra 68% do analisador padrão — os documentos dos quatro repos são em português. Indexar também o caminho do arquivo foi medido e não mudou nada (82%), então ficou de fora. A consulta é reduzida às palavras antes de ir ao Lucene e cada palavra vai entre aspas: é assim que o texto indexado também é quebrado, e nem a pontuação nem uma palavra-operador (`AND`, `OR`, `NOT`) da pergunta pode virar sintaxe. Sem as aspas, uma pergunta com uma dessas palavras soltas fazia o Lucene recusar a consulta inteira.

## Alternativas consideradas

- **Documento inteiro como unidade de busca:** mais simples, mas a fonte citada viraria o arquivo, sem linha, e um documento de 983 linhas casaria com quase toda pergunta.
- **Pedaços com sobreposição:** melhora busca semântica, mas atrapalha a faixa de linhas e não ajuda busca por palavra. Reavaliar quando a parte vetorial entrar.
- **Indexar o caminho do arquivo:** medido, sem ganho (a pergunta t12 fala de "migrations" e o caminho diz `migrate`).
- **Uma ingestão só para estrutura e documentação:** evitaria o dono por camada, mas amarraria reindexar documento a reextrair código, e a mesma rodada teria de passar pelos dois.
- **`DOCUMENTED_IN` de módulo para o README do diretório:** tentador e barato, mas o nó `Module` de `docs/` pode não existir (a estrutura só cria módulo onde há código), e a aresta sumiria em silêncio.

10. **A medida de recuperação de fonte só conta a fonte cujo arquivo está no índice**, e nomeia as perguntas da camada de documentação que ficaram sem nenhuma fonte medida. Fonte fora do índice não é acerto nem erro: dizer "as outras são código" seria afirmar o que não foi verificado, e esconderia uma pergunta inteira (t08, cujas fontes são `nginx.conf.template`).

## Consequências

- `engrama index-docs` depende de `engrama ingest` para ligar rota citada a endpoint. Sem estrutura no grafo, ele indexa e avisa que nenhum endpoint era conhecido.
- A busca de hoje é só por palavra. As 4 fontes que ela não acha (`package.json` de n18, os dois `flyway*.config` de t12 e o README do frontend de n12) são todas de vocabulário diferente do da pergunta, que é justamente o que a parte vetorial resolve.
- Três perguntas da camada de documentação ficam sem nenhuma fonte medida, por dois motivos diferentes: n02 e t09 têm fontes só em código (quem responde é a camada de estrutura, e o enunciado de n02 diz isso), e t08 aponta para `nginx.conf.template`, que o critério do item 1 não cobre. A primeira é classificação da pergunta; a segunda é buraco de cobertura e está como pendência.
- Rota citada num documento que nenhum endpoint expõe fica registrada no relatório como desalinhamento entre documentação e código — um dos achados que a PoC quer mostrar. Hoje são 5, entre elas o `POST /users` do ADR 0001.
- Documento de repo cliente que cita rota de outro repo (o README do frontend, por exemplo) não gera aresta. É limitação consciente da regra "mesmo repo".
