import asyncio
from .common import InputService
from .input_boinc import Boinc
from .input_fah import FoldingAtHomeV8
from .output_mqtt import MqttPublisher
from .settings import load_settings


async def amain():
    settings = load_settings()
    input_services: list[InputService] = []

    publisher = MqttPublisher(settings.mqtt)

    for host in settings.foldingathome.hosts:
        fah_service = FoldingAtHomeV8(host, publisher)
        input_services.append(fah_service)

    for host in settings.boinc.hosts:
        boinc_service = Boinc(host, publisher)
        input_services.append(boinc_service)

    all_services = [*input_services, publisher]
    await asyncio.gather(*[service.setup() for service in all_services])
    # TODO conectar servicios de input en background, no necesitan estar up todos a la vez.

    # Run all input services concurrently
    try:
        await asyncio.gather(*[service.run() for service in input_services])

    except (InterruptedError, KeyboardInterrupt, asyncio.CancelledError):
        pass

    print("Shutting down...")
    await asyncio.gather(*[service.teardown() for service in all_services])


def main():
    asyncio.run(amain())
