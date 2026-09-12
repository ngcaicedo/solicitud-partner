import pytest

from solicitudes_partner.config.settings import Settings


def test_configuration_is_read_when_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PARTNER_SERVICE_NAME", raising=False)
    monkeypatch.delenv("PARTNER_DATABASE_URL", raising=False)
    assert Settings.from_environment() == Settings()
    monkeypatch.setenv("PARTNER_SERVICE_NAME", "configured-service")
    monkeypatch.setenv("PARTNER_DATABASE_URL", "postgresql+psycopg://test")
    assert Settings.from_environment() == Settings(
        service_name="configured-service", database_url="postgresql+psycopg://test"
    )


def test_blank_database_url_disables_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PARTNER_DATABASE_URL", "   ")
    assert Settings.from_environment().database_url is None
