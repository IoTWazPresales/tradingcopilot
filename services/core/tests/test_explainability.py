"""Unit tests for Phase 3 explainability layer."""

import pytest

from app.signals.rationale import categorize_rationale, build_explanation_object, format_explanation


class TestRationaleTaxonomy:
    """Tests for rationale categorization."""
    
    def test_categorize_drivers(self):
        """Strong agreement should be categorized as driver."""
        tags = ["strong_agreement", "majority_bullish"]
        result = categorize_rationale(tags)
        
        assert len(result["drivers"]) == 2
        assert len(result["risks"]) == 0
        assert "Strong alignment across multiple timeframes" in result["drivers"]
        assert "Majority of timeframes show bullish bias" in result["drivers"]
    
    def test_categorize_risks(self):
        """Conflicting signals should be categorized as risks."""
        tags = ["conflicting_signals", "low_confidence_signal"]
        result = categorize_rationale(tags)
        
        assert len(result["risks"]) == 2
        assert len(result["drivers"]) == 0
        assert "Timeframes show conflicting directional bias" in result["risks"]
    
    def test_categorize_notes(self):
        """Volatility info should be categorized as notes."""
        tags = ["1h_high_volatility", "1h_low_confidence"]
        result = categorize_rationale(tags)
        
        assert len(result["notes"]) == 2
        assert len(result["drivers"]) == 0
        assert len(result["risks"]) == 0
    
    def test_mixed_categories(self):
        """Mixed tags should be separated correctly."""
        tags = [
            "strong_agreement",  # driver
            "conflicting_signals",  # risk
            "1h_high_volatility",  # note
        ]
        result = categorize_rationale(tags)
        
        assert len(result["drivers"]) == 1
        assert len(result["risks"]) == 1
        assert len(result["notes"]) == 1
    
    def test_unknown_tags(self):
        """Unknown tags should be treated as notes."""
        tags = ["unknown_tag_xyz"]
        result = categorize_rationale(tags)
        
        assert len(result["notes"]) == 1
        assert "Unknown rationale: unknown_tag_xyz" in result["notes"]
    
    def test_empty_tags(self):
        """Empty tag list should return empty categories."""
        tags = []
        result = categorize_rationale(tags)
        
        assert result["drivers"] == []
        assert result["risks"] == []
        assert result["notes"] == []


class TestExplanationFormatting:
    """Tests for explanation formatting."""
    
    def test_format_with_drivers(self):
        """Should format drivers correctly."""
        text = format_explanation(
            drivers=["Strong bullish momentum", "High confidence"],
            risks=[],
            notes=[],
        )
        
        assert "Drivers:" in text
        assert "Strong bullish momentum" in text
        assert "High confidence" in text
    
    def test_format_with_risks(self):
        """Should format risks correctly."""
        text = format_explanation(
            drivers=[],
            risks=["Conflicting signals", "Low data quality"],
            notes=[],
        )
        
        assert "Risks:" in text
        assert "Conflicting signals" in text
    
    def test_format_mixed(self):
        """Should format mixed categories."""
        text = format_explanation(
            drivers=["Strong trend"],
            risks=["High volatility"],
            notes=["Recent data"],
        )
        
        assert "Drivers:" in text
        assert "Risks:" in text
        # Notes may or may not be included depending on space
    
    def test_format_empty(self):
        """Should handle empty lists."""
        text = format_explanation([], [], [])
        assert text == "No explanation available."
    
    def test_max_items_limit(self):
        """Should respect max_items limit."""
        drivers = ["Item 1", "Item 2", "Item 3", "Item 4", "Item 5", "Item 6"]
        text = format_explanation(drivers, [], [], max_items=3)
        
        assert "Item 1" in text
        assert "Item 2" in text
        assert "Item 3" in text
        assert "Item 6" not in text  # Should be truncated


class TestBuildExplanationObject:
    """Tests for complete explanation building."""
    
    def test_deterministic_output(self):
        """Same tags should always produce same explanation."""
        tags = ["strong_agreement", "majority_bullish", "high_confidence_signal"]
        
        result1 = build_explanation_object(tags)
        result2 = build_explanation_object(tags)
        
        assert result1 == result2
        assert result1["drivers"] == result2["drivers"]
    
    def test_bullish_signal_explanation(self):
        """Bullish signal should have appropriate drivers."""
        tags = [
            "strong_agreement",
            "majority_bullish",
            "1h_strong_bullish",
            "high_confidence_signal",
            "signal_buy",
            "long_position",
        ]
        
        result = build_explanation_object(tags)
        
        assert len(result["drivers"]) == 6
        assert len(result["risks"]) == 0
        assert "Strong alignment across multiple timeframes" in result["drivers"]
    
    def test_conflicting_signal_explanation(self):
        """Conflicting signal should have risks."""
        tags = [
            "weak_agreement",
            "conflicting_signals",
            "short_term_bullish_long_term_bearish",
            "low_agreement_warning",
        ]
        
        result = build_explanation_object(tags)
        
        assert len(result["risks"]) == 4
        # Check that risk messages are present (may have additional details)
        risk_text = " ".join(result["risks"])
        assert "Weak agreement" in risk_text
        assert "Short-term uptrend conflicts with long-term downtrend" in risk_text
    
    def test_neutral_signal_explanation(self):
        """Neutral signal should reflect mixed or weak signals."""
        tags = [
            "signal_neutral",
            "mixed_directions",
            "1h_neutral",
            "no_position_neutral",
        ]
        
        result = build_explanation_object(tags)
        
        assert len(result["risks"]) >= 3  # Most neutral tags are risks
        risk_text = " ".join(result["risks"])
        assert "Signal strength within neutral range" in risk_text


class TestExplanationDeterminism:
    """Ensure explanations are deterministic."""
    
    def test_same_input_same_output_repeated(self):
        """Run same input multiple times, verify identical output."""
        tags = ["strong_agreement", "majority_bullish", "1h_weak_bullish"]
        
        results = [build_explanation_object(tags) for _ in range(10)]
        
        # All results should be identical
        for result in results[1:]:
            assert result == results[0]
    
    def test_order_independence(self):
        """Tag order should not affect categorization (though it may affect display order)."""
        tags1 = ["strong_agreement", "majority_bullish", "signal_buy"]
        tags2 = ["signal_buy", "strong_agreement", "majority_bullish"]
        
        result1 = build_explanation_object(tags1)
        result2 = build_explanation_object(tags2)
        
        # Categories should have same items (may be in different order)
        assert set(result1["drivers"]) == set(result2["drivers"])
        assert set(result1["risks"]) == set(result2["risks"])
        assert set(result1["notes"]) == set(result2["notes"])


class TestHorizonSpecificTags:
    """Test horizon-specific rationale tags."""
    
    def test_bullish_horizon_tags(self):
        """All horizon bullish tags should be drivers."""
        horizons = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
        
        for horizon in horizons:
            tags = [f"{horizon}_strong_bullish", f"{horizon}_weak_bullish"]
            result = categorize_rationale(tags)
            
            assert len(result["drivers"]) == 2, f"Failed for {horizon}"
            assert len(result["risks"]) == 0
    
    def test_bearish_horizon_tags(self):
        """All horizon bearish tags should be drivers."""
        horizons = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
        
        for horizon in horizons:
            tags = [f"{horizon}_strong_bearish", f"{horizon}_weak_bearish"]
            result = categorize_rationale(tags)
            
            assert len(result["drivers"]) == 2, f"Failed for {horizon}"
    
    def test_neutral_horizon_tags(self):
        """All horizon neutral tags should be risks."""
        horizons = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
        
        for horizon in horizons:
            tags = [f"{horizon}_neutral"]
            result = categorize_rationale(tags)
            
            assert len(result["risks"]) == 1, f"Failed for {horizon}"
    
    def test_volatility_tags(self):
        """Volatility tags should be notes."""
        horizons = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
        
        for horizon in horizons:
            tags = [f"{horizon}_high_volatility", f"{horizon}_low_volatility"]
            result = categorize_rationale(tags)
            
            assert len(result["notes"]) == 2, f"Failed for {horizon}"
            assert len(result["drivers"]) == 0
            assert len(result["risks"]) == 0

