from __future__ import annotations

import re


class TranslationParser:
    """Извлекает переводы сегментов из сырого ответа модели.

    Основной путь опирается на пару <<<SEG_N>>> ... <<<END>>> — явный
    терминатор делает парсер устойчивым к прозе вокруг и к переводам,
    содержащим переносы строк. Фолбэк без <<<END>>> — на случай, если
    модель обрезала ответ или потеряла терминаторы.
    """

    _MARKED = re.compile(r"<<<SEG_(\d+)>>>(.*?)<<<END>>>", re.DOTALL)
    _FALLBACK = re.compile(r"<<<SEG_(\d+)>>>(.*?)(?=<<<SEG_\d+>>>|\Z)", re.DOTALL)

    def parse(self, raw: str) -> dict[int, str]:
        text = raw or ""
        matches = self._MARKED.findall(text) or self._FALLBACK.findall(text)

        translations: dict[int, str] = {}
        for idx_str, translation in matches:
            try:
                idx = int(idx_str)
            except (TypeError, ValueError):
                continue
            cleaned = translation.strip()
            if cleaned:
                translations[idx] = cleaned
        return translations
