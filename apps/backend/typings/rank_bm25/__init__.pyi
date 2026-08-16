from collections.abc import Sequence

class BM25L:
    def __init__(
        self,
        corpus: Sequence[Sequence[str]],
        tokenizer: object | None = ...,
        k1: float = ...,
        b: float = ...,
        delta: float = ...,
    ) -> None: ...
    def get_scores(self, query: Sequence[str]) -> Sequence[float]: ...
