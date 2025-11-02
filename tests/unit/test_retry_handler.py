"""Unit tests for retry_handler.

Following CLAUDE.md: pure logic tests, parameterized inputs, test entire structure.
"""

import time
import pytest

from src.utils.retry_handler import retry_with_backoff


@pytest.mark.unit
def test_retry_succeeds_on_first_attempt():
    """Should return result immediately if function succeeds on first try."""
    call_count = 0

    def successful_func():
        nonlocal call_count
        call_count += 1
        return "success"

    result = retry_with_backoff(successful_func, max_retries=3)

    assert result == "success"
    assert call_count == 1


@pytest.mark.unit
def test_retry_succeeds_after_failures():
    """Should retry and eventually succeed after initial failures."""
    call_count = 0

    def eventually_successful():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Not yet")
        return "success"

    result = retry_with_backoff(eventually_successful, max_retries=3, base_delay=0.01)

    assert result == "success"
    assert call_count == 3


@pytest.mark.unit
def test_retry_exhausts_and_raises():
    """Should raise last exception after all retries are exhausted."""
    call_count = 0

    def always_fails():
        nonlocal call_count
        call_count += 1
        raise ValueError(f"Attempt {call_count}")

    with pytest.raises(ValueError, match="Attempt 4"):
        retry_with_backoff(always_fails, max_retries=3, base_delay=0.01)

    assert call_count == 4  # Initial attempt + 3 retries


@pytest.mark.unit
def test_exponential_backoff_timing():
    """Should apply exponential backoff between retries."""
    call_times = []

    def failing_func():
        call_times.append(time.time())
        raise ValueError("Fail")

    base_delay = 0.1
    exponential_base = 2.0

    with pytest.raises(ValueError):
        retry_with_backoff(
            failing_func,
            max_retries=2,
            base_delay=base_delay,
            exponential_base=exponential_base,
        )

    # Verify timing between calls
    assert len(call_times) == 3  # Initial + 2 retries

    # First retry delay: 0.1 * 2^0 = 0.1s
    delay_1 = call_times[1] - call_times[0]
    assert 0.08 <= delay_1 <= 0.15  # Allow some tolerance

    # Second retry delay: 0.1 * 2^1 = 0.2s
    delay_2 = call_times[2] - call_times[1]
    assert 0.18 <= delay_2 <= 0.25


@pytest.mark.unit
def test_max_delay_cap():
    """Should cap delay at max_delay value."""
    call_times = []

    def failing_func():
        call_times.append(time.time())
        raise ValueError("Fail")

    with pytest.raises(ValueError):
        retry_with_backoff(
            failing_func,
            max_retries=2,
            base_delay=1.0,
            exponential_base=10.0,  # Would cause very large delays
            max_delay=0.1,  # But capped at 0.1s
        )

    # All delays should be capped at max_delay
    assert len(call_times) == 3

    delay_1 = call_times[1] - call_times[0]
    assert 0.08 <= delay_1 <= 0.15  # Capped at 0.1s

    delay_2 = call_times[2] - call_times[1]
    assert 0.08 <= delay_2 <= 0.15  # Also capped
