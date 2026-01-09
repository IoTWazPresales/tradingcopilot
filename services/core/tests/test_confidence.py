"""Unit tests for adaptive confidence scoring."""

import pytest

from app.signals.confidence import compute_confidence, compute_continuity_score


class TestComputeConfidence:
    """Tests for compute_confidence function."""
    
    def test_few_bars_low_confidence(self):
        """Few bars should give low confidence."""
        confidence = compute_confidence(
            horizon="1h",
            n_bars=5,  # Very few
            continuity_score=1.0,
            volatility=0.02,
        )
        assert confidence < 0.25, "Few bars should have low confidence"
    
    def test_many_bars_high_confidence(self):
        """Many bars with good continuity should give high confidence."""
        confidence = compute_confidence(
            horizon="1h",
            n_bars=100,  # More than expected (48)
            continuity_score=1.0,
            volatility=0.015,  # Low volatility
        )
        assert confidence > 0.7, "Many bars + good continuity should have high confidence"
    
    def test_gaps_reduce_confidence(self):
        """Gaps in data should reduce confidence."""
        confidence_good = compute_confidence(
            horizon="1h",
            n_bars=50,
            continuity_score=1.0,  # Perfect
            volatility=0.02,
        )
        confidence_gappy = compute_confidence(
            horizon="1h",
            n_bars=50,
            continuity_score=0.6,  # Gappy
            volatility=0.02,
        )
        assert confidence_gappy < confidence_good, "Gaps should reduce confidence"
    
    def test_high_volatility_reduces_confidence(self):
        """Extreme volatility should reduce confidence."""
        confidence_stable = compute_confidence(
            horizon="1h",
            n_bars=50,
            continuity_score=1.0,
            volatility=0.01,  # Low
        )
        confidence_volatile = compute_confidence(
            horizon="1h",
            n_bars=50,
            continuity_score=1.0,
            volatility=0.10,  # High
        )
        assert confidence_volatile < confidence_stable, "High volatility should reduce confidence"
    
    def test_confidence_bounded(self):
        """Confidence should always be in [0, 1]."""
        # Extreme low
        conf_low = compute_confidence("1h", 0, 0.0, 1.0)
        assert 0.0 <= conf_low <= 1.0
        
        # Extreme high
        conf_high = compute_confidence("1h", 1000, 1.0, 0.001)
        assert 0.0 <= conf_high <= 1.0
    
    def test_smooth_increase_with_bars(self):
        """Confidence should increase smoothly as bars increase."""
        confidences = []
        for n_bars in [10, 20, 30, 40, 50, 60, 80, 100]:
            conf = compute_confidence("1h", n_bars, 1.0, 0.02)
            confidences.append(conf)
        
        # Should be monotonically increasing
        for i in range(len(confidences) - 1):
            assert confidences[i] <= confidences[i + 1], "Confidence should increase with more bars"


class TestComputeContinuityScore:
    """Tests for compute_continuity_score function."""
    
    def test_perfect_continuity(self):
        """Regular intervals should give perfect score."""
        bars = [
            {"ts": 1000},
            {"ts": 1060},  # +60s
            {"ts": 1120},  # +60s
            {"ts": 1180},  # +60s
        ]
        score = compute_continuity_score(bars)
        assert score == 1.0, "Perfect intervals should have score 1.0"
    
    def test_single_gap_penalty(self):
        """Single gap should reduce score."""
        bars = [
            {"ts": 1000},
            {"ts": 1060},
            {"ts": 1120},
            {"ts": 1300},  # Gap: 180s instead of 60s
            {"ts": 1360},
        ]
        score = compute_continuity_score(bars)
        assert 0.0 < score < 1.0, "Gap should reduce score"
        assert score >= 0.85, "Single gap shouldn't penalize too heavily"
    
    def test_multiple_gaps_more_penalty(self):
        """Multiple gaps should reduce score more."""
        bars_one_gap = [
            {"ts": 1000},
            {"ts": 1060},
            {"ts": 1120},
            {"ts": 1300},  # Gap: 180 instead of 60
            {"ts": 1360},
        ]
        bars_two_gaps = [
            {"ts": 1000},
            {"ts": 1060},
            {"ts": 1300},  # Gap: 240 instead of 60
            {"ts": 1360},
            {"ts": 1600},  # Gap: 240 instead of 60
        ]
        score_one = compute_continuity_score(bars_one_gap)
        score_two = compute_continuity_score(bars_two_gaps)
        assert score_two < score_one, "More gaps should reduce score more"
    
    def test_non_monotonic_suspicious(self):
        """Non-monotonic timestamps should give low score."""
        bars = [
            {"ts": 1000},
            {"ts": 1060},
            {"ts": 1050},  # Out of order
            {"ts": 1120},
        ]
        score = compute_continuity_score(bars)
        assert score <= 0.5, "Non-monotonic should be suspicious"
    
    def test_too_few_bars_returns_one(self):
        """Too few bars to assess should return 1.0."""
        bars = [{"ts": 1000}]
        score = compute_continuity_score(bars)
        assert score == 1.0, "Single bar should return 1.0"

