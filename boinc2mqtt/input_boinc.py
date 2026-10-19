import asyncio
import datetime
import re
import os

from .common import InputService
from .models import WorkUnit
from .output_mqtt import MqttPublisher
from .settings import BoincHost

BOINCCMD_PATH = os.getenv("BOINCCMD_PATH", "boinccmd")


class Boinc(InputService):
    def __init__(self, host: BoincHost, publisher: MqttPublisher):
        super().__init__(host)
        self.host = host
        self.publisher = publisher
        self._tasks_percentages: dict[str, float] = {}

    async def loop(self) -> bool:
        try:
            cmd = [*self._get_cmd_base(), "--get_state"]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                print(f"Error executing command in {self.host.get_host_name()}: {stderr.decode().strip()}")
                return False

            output = stdout.decode()
            work_units = self._parse_get_state_output(output)
            # print(*work_units, sep="\n")
            await asyncio.gather(*[
                self.publisher.publish(wu.model_dump_json())
                for wu in work_units
            ])
            return True

        except Exception as e:
            print(f"Error in Boinc loop {self.host.get_host_name()}: {e}")
            return False


    def _get_cmd_base(self) -> list[str]:
        cmd = [
            BOINCCMD_PATH,
            "--host", f"{self.host.host}:{self.host.port}"
        ]
        if self.host.password:
            cmd += ["--passwd", self.host.password.get_secret_value()]
        return cmd

    def _parse_get_state_output(self, output: str) -> list[WorkUnit]:
        task_section = output.partition("======== Tasks ========")[2]
        if not task_section:
            return []
        task_section = task_section.partition("========")[0]

        work_units: list[WorkUnit] = []
        task: dict[str, str] = {}

        def append_task() -> None:
            # TODO move "append task" as other method
            if not task:
                return
            if task.get("ready to report") == "yes" or task.get("ended") == "yes":
                # TODO this is a fix for trying to avoid reporting tasks that are already done. Seems to be not working
                return

            percentage = float(task.get("fraction done", 0)) * 100
            task_url = task["project URL"]
            task_name = task["name"]
            task_id = f"{task_url}/{task_name}"
            if not self._update_task_percentage(task_id, percentage):
                # Skip when task percentage is lower than the last reported, meaning it may be completed.
                return

            received = datetime.datetime.strptime(
                task["received"], "%a %b %d %H:%M:%S %Y"
            )
            deadline = datetime.datetime.strptime(
                task["report deadline"], "%a %b %d %H:%M:%S %Y"
            )
            now = datetime.datetime.now()
            resources = task["resources"]
            cpu_count = re.search(r"(\d+)\s+CPU\b", resources, re.IGNORECASE)
            gpu_count = re.search(
                r"(\d+)\s+(?:[\w-]+\s+)*GPU\b", resources, re.IGNORECASE
            )
            work_units.append(
                WorkUnit(
                    host=self.host.get_host_name(),
                    project=task["project URL"],
                    name=task["name"],
                    percentage=percentage,
                    running=task.get("active_task_state", "").upper() == "EXECUTING",
                    start_timestamp=received,
                    total_time_seconds=int((now - received).total_seconds()),
                    run_seconds=int(float(task.get("elapsed task time", 0))),
                    remaining_seconds=int(
                        float(task.get("estimated CPU time remaining", 0))
                    ),
                    timeout_seconds=int((deadline - received).total_seconds()),
                    expire_seconds=int((deadline - now).total_seconds()),
                    cpu_count=int(cpu_count.group(1)) if cpu_count else 0,
                    gpu_count=int(gpu_count.group(1)) if gpu_count else 0,
                )
            )

        for line in task_section.splitlines():
            entry = line.strip()
            if entry.endswith(") -----------") and entry.split(")", 1)[0].isdigit():
                append_task()
                task = {}
                continue
            key, separator, value = entry.partition(":")
            if separator:
                task[key] = value.strip()

        append_task()
        return work_units

    def _update_task_percentage(self, task_id, percentage) -> bool:
        prev_percentage = self._tasks_percentages.get(task_id)
        if prev_percentage is None or prev_percentage < percentage:
            self._tasks_percentages[task_id] = percentage
            return True
        return False
