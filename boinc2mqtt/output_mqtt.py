import asyncio
import aiomqtt

from .common import Service
from .settings import MQTTSettings


class MqttPublisher(Service):
    def __init__(self, settings: MQTTSettings):
        self.settings = settings
        self.client = aiomqtt.Client(
            hostname=self.settings.host,
            port=self.settings.port,
            username=self.settings.username,
            password=self.settings.password.get_secret_value() if self.settings.password else None,
            **self.settings.extra_args,
        )
        self.client.pending_calls_threshold = 100
        self._reconnect_lock = asyncio.Lock()
        self._last_reconnect = None

    async def setup(self):
        await self.client.__aenter__()
        print("MQTT connected")

    async def teardown(self):
        await self.client.__aexit__(None, None, None)
        print("MQTT disconnected")

    async def reconnect(self):
        async with self._reconnect_lock:
            now = asyncio.get_event_loop().time()
            if self._last_reconnect is None or now - self._last_reconnect > 5:
                await self.teardown()
                await self.setup()
                self._last_reconnect = now

    async def publish(self, payload, _is_reconnect_retry=False):
        try:
            await self.client.publish(
                topic=self.settings.topic,
                payload=payload,
                qos=self.settings.qos,
                retain=self.settings.retain,
            )

        except aiomqtt.MqttError as e:
            if not _is_reconnect_retry and "The client is not currently connected" in str(e):
                await self.reconnect()
                await self.publish(payload, _is_reconnect_retry=True)
            else:
                raise e
