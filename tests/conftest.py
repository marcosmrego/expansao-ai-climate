import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: requires a live PostgreSQL database (deselect with -m 'not integration')",
    )
