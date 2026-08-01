from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

import yt_dlp

"""Fast-path: готовые субтитры YouTube вместо локальной транскрипции.

Сначала пробуем ручные субтитры, затем автогенерацию. Результат —
сегменты с таймкодами в том же формате, что отдаёт Whisper, поэтому
дальнейший пайплайн (саммари, чаптеры, перевод) не меняется.
"""

_SUBTITLE_EXTS = {".vtt", ".srt", ".json3", ".srv1", ".srv2", ".srv3", ".ttml"}

_TIMING = re.compile(
    r"((?:\d+:)?\d{1,2}:\d{2}[.,]\d{3})\s*-->\s*((?:\d+:)?\d{1,2}:\d{2}[.,]\d{3})"
)
_TAG = re.compile(r"<[^>]+>")


def fetch_youtube_subtitles(
    youtube_url: str, task_id: str, output_dir: Path
) -> dict[str, Any] | None:
    """Скачать готовые субтитры YouTube без загрузки аудио.

    Возвращает {"segments": [...], "language": str, "kind": "manual"|"auto"}
    или None, если субтитров нет или что-то пошло не так (тогда вызывающий
    код уходит в обычный путь: скачивание аудио + Whisper).
    """
    cookies_path = Path(__file__).parent.parent.parent.parent / "cookies.txt"
    base_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "cookiefile": str(cookies_path) if cookies_path.exists() else None,
    }

    try:
        with yt_dlp.YoutubeDL(base_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
    except Exception as exc:
        print(f"[subtitles] metadata fetch failed: {exc}")
        return None

    preferred_lang = (info.get("language") or "").strip() or None

    lang = _pick_track(info.get("subtitles") or {}, preferred_lang, prefer_original=True)
    kind = "manual"
    if not lang:
        lang = _pick_track(info.get("automatic_captions") or {}, preferred_lang, prefer_original=False)
        kind = "auto"
    if not lang:
        return None

    dl_opts = dict(base_opts)
    dl_opts.update(
        {
            "writesubtitles": kind == "manual",
            "writeautomaticsub": kind == "auto",
            "subtitleslangs": [lang],
            "subtitlesformat": "vtt",
            "outtmpl": str(Path(output_dir) / f"{task_id}.%(ext)s"),
        }
    )
    try:
        with yt_dlp.YoutubeDL(dl_opts) as ydl:
            ydl.download([youtube_url])
    except Exception as exc:
        print(f"[subtitles] download failed ({kind}, {lang}): {exc}")
        return None

    vtt_path = _find_subtitle_file(Path(output_dir), task_id, lang)
    if not vtt_path:
        return None

    segments = parse_vtt(
        vtt_path.read_text(encoding="utf-8", errors="ignore"),
        dedupe=(kind == "auto"),
    )
    if not segments:
        return None

    return {"segments": segments, "language": lang, "kind": kind}


def _pick_track(
    captions: dict[str, list[dict[str, Any]]],
    preferred_lang: str | None,
    prefer_original: bool,
) -> str | None:
    """Выбрать язык дорожки субтитров, для которой есть vtt-формат."""
    langs = [
        lang
        for lang, fmts in captions.items()
        if any(f.get("ext") == "vtt" for f in fmts)
    ]
    if not langs:
        return None
    if preferred_lang:
        for lang in langs:
            if lang == preferred_lang or lang.startswith(preferred_lang + "-"):
                return lang
    if prefer_original:
        # Ручные субтитры: берём первую дорожку (обычно язык оригинала).
        return langs[0]
    # Автогенерация: список забит языками переводов, без метаданных
    # разумнее взять en, чем первый по алфавиту.
    if "en" in langs:
        return "en"
    return langs[0]


def _find_subtitle_file(output_dir: Path, task_id: str, lang: str) -> Path | None:
    exact = output_dir / f"{task_id}.{lang}.vtt"
    if exact.exists():
        return exact
    for f in sorted(output_dir.iterdir()):
        if f.name.startswith(task_id) and f.suffix.lower() in _SUBTITLE_EXTS:
            return f
    return None


def _to_seconds(ts: str) -> float:
    parts = ts.replace(",", ".").split(":")
    seconds = float(parts[-1])
    minutes = int(parts[-2])
    hours = int(parts[-3]) if len(parts) > 2 else 0
    return hours * 3600 + minutes * 60 + seconds


def parse_vtt(content: str, dedupe: bool = False) -> list[dict[str, Any]]:
    """Разобрать VTT в сегменты [{start, end, text}].

    dedupe=True нужен для автосубтитров YouTube: они идут «накатывающимся»
    окном, где первая строка каждого cue повторяет последнюю строку
    предыдущего. Повторные строки отбрасываем, в сегмент попадает только
    новый текст.
    """
    segments: list[dict[str, Any]] = []
    emitted: list[str] = []

    for block in re.split(r"\r?\n[ \t]*\r?\n", content):
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        timing_match = None
        timing_idx = -1
        for i, line in enumerate(lines):
            timing_match = _TIMING.search(line)
            if timing_match:
                timing_idx = i
                break
        if timing_match is None:
            continue

        start = _to_seconds(timing_match.group(1))
        end = _to_seconds(timing_match.group(2))

        text_lines: list[str] = []
        for line in lines[timing_idx + 1:]:
            clean = html.unescape(_TAG.sub("", line)).strip()
            if clean:
                text_lines.append(clean)

        if dedupe:
            new_lines = []
            for line in text_lines:
                if not new_lines and emitted and line == emitted[-1]:
                    continue
                new_lines.append(line)
            text_lines = new_lines

        if not text_lines:
            continue

        emitted.extend(text_lines)
        segments.append(
            {
                "start": round(start, 3),
                "end": round(end, 3),
                "text": "\n".join(text_lines),
            }
        )

    return segments
