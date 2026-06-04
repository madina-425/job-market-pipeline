import pytest
from src.loaders.rds_loader import RDSLoader

def test_rds_health_check():
    """Проверяет подключение к RDS через health_check"""
    loader = RDSLoader()
    result = loader.health_check()
    assert result is True, "RDS health check не пройден"

def test_rds_engine_created():
    """Проверяет, что engine успешно создан"""
    loader = RDSLoader()
    assert loader.engine is not None, "Engine не создан"

def test_rds_can_execute_query():
    """Проверяет возможность выполнить простой запрос"""
    loader = RDSLoader()
    try:
        df = loader.load_for_analytics("SELECT 1 as test")
        assert not df.empty, "Запрос вернул пустой результат"
        assert df.iloc[0]['test'] == 1
    except Exception as e:
        pytest.fail(f"Ошибка выполнения запроса: {str(e)}")
