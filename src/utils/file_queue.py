import json
import os
import threading
import time


class FileMessageQueue:
    def __init__(self, queue_dir="/tmp/twitter_queue"):
        self.queue_dir = queue_dir
        os.makedirs(self.queue_dir, exist_ok=True)
        self.lock = threading.Lock()

    def _get_next_index(self):
        existing = [f for f in os.listdir(self.queue_dir) if f.endswith(".json")]
        if not existing:
            return 1
        nums = [int(f.split(".")[0]) for f in existing]
        return max(nums) + 1

    def put(self, message):
        with self.lock:
            index = self._get_next_index()
            filename = os.path.join(self.queue_dir, f"{index:06d}.json")
            with open(filename, "w") as f:
                json.dump(message, f)

    def get(self, block=False, poll_interval=1):
        while True:
            files = sorted(f for f in os.listdir(self.queue_dir) if f.endswith(".json"))
            if files:
                filename = os.path.join(self.queue_dir, files[0])
                try:
                    with open(filename, "r") as f:
                        message = json.load(f)
                    os.remove(filename)
                    return message
                except Exception as e:
                    print(f"Error reading file: {e}")
                    time.sleep(poll_interval)
            elif not block:
                return None
            else:
                time.sleep(poll_interval)
