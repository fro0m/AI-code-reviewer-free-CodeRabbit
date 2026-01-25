"""Tests for ProjectManager and LLMClientManager."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from code_scanner.project_manager import ProjectManager
from code_scanner.llm_client_manager import LLMClientManager
from code_scanner.models import Project, LLMConfig


@pytest.fixture
def mock_config():
    """Create a mock Config object."""
    config = Mock()
    config.llm = Mock(
        backend="lm-studio",
        host="localhost",
        port=1234,
        model="test-model",
        context_limit=4096,
    )
    config.check_groups = []
    config.output_file = "code_scanner_results.md"
    config.log_file = "code_scanner.log"
    config.target_directory = Path("/test/project")
    return config


@pytest.fixture
def project_manager():
    """Create a ProjectManager instance."""
    return ProjectManager()


@pytest.fixture
def llm_client_manager():
    """Create an LLMClientManager instance."""
    return LLMClientManager()


class TestProjectManager:
    """Tests for ProjectManager class."""

    def test_add_project(self, project_manager, mock_config):
        """Test adding a project to the manager."""
        project = project_manager.add_project(
            project_id="project_0",
            target_directory=Path("/test/project0"),
            config_file=Path("/test/config0.toml"),
            config=mock_config,
        )

        assert project.project_id == "project_0"
        assert project.target_directory == Path("/test/project0")
        assert project.config_file == Path("/test/config0.toml")
        assert project.config == mock_config
        assert project_manager.get_project_by_id("project_0") == project

    def test_add_multiple_projects(self, project_manager, mock_config):
        """Test adding multiple projects."""
        for i in range(3):
            project_manager.add_project(
                project_id=f"project_{i}",
                target_directory=Path(f"/test/project{i}"),
                config_file=Path(f"/test/config{i}.toml"),
                config=mock_config,
            )

        projects = project_manager.get_all_projects()
        assert len(projects) == 3

    def test_get_project_by_id(self, project_manager, mock_config):
        """Test getting a project by ID."""
        project = project_manager.add_project(
            project_id="project_0",
            target_directory=Path("/test/project0"),
            config_file=Path("/test/config0.toml"),
            config=mock_config,
        )

        retrieved = project_manager.get_project_by_id("project_0")
        assert retrieved.project_id == "project_0"

    def test_get_project_by_id_not_found(self, project_manager):
        """Test getting a non-existent project by ID."""
        retrieved = project_manager.get_project_by_id("nonexistent")
        assert retrieved is None

    def test_get_project_by_directory(self, project_manager, mock_config):
        """Test getting a project by directory."""
        project = project_manager.add_project(
            project_id="project_0",
            target_directory=Path("/test/project0"),
            config_file=Path("/test/config0.toml"),
            config=mock_config,
        )

        retrieved = project_manager.get_project_by_directory(Path("/test/project0"))
        assert retrieved.project_id == "project_0"

    def test_get_project_by_directory_not_found(self, project_manager):
        """Test getting a non-existent project by directory."""
        retrieved = project_manager.get_project_by_directory(Path("/nonexistent"))
        assert retrieved is None

    def test_get_all_projects(self, project_manager, mock_config):
        """Test getting all projects."""
        project_manager.add_project(
            project_id="project_0",
            target_directory=Path("/test/project0"),
            config_file=Path("/test/config0.toml"),
            config=mock_config,
        )
        project_manager.add_project(
            project_id="project_1",
            target_directory=Path("/test/project1"),
            config_file=Path("/test/config1.toml"),
            config=mock_config,
        )

        projects = project_manager.get_all_projects()
        assert len(projects) == 2
        assert projects[0].project_id == "project_0"
        assert projects[1].project_id == "project_1"

    def test_get_active_project_none(self, project_manager):
        """Test getting active project when none is active."""
        active = project_manager.get_active_project()
        assert active is None

    def test_get_previous_active_project_none(self, project_manager):
        """Test getting previous active project when none was active."""
        previous = project_manager.get_previous_active_project()
        assert previous is None

    def test_switch_to_project(self, project_manager, mock_config):
        """Test switching to a project."""
        project = project_manager.add_project(
            project_id="project_0",
            target_directory=Path("/test/project0"),
            config_file=Path("/test/config0.toml"),
            config=mock_config,
        )

        project_manager.switch_to_project(project)

        assert project.is_active is True
        active = project_manager.get_active_project()
        assert active.project_id == "project_0"

    def test_switch_to_project_already_active(self, project_manager, mock_config):
        """Test switching to a project that is already active."""
        project = project_manager.add_project(
            project_id="project_0",
            target_directory=Path("/test/project0"),
            config_file=Path("/test/config0.toml"),
            config=mock_config,
        )

        project_manager.switch_to_project(project)
        previous_active = project_manager.get_active_project()

        # Switch again - should be a no-op
        project_manager.switch_to_project(project)

        # Active project should not change
        assert project_manager.get_active_project() == previous_active

    def test_determine_active_project_single_project(self, project_manager, mock_config):
        """Test determining active project with only one project."""
        project = project_manager.add_project(
            project_id="project_0",
            target_directory=Path("/test/project0"),
            config_file=Path("/test/config0.toml"),
            config=mock_config,
        )

        active = project_manager.determine_active_project()
        assert active.project_id == "project_0"

    def test_determine_active_project_no_projects(self, project_manager):
        """Test determining active project with no projects."""
        active = project_manager.determine_active_project()
        assert active is None

    def test_determine_active_project_no_changes(self, project_manager, mock_config):
        """Test determining active project when no projects have changes."""
        project_manager.add_project(
            project_id="project_0",
            target_directory=Path("/test/project0"),
            config_file=Path("/test/config0.toml"),
            config=mock_config,
        )
        project_manager.add_project(
            project_id="project_1",
            target_directory=Path("/test/project1"),
            config_file=Path("/test/config1.toml"),
            config=mock_config,
        )

        # Both projects have no git watchers, so no changes
        active = project_manager.determine_active_project()
        assert active is None

    def test_set_all_projects_status(self, project_manager, mock_config):
        """Test setting status for all projects."""
        from code_scanner.models import ScanStatus
        from unittest.mock import MagicMock
        
        # Add multiple projects with mock output generators
        project0 = project_manager.add_project(
            project_id="project_0",
            target_directory=Path("/test/project0"),
            config_file=Path("/test/config0.toml"),
            config=mock_config,
        )
        project1 = project_manager.add_project(
            project_id="project_1",
            target_directory=Path("/test/project1"),
            config_file=Path("/test/config1.toml"),
            config=mock_config,
        )
        
        # Add mock output generators to projects
        project0.output_generator = MagicMock()
        project0.issue_tracker = MagicMock()
        project1.output_generator = MagicMock()
        project1.issue_tracker = MagicMock()
        
        # Set all projects to NOT_RUNNING status
        project_manager.set_all_projects_status(ScanStatus.NOT_RUNNING)
        
        # Verify both projects have NOT_RUNNING status
        assert project0.scan_status == ScanStatus.NOT_RUNNING
        assert project1.scan_status == ScanStatus.NOT_RUNNING
        
        # Verify output_generator.write was called for both projects
        project0.output_generator.write.assert_called_once()
        project1.output_generator.write.assert_called_once()
        
        # Verify the call arguments include NOT_RUNNING status
        call_args0 = project0.output_generator.write.call_args
        call_args1 = project1.output_generator.write.call_args
        assert call_args0[0][2] == ScanStatus.NOT_RUNNING
        assert call_args1[0][2] == ScanStatus.NOT_RUNNING

    def test_set_all_projects_status_with_error_message(self, project_manager, mock_config):
        """Test setting status for all projects with error message."""
        from code_scanner.models import ScanStatus
        from unittest.mock import MagicMock
        
        # Add a project with mock output generator
        project = project_manager.add_project(
            project_id="project_0",
            target_directory=Path("/test/project0"),
            config_file=Path("/test/config0.toml"),
            config=mock_config,
        )
        
        # Add mock output generator to project
        project.output_generator = MagicMock()
        project.issue_tracker = MagicMock()
        
        # Set all projects to ERROR status with error message
        error_msg = "Connection lost"
        project_manager.set_all_projects_status(ScanStatus.ERROR, error_message=error_msg)
        
        # Verify project has ERROR status and error message
        assert project.scan_status == ScanStatus.ERROR
        assert project.error_message == error_msg
        
        # Verify output_generator.write was called with ERROR status and error message
        call_args = project.output_generator.write.call_args
        assert call_args[0][2] == ScanStatus.ERROR  # Third argument is scan_status


class TestLLMClientManager:
    """Tests for LLMClientManager class."""

    def test_get_current_client_none(self, llm_client_manager):
        """Test getting current client when none is set."""
        client = llm_client_manager.get_current_client()
        assert client is None

    def test_get_current_config_none(self, llm_client_manager):
        """Test getting current config when none is set."""
        config = llm_client_manager.get_current_config()
        assert config is None

    @patch("code_scanner.llm_client_manager.LLMClientManager._create_client_from_config")
    def test_switch_client_first_time(self, mock_create_client, llm_client_manager):
        """Test switching to a client for the first time."""
        config = LLMConfig(
            backend="lm-studio",
            host="localhost",
            port=1234,
            model="test-model",
            context_limit=4096,
        )

        mock_client = Mock()
        mock_create_client.return_value = mock_client

        client = llm_client_manager.switch_client(config)

        assert client == mock_client
        assert llm_client_manager.get_current_client() == mock_client
        assert llm_client_manager.get_current_config() == config
        mock_create_client.assert_called_once_with(config)

    @patch("code_scanner.llm_client_manager.LLMClientManager._create_client_from_config")
    def test_switch_client_same_config(self, mock_create_client, llm_client_manager):
        """Test switching to a client with the same config (should reuse)."""
        config = LLMConfig(
            backend="lm-studio",
            host="localhost",
            port=1234,
            model="test-model",
            context_limit=4096,
        )

        mock_client = Mock()
        mock_create_client.return_value = mock_client

        # First switch
        client1 = llm_client_manager.switch_client(config)
        assert mock_create_client.call_count == 1

        # Second switch with same config
        client2 = llm_client_manager.switch_client(config)
        assert mock_create_client.call_count == 1  # Should not create new client
        assert client2 == client1  # Should return the same client

    @patch("code_scanner.llm_client_manager.LLMClientManager._create_client_from_config")
    def test_switch_client_different_config(self, mock_create_client, llm_client_manager):
        """Test switching to a client with a different config."""
        config1 = LLMConfig(
            backend="lm-studio",
            host="localhost",
            port=1234,
            model="test-model",
            context_limit=4096,
        )

        config2 = LLMConfig(
            backend="lm-studio",
            host="localhost",
            port=1234,
            model="different-model",  # Different model
            context_limit=4096,
        )

        mock_client1 = Mock()
        mock_client2 = Mock()
        mock_create_client.side_effect = [mock_client1, mock_client2]

        # First switch
        client1 = llm_client_manager.switch_client(config1)
        assert mock_create_client.call_count == 1

        # Second switch with different config
        client2 = llm_client_manager.switch_client(config2)
        assert mock_create_client.call_count == 2  # Should create new client
        assert client2 != client1  # Should return the new client

    def test_configs_equal(self):
        """Test config equality comparison."""
        config1 = LLMConfig(
            backend="lm-studio",
            host="localhost",
            port=1234,
            model="test-model",
            context_limit=4096,
        )

        config2 = LLMConfig(
            backend="lm-studio",
            host="localhost",
            port=1234,
            model="test-model",
            context_limit=4096,
        )

        # Create a temporary LLMClientManager to test the private method
        manager = LLMClientManager()
        assert manager._configs_equal(config1, config2) is True

    def test_configs_equal_different_backend(self):
        """Test config equality comparison with different backend."""
        config1 = LLMConfig(
            backend="lm-studio",
            host="localhost",
            port=1234,
            model="test-model",
            context_limit=4096,
        )

        config2 = LLMConfig(
            backend="ollama",  # Different backend
            host="localhost",
            port=1234,
            model="test-model",
            context_limit=4096,
        )

        manager = LLMClientManager()
        assert manager._configs_equal(config1, config2) is False

    def test_configs_equal_different_host(self):
        """Test config equality comparison with different host."""
        config1 = LLMConfig(
            backend="lm-studio",
            host="localhost",
            port=1234,
            model="test-model",
            context_limit=4096,
        )

        config2 = LLMConfig(
            backend="lm-studio",
            host="different-host",  # Different host
            port=1234,
            model="test-model",
            context_limit=4096,
        )

        manager = LLMClientManager()
        assert manager._configs_equal(config1, config2) is False

    def test_configs_equal_different_port(self):
        """Test config equality comparison with different port."""
        config1 = LLMConfig(
            backend="lm-studio",
            host="localhost",
            port=1234,
            model="test-model",
            context_limit=4096,
        )

        config2 = LLMConfig(
            backend="lm-studio",
            host="localhost",
            port=5678,  # Different port
            model="test-model",
            context_limit=4096,
        )

        manager = LLMClientManager()
        assert manager._configs_equal(config1, config2) is False

    def test_configs_equal_different_model(self):
        """Test config equality comparison with different model."""
        config1 = LLMConfig(
            backend="lm-studio",
            host="localhost",
            port=1234,
            model="test-model",
            context_limit=4096,
        )

        config2 = LLMConfig(
            backend="lm-studio",
            host="localhost",
            port=1234,
            model="different-model",  # Different model
            context_limit=4096,
        )

        manager = LLMClientManager()
        assert manager._configs_equal(config1, config2) is False

    def test_configs_equal_different_context_limit(self):
        """Test config equality comparison with different context limit."""
        config1 = LLMConfig(
            backend="lm-studio",
            host="localhost",
            port=1234,
            model="test-model",
            context_limit=4096,
        )

        config2 = LLMConfig(
            backend="lm-studio",
            host="localhost",
            port=1234,
            model="test-model",
            context_limit=8192,  # Different context limit
        )

        manager = LLMClientManager()
        assert manager._configs_equal(config1, config2) is False

    def test_disconnect_current_none(self, llm_client_manager):
        """Test disconnecting when no client is set."""
        # Should not raise an error
        llm_client_manager._disconnect_current()
        assert llm_client_manager.get_current_client() is None
        assert llm_client_manager.get_current_config() is None

    @patch("code_scanner.llm_client_manager.LLMClientManager._create_client_from_config")
    def test_disconnect_current_with_client(self, mock_create_client, llm_client_manager):
        """Test disconnecting when a client is set."""
        config = LLMConfig(
            backend="lm-studio",
            host="localhost",
            port=1234,
            model="test-model",
            context_limit=4096,
        )

        mock_client = Mock()
        mock_create_client.return_value = mock_client

        llm_client_manager.switch_client(config)
        assert llm_client_manager.get_current_client() == mock_client

        # Disconnect
        llm_client_manager._disconnect_current()
        assert llm_client_manager.get_current_client() is None
        assert llm_client_manager.get_current_config() is None
