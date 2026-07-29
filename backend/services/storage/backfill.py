"""Backfill: legacy tasks → knowledge layer (ADR-0007).

Pure orchestration: all identity generation, chunk construction, enrichment
mapping, cascade behavior, logging, and idempotency live in
KnowledgeIngestService — this module only enumerates tasks, applies
eligibility rules, and invokes the same methods the live pipeline calls.
It is also the permanent repair path for shadow-write failures: any
completed task with document_id IS NULL is (re)attempted on every run.

Usage from the project root:

    python -m backend.services.storage.backfill [--dry-run]
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field

from ..knowledge_ingest_service import KnowledgeIngestService, _LOG_PATH
from .base import TaskStore


@dataclass
class BackfillReport:
    dry_run: bool = False
    scanned: int = 0
    already_linked: int = 0
    imported: int = 0
    repaired: int = 0
    skipped_failed_status: int = 0
    skipped_no_segments: int = 0
    failed: int = 0
    elapsed_seconds: float = 0.0
    decisions: list[str] = field(default_factory=list)

    def render(self) -> str:
        mode = " (dry-run)" if self.dry_run else ""
        lines = [f"Backfill report{mode}:"]
        lines += [f"  {d}" for d in self.decisions]
        lines += [
            "-" * 40,
            f"  scanned:               {self.scanned}",
            f"  already linked:        {self.already_linked}",
            f"  imported:              {self.imported}",
            f"  repaired:              {self.repaired}",
            f"  skipped (not done):    {self.skipped_failed_status}",
            f"  skipped (no segments): {self.skipped_no_segments}",
            f"  failed:                {self.failed}",
            f"  elapsed:               {self.elapsed_seconds:.2f}s",
        ]
        return "\n".join(lines)


def _failed_task_ids_from_log() -> set[str]:
    """Task ids with a prior FAILURE entry in the shadow log (repair detection)."""
    failed: set[str] = set()
    try:
        if _LOG_PATH.exists():
            for line in _LOG_PATH.read_text(encoding="utf-8").splitlines():
                if "FAILURE task=" in line:
                    failed.add(line.split("FAILURE task=", 1)[1].split()[0])
    except Exception as exc:
        print(f"⚠️ Could not read shadow log for repair detection: {exc}")
    return failed


def backfill_tasks(
    task_store: TaskStore,
    ingest: KnowledgeIngestService,
    *,
    dry_run: bool = False,
) -> BackfillReport:
    """Enumerate tasks and shadow-write the eligible ones via *ingest*.

    Per-document transaction boundaries are guaranteed by the stores; the
    per-task try/except here ensures one bad record cannot abort the run.
    """
    report = BackfillReport(dry_run=dry_run)
    started = time.perf_counter()
    previously_failed = _failed_task_ids_from_log()

    for task_id in task_store.list_ids():
        report.scanned += 1
        try:
            task = task_store.load(task_id)
            if task is None:
                report.failed += 1
                report.decisions.append(f"task={task_id} → failed (unreadable record)")
                continue

            if task.document_id:
                report.already_linked += 1
                report.decisions.append(f"task={task_id} → skipped (already linked)")
                continue
            if task.status != "completed":
                report.skipped_failed_status += 1
                report.decisions.append(f"task={task_id} → skipped (status={task.status})")
                continue
            if not task.transcript_segments:
                report.skipped_no_segments += 1
                report.decisions.append(f"task={task_id} → skipped (no segments)")
                continue

            if dry_run:
                report.imported += 1  # would be imported
                report.decisions.append(f"task={task_id} → would import")
                continue

            document_id = ingest.shadow_write_task(
                task, content_hash=None, origin_filename=None
            )
            if not document_id:
                report.failed += 1
                report.decisions.append(f"task={task_id} → failed (shadow write)")
                continue

            task.document_id = document_id
            task_store.save(task)
            if task.translation_results:
                ingest.shadow_write_translations(task)

            report.imported += 1
            if task_id in previously_failed:
                report.repaired += 1
                report.decisions.append(f"task={task_id} → repaired")
            else:
                report.decisions.append(f"task={task_id} → imported")
        except Exception as exc:
            # Belt-and-braces: the service never raises, but a corrupt
            # record or store hiccup must not abort the whole run.
            report.failed += 1
            report.decisions.append(f"task={task_id} → failed ({exc!r})")

    report.elapsed_seconds = round(time.perf_counter() - started, 2)
    return report


def main() -> int:
    from ..task_manager import _default_store
    from . import default_document_store, default_knowledge_store

    dry_run = "--dry-run" in sys.argv[1:]
    ingest = KnowledgeIngestService(default_document_store(), default_knowledge_store())
    report = backfill_tasks(_default_store(), ingest, dry_run=dry_run)
    print(report.render())
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
