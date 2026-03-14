"""Tests for the async_log_event decorator."""

import logging

from discord_against_humanity.utils.debug import async_log_event


class TestAsyncLogEvent:
    """Tests for async_log_event()."""

    async def test_returns_result(self):
        @async_log_event
        async def sample_func(x, y):
            return x + y

        result = await sample_func(2, 3)
        assert result == 5

    async def test_returns_none(self):
        @async_log_event
        async def void_func():
            pass

        result = await void_func()
        assert result is None

    async def test_preserves_function_name(self):
        @async_log_event
        async def my_function():
            return 42

        assert my_function.__name__ == "my_function"

    async def test_passes_kwargs(self):
        @async_log_event
        async def kw_func(a, b=10):
            return a * b

        result = await kw_func(3, b=5)
        assert result == 15

    async def test_logs_debug_on_call(self, caplog):
        @async_log_event
        async def logged_func(val):
            return val

        with caplog.at_level(logging.DEBUG):
            await logged_func("hello")

        assert any("Calling" in record.message for record in caplog.records)

    async def test_logs_result_when_not_none(self, caplog):
        @async_log_event
        async def returns_value():
            return "data"

        with caplog.at_level(logging.DEBUG):
            await returns_value()

        assert any("Result" in record.message for record in caplog.records)

    async def test_does_not_log_result_when_none(self, caplog):
        @async_log_event
        async def returns_nothing():
            return None

        with caplog.at_level(logging.DEBUG):
            await returns_nothing()

        result_logs = [r for r in caplog.records if "Result" in r.message]
        assert len(result_logs) == 0

    async def test_propagates_exception(self):
        @async_log_event
        async def raises():
            raise ValueError("boom")

        try:
            await raises()
            assert False, "Should have raised"
        except ValueError as e:
            assert str(e) == "boom"
