"""Sanity-тест переписанного пайплайна перевода (без реального AI)."""
import sys
sys.path.insert(0, ".")

from backend.services.transcript_enrichment_service import TranscriptEnrichmentService
from backend.services.translation.batch_builder import BatchBuilder
from backend.services.translation.parser import TranslationParser
from backend.services.translation.retry import AdaptivePacer
from backend.services.ai_provider import DummyAIProvider

failures = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


# 1. BatchBuilder: деление по max_chars, а не по количеству
segs = [{"text": "x" * 1000, "start": i} for i in range(10)]
batches = BatchBuilder(max_chars=4500).build(segs)
check("batch by chars: 3 batches", len(batches) == 3)
check("batch by chars: sizes 4/4/2", [len(b) for b in batches] == [4, 4, 2])
big = [{"text": "x" * 9000, "start": 0}, {"text": "y" * 10, "start": 1}]
check("oversized segment gets own batch", [len(b) for b in BatchBuilder(4500).build(big)] == [1, 1])

# 2. Parser: основной формат и фолбэк без <<<END>>>
p = TranslationParser()
raw = "<<<SEG_0>>>\nПривет\nмир\n<<<END>>>\n<<<SEG_2>>>\nПока\n<<<END>>>"
check("parser main format", p.parse(raw) == {0: "Привет\nмир", 2: "Пока"})
raw_fallback = "<<<SEG_0>>> Привет\n<<<SEG_1>>> Пока"
check("parser fallback without END", p.parse(raw_fallback) == {0: "Привет", 1: "Пока"})
check("parser garbage -> empty", p.parse("no markers here") == {})

# 3. Полный флоу: пропущенный сегмент доезжает repair-проходом
class FakeProvider(DummyAIProvider):
    def __init__(self):
        self.calls = 0

    def generate_text(self, prompt, max_tokens=None):
        self.calls += 1
        if self.calls == 1:
            # Первый батч: сегмент 1 «потерян»
            return "<<<SEG_0>>>\nПЕРЕВОД0\n<<<END>>>\n<<<SEG_2>>>\nПЕРЕВОД2\n<<<END>>>"
        # Repair-запрос
        assert "<<<SEG_0>>>" in prompt and "text1" in prompt
        return "<<<SEG_0>>>\nПЕРЕВОД1\n<<<END>>>"

service = TranscriptEnrichmentService(FakeProvider(), max_chars=10_000)
service.pacer = AdaptivePacer(sleep=lambda s: None)
segments = [{"text": f"text{i}", "start": i} for i in range(3)]
out1 = out = service.enrich_segments(segments, source_language="English")
check("repair: all ready", all(s["enrichment"]["translation_status"] == "ready" for s in out))
check("repair: translations applied", [s["enrichment"]["translation"] for s in out] == ["ПЕРЕВОД0", "ПЕРЕВОД1", "ПЕРЕВОД2"])
check("repair: 2 AI calls total", service.ai_provider.calls == 2)

# 4. Квотная ошибка: батч failed, pacer ускоряет паузу, остальные живы
class QuotaProvider(DummyAIProvider):
    def __init__(self):
        self.calls = 0

    def generate_text(self, prompt, max_tokens=None):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("429 RESOURCE_EXHAUSTED quota")
        return "<<<SEG_0>>>\nОК\n<<<END>>>"

service2 = TranscriptEnrichmentService(QuotaProvider(), max_chars=30)
service2.pacer = AdaptivePacer(sleep=lambda s: None)
segments = [{"text": f"text{i}", "start": i} for i in range(4)]
out = service2.enrich_segments(segments, source_language="English")
statuses = [s["enrichment"]["translation_status"] for s in out]
check("quota: first batch failed, rest ready", statuses == ["failed", "ready", "ready", "ready"])
pacer_check = AdaptivePacer(sleep=lambda s: None)
pacer_check.on_rate_limit()
check("pacer: delay grows on rate limit", pacer_check.delay == 4.0)
pacer_check.on_success()
check("pacer: delay decays on success", pacer_check.delay == 2.0)

# 5. Сегмент, который не вернулся даже после repair -> failed
class StubbornProvider(DummyAIProvider):
    def __init__(self):
        self.calls = 0

    def generate_text(self, prompt, max_tokens=None):
        self.calls += 1
        if self.calls == 1:
            # Первый батч: сегмент 1 «потерян»
            return "<<<SEG_0>>>\nОК\n<<<END>>>"
        # Repair-запросы: модель упорно не возвращает маркеры
        return "no markers here"

service3 = TranscriptEnrichmentService(StubbornProvider(), max_chars=10_000)
service3.pacer = AdaptivePacer(sleep=lambda s: None)
out3 = service3.enrich_segments([{"text": "a", "start": 0}, {"text": "b", "start": 1}])
check("stubborn missing -> failed after repair",
      [s["enrichment"]["translation_status"] for s in out3] == ["ready", "failed"])

# 6. build_full_translation
full = service.build_full_translation(out1)
check("full translation join", full == "ПЕРЕВОД0\n\nПЕРЕВОД1\n\nПЕРЕВОД2")

# 7. Импорт роута (синтаксис/совместимость после правки кэша)
import backend.routes.video  # noqa: F401
check("routes.video imports", True)

print()
if failures:
    print("FAILED:", failures)
    sys.exit(1)
print("ALL OK")
