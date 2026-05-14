import pytest


@pytest.fixture(autouse=True)
def disable_color(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLOR", "disabled")
