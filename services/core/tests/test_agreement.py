"""Unit tests for multi-horizon agreement logic."""

import pytest

from app.signals.agreement import compute_agreement_score, compute_consensus, compute_horizon_signal
from app.signals.types import HorizonSignal, FeatureSet


class TestComputeHorizonSignal:
    """Tests for compute_horizon_signal function."""
    
    def test_bullish_bars_bullish_signal(self):
        """Bullish bars should produce bullish signal."""
        bars = [
            {"ts": 1000, "close": 100, "high": 101, "low": 99, "open": 99.5},
            {"ts": 1060, "close": 102, "high": 103, "low": 101, "open": 101.5},
            {"ts": 1120, "close": 104, "high": 105, "low": 103, "open": 103.5},
            {"ts": 1180, "close": 106, "high": 107, "low": 105, "open": 105.5},
        ]
        signal = compute_horizon_signal("1h", bars)
        assert signal.direction_score > 0, "Bullish bars should have positive direction"
        assert "1h_" in signal.rationale[0], "Should have horizon-specific rationale"
    
    def test_bearish_bars_bearish_signal(self):
        """Bearish bars should produce bearish signal."""
        bars = [
            {"ts": 1000, "close": 106, "high": 107, "low": 105, "open": 105.5},
            {"ts": 1060, "close": 104, "high": 105, "low": 103, "open": 103.5},
            {"ts": 1120, "close": 102, "high": 103, "low": 101, "open": 101.5},
            {"ts": 1180, "close": 100, "high": 101, "low": 99, "open": 99.5},
        ]
        signal = compute_horizon_signal("1h", bars)
        assert signal.direction_score < 0, "Bearish bars should have negative direction"
    
    def test_signal_has_confidence(self):
        """Signal should include confidence score."""
        bars = [
            {"ts": 1000, "close": 100, "high": 101, "low": 99, "open": 99.5},
            {"ts": 1060, "close": 101, "high": 102, "low": 100, "open": 100.5},
        ]
        signal = compute_horizon_signal("1m", bars)
        assert 0.0 <= signal.confidence <= 1.0, "Confidence should be bounded"
        assert signal.confidence > 0, "Should have some confidence with data"


class TestComputeConsensus:
    """Tests for compute_consensus function."""
    
    def test_aligned_bullish_horizons_bullish_consensus(self):
        """All bullish horizons should give bullish consensus."""
        signals = [
            HorizonSignal(
                horizon="1m",
                direction_score=0.6,
                strength=0.7,
                confidence=0.8,
                features=FeatureSet("1m", 50, 0.5, 0.02, 1.0, 0.8, 105, 100, 1.5),
                rationale=["1m_strong_bullish"],
            ),
            HorizonSignal(
                horizon="1h",
                direction_score=0.7,
                strength=0.8,
                confidence=0.9,
                features=FeatureSet("1h", 50, 0.6, 0.01, 1.0, 0.9, 110, 100, 2.0),
                rationale=["1h_strong_bullish"],
            ),
            HorizonSignal(
                horizon="1d",
                direction_score=0.8,
                strength=0.9,
                confidence=0.95,
                features=FeatureSet("1d", 30, 0.7, 0.015, 1.0, 0.85, 120, 100, 3.0),
                rationale=["1d_strong_bullish"],
            ),
        ]
        consensus = compute_consensus(signals)
        assert consensus.consensus_direction > 0.5, "Aligned bullish should give strong bullish consensus"
        assert consensus.agreement_score > 0.7, "Aligned signals should have high agreement"
        assert "strong_agreement" in consensus.rationale or "moderate_agreement" in consensus.rationale
    
    def test_mixed_horizons_neutral_or_weak(self):
        """Mixed bullish/bearish should give neutral or weak signal."""
        signals = [
            HorizonSignal(
                horizon="1m",
                direction_score=0.5,  # Bullish
                strength=0.6,
                confidence=0.7,
                features=FeatureSet("1m", 50, 0.4, 0.02, 1.0, 0.8, 105, 100, 1.5),
                rationale=["1m_weak_bullish"],
            ),
            HorizonSignal(
                horizon="1h",
                direction_score=-0.4,  # Bearish
                strength=0.5,
                confidence=0.7,
                features=FeatureSet("1h", 50, -0.3, 0.02, -1.0, 0.7, 95, 100, 2.0),
                rationale=["1h_weak_bearish"],
            ),
        ]
        consensus = compute_consensus(signals)
        assert abs(consensus.consensus_direction) < 0.5, "Mixed signals should not be extreme"
        assert consensus.agreement_score < 0.8, "Conflict should reduce agreement"
        assert "conflicting_signals" in consensus.rationale or "mixed_directions" in consensus.rationale
    
    def test_longer_horizons_weighted_more(self):
        """Longer horizons should have more influence on consensus."""
        # Short term bullish, long term bearish
        signals = [
            HorizonSignal(
                horizon="1m",
                direction_score=0.6,
                strength=0.7,
                confidence=0.8,
                features=FeatureSet("1m", 50, 0.5, 0.02, 1.0, 0.8, 105, 100, 1.5),
                rationale=["1m_strong_bullish"],
            ),
            HorizonSignal(
                horizon="1d",
                direction_score=-0.7,
                strength=0.8,
                confidence=0.9,
                features=FeatureSet("1d", 30, -0.6, 0.015, -1.0, 0.85, 90, 100, 3.0),
                rationale=["1d_strong_bearish"],
            ),
        ]
        consensus = compute_consensus(signals)
        # 1d has higher weight (2.5) vs 1m (0.5), so should pull consensus bearish
        # Note: Also weighted by confidence, but 1d has higher weight overall
        assert consensus.consensus_direction < 0.2, "Long-term bearish should dominate despite short-term bullish"
    
    def test_conflict_pattern_detected(self):
        """Short-term vs long-term conflict should be detected."""
        signals = [
            HorizonSignal(
                horizon="5m",
                direction_score=0.5,
                strength=0.6,
                confidence=0.7,
                features=FeatureSet("5m", 50, 0.4, 0.02, 1.0, 0.8, 105, 100, 1.5),
                rationale=["5m_weak_bullish"],
            ),
            HorizonSignal(
                horizon="1d",
                direction_score=-0.6,
                strength=0.7,
                confidence=0.8,
                features=FeatureSet("1d", 30, -0.5, 0.015, -1.0, 0.85, 90, 100, 3.0),
                rationale=["1d_strong_bearish"],
            ),
        ]
        consensus = compute_consensus(signals)
        rationale_str = " ".join(consensus.rationale)
        # Should detect this specific conflict pattern
        assert (
            "short_term_bullish_long_term_bearish" in rationale_str
            or "mixed_directions" in rationale_str
        ), "Should detect short-term vs long-term conflict"
    
    def test_no_signals_neutral_consensus(self):
        """Empty signal list should return neutral."""
        consensus = compute_consensus([])
        assert consensus.consensus_direction == 0.0
        assert consensus.consensus_confidence == 0.0
        assert "no_data" in consensus.rationale


class TestComputeAgreementScore:
    """Tests for compute_agreement_score function."""
    
    def test_perfect_agreement_high_score(self):
        """All signals at same direction should have high agreement."""
        signals = [
            HorizonSignal(
                horizon="1m",
                direction_score=0.7,
                strength=0.8,
                confidence=0.9,
                features=FeatureSet("1m", 50, 0.6, 0.02, 1.0, 0.8, 105, 100, 1.5),
                rationale=[],
            ),
            HorizonSignal(
                horizon="1h",
                direction_score=0.72,
                strength=0.85,
                confidence=0.92,
                features=FeatureSet("1h", 50, 0.65, 0.015, 1.0, 0.85, 106, 100, 2.0),
                rationale=[],
            ),
        ]
        consensus_dir = 0.71
        agreement = compute_agreement_score(signals, consensus_dir)
        assert agreement > 0.95, "Near-identical signals should have very high agreement"
    
    def test_opposite_signals_low_agreement(self):
        """Opposite signals should have low agreement."""
        signals = [
            HorizonSignal(
                horizon="1m",
                direction_score=0.8,
                strength=0.9,
                confidence=0.9,
                features=FeatureSet("1m", 50, 0.7, 0.02, 1.0, 0.8, 110, 100, 1.5),
                rationale=[],
            ),
            HorizonSignal(
                horizon="1h",
                direction_score=-0.8,
                strength=0.9,
                confidence=0.9,
                features=FeatureSet("1h", 50, -0.7, 0.015, -1.0, 0.85, 90, 100, 2.0),
                rationale=[],
            ),
        ]
        consensus_dir = 0.0  # Neutral from conflict
        agreement = compute_agreement_score(signals, consensus_dir)
        assert agreement <= 0.6, "Opposite signals should have low agreement"
    
    def test_empty_signals_returns_one(self):
        """Empty list should return 1.0 (no conflict)."""
        agreement = compute_agreement_score([], 0.0)
        assert agreement == 1.0

