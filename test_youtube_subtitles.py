"""Sanity-тест fast-path субтитров YouTube: VTT-парсер и выбор дорожки."""
import sys
sys.path.insert(0, ".")

from backend.services.input_sources.youtube_subtitles import parse_vtt, _pick_track

failures = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


# 1. Ручные субтитры: обычный VTT без дедупликации
manual_vtt = """WEBVTT
Kind: captions
Language: en

00:00:01.000 --> 00:00:04.000
Hello there

00:00:04.000 --> 00:00:07.500
this is a test
of manual subtitles

00:00:07.500 --> 00:00:09.000
Да.
"""
segs = parse_vtt(manual_vtt, dedupe=False)
check("manual: 3 segments", len(segs) == 3)
check("manual: timestamps", (segs[0]["start"], segs[0]["end"]) == (1.0, 4.0))
check("manual: multiline text", segs[1]["text"] == "this is a test\nof manual subtitles")
check("manual: repeated line kept (no dedupe)", segs[2]["text"] == "Да.")

# 2. Автосубтитры: накатывающееся окно + inline-теги
auto_vtt = """WEBVTT
Kind: captions
Language: ru

00:00:00.000 --> 00:00:01.840 align:start position:0%
и вот мы<00:00:00.560><c> снова</c>

00:00:01.840 --> 00:00:03.840 align:start position:0%
и вот мы снова
встретились сегодня

00:00:03.840 --> 00:00:05.500 align:start position:0%
встретились сегодня
чтобы поговорить
"""
segs = parse_vtt(auto_vtt, dedupe=True)
check("auto: 3 segments", len(segs) == 3)
check("auto: tags stripped", segs[0]["text"] == "и вот мы снова")
check("auto: rolling duplicate removed", segs[1]["text"] == "встретились сегодня")
check("auto: second step", segs[2]["text"] == "чтобы поговорить")

full_text = "\n".join(s["text"] for s in segs)
check("auto: no duplicated lines in full text",
      full_text == "и вот мы снова\nвстретились сегодня\nчтобы поговорить")

# 3. Выбор дорожки
manual_caps = {"en": [{"ext": "vtt"}], "ru": [{"ext": "vtt"}]}
check("pick manual: preferred lang wins", _pick_track(manual_caps, "ru", True) == "ru")
check("pick manual: first track without preference", _pick_track(manual_caps, None, True) == "en")

auto_caps = {"af": [{"ext": "vtt"}], "en": [{"ext": "vtt"}], "ru": [{"ext": "json3"}], "de": [{"ext": "vtt"}]}
check("pick auto: skips non-vtt preferred lang", _pick_track(auto_caps, "ru", False) == "en")
check("pick auto: preferred lang with region", _pick_track({"en-US": [{"ext": "vtt"}]}, "en", False) == "en-US")
check("pick: empty -> None", _pick_track({}, "en", False) is None)
check("pick: no vtt -> None", _pick_track({"ru": [{"ext": "srv3"}]}, None, True) is None)

# 4. Импорты изменённых модулей
import backend.services.input_sources.youtube_source  # noqa: F401
import backend.routes.video  # noqa: F401
check("imports OK", True)

print()
if failures:
    print("FAILED:", failures)
    sys.exit(1)
print("ALL OK")
