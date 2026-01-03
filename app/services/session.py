"""HTTP session management."""

from curl_cffi.requests import AsyncSession
from app.config import settings


_session: AsyncSession | None = None


async def get_session() -> AsyncSession:
    """Get or create a shared async session."""
    global _session
    if _session is None:
        _session = AsyncSession()
    return _session


async def close_session() -> None:
    """Close the shared async session."""
    global _session
    if _session is not None:
        await _session.close()
        _session = None