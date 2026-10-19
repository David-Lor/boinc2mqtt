import abc
import asyncio
import contextlib

from .settings import BaseHost


class Service(abc.ABC):
    async def setup(self):
        pass

    async def teardown(self):
        pass


class InputService(Service):
    def __init__(self, settings: BaseHost):
        self._host_settings = settings
        self._stop_event = asyncio.Event()

    @abc.abstractmethod
    async def loop(self) -> bool:
        pass

    async def run(self):
        while not self._stop_event.is_set():
            try:
                ok = await self.loop()
            except Exception as ex:
                print("Error in loop", ex, ex.__class__.__name__)
                ok = False

            sleep_time = self._host_settings.scrape.get_delay_seconds()
            if not ok:
                sleep_time *= 2

            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._host_settings.scrape.get_delay_seconds()
                )

    async def teardown(self):
        self._stop_event.set()
