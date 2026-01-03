
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from code_scanner.mcp_server import get_issues, code_scanner_status

async def _test_mcp_get_issues():
    with patch("httpx.AsyncClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.__aenter__.return_value = mock_instance
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"issues": [{"title": "Test"}]}
        
        mock_instance.get = AsyncMock(return_value=mock_response)
        
        result = await get_issues()
        assert "Test" in result

def test_mcp_get_issues():
    asyncio.run(_test_mcp_get_issues())

async def _test_mcp_status():
    with patch("httpx.AsyncClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.__aenter__.return_value = mock_instance
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"path": "/tmp/test"}]
        
        mock_instance.get = AsyncMock(return_value=mock_response)
        
        result = await code_scanner_status()
        assert "/tmp/test" in result

def test_mcp_status():
    asyncio.run(_test_mcp_status())
