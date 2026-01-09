"""Unit tests for feature extraction."""

import pytest

from app.signals.features import compute_direction_score, compute_strength, extract_features


class TestExtractFeatures:
    """Tests for extract_features function."""
    
    def test_no_bars_returns_neutral(self):
        """Empty bars should return neutral features."""
        features = extract_features("1h", [])
        assert features.n_bars == 0
        assert features.momentum == 0.0
        assert features.volatility == 0.0
        assert features.trend_direction == 0.0
    
    def test_uptrend_positive_momentum(self):
        """Rising prices should give positive momentum."""
        bars = [
            {"close": 100, "high": 101, "low": 99},
            {"close": 102, "high": 103, "low": 101},
            {"close": 104, "high": 105, "low": 103},
            {"close": 106, "high": 107, "low": 105},
            {"close": 108, "high": 109, "low": 107},
        ]
        features = extract_features("1h", bars)
        assert features.momentum > 0, "Uptrend should have positive momentum"
        assert features.trend_direction == 1.0
    
    def test_downtrend_negative_momentum(self):
        """Falling prices should give negative momentum."""
        bars = [
            {"close": 108, "high": 109, "low": 107},
            {"close": 106, "high": 107, "low": 105},
            {"close": 104, "high": 105, "low": 103},
            {"close": 102, "high": 103, "low": 101},
            {"close": 100, "high": 101, "low": 99},
        ]
        features = extract_features("1h", bars)
        assert features.momentum < 0, "Downtrend should have negative momentum"
        assert features.trend_direction == -1.0
    
    def test_flat_market_neutral_momentum(self):
        """Sideways prices should give near-zero momentum."""
        bars = [
            {"close": 100, "high": 101, "low": 99},
            {"close": 100.5, "high": 101.5, "low": 99.5},
            {"close": 99.8, "high": 101, "low": 98.8},
            {"close": 100.2, "high": 101.2, "low": 99.2},
        ]
        features = extract_features("1h", bars)
        assert abs(features.momentum) < 0.3, "Flat market should have low momentum"
    
    def test_volatile_market_high_volatility(self):
        """Large price swings should give high volatility."""
        bars = [
            {"close": 100, "high": 105, "low": 95},
            {"close": 95, "high": 100, "low": 90},
            {"close": 105, "high": 110, "low": 100},
            {"close": 98, "high": 105, "low": 93},
        ]
        features = extract_features("1h", bars)
        assert features.volatility > 0.02, "Volatile market should have high volatility"
    
    def test_feature_set_structure(self):
        """Feature set should have all required fields."""
        bars = [
            {"close": 100, "high": 101, "low": 99},
            {"close": 102, "high": 103, "low": 101},
        ]
        features = extract_features("1h", bars)
        assert features.horizon == "1h"
        assert features.n_bars == 2
        assert hasattr(features, "momentum")
        assert hasattr(features, "volatility")
        assert hasattr(features, "trend_direction")
        assert hasattr(features, "stability")
        assert hasattr(features, "last_close")
        assert hasattr(features, "first_close")
        assert hasattr(features, "avg_range")


class TestComputeDirectionScore:
    """Tests for compute_direction_score function."""
    
    def test_positive_momentum_positive_score(self):
        """Positive momentum should give positive score."""
        from app.signals.types import FeatureSet
        
        features = FeatureSet(
            horizon="1h",
            n_bars=50,
            momentum=0.5,
            volatility=0.01,
            trend_direction=1.0,
            stability=0.8,
            last_close=105,
            first_close=100,
            avg_range=2.0,
        )
        score = compute_direction_score(features)
        assert score > 0, "Positive momentum should give positive score"
    
    def test_low_stability_reduces_score(self):
        """Low stability should reduce score magnitude."""
        from app.signals.types import FeatureSet
        
        features_stable = FeatureSet(
            horizon="1h",
            n_bars=50,
            momentum=0.6,
            volatility=0.01,
            trend_direction=1.0,
            stability=0.9,
            last_close=105,
            first_close=100,
            avg_range=1.0,
        )
        features_unstable = FeatureSet(
            horizon="1h",
            n_bars=50,
            momentum=0.6,
            volatility=0.08,
            trend_direction=1.0,
            stability=0.3,
            last_close=105,
            first_close=100,
            avg_range=5.0,
        )
        score_stable = compute_direction_score(features_stable)
        score_unstable = compute_direction_score(features_unstable)
        assert abs(score_stable) > abs(score_unstable), "Low stability should reduce score"
    
    def test_score_bounded(self):
        """Direction score should be in [-1, 1]."""
        from app.signals.types import FeatureSet
        
        features = FeatureSet(
            horizon="1h",
            n_bars=50,
            momentum=0.999,  # Extreme
            volatility=0.0,
            trend_direction=1.0,
            stability=1.0,
            last_close=200,
            first_close=100,
            avg_range=2.0,
        )
        score = compute_direction_score(features)
        assert -1.0 <= score <= 1.0, "Score must be bounded to [-1, 1]"


class TestComputeStrength:
    """Tests for compute_strength function."""
    
    def test_high_momentum_high_strength(self):
        """High momentum should give high strength."""
        from app.signals.types import FeatureSet
        
        features = FeatureSet(
            horizon="1h",
            n_bars=50,
            momentum=0.8,
            volatility=0.01,
            trend_direction=1.0,
            stability=0.9,
            last_close=110,
            first_close=100,
            avg_range=1.5,
        )
        strength = compute_strength(features)
        assert strength > 0.5, "High momentum should give high strength"
    
    def test_strength_direction_independent(self):
        """Strength should be same for positive and negative momentum of same magnitude."""
        from app.signals.types import FeatureSet
        
        features_up = FeatureSet(
            horizon="1h",
            n_bars=50,
            momentum=0.6,
            volatility=0.01,
            trend_direction=1.0,
            stability=0.8,
            last_close=106,
            first_close=100,
            avg_range=1.0,
        )
        features_down = FeatureSet(
            horizon="1h",
            n_bars=50,
            momentum=-0.6,
            volatility=0.01,
            trend_direction=-1.0,
            stability=0.8,
            last_close=94,
            first_close=100,
            avg_range=1.0,
        )
        strength_up = compute_strength(features_up)
        strength_down = compute_strength(features_down)
        assert abs(strength_up - strength_down) < 0.01, "Strength should be direction-independent"
    
    def test_strength_bounded(self):
        """Strength should be in [0, 1]."""
        from app.signals.types import FeatureSet
        
        features = FeatureSet(
            horizon="1h",
            n_bars=50,
            momentum=0.999,
            volatility=0.0,
            trend_direction=1.0,
            stability=1.0,
            last_close=200,
            first_close=100,
            avg_range=2.0,
        )
        strength = compute_strength(features)
        assert 0.0 <= strength <= 1.0, "Strength must be bounded to [0, 1]"

