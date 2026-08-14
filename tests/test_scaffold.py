"""Scaffold sanity: packages import and console entry points resolve."""

from importlib.metadata import entry_points


def test_packages_import() -> None:
    import ledger  # noqa: F401
    import nre  # noqa: F401
    import nre.canon  # noqa: F401
    import nre.verify  # noqa: F401


def test_console_scripts_registered() -> None:
    eps = {ep.name: ep.value for ep in entry_points(group="console_scripts")}
    assert eps.get("ledger") == "ledger.cli:main"
    assert eps.get("nre-verify-fixtures") == "nre.verify.cli:main"
