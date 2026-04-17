import abc
import asyncio
import logging

logger = logging.getLogger(__name__)


class AbstractTask(abc.ABC):
    task: asyncio.Task
    running: bool = False

    def start(self):
        if not self.running:
            self.running = True
            self.task = asyncio.create_task(self._run())

    async def wait(self):
        if self.running:
            await self.task

    async def _run(self):
        while self.running:
            try:
                await self.run_once()
            except Exception:
                logger.exception("Unhandled error in %s", self.__class__.__name__)
                await asyncio.sleep(30)

    @abc.abstractmethod
    async def run_once(self):
        pass

    async def close(self):
        if self.running:
            self.running = False
            await self.task
