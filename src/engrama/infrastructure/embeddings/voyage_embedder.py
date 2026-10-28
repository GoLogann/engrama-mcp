import logging
import time
from collections.abc import Iterator, Sequence

import voyageai
import voyageai.error

from engrama.application.ports.knowledge import Embedder, EmbeddingUnavailable, Vector

logger = logging.getLogger(__name__)

# Modelo padrao: os documentos dos quatro repos sao em portugues, e a familia
# `voyage-4` e a que declara suporte multilingue. O tamanho do vetor vem do
# padrao do modelo; nao passo `output_dimension` porque a documentacao lista
# os tamanhos aceitos sem nomear o parametro, e chutar nome de campo e o tipo
# de erro que so aparece em producao.
DEFAULT_MODEL = "voyage-4-large"
DEFAULT_DIMENSIONS = 1024

# Limites por requisicao. O teto de caracteres existe por causa da conta sem
# forma de pagamento, que fica com 3 requisicoes e 10 mil tokens por minuto:
# ~28 mil caracteres dao ~7 mil tokens, que cabe numa requisicao do teto
# baixo. Conta com pagamento cadastrado tem limite padrao e nao sente isso.
_MAX_TEXTS = 64
_MAX_CHARS = 28_000

# Espera entre tentativas quando a conta bate no teto por minuto. Comeca acima
# de 20s de proposito: com 3 requisicoes por minuto, tentar de novo em 1s so
# gasta tentativa. O `max_retries` do cliente cobre falha de rede; isto cobre
# o limite de taxa, que precisa de espera na casa de dezenas de segundos.
_RATE_LIMIT_WAITS = (25.0, 45.0, 65.0, 90.0)


class VoyageEmbedder(Embedder):
    """Embeddings pela API da Voyage (hoje servida em `ai.mongodb.com`).

    O cliente escolhe o endereco pelo formato da chave: chave criada no Atlas
    vai para `ai.mongodb.com` e chave antiga da Voyage, para
    `api.voyageai.com`. Por isso nao fixo `base_url` aqui — fixar quebraria
    um dos dois casos.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        dimensions: int = DEFAULT_DIMENSIONS,
    ) -> None:
        if not api_key:
            raise ValueError("VOYAGE_API_KEY vazia: a busca vetorial precisa da chave")
        self._client = voyageai.Client(api_key=api_key)
        self._model = model
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        vectors: list[Vector] = []
        for batch in _batches(texts):
            vectors += self._embed(batch, input_type="document")
        return vectors

    def embed_query(self, text: str) -> Vector:
        return self._embed([text], input_type="query")[0]

    def _embed(self, texts: Sequence[str], *, input_type: str) -> list[Vector]:
        result = self._call(texts, input_type=input_type)
        vectors = [tuple(float(number) for number in row) for row in result.embeddings]
        for vector in vectors:
            if len(vector) != self._dimensions:
                raise ValueError(
                    f"{self._model} devolveu vetor de {len(vector)} numeros, e o indice "
                    f"vetorial foi criado com {self._dimensions}. Trocar o tamanho exige "
                    f"apagar e recriar o indice."
                )
        return vectors

    def _call(self, texts: Sequence[str], *, input_type: str):
        """Chama a API esperando quando a conta bate no teto por minuto.

        Espera em vez de desistir porque indexar e trabalho de lote: perder a
        rodada inteira por causa de um teto por minuto obrigaria a refazer o
        que ja foi embutido. Esgotadas as esperas, o erro do provedor e
        traduzido para `EmbeddingUnavailable`, que e o que a busca entende
        sem conhecer a Voyage.
        """
        for wait in (*_RATE_LIMIT_WAITS, None):
            try:
                return self._client.embed(list(texts), model=self._model, input_type=input_type)
            except voyageai.error.RateLimitError as error:
                if wait is None:
                    raise EmbeddingUnavailable(f"teto de taxa da Voyage: {error}") from error
                logger.warning("Teto de taxa da Voyage: esperando %.0fs para tentar de novo", wait)
                time.sleep(wait)
        raise AssertionError("inalcancavel: a ultima tentativa levanta ou devolve")


def _batches(texts: Sequence[str]) -> Iterator[Sequence[str]]:
    """Divide por quantidade e por tamanho, o que estourar primeiro."""
    batch: list[str] = []
    chars = 0
    for text in texts:
        if batch and (len(batch) >= _MAX_TEXTS or chars + len(text) > _MAX_CHARS):
            yield batch
            batch, chars = [], 0
        batch.append(text)
        chars += len(text)
    if batch:
        yield batch
