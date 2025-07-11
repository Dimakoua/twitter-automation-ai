import logging
import random
import threading
import time
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


class ProxyManager:
    def __init__(
        self,
        test_url: str = "https://httpbin.org/ip",
        timeout: int = 10,
        rotate_every: int = 300,
    ):
        self.test_url = test_url
        self.timeout = timeout
        self.rotate_every = rotate_every
        self.proxies: List[str] = []
        self.lock = threading.Lock()

        self.load_proxies()

        self.rotation_thread = threading.Thread(
            target=self._rotate_proxies_periodically, daemon=True, name="ProxyRotator"
        )
        self.rotation_thread.start()

    def load_proxies(self):
        logger.info("Fetching proxy list...")
        raw_proxies = self.fetch_http_proxies()
        logger.info(f"Found {len(raw_proxies)} proxies. Testing...")

        working_proxies = []
        for proxy in raw_proxies:
            logger.info(f"Testing proxy - {proxy}")
            latency = self.is_proxy_working(proxy, self.test_url, self.timeout)
            if latency is not None:
                working_proxies.append((proxy, latency))
                logger.info(f"Proxy {proxy} latency: {latency:.2f}s")

        working_proxies.sort(key=lambda x: x[1])  # Sort by latency

        with self.lock:
            self.proxies = [p[0] for p in working_proxies]

        logger.info(f"{len(self.proxies)} working proxies loaded.")

    def _rotate_proxies_periodically(self):
        while True:
            time.sleep(self.rotate_every)
            logger.info("Rotating proxies...")
            self.load_proxies()

    def get_proxy(self) -> Optional[str]:
        with self.lock:
            if not self.proxies:
                logger.warning("Proxy list empty!")
                return None
            proxy = random.choice(self.proxies)
            logger.debug(f"Providing proxy: {proxy}")
            return proxy

    def report_bad_proxy(self, proxy: str):
        with self.lock:
            if proxy in self.proxies:
                self.proxies.remove(proxy)
                logger.warning(f"Removed bad proxy: {proxy}")

    @staticmethod
    def is_proxy_working(
        proxy: str, test_url: str, timeout: int = 5
    ) -> Optional[float]:
        try:
            start = time.time()
            response = requests.get(
                test_url,
                proxies={"http": proxy, "https": proxy},
                timeout=timeout,
            )
            if response.status_code == 200:
                latency = time.time() - start
                return latency
        except Exception:
            pass
        return None

    @staticmethod
    def fetch_http_proxies() -> List[str]:
        url = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all&skip=0&limit=20"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            raw = response.text.strip().splitlines()
            return [f"http://{line.strip()}" for line in raw if line.strip()]
        except Exception as e:
            logger.error(f"Failed to fetch proxies: {e}")
            return []
