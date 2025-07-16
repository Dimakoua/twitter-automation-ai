import asyncio
import time

from apscheduler.schedulers.background import BackgroundScheduler

from runners.airdrop_hunter_runner import AirdropHunterunner
from runners.like_runner import LikeRunner
from runners.publish_queue_messages_runner import run as publisher_runner


def run_async_job(job_func):
    try:
        asyncio.run(job_func())
    except Exception as e:
        print(f"Error in scheduled async job {job_func.__name__}: {e}")


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        lambda: run_async_job(publisher_runner),
        "interval",
        minutes=15,
        id="publisher_job",
        name="Run Publisher",
    )
    like_runner = LikeRunner()
    scheduler.add_job(
        lambda: run_async_job(like_runner.run),
        "interval",
        minutes=45,
        id="likes_job",
        name="Run Likes",
    )
    # airdrop_hunter_runner = AirdropHunterunner()
    # scheduler.add_job(
    #     lambda: run_async_job(airdrop_hunter_runner.run),
    #     "interval",
    #     minutes=1,
    #     id="airdrop_hunter_job",
    #     name="Run Airdrop Hunter",
    # )
    scheduler.start()
    print("Scheduler started. Press Ctrl+C to exit.")
    try:
        # Keep the main thread alive
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("Scheduler shut down.")


if __name__ == "__main__":
    start_scheduler()
