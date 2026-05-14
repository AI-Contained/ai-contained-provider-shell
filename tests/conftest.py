import pytest


@pytest.fixture(autouse=True)
def disable_color(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLOR", "disabled")
    monkeypatch.setenv("EXPERIMENTAL_APPROVE_ALL_READS", "")
