"""Тесты устойчивости перевода: retry батча, failover на резервный
профиль и догрузка частичного кэша (без реальных API-ключей)."""
import re
import sys
import uuid
from types import SimpleNamespace

sys.path.insert(0, ".")

from backend.services.transcript_enrichment_service import TranscriptEnrichmentService
from backend.services.translation.retry import AdaptivePacer
from backend.services.ai_provider import (
    AIProviderConfigurationError,
    DummyAIProvider,
    resolve_ai_profile,
)
import backend.routes.video as video_routes

failures = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


def make_service(provider, max_chars=10_000):
    service = TranscriptEnrichmentService(provider, max_chars=max_chars)
    service.pacer = AdaptivePacer(sleep=lambda s: None)
    service._sleep = lambda s: None
    return service


class MarkerProvider(DummyAIProvider):
    """«Переводит» любой батч: отвечает маркерами по числу <<<SEG_N>>> в промпте."""

    def __init__(self, prefix="ПЕРЕВОД"):
        self.calls = 0
        self.prompts = []
        self.prefix = prefix

    def generate_text(self, prompt, max_tokens=None):
        self.calls += 1
        self.prompts.append(prompt)
        # В правилах промпта маркер только <<<SEG_N>>> (буква), сегменты — с цифрами
        n = len(re.findall(r"<<<SEG_\d+>>>", prompt))
        return "".join(
            f"<<<SEG_{i}>>>\n{self.prefix}{i}\n<<<END>>>\n" for i in range(n)
        )


# (а) Retry: батч падает 2 раза, потом успех — failed нет
class FlakyProvider(DummyAIProvider):
    def __init__(self):
        self.calls = 0

    def generate_text(self, prompt, max_tokens=None):
        self.calls += 1
        if self.calls <= 2:
            raise RuntimeError("429 RESOURCE_EXHAUSTED quota")
        return "<<<SEG_0>>>\nОК0\n<<<END>>>\n<<<SEG_1>>>\nОК1\n<<<END>>>"


sleeps = []
flaky = FlakyProvider()
service = make_service(flaky)
service._sleep = sleeps.append
segments = [{"text": f"text{i}", "start": i} for i in range(2)]
out = service.enrich_segments(segments, source_language="English")
check("retry: all ready after 2 failures",
      all(s["enrichment"]["translation_status"] == "ready" for s in out))
check("retry: 3 provider calls", flaky.calls == 3)
check("retry: exponential backoff 5s/15s", sleeps == [5.0, 15.0])

# (б) Failover: основной профиль всегда падает, резервный переводит
class AlwaysFailProvider(DummyAIProvider):
    def __init__(self):
        self.calls = 0

    def generate_text(self, prompt, max_tokens=None):
        self.calls += 1
        raise RuntimeError("429 RESOURCE_EXHAUSTED quota")


broken = AlwaysFailProvider()
service2 = make_service(broken)
out2 = service2.enrich_segments(
    [{"text": f"text{i}", "start": i} for i in range(2)], source_language="English"
)
check("failover: primary leaves all failed",
      all(s["enrichment"]["translation_status"] == "failed" for s in out2))
check("failover: primary retried before giving up", broken.calls == 4)

gemini_profile = resolve_ai_profile("gemini_flash")
backup = MarkerProvider(prefix="РЕЗЕРВ")
real_get_ai_provider = video_routes.get_ai_provider
try:
    video_routes.get_ai_provider = lambda pid: (resolve_ai_profile(pid), backup)
    recovered = video_routes._retry_failed_segments_with_failover(
        out2, gemini_profile, "English", "Russian"
    )
finally:
    video_routes.get_ai_provider = real_get_ai_provider
check("failover: all ready via backup profile",
      all(s["enrichment"]["translation_status"] == "ready" for s in recovered))
check("failover: backup translated only failed subset", backup.calls == 1)
check("failover: translations applied",
      [s["enrichment"]["translation"] for s in recovered] == ["РЕЗЕРВ0", "РЕЗЕРВ1"])

# Failover молча пропускается, если резервный профиль недоступен (нет ключа)
still_failed = make_service(AlwaysFailProvider()).enrich_segments(
    [{"text": f"text{i}", "start": i} for i in range(2)], source_language="English"
)
try:
    def raise_config(pid):
        raise AIProviderConfigurationError("OPENROUTER_API_KEY is empty")

    video_routes.get_ai_provider = raise_config
    skipped = video_routes._retry_failed_segments_with_failover(
        still_failed, gemini_profile, "English", "Russian"
    )
finally:
    video_routes.get_ai_provider = real_get_ai_provider
check("failover: missing backup key -> silent skip",
      all(s["enrichment"]["translation_status"] == "failed" for s in skipped))

# (в) Частичный кэш: повторный запрос до-переводит только неготовые сегменты
task_id = str(uuid.uuid4())
counting = MarkerProvider(prefix="НОВЫЙ")
cached_segments = [
    {
        "start": 0.0, "end": 1.0, "text": "text0",
        "enrichment": {"translation": "УЖЕ0", "translation_status": "ready"},
    },
    {
        "start": 1.0, "end": 2.0, "text": "text1",
        "enrichment": {"translation": None, "translation_status": "failed"},
    },
    {
        "start": 2.0, "end": 3.0, "text": "text2",
        "enrichment": {"translation": "УЖЕ2", "translation_status": "ready"},
    },
]
task = SimpleNamespace(
    id=task_id,
    status="completed",
    transcript_segments=[
        {"start": 0.0, "end": 1.0, "text": "text0"},
        {"start": 1.0, "end": 2.0, "text": "text1"},
        {"start": 2.0, "end": 3.0, "text": "text2"},
    ],
    transcript_language="en",
    language="en",
    ai_profile_id="gemini_flash",
    translation_results={
        "gemini_flash:russian": {
            "target_language": "Russian",
            "ai_profile_id": "gemini_flash",
            "transcript_segments": cached_segments,
        }
    },
)
updates = []
fake_task_manager = SimpleNamespace(
    get=lambda tid: task if tid == task_id else None,
    update=lambda tid, **kw: updates.append(kw),
)

real_task_manager = video_routes.task_manager
try:
    video_routes.task_manager = fake_task_manager
    video_routes.get_ai_provider = lambda pid: (resolve_ai_profile(pid), counting)
    req = video_routes.TranslateTranscriptRequest(target_language="ru")
    response = video_routes.translate_task_transcript(task_id, req)
finally:
    video_routes.task_manager = real_task_manager
    video_routes.get_ai_provider = real_get_ai_provider

translations = [s.enrichment.translation for s in response.transcript_segments]
statuses = [s.enrichment.translation_status for s in response.transcript_segments]
check("partial cache: all ready after reload", statuses == ["ready"] * 3)
check("partial cache: ready segments untouched",
      translations[0] == "УЖЕ0" and translations[2] == "УЖЕ2")
check("partial cache: failed segment translated", translations[1] == "НОВЫЙ0")
check("partial cache: only one AI call for the pending segment", counting.calls == 1)
check("partial cache: prompt contained only the pending text",
      "text1" in counting.prompts[0]
      and "text0" not in counting.prompts[0]
      and "text2" not in counting.prompts[0])
check("partial cache: merged result stored",
      bool(updates)
      and all(
          s["enrichment"]["translation_status"] == "ready"
          for s in updates[0]["translation_results"]["gemini_flash:russian"]["transcript_segments"]
      ))

print()
if failures:
    print("FAILED:", failures)
    sys.exit(1)
print("ALL OK")
