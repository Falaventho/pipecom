import sys
import os

try:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
except Exception:
    pass

import pipecom
import time
import json


def task_processor(message):
    try:
        task = json.loads(message)
        print(f"Processing task: {task['name']}")

        # Simulate task processing
        time.sleep(task.get('duration', 1))

        return json.dumps({"status": "completed", "task_id": task['id']})
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


# Start task processor
processor = pipecom.Pipe("task_queue", task_processor, max_messages=10)
processor.listen()

# Submit tasks
tasks = [
    {"id": 1, "name": "Process data", "duration": 2},
    {"id": 2, "name": "Generate report", "duration": 1},
    {"id": 3, "name": "Send email", "duration": 0.5}
]

for task in tasks:
    result = pipecom.send("task_queue", json.dumps(task), timeout=10)
    print(f"Task {task['id']} submitted: {'Success' if result else 'Failed'}")
