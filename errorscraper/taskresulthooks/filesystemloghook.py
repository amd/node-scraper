import json
import os
from typing import Optional

from errorscraper.connection.inband import FileArtifact
from errorscraper.interfaces.taskresulthook import TaskResultHook
from errorscraper.models import DataModel, TaskResult
from errorscraper.utils import get_unique_filename, pascal_to_snake


class FileSystemLogHook(TaskResultHook):

    def __init__(self, log_base_path=None, **kwargs) -> None:
        if log_base_path is None:
            log_base_path = os.getcwd()

        self.log_base_path = log_base_path

    def process_result(self, task_result: TaskResult, data: Optional[DataModel] = None, **kwargs):
        """post process task result

        Args:
            task_result (TaskResult): input task result
        """
        log_path = self.log_base_path
        if task_result.parent:
            log_path = os.path.join(log_path, pascal_to_snake(task_result.parent))
        if task_result.task:
            log_path = os.path.join(log_path, pascal_to_snake(task_result.task))

        os.makedirs(log_path, exist_ok=True)

        with open(os.path.join(log_path, "result.json"), "w", encoding="utf-8") as log_file:
            log_file.write(task_result.model_dump_json(exclude={"artifacts", "events"}, indent=2))

        artifact_map = {}
        for artifact in task_result.artifacts:
            if isinstance(artifact, FileArtifact):
                log_name = get_unique_filename(log_path, artifact.filename)
                with open(os.path.join(log_path, log_name), "w", encoding="utf-8") as log_file:
                    log_file.write(artifact.contents)
            else:
                name = f"{pascal_to_snake(artifact.__class__.__name__)}s"
                if name in artifact_map:
                    artifact_map[name].append(artifact.model_dump(mode="json"))
                else:
                    artifact_map[name] = [artifact.model_dump(mode="json")]

        for name, artifacts in artifact_map.items():
            log_name = get_unique_filename(log_path, f"{name}.json")
            with open(os.path.join(log_path, log_name), "w", encoding="utf-8") as log_file:
                json.dump(artifacts, log_file, indent=2)

        if task_result.events:
            event_log = get_unique_filename(log_path, "events.json")
            events = [
                event.model_dump(mode="json", exclude_none=True) for event in task_result.events
            ]
            with open(os.path.join(log_path, event_log), "w", encoding="utf-8") as log_file:
                json.dump(events, log_file, indent=2)

        if data:
            data.log_model(log_path)
