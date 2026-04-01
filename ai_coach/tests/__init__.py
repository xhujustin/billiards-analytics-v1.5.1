"""AI Coach 測試套件初始化"""

import pytest

# pytest markers
def pytest_configure(config):
    config.addinivalue_line("markers", "unit: unit tests")
    config.addinivalue_line("markers", "integration: integration tests")
