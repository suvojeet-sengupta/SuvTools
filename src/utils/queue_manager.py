import asyncio
from src.utils.logger import logger

class QueueManager:
    def __init__(self, max_concurrent: int):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.waiting_jobs = []
        self.active_jobs = set()
        self.lock = asyncio.Lock()
        logger.info(f"QueueManager initialized with max_concurrent={max_concurrent}")

    async def acquire_slot(self, job_id: str) -> int:
        """Adds a job to the waiting queue and returns its initial position (1-indexed)."""
        async with self.lock:
            if job_id not in self.waiting_jobs:
                self.waiting_jobs.append(job_id)
            pos = self.waiting_jobs.index(job_id) + 1
            logger.info(f"Job {job_id} queued at position {pos}")
            return pos

    async def start_job(self, job_id: str):
        """Blocks until a slot is acquired. Moves the job from waiting to active."""
        logger.info(f"Job {job_id} waiting to acquire execution slot...")
        await self.semaphore.acquire()
        async with self.lock:
            if job_id in self.waiting_jobs:
                self.waiting_jobs.remove(job_id)
            self.active_jobs.add(job_id)
            logger.info(f"Job {job_id} acquired slot and is now active.")

    async def release_slot(self, job_id: str):
        """Releases the slot. Removes the job from active or waiting lists."""
        async with self.lock:
            was_active = job_id in self.active_jobs
            if was_active:
                self.active_jobs.remove(job_id)
            if job_id in self.waiting_jobs:
                self.waiting_jobs.remove(job_id)

        if was_active:
            self.semaphore.release()
            logger.info(f"Job {job_id} released active slot.")
        else:
            logger.info(f"Job {job_id} removed from waitlist before starting.")

    async def get_position(self, job_id: str) -> int:
        """Returns the current position of a job in the waitlist. Returns 0 if active or not found."""
        async with self.lock:
            if job_id in self.waiting_jobs:
                return self.waiting_jobs.index(job_id) + 1
            return 0

# Global Queue Manager (configured in config or bot loader)
