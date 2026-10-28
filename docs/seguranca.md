# Segredos e dados sensíveis

O engrama lê código e documentação, nunca bancos de dados, e nunca devolve uma credencial numa resposta. Isso é garantido em duas camadas: um filtro no texto que entra no grafo (`SecretScanner`, implementado em `RegexSecretScanner`) e um sanitizador em toda saída do MCP (fase 4). O filtro roda hoje na indexação de documentos (`engrama index-docs`), que é onde texto de verdade passa a ser gravado; a extração da estrutura grava caminhos, linhas e rotas, não trechos. Os formatos das credenciais da tabela abaixo são casos de teste do filtro com valores falsos (`tests/unit/infrastructure/test_secret_scanner.py`), e as linhas reais dos clones também são testadas (`tests/integration/test_secret_scanner_repos.py`, que lê o valor do próprio clone e nunca o grava no teste).

## Regras da ingestão

1. **Arquivos nunca lidos:** `.env` e `.env.*` (exceto `.env.example`), `*.pem`, `*.key`, `*.p12`, `id_rsa*`, binários (`.exe`, `.so`, `.dll`, `.jar`), imagens, PDFs, `*.snapshot`, `node_modules/`, `build/`, `dist/` e relatórios brutos de experimento (`*_YYYYMMDD_HHMMSS.json`). Desses, só o caminho entra no grafo, nunca o conteúdo.
2. **Valores mascarados, chaves mantidas:** em YAML, `.env.example`, compose, workflows de CI e blocos de código em Markdown, o valor de toda chave que case com `PASSWORD|PASSWD|PASSPHRASE|SECRET|SALT|TOKEN|API_KEY|PRIVATE_KEY|CREDENTIAL` vira `<redacted>`. Em `${VAR:-padrão}`, `${VAR-padrão}` e `${VAR:=padrão}` a variável é mantida e só o padrão é mascarado (`${VAR:-<redacted>}`), porque o compose embute esse padrão no repositório; `${VAR:-}` e `${VAR}` ficam intactos. A chave continua no grafo, porque saber que existe `JWT_SECRET` é conhecimento útil; o valor não.
3. **Strings de conexão:** `password=...` dentro de strings de conexão e `usuario:senha@host` em URLs são mascarados.
4. **Literais no código:** um literal atribuído a uma variável cujo nome contém `secret`, `password`, `token` ou `key` é mascarado (é o caso do padrão de desenvolvimento do JWT na Quest API). Exceção: quando o valor é a própria palavra da chave (`OpenAI(api_key=api_key)`), é parâmetro repassado, não segredo — mascarar estragaria o exemplo de código e o único "segredo" revelado seria o nome da chave.
5. **Padrões de provedor:** todo texto ingerido passa pelos detectores de provedor do [detect-secrets](https://github.com/Yelp/detect-secrets) (AWS, GitHub, chaves privadas, JWT, entre outros). Um achado é mascarado e registrado com a linha. Os detectores de entropia ficaram de fora: chamados linha a linha, eles não aplicam limiar e marcam até nomes como `passwordController`. A regra 2 cobre o caso comum de segredo em configuração.

## Regras da saída

- Toda resposta do MCP passa pelas mesmas máscaras das regras 2 a 5 antes de sair. Se algo escapou da ingestão, para aqui.
- Conteúdo lido do grafo é dado, nunca instrução: descrições de tools não incluem texto vindo dos repos.

## Onde há segredos nos repos da PoC

Levantado nos commits fixados em `config/repos.yaml`. São credenciais de desenvolvimento, já públicas nos repos, mas o engrama não as repete.

| Arquivo | Linha | Chave |
| --- | --- | --- |
| `phishing-quest-api/docker-compose.yml` | 9 | `POSTGRES_PASSWORD` |
| `phishing-quest-api/config.yaml` | 15 | `password=` na `connectionstring` |
| `phishing-quest-api/PLANO_EXECUCAO.md` | 23 | `DB_PASSWORD` |
| `phishing-quest-api/PLANO_EXECUCAO.md` | 27 | `JWT_SECRET` |
| `phishing-quest-api/core/service/jwt_service.go` | 39 | literal padrão de `secret` |
| `phishing-quest-api/migrate/flyway.config` | 3 | `flyway.password` |
| `phishing-quest-api/.github/workflows/workflow_pr_ci.yml` | 90, 103, 106, 107, 129 | `POSTGRES_PASSWORD`, `DB_PASSWORD`, `JWT_SECRET`, `RESEARCH_EXPORT_SALT`, `-password=` |
| `phishforge-api/docker-compose.yml` | 9, 120, 195 | `POSTGRES_PASSWORD`, `DB_PASSWORD`, `PGPASSWORD` |
| `phishforge-api/docker-compose.yml` | 135, 174 | padrão de `${API_KEY:-...}` (em `API_KEY` e `CURATION_API_KEY`) |
| `phishforge-api/migrate/flyway.config` | 3 | `flyway.password` |

Arquivos excluídos por tipo nos mesmos commits: 14 PDFs (artigos da base do RAG em `phishforge-api/data/articles/`), 21 imagens, 1 snapshot do Qdrant e 1 executável (`phishing-quest-api/phishing-quest.exe`).

## O que a máscara faz nos quatro repos

Na indexação dos 16 documentos, 6 valores são mascarados, todos pela regra 2:

| Documento | Linha | Chave |
| --- | --- | --- |
| `phishforge-api/docs/guia_geracao_exemplos.md` | 69 | `OPENAI_API_KEY` |
| `phishforge-api/migrate/flyway.config` | 3 | `flyway.password` |
| `phishing-quest-api/PLANO_EXECUCAO.md` | 23 | `DB_PASSWORD` |
| `phishing-quest-api/PLANO_EXECUCAO.md` | 27 | `JWT_SECRET` |
| `phishing-quest-api/migrate/flyway-prod.config` | 12 | `flyway.password` |
| `phishing-quest-api/migrate/flyway.config` | 3 | `flyway.password` |

O resto do texto fica intacto: `flyway.locations` e `flyway.url` continuam no grafo, que é o que responde a pergunta t12.

## Limitações conhecidas

1. **Valor em prosa, sem chave ao lado, passa.** O padrão de `API_KEY` aparece escrito como literal em `phishforge-api/README.md:36` e em `phishforge-api/docs/guia_geracao_exemplos.md:153` ("preencha o campo `x-api-key` com ..."), e esses dois textos agora são indexados. As saídas candidatas são montar a lista de valores a mascarar a partir dos padrões que o compose e os `.env.example` declaram, ou revisar a saída na Fase 4. Nos quatro repos o valor em questão é um padrão de desenvolvimento documentado de propósito, e nenhuma pergunta de ouro depende dele.
2. **Credencial igual ao nome do projeto não dá para apagar do texto.** A senha de desenvolvimento do `flyway.config` da phishforge-api é a palavra `phishforge`, que também é o nome do banco, do usuário e do host. A máscara age na atribuição (`flyway.password=<redacted>`); apagar a palavra do texto todo destruiria o documento. O teste de integração confere a linha da senha, não o arquivo inteiro.
3. **A máscara ainda não roda na saída do MCP**, que só existe na Fase 4.

## Dados pessoais

- O export do console do pesquisador (com PII opcional) é gerado em tempo de execução e não está nos repos; o engrama não o lê.
- O engrama não se conecta aos bancos das APIs. O que ele sabe sobre os dados vem das migrations e do código.
