"""In-memory job store. Will be replaced with a proper DB later."""

import uuid
from datetime import datetime

from app.models.schemas import JobListing, JobStatus


class JobStore:
    def __init__(self):
        self._jobs: dict[str, JobListing] = {}

    def add(self, job: JobListing) -> JobListing:
        if not job.id:
            job.id = str(uuid.uuid4())
        job.discovered_at = datetime.utcnow()
        self._jobs[job.id] = job
        return job

    def add_many(self, jobs: list[JobListing]) -> list[JobListing]:
        return [self.add(j) for j in jobs]

    def get(self, job_id: str) -> JobListing | None:
        return self._jobs.get(job_id)

    def get_all(self, status: JobStatus | None = None) -> list[JobListing]:
        jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        return sorted(jobs, key=lambda j: j.discovered_at, reverse=True)

    def update_status(self, job_id: str, status: JobStatus) -> JobListing | None:
        job = self._jobs.get(job_id)
        if job:
            job.status = status
        return job

    def count(self) -> int:
        return len(self._jobs)

    def exists_by_url(self, url: str) -> bool:
        return any(j.url == url for j in self._jobs.values())


job_store = JobStore()
