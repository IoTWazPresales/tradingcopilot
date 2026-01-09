"""Unit tests for signal state mapping."""

import pytest

from app.signals.states import map_to_signal_state
from app.signals.types import ConsensusSignal, SignalState


class TestMapToSignalState:
    """Tests for map_to_signal_state function."""
    
    def test_strong_buy_threshold(self):
        """Direction >= 0.65 should map to STRONG_BUY."""
        consensus = ConsensusSignal(
            consensus_direction=0.70,
            consensus_confidence=0.8,
            agreement_score=0.9,
            horizon_signals=[],
            rationale=["test"],
        )
        state, rationale = map_to_signal_state(consensus)
        assert state == SignalState.STRONG_BUY
        assert "signal_strong_buy" in rationale
    
    def test_buy_threshold(self):
        """Direction in [0.20, 0.65) should map to BUY."""
        consensus = ConsensusSignal(
            consensus_direction=0.40,
            consensus_confidence=0.7,
            agreement_score=0.8,
            horizon_signals=[],
            rationale=["test"],
        )
        state, rationale = map_to_signal_state(consensus)
        assert state == SignalState.BUY
        assert "signal_buy" in rationale
    
    def test_neutral_threshold(self):
        """Direction in [-0.20, 0.20] should map to NEUTRAL."""
        consensus = ConsensusSignal(
            consensus_direction=0.05,
            consensus_confidence=0.5,
            agreement_score=0.6,
            horizon_signals=[],
            rationale=["test"],
        )
        state, rationale = map_to_signal_state(consensus)
        assert state == SignalState.NEUTRAL
        assert "signal_neutral" in rationale
    
    def test_sell_threshold(self):
        """Direction in (-0.65, -0.20] should map to SELL."""
        consensus = ConsensusSignal(
            consensus_direction=-0.35,
            consensus_confidence=0.7,
            agreement_score=0.8,
            horizon_signals=[],
            rationale=["test"],
        )
        state, rationale = map_to_signal_state(consensus)
        assert state == SignalState.SELL
        assert "signal_sell" in rationale
    
    def test_strong_sell_threshold(self):
        """Direction <= -0.65 should map to STRONG_SELL."""
        consensus = ConsensusSignal(
            consensus_direction=-0.75,
            consensus_confidence=0.8,
            agreement_score=0.9,
            horizon_signals=[],
            rationale=["test"],
        )
        state, rationale = map_to_signal_state(consensus)
        assert state == SignalState.STRONG_SELL
        assert "signal_strong_sell" in rationale
    
    def test_high_confidence_tagged(self):
        """High confidence should be tagged in rationale."""
        consensus = ConsensusSignal(
            consensus_direction=0.5,
            consensus_confidence=0.85,  # High
            agreement_score=0.9,
            horizon_signals=[],
            rationale=[],
        )
        state, rationale = map_to_signal_state(consensus)
        assert "high_confidence_signal" in rationale
    
    def test_low_confidence_tagged(self):
        """Low confidence should be tagged in rationale."""
        consensus = ConsensusSignal(
            consensus_direction=0.5,
            consensus_confidence=0.2,  # Low
            agreement_score=0.6,
            horizon_signals=[],
            rationale=[],
        )
        state, rationale = map_to_signal_state(consensus)
        assert "low_confidence_signal" in rationale
    
    def test_low_agreement_warning(self):
        """Low agreement should trigger warning."""
        consensus = ConsensusSignal(
            consensus_direction=0.5,
            consensus_confidence=0.7,
            agreement_score=0.4,  # Low agreement
            horizon_signals=[],
            rationale=[],
        )
        state, rationale = map_to_signal_state(consensus)
        assert "low_agreement_warning" in rationale
    
    def test_boundary_conditions(self):
        """Test exact boundary values."""
        # Exact threshold values
        test_cases = [
            (0.65, SignalState.STRONG_BUY),
            (0.20, SignalState.BUY),
            (0.0, SignalState.NEUTRAL),
            (-0.19, SignalState.NEUTRAL),  # Just inside neutral range
            (-0.20, SignalState.SELL),     # Exact boundary is SELL
            (-0.65, SignalState.STRONG_SELL),
        ]
        
        for direction, expected_state in test_cases:
            consensus = ConsensusSignal(
                consensus_direction=direction,
                consensus_confidence=0.7,
                agreement_score=0.8,
                horizon_signals=[],
                rationale=[],
            )
            state, _ = map_to_signal_state(consensus)
            assert state == expected_state, f"Direction {direction} should map to {expected_state}"

