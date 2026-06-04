import os

import pytest

from src.loaders.rds_loader import RDSLoader

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_RDS_INTEGRATION"),
    reason="Requires a reachable Postgres/RDS instance; set RUN_RDS_INTEGRATION=1 to run.",
)


def test_rds_health_check():
    """Проверяет подключение к RDS через health_check"""
    loader = RDSLoader()
    assert loader.health_check() is True, "RDS health check не пройден"


def test_rds_engine_created():
    """Проверяет, что engine успешно создан"""
    loader = RDSLoader()
    assert loader.engine is not None, "Engine не создан"


def test_rds_can_execute_query():
    """Проверяет возможность выполнить простой запрос"""
    loader = RDSLoader()
    df = loader.load_for_analytics("SELECT 1 as test")
    assert not df.empty, "Запрос вернул пустой результат"
    assert int(df.iloc[0]["test"]) == 1