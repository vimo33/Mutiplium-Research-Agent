from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from multiplium.providers.factory import ProviderFactory
from multiplium.config import Settings, ProviderConfig
from multiplium.tools.manager import ToolManager


@pytest.fixture
def mock_settings():
    """Create mock settings with multiple providers."""
    return Settings(
        orchestrator=MagicMock(dry_run=False),
        providers={
            "openai": ProviderConfig(
                enabled=True,
                model="gpt-4",
                temperature=0.1,
                max_steps=20,
            ),
            "google": ProviderConfig(
                enabled=True,
                model="gemini-2.5-pro",
                temperature=0.1,
                max_steps=20,
            ),
            "anthropic": ProviderConfig(
                enabled=False,  # Disabled
                model="claude-3-5-sonnet",
                temperature=0.1,
                max_steps=20,
            ),
        },
        tools=[],
    )


@pytest.fixture
def mock_tool_manager():
    """Create a mock ToolManager."""
    return MagicMock(spec=ToolManager)


class TestProviderFactory:
    """Test the ProviderFactory class."""

    def test_factory_initialization(self, mock_settings, mock_tool_manager):
        """Test that factory initializes correctly with settings."""
        factory = ProviderFactory(mock_settings, mock_tool_manager)
        
        assert factory is not None

    def test_iter_active_agents_returns_only_enabled(self, mock_settings, mock_tool_manager):
        """Test that iter_active_agents returns only enabled providers."""
        factory = ProviderFactory(mock_settings, mock_tool_manager)
        
        active_agents = list(factory.iter_active_agents())
        
        # Should return 2 providers (openai and google, not anthropic)
        assert len(active_agents) == 2
        
        provider_names = [name for name, _ in active_agents]
        assert "openai" in provider_names
        assert "google" in provider_names
        assert "anthropic" not in provider_names

    def test_iter_active_agents_with_all_disabled(self, mock_tool_manager):
        """Test behavior when all providers are disabled."""
        settings = Settings(
            orchestrator=MagicMock(dry_run=False),
            providers={
                "openai": ProviderConfig(enabled=False, model="gpt-4"),
                "google": ProviderConfig(enabled=False, model="gemini-2.5-pro"),
            },
            tools=[],
        )
        
        factory = ProviderFactory(settings, mock_tool_manager)
        active_agents = list(factory.iter_active_agents())
        
        assert len(active_agents) == 0

    def test_factory_respects_dry_run_mode(self, mock_settings, mock_tool_manager):
        """Test that dry_run flag is passed to providers."""
        mock_settings.orchestrator.dry_run = True
        
        factory = ProviderFactory(mock_settings, mock_tool_manager, dry_run=True)
        
        active_agents = list(factory.iter_active_agents())
        
        # Verify providers are created with dry_run=True
        for name, provider in active_agents:
            assert provider.dry_run is True

    def test_factory_creates_correct_provider_types(self, mock_settings, mock_tool_manager):
        """Test that factory creates the correct provider types."""
        factory = ProviderFactory(mock_settings, mock_tool_manager)
        
        active_agents = dict(factory.iter_active_agents())
        
        # Check that OpenAI provider is created
        assert "openai" in active_agents
        openai_provider = active_agents["openai"]
        assert openai_provider.name == "openai"
        assert openai_provider.config.model == "gpt-4"
        
        # Check that Google provider is created
        assert "google" in active_agents
        google_provider = active_agents["google"]
        assert google_provider.name == "google"
        assert google_provider.config.model == "gemini-2.5-pro"

    def test_factory_handles_missing_provider_config(self, mock_tool_manager):
        """Test that factory handles empty provider config."""
        settings = Settings(
            orchestrator=MagicMock(dry_run=False),
            providers={},
            tools=[],
        )
        
        factory = ProviderFactory(settings, mock_tool_manager)
        active_agents = list(factory.iter_active_agents())
        
        assert len(active_agents) == 0

    def test_provider_config_passed_correctly(self, mock_settings, mock_tool_manager):
        """Test that provider configuration is passed correctly."""
        factory = ProviderFactory(mock_settings, mock_tool_manager)
        
        active_agents = dict(factory.iter_active_agents())
        openai_provider = active_agents["openai"]
        
        assert openai_provider.config.temperature == 0.1
        assert openai_provider.config.max_steps == 20
        assert openai_provider.config.model == "gpt-4"

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"})
    def test_factory_with_api_keys_from_env(self, mock_settings, mock_tool_manager):
        """Test that factory works with API keys from environment."""
        factory = ProviderFactory(mock_settings, mock_tool_manager)
        
        active_agents = dict(factory.iter_active_agents())
        
        # Providers should be created successfully
        assert len(active_agents) == 2


class TestProviderFactoryErrorHandling:
    """Test error handling in ProviderFactory."""

    def test_factory_handles_invalid_provider_name(self, mock_tool_manager):
        """Test that factory handles invalid provider names gracefully."""
        settings = Settings(
            orchestrator=MagicMock(dry_run=False),
            providers={
                "invalid_provider": ProviderConfig(
                    enabled=True,
                    model="test-model",
                ),
            },
            tools=[],
        )
        
        factory = ProviderFactory(settings, mock_tool_manager)
        
        # Should not crash, but may return empty list or skip invalid provider
        active_agents = list(factory.iter_active_agents())
        
        # Depending on implementation, might be 0 or might raise error
        # This test ensures it doesn't crash catastrophically
        assert isinstance(active_agents, list)

    def test_factory_with_partial_config(self, mock_tool_manager):
        """Test factory with minimal provider configuration."""
        settings = Settings(
            orchestrator=MagicMock(dry_run=False),
            providers={
                "openai": ProviderConfig(
                    enabled=True,
                    model="gpt-4",
                    # Missing temperature, max_steps (should use defaults)
                ),
            },
            tools=[],
        )
        
        factory = ProviderFactory(settings, mock_tool_manager)
        active_agents = list(factory.iter_active_agents())
        
        assert len(active_agents) == 1


class TestProviderToolManagerIntegration:
    """Test integration between providers and ToolManager."""

    def test_providers_receive_tool_manager(self, mock_settings, mock_tool_manager):
        """Test that all providers receive the tool manager instance."""
        factory = ProviderFactory(mock_settings, mock_tool_manager)
        
        active_agents = list(factory.iter_active_agents())
        
        for name, provider in active_agents:
            assert provider.tool_manager is mock_tool_manager

    def test_providers_share_same_tool_manager(self, mock_settings, mock_tool_manager):
        """Test that all providers share the same ToolManager instance."""
        factory = ProviderFactory(mock_settings, mock_tool_manager)
        
        active_agents = list(factory.iter_active_agents())
        
        # All providers should have the exact same tool_manager instance
        tool_managers = [provider.tool_manager for _, provider in active_agents]
        assert all(tm is mock_tool_manager for tm in tool_managers)

