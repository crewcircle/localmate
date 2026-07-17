"""Tests for retry_on_failure decorator."""
import pytest
from utils.retry import retry_on_failure


@pytest.mark.asyncio
async def test_retry_decorator_retries_on_failure():
    """Retry decorator retries on exception and eventually succeeds."""
    call_count = 0

    @retry_on_failure(max_retries=2, delay=0.01)
    async def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("API unavailable")
        return {"status": "ok"}

    result = await flaky_function()

    assert result == {"status": "ok"}
    assert call_count == 3
