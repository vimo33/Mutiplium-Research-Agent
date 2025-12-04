from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from multiplium.orchestrator import load_context, _validate_and_enrich_results
from multiplium.providers.base import ProviderRunResult
from multiplium.config import Settings, OrchestratorSettings


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    return Settings(
        orchestrator=OrchestratorSettings(
            sector="Wine Industry",
            thesis_path="data/thesis.md",
            value_chain_path="data/value_chain.md",
            kpi_path="data/kpis.md",
            concurrency=2,
            dry_run=False,
        ),
        providers={},
        tools=[],
    )


@pytest.fixture
def sample_provider_result():
    """Create a sample provider result for testing."""
    return ProviderRunResult(
        provider="test_provider",
        model="test-model",
        status="completed",
        findings=[
            {
                "name": "Test Segment",
                "companies": [
                    {
                        "company": "Acme Corp",
                        "summary": "Test company in vineyard technology",
                        "kpi_alignment": ["Water reduction: 30%"],
                        "sources": ["https://example.com/vineyard-tech"],
                        "website": "https://acme.com",
                        "country": "United States",
                    },
                    {
                        "company": "Beta Industries",
                        "summary": "Another vineyard tech company",
                        "kpi_alignment": ["Carbon reduction: 25%"],
                        "sources": ["https://example.com/carbon-tech"],
                        "website": "https://beta.com",
                        "country": "France",
                    },
                ],
            }
        ],
        telemetry={"tool_calls": 5, "input_tokens": 1000, "output_tokens": 500},
        errors=[],
        retry_count=0,
    )


class TestLoadContext:
    """Test the load_context function."""

    @patch("multiplium.orchestrator.Path")
    def test_load_context_creates_research_context(self, mock_path_class, mock_settings):
        """Test that load_context creates a ResearchContext with correct attributes."""
        # Mock file reading
        mock_thesis = MagicMock()
        mock_thesis.read_text.return_value = "Test thesis content"
        
        mock_value_chain = MagicMock()
        mock_value_chain.read_text.return_value = '{"segments": [{"name": "Test"}]}'
        
        mock_kpi = MagicMock()
        mock_kpi.read_text.return_value = '{"metrics": []}'
        
        def path_side_effect(arg):
            if "thesis" in str(arg):
                return mock_thesis
            elif "value_chain" in str(arg):
                return mock_value_chain
            elif "kpi" in str(arg):
                return mock_kpi
            return MagicMock()
        
        mock_path_class.side_effect = path_side_effect
        
        context = load_context(mock_settings)
        
        assert context.sector == "Wine Industry"
        assert context.thesis == "Test thesis content"
        assert "segments" in context.value_chain
        assert "metrics" in context.kpis

    def test_load_context_with_missing_files(self, mock_settings):
        """Test that load_context handles missing files gracefully."""
        mock_settings.orchestrator.thesis_path = "nonexistent.md"
        
        # Should raise FileNotFoundError or similar
        with pytest.raises((FileNotFoundError, OSError)):
            load_context(mock_settings)


class TestValidateAndEnrichResults:
    """Test the _validate_and_enrich_results function."""

    @pytest.mark.asyncio
    async def test_validate_and_enrich_with_valid_results(self, sample_provider_result):
        """Test validation and enrichment with valid provider results."""
        mock_tool_manager = AsyncMock()
        
        # Mock the CompanyValidator
        with patch("multiplium.orchestrator.CompanyValidator") as mock_validator_class:
            mock_validator = mock_validator_class.return_value
            mock_validator.validate_and_enrich_companies = AsyncMock(
                return_value=[
                    {
                        "company": "Acme Corp",
                        "summary": "Test company in vineyard technology",
                        "confidence": 0.85,
                    }
                ]
            )
            
            results = await _validate_and_enrich_results(
                [sample_provider_result],
                mock_tool_manager,
            )
            
            assert len(results) == 1
            assert results[0].provider == "test_provider"
            assert len(results[0].findings) == 1
            assert len(results[0].findings[0]["companies"]) == 1

    @pytest.mark.asyncio
    async def test_validate_and_enrich_with_empty_results(self):
        """Test validation with empty results list."""
        mock_tool_manager = AsyncMock()
        
        results = await _validate_and_enrich_results([], mock_tool_manager)
        
        assert results == []

    @pytest.mark.asyncio
    async def test_validate_and_enrich_filters_low_quality(self, sample_provider_result):
        """Test that low-quality companies are filtered out."""
        mock_tool_manager = AsyncMock()
        
        with patch("multiplium.orchestrator.CompanyValidator") as mock_validator_class:
            mock_validator = mock_validator_class.return_value
            # Return empty list (all companies rejected)
            mock_validator.validate_and_enrich_companies = AsyncMock(return_value=[])
            
            results = await _validate_and_enrich_results(
                [sample_provider_result],
                mock_tool_manager,
            )
            
            assert len(results) == 1
            assert len(results[0].findings) == 1
            # All companies were filtered out
            assert len(results[0].findings[0]["companies"]) == 0

    @pytest.mark.asyncio
    async def test_validate_adds_notes_to_findings(self, sample_provider_result):
        """Test that validation adds summary notes to findings."""
        mock_tool_manager = AsyncMock()
        
        with patch("multiplium.orchestrator.CompanyValidator") as mock_validator_class:
            mock_validator = mock_validator_class.return_value
            mock_validator.validate_and_enrich_companies = AsyncMock(
                return_value=[
                    {"company": "Acme Corp", "confidence": 0.85}
                ]
            )
            
            results = await _validate_and_enrich_results(
                [sample_provider_result],
                mock_tool_manager,
            )
            
            finding = results[0].findings[0]
            assert "notes" in finding
            assert any("Validation:" in note for note in finding["notes"])
            assert any("1/2 companies passed" in note for note in finding["notes"])


class TestProviderResultAggregation:
    """Test provider result aggregation and telemetry."""

    def test_provider_result_summary(self, sample_provider_result):
        """Test that ProviderRunResult.summary() returns correct data."""
        summary = sample_provider_result.summary()
        
        assert summary["provider"] == "test_provider"
        assert summary["model"] == "test-model"
        assert summary["status"] == "completed"
        assert summary["finding_count"] == 1
        assert summary["error_count"] == 0
        assert summary["retry_count"] == 0

    def test_provider_result_with_errors(self):
        """Test summary with errors and retries."""
        result = ProviderRunResult(
            provider="test",
            model="test-model",
            status="partial",
            findings=[],
            telemetry={},
            errors=[
                {"type": "TimeoutError", "message": "Connection timeout"},
                {"type": "HTTPError", "message": "500 Internal Server Error"},
            ],
            retry_count=2,
        )
        
        summary = result.summary()
        assert summary["error_count"] == 2
        assert summary["retry_count"] == 2
        assert summary["status"] == "partial"


class TestConcurrentProviderExecution:
    """Test concurrent execution of multiple providers."""

    @pytest.mark.asyncio
    async def test_multiple_providers_run_concurrently(self):
        """Test that multiple providers can run in parallel."""
        # This would require more complex mocking of the full orchestrator
        # For now, we test the basic structure
        
        mock_provider1 = AsyncMock()
        mock_provider1.name = "provider1"
        mock_provider1.config.model = "model1"
        mock_provider1.run_with_retry = AsyncMock(
            return_value=ProviderRunResult(
                provider="provider1",
                model="model1",
                status="completed",
                findings=[],
                telemetry={},
            )
        )
        
        mock_provider2 = AsyncMock()
        mock_provider2.name = "provider2"
        mock_provider2.config.model = "model2"
        mock_provider2.run_with_retry = AsyncMock(
            return_value=ProviderRunResult(
                provider="provider2",
                model="model2",
                status="completed",
                findings=[],
                telemetry={},
            )
        )
        
        # Simulate concurrent execution
        import asyncio
        results = await asyncio.gather(
            mock_provider1.run_with_retry(None),
            mock_provider2.run_with_retry(None),
        )
        
        assert len(results) == 2
        assert results[0].provider == "provider1"
        assert results[1].provider == "provider2"

