
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
from fastapi.testclient import TestClient

from code_scanner.service import app, ScannerEngine, engines
from code_scanner.config import Config, ServiceConfig

client = TestClient(app)

@pytest.fixture
def mock_engine():
    with patch("code_scanner.service.ScannerEngine") as MockEngine:
        instance = MockEngine.return_value
        instance.start = MagicMock()
        instance.stop = MagicMock()
        instance.get_issues = MagicMock(return_value=[])
        instance.stop_event = MagicMock()
        instance.stop_event.is_set.return_value = False
        yield MockEngine

@pytest.fixture
def mock_load_config():
    with patch("code_scanner.service.load_config") as mock:
        mock.return_value = MagicMock(spec=Config)
        mock.return_value.target_directory = Path("/tmp/test")
        yield mock

@pytest.fixture
def mock_persistence():
    with patch("code_scanner.service.save_state") as mock_save, \
         patch("code_scanner.service.load_state") as mock_load:
        yield mock_save, mock_load

def test_add_watcher(mock_engine, mock_load_config, mock_persistence):
    response = client.post("/watch/add", json={"path": "/tmp/test", "config_path": None})
    assert response.status_code == 200
    assert response.json()["status"] == "started"
    assert "/tmp/test" in engines
    
    # Verify duplicates
    response = client.post("/watch/add", json={"path": "/tmp/test"})
    assert response.json()["status"] == "already_watching"

def test_remove_watcher(mock_engine, mock_load_config, mock_persistence):
    # Setup
    engines["/tmp/test"] = mock_engine.return_value
    
    response = client.post("/watch/remove", json={"path": "/tmp/test"})
    assert response.status_code == 200
    assert response.json()["status"] == "stopped"
    assert "/tmp/test" not in engines
    
    # Verify missing
    response = client.post("/watch/remove", json={"path": "/tmp/test"})
    assert response.status_code == 404

def test_status(mock_engine):
    engines["/tmp/test"] = mock_engine.return_value
    
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["target_directory"] == "/tmp/test"
    assert data[0]["is_running"] is True

def test_issues_aggregation(mock_engine):
    # Mock issue
    issue_mock = MagicMock()
    issue_mock.__dict__ = {"title": "Bug", "severity": "high"}
    mock_engine.return_value.get_issues.return_value = [issue_mock]
    
    engines["/tmp/test"] = mock_engine.return_value
    
    response = client.get("/issues")
    assert response.status_code == 200
    data = response.json()
    assert len(data["issues"]) == 1
    assert data["issues"][0]["title"] == "Bug"
    assert data["issues"][0]["project_path"] == "/tmp/test"
