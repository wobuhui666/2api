"""Recaptcha token management with shared token support and background refresh."""

import re
import asyncio
import random
import string
import time
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from loguru import logger

from app.config import settings


def random_string(length: int = 10) -> str:
    """Generate a random string of specified length."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


class RecaptchaManager:
    """Manager for recaptcha token with shared token, expiry management, and background refresh."""

    def __init__(self):
        self._token: str | None = None
        self._token_created_at: float | None = None
        self._lock = asyncio.Lock()
        self._refresh_lock = asyncio.Lock()
        self._refresh_task: asyncio.Task | None = None
        self._session: AsyncSession | None = None
        self._running = False

    @property
    def is_token_expired(self) -> bool:
        """Check if the current token has expired."""
        if self._token is None or self._token_created_at is None:
            return True
        elapsed = time.time() - self._token_created_at
        return elapsed >= settings.token_ttl

    @property
    def is_token_valid(self) -> bool:
        """Check if we have a valid (non-expired) token."""
        return self._token is not None and not self.is_token_expired

    async def start_background_refresh(self, session: AsyncSession) -> None:
        """Start the background token refresh task."""
        self._session = session
        self._running = True
        
        # Get initial token
        await self.get_token(session)
        
        # Start background refresh loop
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(self._background_refresh_loop())
            logger.info(
                f"Started background token refresh (interval: {settings.token_refresh_interval}s, "
                f"TTL: {settings.token_ttl}s)"
            )

    async def stop_background_refresh(self) -> None:
        """Stop the background token refresh task."""
        self._running = False
        if self._refresh_task is not None and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped background token refresh")
        self._refresh_task = None

    async def _background_refresh_loop(self) -> None:
        """Background loop that periodically refreshes the token."""
        while self._running:
            try:
                await asyncio.sleep(settings.token_refresh_interval)
                if not self._running:
                    break
                
                if self._session is not None:
                    logger.debug("Background token refresh triggered")
                    await self._do_refresh(self._session)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background token refresh failed: {e}")
                # Continue running, will retry on next interval

    async def get_token(self, session: AsyncSession) -> str | None:
        """Get a valid recaptcha token, refreshing if necessary."""
        # If we have a valid (non-expired) token, return it
        if self.is_token_valid:
            return self._token

        # Try to refresh the token
        async with self._lock:
            # Double-check after acquiring lock
            if self.is_token_valid:
                return self._token

            # Refresh the token
            return await self._do_refresh(session)

    async def invalidate_and_refresh(self, session: AsyncSession) -> str | None:
        """Invalidate the current token and get a new one."""
        async with self._refresh_lock:
            self._token = None
            self._token_created_at = None
            return await self.get_token(session)

    async def _do_refresh(self, session: AsyncSession) -> str | None:
        """Actually perform the token refresh."""
        token = await self._refresh_token(session)
        if token:
            self._token = token
            self._token_created_at = time.time()
        return token

    async def _refresh_token(self, session: AsyncSession) -> str | None:
        """Refresh the recaptcha token with retry logic."""
        for attempt in range(3):
            random_cb = random_string(10)
            anchor_url = (
                f"{settings.recaptcha_base_api}/recaptcha/enterprise/anchor?"
                f"ar=1&k=6LdCjtspAAAAAMcV4TGdWLJqRTEk1TfpdLqEnKdj"
                f"&co=aHR0cHM6Ly9jb25zb2xlLmNsb3VkLmdvb2dsZS5jb206NDQz"
                f"&hl=zh-CN&v=jdMmXeCQEkPbnFDy9T04NbgJ&size=invisible"
                f"&anchor-ms=20000&execute-ms=15000&cb={random_cb}"
            )
            reload_url = (
                f"{settings.recaptcha_base_api}/recaptcha/enterprise/reload?"
                f"k=6LdCjtspAAAAAMcV4TGdWLJqRTEk1TfpdLqEnKdj"
            )

            token = await self._execute_recaptcha(session, anchor_url, reload_url)
            if token:
                logger.info("Successfully obtained recaptcha token")
                return token

            logger.warning(
                f"Failed to get recaptcha token, attempt {attempt + 1}/3, retrying..."
            )

        logger.error("Failed to get recaptcha token after 3 attempts")
        return None

    async def _execute_recaptcha(
        self, session: AsyncSession, anchor_url: str, reload_url: str
    ) -> str | None:
        """Execute the recaptcha flow to get a token."""
        try:
            # Get initial recaptcha token from anchor page
            anchor_response = await session.get(
                anchor_url,
                impersonate="chrome131",
                proxy=settings.proxy,
            )

            soup = BeautifulSoup(anchor_response.text, "html.parser")
            token_element = soup.find("input", {"id": "recaptcha-token"})

            if token_element is None:
                logger.error("Recaptcha token element not found in anchor page")
                return None

            base_token = str(token_element.get("value"))

            # Parse URL parameters for reload request
            parsed = urlparse(anchor_url)
            params = parse_qs(parsed.query)

            payload = {
                "v": params["v"][0],
                "reason": "q",
                "k": params["k"][0],
                "c": base_token,
                "co": params["co"][0],
                "hl": params["hl"][0],
                "size": "invisible",
                "vh": "6581054572",
                "chr": "",
                "bg": "",
            }

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
            }

            # Send reload request to get final token
            reload_response = await session.post(
                reload_url,
                data=payload,
                headers=headers,
                impersonate="chrome131",
                proxy=settings.proxy,
            )

            # Extract token from response
            match = re.search(r'rresp","(.*?)"', reload_response.text)
            if not match:
                logger.error("Failed to extract rresp token from reload response")
                return None

            return match.group(1)

        except Exception as e:
            logger.error(f"Error executing recaptcha: {e}")
            return None


# Global recaptcha manager instance
recaptcha_manager = RecaptchaManager()