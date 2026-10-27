# Segredos e dados sensíveis

O engrama lê código e documentação, nunca bancos de dados, e nunca devolve uma credencial numa resposta. Isso é garantido em duas camadas: um filtro na ingestão (`SecretScanner`, implementado em `RegexSecretScanner`) e um sanitizador em toda saída do MCP (fase 4). As credenciais da tabela abaixo são casos de teste do filtro (`tests/unit/infrastructure/test_secret_scanner.py`), com valores falsos.

## Regras da ingestão

1. **Arquivos nunca lidos:** `.env` e `.env.*` (exceto `.env.example`), `*.pem`, `*.key`, `*.p12`, `id_rsa*`, binários (`.exe`, `.so`, `.dll`, `.jar`), imagens, PDFs, `*.snapshot`, `node_modules/`, `build/`, `dist/` e relatórios brutos de experimento (`*_YYYYMMDD_HHMMSS.json`). Desses, só o caminho entra no grafo, nunca o conteúdo.
2. **Valores mascarados, chaves mantidas:** em YAML, `.env.example`, compose, workflows de CI e blocos de código em Markdown, o valor de toda chave que case com `PASSWORD|PASSWD|SECRET|TOKEN|API_KEY|PRIVATE_KEY|CREDENTIAL` vira `<redacted>`. A chave continua no grafo, porque saber que existe `JWT_SECRET` é conhecimento útil; o valor não.
3. **Strings de conexão:** `password=...` dentro de strings de conexão e `usuario:senha@host` em URLs são mascarados.
4. **Literais no código:** um literal atribuído a uma variável cujo nome contém `secret`, `password`, `token` ou `key` é mascarado (é o caso do padrão de desenvolvimento do JWT na Quest API).
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
| `phishing-quest-api/.github/workflows/workflow_pr_ci.yml` | 90, 103, 106, 129 | `POSTGRES_PASSWORD`, `DB_PASSWORD`, `JWT_SECRET`, `-password=` |
| `phishforge-api/docker-compose.yml` | 9, 120, 195 | `POSTGRES_PASSWORD`, `DB_PASSWORD`, `PGPASSWORD` |

Arquivos excluídos por tipo nos mesmos commits: 14 PDFs (artigos da base do RAG em `phishforge-api/data/articles/`), 21 imagens, 1 snapshot do Qdrant e 1 executável (`phishing-quest-api/phishing-quest.exe`).

## Dados pessoais

- O export do console do pesquisador (com PII opcional) é gerado em tempo de execução e não está nos repos; o engrama não o lê.
- O engrama não se conecta aos bancos das APIs. O que ele sabe sobre os dados vem das migrations e do código.
