import json
import os
import shutil
import threading
import time


class FileMessageQueue:
    def __init__(self, queue_dir="/tmp/twitter_queue"):
        self.queue_dir = queue_dir
        self.processing_dir = os.path.join(self.queue_dir, "processing")
        self.dead_letter_dir = os.path.join(self.queue_dir, "dead_letter")

        os.makedirs(self.queue_dir, exist_ok=True)
        os.makedirs(self.processing_dir, exist_ok=True)
        os.makedirs(self.dead_letter_dir, exist_ok=True)

        self.lock = threading.Lock()

    def _get_next_index(self):
        # This now considers both queue and processing directories to ensure unique IDs
        existing_queue = [f for f in os.listdir(self.queue_dir) if f.endswith(".json")]
        existing_processing = [
            f for f in os.listdir(self.processing_dir) if f.endswith(".json")
        ]
        all_files = existing_queue + existing_processing

        if not all_files:
            return 1
        nums = [int(f.split(".")[0]) for f in all_files]
        return max(nums) + 1

    def put(self, message):
        with self.lock:
            index = self._get_next_index()
            filename = os.path.join(self.queue_dir, f"{index:06d}.json")
            with open(filename, "w") as f:
                json.dump(message, f)
            return f"{index:06d}.json"

    def get(self, block=False, poll_interval=1):
        while True:
            with self.lock:
                files = sorted(
                    f for f in os.listdir(self.queue_dir) if f.endswith(".json")
                )
                if files:
                    source_filename = os.path.join(self.queue_dir, files[0])
                    message_id = files[0]
                    destination_filename = os.path.join(self.processing_dir, message_id)

                    try:
                        # Atomically move the file to the processing directory
                        shutil.move(source_filename, destination_filename)

                        with open(destination_filename, "r") as f:
                            message = json.load(f)
                        return message, message_id  # Return the message and its ID
                    except Exception as e:
                        print(f"Error moving or reading file {source_filename}: {e}")
                        # If an error occurs during move/read, put it back or handle as appropriate
                        if os.path.exists(destination_filename):
                            shutil.move(
                                destination_filename, source_filename
                            )  # Try to move it back
                        time.sleep(poll_interval)
                elif not block:
                    return None, None
                else:
                    time.sleep(poll_interval)

    def ack(self, message_id):
        with self.lock:
            filename = os.path.join(self.processing_dir, message_id)
            if os.path.exists(filename):
                os.remove(filename)
                return True
            return False

    def nack(self, message_id, requeue=True, dead_letter_after_attempts=3):
        with self.lock:
            processing_filename = os.path.join(self.processing_dir, message_id)
            if os.path.exists(processing_filename):
                if requeue:
                    # Implement retry count or other logic if needed
                    # For simplicity, we'll just move it back.
                    # In a real system, you might increment a retry counter within the message
                    # and move to dead_letter_dir if attempts exceed a threshold.
                    current_retries = self._get_retries_from_message(
                        processing_filename
                    )
                    if (
                        current_retries < dead_letter_after_attempts - 1
                    ):  # -1 because we increment below
                        # Increment retry count and move back to the main queue
                        message_content = None
                        with open(processing_filename, "r") as f:
                            message_content = json.load(f)
                        message_content["__retries"] = (
                            message_content.get("__retries", 0) + 1
                        )
                        with open(processing_filename, "w") as f:
                            json.dump(message_content, f)
                        shutil.move(
                            processing_filename,
                            os.path.join(self.queue_dir, message_id),
                        )
                        return True
                    else:
                        # Move to dead-letter queue
                        shutil.move(
                            processing_filename,
                            os.path.join(self.dead_letter_dir, message_id),
                        )
                        return True  # Successfully moved to dead letter
                else:
                    # If not requeue, just remove it (equivalent to a silent discard)
                    os.remove(processing_filename)
                    return True
            return False

    def _get_retries_from_message(self, filename):
        try:
            with open(filename, "r") as f:
                message = json.load(f)
                return message.get("__retries", 0)
        except Exception as e:
            print(f"Error reading retries from file {filename}: {e}")
            return 0
