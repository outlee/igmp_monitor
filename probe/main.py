import asyncio
import logging
import multiprocessing
import os
import sys
import time

from config import CHANNELS_PER_WORKER, WORKER_COUNT
from storage.sqlite_db import SQLiteDB
from worker import ChannelWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def run_worker(worker_id: int, channels):
    w = ChannelWorker(worker_id=worker_id, channels=channels)
    w.run()


async def init_db_and_load_channels():
    db = SQLiteDB()
    await db.start()
    channels = await db.get_enabled_channels()
    await db.stop()
    return channels


async def main():
    logger.info("IPTV Monitor Probe starting (workers=%d, channels_per_worker=%d)", WORKER_COUNT, CHANNELS_PER_WORKER)

    channels = await init_db_and_load_channels()
    if not channels:
        logger.warning("No channels found in database. Run scripts/init_db.py first.")
        logger.info("Waiting for channels to be configured...")
        while True:
            await asyncio.sleep(10)
            channels = await init_db_and_load_channels()
            if channels:
                logger.info("Found %d channels, starting workers.", len(channels))
                break

    logger.info("Loaded %d channels from database", len(channels))

    chunks = [channels[i:i + CHANNELS_PER_WORKER] for i in range(0, len(channels), CHANNELS_PER_WORKER)]

    processes = []
    for i, chunk in enumerate(chunks):
        p = multiprocessing.Process(
            target=run_worker,
            args=(i, chunk),
            daemon=True,
            name=f"probe-worker-{i}",
        )
        p.start()
        processes.append(p)
        logger.info("Started worker %d with %d channels", i, len(chunk))

    try:
        while True:
            await asyncio.sleep(30)
            for i, p in enumerate(processes):
                if not p.is_alive():
                    logger.warning("Worker %d died, restarting with fresh channel list...", i)
                    # 重新加载 channels，避免使用陈旧列表
                    try:
                        fresh_channels = await init_db_and_load_channels()
                        if fresh_channels:
                            new_chunks = [fresh_channels[j:j + CHANNELS_PER_WORKER]
                                          for j in range(0, len(fresh_channels), CHANNELS_PER_WORKER)]
                            if i < len(new_chunks):
                                chunks[i] = new_chunks[i]
                    except Exception as e:
                        logger.error("Failed to reload channels on worker restart: %s", e)

                    new_p = multiprocessing.Process(
                        target=run_worker,
                        args=(i, chunks[i]),
                        daemon=True,
                        name=f"probe-worker-{i}",
                    )
                    new_p.start()
                    processes[i] = new_p
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        for p in processes:
            p.terminate()
        for p in processes:
            p.join(timeout=5)


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn", force=True)
    asyncio.run(main())
