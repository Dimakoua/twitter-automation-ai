import asyncio
import argparse
from src.main import TwitterOrchestrator

async def main():
    parser = argparse.ArgumentParser(description='Run Twitter automation tasks.')
    parser.add_argument('--task', type=str, required=True, choices=['all', 'airdrop_hunter', 'like_and_comment'], help='The task to run.')
    args = parser.parse_args()

    orchestrator = TwitterOrchestrator()

    if args.task == 'all':
        await orchestrator.run()
    elif args.task == 'airdrop_hunter':
        # This will run the airdrop hunter for all accounts that have it enabled.
        await orchestrator.run()
    elif args.task == 'like_and_comment':
        # This will run the like and comment processor for all accounts.
        await orchestrator.run()

if __name__ == "__main__":
    asyncio.run(main())