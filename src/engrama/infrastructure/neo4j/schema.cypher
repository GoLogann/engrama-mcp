// Unicidade da chave natural de cada familia de no (formatos em docs/ontologia.md).
CREATE CONSTRAINT project_key IF NOT EXISTS FOR (n:Project) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT repo_key IF NOT EXISTS FOR (n:Repo) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT module_key IF NOT EXISTS FOR (n:Module) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT endpoint_key IF NOT EXISTS FOR (n:Endpoint) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT datastore_key IF NOT EXISTS FOR (n:DataStore) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT concept_key IF NOT EXISTS FOR (n:Concept) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT doc_key IF NOT EXISTS FOR (n:Doc) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT decision_key IF NOT EXISTS FOR (n:Decision) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT chunk_key IF NOT EXISTS FOR (n:Chunk) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT issue_key IF NOT EXISTS FOR (n:Issue) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT episode_key IF NOT EXISTS FOR (n:Episode) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT person_key IF NOT EXISTS FOR (n:Person) REQUIRE n.key IS UNIQUE;

// Consultas por vigencia: "o que vale hoje" filtra por valid_to nulo.
CREATE INDEX episode_valid_to IF NOT EXISTS FOR (n:Episode) ON (n.valid_to);

// Busca por texto na camada de documentacao. O analisador portugues reduz a
// palavra ao radical ("tecnologias" acha "tecnologia"), que e a lingua dos
// documentos dos quatro repos. Trocar de analisador exige apagar o indice:
// com IF NOT EXISTS, o que ja existe fica como esta.
CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS FOR (n:Chunk) ON EACH [n.text, n.heading]
OPTIONS {indexConfig: {`fulltext.analyzer`: 'portuguese'}};

// Metade vetorial da busca hibrida. O tamanho esta fixo aqui porque o indice
// nasce com ele: trocar o modelo de embedding para outro tamanho exige apagar
// e recriar o indice, e o `VoyageEmbedder` recusa gravar vetor de tamanho
// diferente justamente para isso nao passar em silencio. Cosseno porque os
// vetores da Voyage ja vem normalizados.
CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS FOR (n:Chunk) ON n.embedding
OPTIONS {indexConfig: {`vector.dimensions`: 1024, `vector.similarity_function`: 'cosine'}};
