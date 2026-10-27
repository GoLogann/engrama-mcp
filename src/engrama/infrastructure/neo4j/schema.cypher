// Unicidade da chave natural de cada familia de no (formatos em docs/ontologia.md).
// Indices vetoriais e de texto completo entram na fase 2, com a busca hibrida.
CREATE CONSTRAINT project_key IF NOT EXISTS FOR (n:Project) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT repo_key IF NOT EXISTS FOR (n:Repo) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT module_key IF NOT EXISTS FOR (n:Module) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT endpoint_key IF NOT EXISTS FOR (n:Endpoint) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT datastore_key IF NOT EXISTS FOR (n:DataStore) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT concept_key IF NOT EXISTS FOR (n:Concept) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT doc_key IF NOT EXISTS FOR (n:Doc) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT decision_key IF NOT EXISTS FOR (n:Decision) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT issue_key IF NOT EXISTS FOR (n:Issue) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT episode_key IF NOT EXISTS FOR (n:Episode) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT person_key IF NOT EXISTS FOR (n:Person) REQUIRE n.key IS UNIQUE;

// Consultas por vigencia: "o que vale hoje" filtra por valid_to nulo.
CREATE INDEX episode_valid_to IF NOT EXISTS FOR (n:Episode) ON (n.valid_to);
