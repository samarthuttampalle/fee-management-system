"""Phase 0 scaffold smoke test: package imports cleanly."""

from fee_management import config


def test_settings_load_defaults() -> None:
    config.get_settings.cache_clear()
    settings = config.get_settings()
    assert settings.functions_worker_runtime == "python"
    assert isinstance(settings.environment, str)
    assert settings.sql_pool_size == 5
