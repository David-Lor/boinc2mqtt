import asyncio
import datetime
import lufah
from .common import InputService
from .settings import FaHHost
from .output_mqtt import MqttPublisher
from .models import WorkUnit, FaHResponseWorkUnit


class FoldingAtHomeV8(InputService):
    def __init__(self, host: FaHHost, publisher: MqttPublisher):
        super().__init__(host)
        self.host = host
        self.publisher = publisher
        self.client = lufah.FahClient(f"{host.host}:{host.port}")
        self._login_id = None

    async def setup(self):
        await self.client.connect()
        print("Connected", self.host.model_dump())

    async def loop(self):
        if not self.client.is_connected:
            await self.client.connect()
            # errores de conexión (ej. host apagado):
            # 192.168.0.11:7396:Failed to connect to ws://192.168.0.11:7396/api/websocket
            # no salta excepción
            return

        try:
            data = self.client.data
        except Exception as ex:
            print("Scrape error", self.host.get_host_name(), ex, ex.__class__.__name__)

        try:
            await asyncio.gather(*[self._publish(wu) for wu in self._parse_data(data)])
        except Exception as ex:
            print("Publish error", self.host.get_host_name(), ex, ex.__class__.__name__)

    async def _publish(self, work_unit: WorkUnit):
        await self.publisher.publish(work_unit.model_dump_json())

    def _parse_data(self, data: dict):
        for unit in data.get("units", []):
            fah_workunit = FaHResponseWorkUnit.model_validate(unit, strict=False)
            now = datetime.datetime.now(tz=datetime.timezone.utc)
            total_seconds = int((now - fah_workunit.wu.time).total_seconds())

            yield WorkUnit(
                host=self.host.get_host_name(),
                project="foldingathome",
                name=str(fah_workunit.assignment.project),
                percentage=fah_workunit.wu_progress * 100,
                running=not bool(fah_workunit.pause_reason),
                start_timestamp=fah_workunit.wu.time,
                total_time_seconds=total_seconds,
                run_seconds=None,  # TODO Revisar
                remaining_seconds=int(fah_workunit.eta.total_seconds()),
                timeout_seconds=fah_workunit.assignment.timeout - total_seconds,
                expire_seconds=fah_workunit.assignment.deadline - total_seconds,
                cpu_count=fah_workunit.cpus,
                gpu_count=len(fah_workunit.gpus),
            )
