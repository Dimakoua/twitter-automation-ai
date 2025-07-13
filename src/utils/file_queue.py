import json
import os
import shutil
import threading
import time


class FileMessageQueue:
    def __init__(self, queue_dir="/tmp/twitter_queue", visibility_timeout=300):
        self.queue_dir = queue_dir
        self.processing_dir = os.path.join(self.queue_dir, "processing")
        self.dead_letter_dir = os.path.join(self.queue_dir, "dead_letter")
        self.visibility_timeout = visibility_timeout  # Time in seconds a message can be in processing before being re-queued

        os.makedirs(self.queue_dir, exist_ok=True)
        os.makedirs(self.processing_dir, exist_ok=True)
        os.makedirs(self.dead_letter_dir, exist_ok=True)

        self.lock = threading.Lock()

        # Start a background thread to check for stuck messages
        self._stuck_message_monitor_thread = threading.Thread(
            target=self._monitor_stuck_messages, daemon=True
        )
        self._stuck_message_monitor_thread.start()

    def _get_next_index(self):
        existing_queue = [f for f in os.listdir(self.queue_dir) if f.endswith(".json")]
        existing_processing = [
            f for f in os.listdir(self.processing_dir) if f.endswith(".json")
        ]
        existing_dead_letter = [
            f for f in os.listdir(self.dead_letter_dir) if f.endswith(".json")
        ]  # Also consider dead letter
        all_files = existing_queue + existing_processing + existing_dead_letter

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
                # First, process any messages that have exceeded their visibility timeout
                self._requeue_stuck_messages()

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
                        # After moving, update its modification time to record when it entered processing
                        os.utime(
                            destination_filename, None
                        )  # Sets access and modification times to current time

                        with open(destination_filename, "r") as f:
                            message = json.load(f)
                        return message, message_id
                    except Exception as e:
                        print(f"Error moving or reading file {source_filename}: {e}")
                        # If an error occurs during move/read, try to move it back to the queue
                        # This handles cases where the move was successful but reading failed.
                        if os.path.exists(destination_filename):
                            try:
                                shutil.move(destination_filename, source_filename)
                                print(
                                    f"Moved {destination_filename} back to queue due to read error."
                                )
                            except Exception as move_back_e:
                                print(
                                    f"Error moving {destination_filename} back to queue: {move_back_e}"
                                )
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
                    current_retries = self._get_retries_from_message(
                        processing_filename
                    )
                    # Check if the message is already too old/retried to be re-queued
                    if current_retries < dead_letter_after_attempts - 1:
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
                        shutil.move(
                            processing_filename,
                            os.path.join(self.dead_letter_dir, message_id),
                        )
                        return True
                else:
                    os.remove(processing_filename)
                    return True
            return False

    def _get_retries_from_message(self, filename):
        try:
            with open(filename, "r") as f:
                message = json.load(f)
                return message.get("__retries", 0)
        except json.JSONDecodeError as e:
            print(
                f"Error decoding JSON from file {filename}: {e}. File might be corrupted."
            )
            return 0  # Treat as 0 retries, but an NACK will likely fail if the file is truly bad
        except Exception as e:
            print(f"Error reading retries from file {filename}: {e}")
            return 0

    def _requeue_stuck_messages(self):
        """
        Checks the processing directory for messages that have exceeded the
        visibility timeout and moves them back to the main queue.
        This is called by get() and also by a background monitor thread.
        """
        now = time.time()
        for filename in os.listdir(self.processing_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self.processing_dir, filename)
                try:
                    # os.path.getmtime returns the time of last modification
                    modified_time = os.path.getmtime(filepath)
                    if (now - modified_time) > self.visibility_timeout:
                        print(
                            f"Message {filename} in processing_dir timed out. Re-queuing..."
                        )
                        # We use nack with requeue=True to leverage the retry logic
                        # and potentially move to dead-letter if too many retries.
                        # However, nack expects the file to be processed.
                        # For simplicity here, we'll just move it back and let get() pick it up.
                        # A more robust solution might increment retries and then move.
                        # Let's simplify by just moving it back and letting _get_retries_from_message handle it on the next get().
                        current_retries = self._get_retries_from_message(filepath)
                        message_content = None
                        with open(filepath, "r") as f:
                            message_content = json.load(f)
                        message_content["__retries"] = (
                            message_content.get("__retries", 0) + 1
                        )
                        with open(filepath, "w") as f:
                            json.dump(message_content, f)
                        shutil.move(filepath, os.path.join(self.queue_dir, filename))
                except FileNotFoundError:
                    # File might have been removed by another thread/process in the meantime
                    pass
                except Exception as e:
                    print(f"Error checking/re-queueing stuck message {filepath}: {e}")

    def _monitor_stuck_messages(self):
        """
        Background thread to periodically check for and re-queue stuck messages.
        """
        while True:
            with (
                self.lock
            ):  # Acquire lock to avoid race conditions with get/put/ack/nack
                self._requeue_stuck_messages()
            time.sleep(
                self.visibility_timeout / 2
            )  # Check more frequently than timeout