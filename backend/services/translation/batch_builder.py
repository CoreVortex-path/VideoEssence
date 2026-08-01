from __future__ import annotations

from typing import Any


class BatchBuilder:
    """Делит сегменты на батчи по суммарной длине текста (max_chars).

    Ничего не знает про AI — работает только с текстом. Размер батча
    предсказуем и для длинных, и для коротких видео, в отличие от
    фиксированного количества сегментов.
    """

    # Примерный вес маркеров <<<SEG_N>>> / <<<END>>> на один сегмент.
    MARKER_OVERHEAD = 25

    def __init__(self, max_chars: int = 4500) -> None:
        self.max_chars = max(1, max_chars)

    def build(self, segments: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        batches: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        current_chars = 0

        for seg in segments:
            text_len = len(str(seg.get("text", "")).strip())
            weight = text_len + self.MARKER_OVERHEAD
            if current and current_chars + weight > self.max_chars:
                batches.append(current)
                current = []
                current_chars = 0
            current.append(seg)
            current_chars += weight

        if current:
            batches.append(current)
        return batches
