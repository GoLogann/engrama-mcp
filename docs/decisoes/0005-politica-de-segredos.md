# ADR 0005 — Política de segredos: `RegexSecretScanner` e `.env.example`

- **Status:** aceita
- **Data:** 27/10/2026

## Contexto

O plano nomeava um `DetectSecretsScanner` e dizia que arquivos `.env*` nunca são ingeridos. Ao testar o detect-secrets linha a linha (`scan_line`), os detectores de entropia não aplicam limiar e marcam até `passwordController` e `text`. As credenciais reais dos 4 repos aparecem como `chave: valor`, `${VAR:-padrão}` e strings de conexão.

## Decisão

- `RegexSecretScanner` combina regras próprias (chave=valor, padrão de `${VAR:-x}`, `usuário:senha@host`, literais atribuídos a nomes sensíveis) com apenas os detectores de provedor do detect-secrets (AWS, GitHub, chave privada, JWT...).
- `.env` e `.env.*` nunca são lidos, **exceto** `.env.example`, que documenta quais variáveis existem. O valor de cada chave sensível dele é mascarado por `redact` quando o texto for indexado (Fase 2); até lá o arquivo só é liberado para leitura, e nenhum valor dele chega ao grafo.
- `read()` de uma árvore de fontes recusa o que a política exclui, não só `files()`.

## Alternativas consideradas

- Todos os detectores do detect-secrets: falsos positivos em nomes de variável, e o texto mascarado perderia o sentido.
- Excluir `.env.example`: perderíamos a lista de variáveis de ambiente de cada projeto, que é conhecimento útil.

## Consequências

- Um valor escrito em prosa, sem chave ao lado, passa pelo filtro (`docs/seguranca.md`, "Limitação conhecida"). A Fase 2, que indexa documentos, precisa fechar isso.
- `redact` ainda não é chamado em código de produção: hoje só entram no grafo caminhos, linhas e rotas. Ele é ligado na indexação de documentos (Fase 2) e na saída do MCP (Fase 4).
