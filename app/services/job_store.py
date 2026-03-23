"""SQLite-backed job store — survives server restarts."""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from app.models.schemas import JobListing, JobStatus, WorkMode

_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "jobs.db"


def _ensure_dir():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _job_to_row(job: JobListing) -> tuple:
    return (
        job.id,
        job.title,
        job.company,
        job.company_size,
        job.company_funding_eur,
        job.company_sector,
        job.location,
        job.work_mode.value if job.work_mode else None,
        job.salary_min,
        job.salary_max,
        job.has_equity,
        job.description,
        job.url,
        job.source,
        job.posted_at.isoformat() if job.posted_at else None,
        job.discovered_at.isoformat(),
        job.status.value,
    )


def _row_to_job(row: sqlite3.Row) -> JobListing:
    return JobListing(
        id=row["id"],
        title=row["title"],
        company=row["company"],
        company_size=row["company_size"],
        company_funding_eur=row["company_funding_eur"],
        company_sector=row["company_sector"],
        location=row["location"],
        work_mode=WorkMode(row["work_mode"]) if row["work_mode"] else None,
        salary_min=row["salary_min"],
        salary_max=row["salary_max"],
        has_equity=bool(row["has_equity"]) if row["has_equity"] is not None else None,
        description=row["description"],
        url=row["url"],
        source=row["source"],
        posted_at=datetime.fromisoformat(row["posted_at"]) if row["posted_at"] else None,
        discovered_at=datetime.fromisoformat(row["discovered_at"]),
        status=JobStatus(row["status"]),
    )


class JobStore:
    def __init__(self, db_path: Path = _DB_PATH):
        _ensure_dir()
        self._db_path = db_path
        self._init_db()
        # Track which jobs were already in DB before this session
        self._pre_existing_urls: set[str] = self._load_existing_urls()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    company_size INTEGER,
                    company_funding_eur INTEGER,
                    company_sector TEXT,
                    location TEXT NOT NULL,
                    work_mode TEXT,
                    salary_min INTEGER,
                    salary_max INTEGER,
                    has_equity INTEGER,
                    description TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    source TEXT NOT NULL,
                    posted_at TEXT,
                    discovered_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'new'
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_url ON jobs(url)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")

    def _load_existing_urls(self) -> set[str]:
        with self._conn() as conn:
            rows = conn.execute("SELECT url FROM jobs").fetchall()
            return {row["url"] for row in rows}

    def add(self, job: JobListing) -> JobListing:
        if not job.id:
            job.id = str(uuid.uuid4())
        job.discovered_at = datetime.utcnow()
        with self._conn() as conn:
            try:
                conn.execute(
                    """INSERT INTO jobs (id, title, company, company_size,
                       company_funding_eur, company_sector, location, work_mode,
                       salary_min, salary_max, has_equity, description, url,
                       source, posted_at, discovered_at, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    _job_to_row(job),
                )
            except sqlite3.IntegrityError:
                pass  # duplicate URL
        return job

    def add_many(self, jobs: list[JobListing]) -> list[JobListing]:
        return [self.add(j) for j in jobs]

    def get(self, job_id: str) -> JobListing | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            return _row_to_job(row) if row else None

    def get_all(self, status: JobStatus | None = None) -> list[JobListing]:
        with self._conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE status = ? ORDER BY discovered_at DESC",
                    (status.value,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM jobs ORDER BY discovered_at DESC"
                ).fetchall()
            return [_row_to_job(r) for r in rows]

    def update_status(self, job_id: str, status: JobStatus) -> JobListing | None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE jobs SET status = ? WHERE id = ?", (status.value, job_id)
            )
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            return _row_to_job(row) if row else None

    def count(self, exclude_archived: bool = False) -> int:
        with self._conn() as conn:
            if exclude_archived:
                row = conn.execute(
                    "SELECT COUNT(*) as c FROM jobs WHERE status != 'archived'"
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) as c FROM jobs").fetchone()
            return row["c"]

    def exists_by_url(self, url: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM jobs WHERE url = ? LIMIT 1", (url,)
            ).fetchone()
            return row is not None

    def is_new_this_session(self, url: str) -> bool:
        """Check if a job was discovered in this session (not pre-existing)."""
        return url not in self._pre_existing_urls


job_store = JobStore()
