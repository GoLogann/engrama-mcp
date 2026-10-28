# ADR 0011 — Busca por significado, com a palavra como reserva

- **Status:** aceita
- **Data:** 28/10/2026

## Contexto

O ADR 0010 fechou a camada de documentação com busca por palavra, no índice de texto completo do Neo4j com analisador português: 82% das fontes esperadas pelas perguntas de ouro (18 de 22, k=10). As quatro que faltavam eram todas do mesmo tipo — a pergunta usa um vocabulário e o arquivo usa outro: t12 fala de "migrations" e o arquivo diz `flyway`/`migrate`; n18 fala de "tecnologias" e o `package.json` lista nomes de pacote.

O plano da PoC prevê para esse caso **busca híbrida**: metade por palavra, metade vetorial, juntadas por RRF (*Reciprocal Rank Fusion*). Com a chave da Voyage disponível, a parte vetorial foi implementada e a previsão do plano foi medida em vez de assumida.

## Medição

Mesmas 22 fontes de documento, mesmo corpus (121 pedaços, 18 documentos), modelo `voyage-4-large`, índice vetorial de 1024 com cosseno. Cada célula é *arquivo certo na lista / pedaço que cobre a linha citada*.

| Variante | k=5 | k=10 | k=20 |
| --- | --- | --- | --- |
| Só palavra | 82% / 63% | 82% / 79% | 86% / **89%** |
| **Só vetor** | 86% / 74% | **91%** / 74% | **95%** / 79% |
| Híbrida por RRF | 86% / 68% | 86% / 74% | 91% / 79% |

A fusão perde para o vetor puro em **todos** os tamanhos de lista. Não é falta de calibração: foram medidas 18 combinações de `k` (1, 3, 5, 10, 20, 60) e de profundidade de candidatos (10, 20, 50), e **todas** dão 86%. Uma variante que troca a soma pela melhor posição (não penalizar o achado de uma lista só) também dá 86%, nas nove combinações testadas.

A causa é estrutural. O RRF soma `1/(k + posição)` de cada lista, então um item visto pelas duas buscas em 10º lugar ganha de um item visto por uma só em 6º — é consenso, que é o que o método promete. Mas as duas metades aqui são **complementares, não redundantes**:

| Fonte que falta | Posição na palavra | Posição no vetor |
| --- | --- | --- |
| `phishforge-api/migrate/flyway.config` (t12) | não acha nos 50 | 6º |
| `phishforge-frontend/README.md` (n12) | 25º | 18º |
| `phishforge-frontend/package.json` (n18) | 26º | 36º |

Com dez vagas de saída divididas entre duas listas, um achado em 6º lugar numa delas não cabe. A variante por melhor posição equivale a intercalar as listas, e o 6º do vetor cai para a 12ª posição da saída: também não cabe.

A hipótese que restava a favor de manter as duas metades era que as 40 perguntas de ouro são todas em linguagem natural, o que favorece embedding, e que a tool do MCP também receberia consulta de casamento exato, onde a palavra ganharia. **Medida, a hipótese não se sustentou:**

| Consulta | Palavra | Vetor |
| --- | --- | --- |
| `POST /api/v1/generate` | 1º | 1º |
| `flyway.locations` | 2º | **1º** |
| `OPENAI_API_KEY` | 2º | **1º** |
| `docker compose up` | 2º | 2º |
| `nginx` | não acha | não acha |

(`nginx` falha nas duas porque `nginx.conf.template` não é indexado — é o buraco conhecido do t08, item 10 do ADR 0010.)

## Decisão

1. **O ranking é o índice vetorial.** 91% em k=10 contra 86% da fusão e 82% da palavra, e empate ou vantagem também em consulta de casamento exato.

2. **A busca por palavra fica como reserva, não como metade de uma fusão.** Sem `VOYAGE_API_KEY`, `Neo4jKnowledgeIndex` ranqueia por palavra. O motivo não é qualidade — ela acha menos — e sim não exigir chave de API de quem só quer rodar o projeto, e não derrubar a busca quando a conta esgota o teto de taxa. O índice de texto completo e o analisador português continuam como estão.

3. **A reserva nunca é escolhida em silêncio.** `KnowledgeIndex.ranking()` entrou no contrato da porta e diz `vetor` ou `palavra`; `SourceRecallReport` carrega esse valor e `engrama check-sources` o imprime, com aviso quando mediu a reserva. Um relatório que não diz qual motor respondeu afirma o número de um sobre o outro.

4. **Só teto de taxa esgotado degrada; erro de configuração sobe.** O `VoyageEmbedder` espera e tenta de novo (25s, 45s, 65s, 90s) e, esgotado, traduz o erro do provedor para `EmbeddingUnavailable`. A busca cai para a reserva e avisa. Chave errada, modelo inexistente ou índice ausente sobem como vieram: a saída é consertar, não responder pior sem ninguém saber.

5. **O serviço de fusão por RRF foi removido do código.** Ficou sem uso em produção, e código morto num repositório público é pior do que uma decisão registrada. Ele existiu no commit `92577ce`, com oito testes, e as medições acima são o que justifica tirá-lo.

6. **O vetor não entra na entidade `Chunk`.** É artefato de recuperação, derivado do texto, não fato do domínio: quem embute é a porta `Embedder` e quem grava é a `VectorStore`. `IndexDocuments` embute **depois** de escrever o grafo, e `store` ignora chave que não existe, então vetor nunca cria nó. Nenhuma leitura do MCP devolve o vetor.

7. **`voyage-4-large`, 1024 dimensões, cosseno.** O tamanho fica fixo no `schema.cypher` porque o índice nasce com ele; o adapter recusa vetor de tamanho diferente, para a troca de modelo não corromper o índice em silêncio. Sem `output_dimension` na chamada: a documentação lista os tamanhos aceitos sem nomear o parâmetro, e chutar nome de campo é erro que só aparece em produção.

## Alternativas consideradas

- **Híbrida por RRF, como o plano previa:** medida, perde em todos os tamanhos de lista. Registrada aqui com os números em vez de descartada por gosto.
- **Fusão por melhor posição em vez de soma:** endereça o diagnóstico (não punir o achado de uma lista só), mas equivale a intercalar as listas e dá o mesmo 86%.
- **Remover a metade por palavra:** chegaria aos mesmos 91% com menos código, mas tornaria a busca impossível sem chave de API e transformaria toda consulta numa chamada de rede — no teto gratuito, três por minuto.
- **Lista de saída maior (k=20):** o vetor chega a 95% e a palavra, a 89% de linha. Não foi adotado como padrão porque ler 20 pedaços é um resultado mais fraco do que ler 10; fica disponível em `--limit`.
- **Modelo local de embedding:** dispensaria chave e custo. Não medido, porque a chave chegou antes. Continua como saída se o acesso à Voyage se perder.
- **Embutir `repo/caminho` e a trilha de títulos junto com o texto do pedaço:** medido em 28/10/2026 e **descartado**. A hipótese era que o vetor não sabia de que repo o pedaço era — a pergunta n12 diz "pelo site do PhishForge" e os dez primeiros resultados eram todos documentos da *API*. Com o contexto embutido, o acerto de arquivo ficou igual (23/26), as três fontes não encontradas foram exatamente as mesmas, e a cobertura de linha **piorou**, de 78% para 74%: o prefixo dilui o conteúdo do pedaço e muda qual deles é recuperado. A falha de n12 não é de contexto de repo — as palavras distintivas da pergunta ("gerar exemplos") apontam para os documentos da API, e a resposta mora na configuração do nginx do frontend. O próximo lance para essa métrica é reranking (`rerank-3` da Voyage), que pontua o par pergunta-documento em vez de comparar vetores.

## Consequências

- A camada de documentação passa o Portão 2 no critério de fonte (≥ 90%): 91% em k=10. O Portão 2 completo ainda exige resposta certa, que depende de LLM.
- **Toda busca passa a custar uma chamada de rede.** Numa conta Voyage sem forma de pagamento são 3 requisições por minuto, o que torna `check-sources` (22 perguntas) uma operação de minutos. Cadastrar forma de pagamento libera o limite padrão e mantém os 200 milhões de tokens gratuitos.
- **A busca deixa de ter a noção de "não achei".** Busca vetorial devolve sempre os k vizinhos mais próximos, então consulta sem casamento traz resultados irrelevantes em vez de lista vazia. Quem decide relevância passa a ser quem consome, e na Fase 4 a tool do MCP precisa disso explícito para não convidar o modelo a citar fonte irrelevante. Está coberto por teste de contrato.
- Fica aberto: n12 e n18 continuam sem fonte recuperável em k=10 (o README do frontend e o `package.json`), e a cobertura de linha do vetor (74%) é pior que a da palavra em k=20 (89%) — o MCP cita `arquivo:linha`, então isso ainda custa precisão.
- A medida tem **n = 22 fontes**. A diferença entre 86% e 91% são duas fontes. O mecanismo está explicado e é reprodutível; o tamanho do efeito, com essa amostra, não suporta mais do que a direção.
