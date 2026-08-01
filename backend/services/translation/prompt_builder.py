from __future__ import annotations

from typing import Any


class TranslationPromptBuilder:
    """Строит промпт перевода для одного батча.

    Отдельный класс, чтобы позже добавлять режимы (literal, technical,
    learning, simplified) без изменения остального кода.
    """

    def build(
        self,
        batch: list[dict[str, Any]],
        source_language: str | None,
        target_language: str,
        batch_index: int,
        batch_total: int,
    ) -> str:
        blocks = []
        for i, seg in enumerate(batch):
            text = str(seg.get("text", "")).strip()
            blocks.append(f"<<<SEG_{i}>>>\n{text}\n<<<END>>>")

        language_note = (
            f"Source language is likely {source_language}."
            if source_language
            else "Detect source language from text."
        )

        return f"""Translate the following transcript segments into {target_language}.

Batch: {batch_index}/{batch_total}
{language_note}

Rules:
- Each segment is wrapped as <<<SEG_N>>> ... <<<END>>>.
- Preserve every <<<SEG_N>>> marker and its <<<END>>> terminator exactly as written.
- Translate only the text between a marker and its terminator.
- Do not add, remove, or renumber segments.
- Do not include markdown wrappers, explanations, or JSON.
- Return only the translated segments in the same wrapped format.

Input:
{chr(10).join(blocks)}

Output:"""
