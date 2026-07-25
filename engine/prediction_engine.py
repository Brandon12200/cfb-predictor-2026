"""
Core prediction engine for College Football Market Edge Platform.
Orchestrates factor calculations and generates contrarian predictions.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from config import config
from data.data_manager import data_manager
from factors.factor_registry import factor_registry
from utils.normalizer import normalizer
from engine.variance_detector import variance_detector

# ── Phase 3c calibration constants (PROPOSED — ratified in docs/CALIBRATION_LOG.md; frozen at the
# tag). Evidence class `reasoned`: NOT fit to the 2025 archive (its confidence/edge distributions
# are Bug-#7-contaminated, SPEC §3), set by stated argument on the model's own scale and
# structurally sanity-checked on the NEW model's dry-run output — never tuned to hit an ATS%. ───
#
# L4 — NO_BET floors. NO_BET fires when ANY of: the edge is below the (dynamic, confidence-aware)
# `min_edge_threshold` already computed for the pick; confidence is below the floor below; or the
# variance detector flags hard factor disagreement.
NO_BET_CONFIDENCE_FLOOR = 0.50          # = the B/C tier boundary → a bet is only ever tier A or B;
                                        # tier C (conf < 0.50) is therefore NO_BET, never a bet grade
NO_BET_VARIANCE_LEVELS = frozenset({'extreme'})        # variance_level that forces NO_BET
NO_BET_VARIANCE_ACTIONS = frozenset({'AVOID_OR_MINIMUM'})  # variance recommendation.action gate
#
# L3 — A/B/C confidence tiers, keyed off confidence_score. Boundaries are reasoned; the
# monotonic-ATS%-by-tier property is a structural sanity check on the NEW model's output, NOT a
# 2025-evidence gate (the archive confidence→ATS table is inadmissible, SPEC §3).
CONFIDENCE_TIER_A_MIN = 0.65            # A: strong-conviction bets
CONFIDENCE_TIER_B_MIN = 0.50            # B: standard; below B_MIN → tier C (thin, still a bet)


class PredictionEngine:
    """
    Core prediction engine that orchestrates the contrarian prediction process.
    
    The engine follows this flow:
    1. Fetch Vegas consensus spread
    2. Calculate all factor adjustments
    3. Apply adjustments to create contrarian prediction
    4. Assess edge size and confidence
    5. Generate insights and recommendations
    """
    
    def __init__(self):
        """Initialize prediction engine."""
        self.data_manager = data_manager
        self.factor_registry = factor_registry
        self.normalizer = normalizer
        
        # Performance tracking
        self.prediction_stats = {
            'total_predictions': 0,
            'successful_predictions': 0,
            'failed_predictions': 0,
            'avg_execution_time': 0.0
        }
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        self.logger.info("Prediction engine initialized")
    
    def generate_prediction(self, home_team: str, away_team: str, 
                          week: Optional[int] = None) -> Dict[str, Any]:
        """
        Generate a contrarian prediction for a given matchup.
        
        Args:
            home_team: Home team name (will be normalized)
            away_team: Away team name (will be normalized)
            week: Week number (optional)
            
        Returns:
            Dictionary with complete prediction results
        """
        start_time = datetime.now()
        
        try:
            # Normalize team names
            home_normalized = self.normalizer.normalize(home_team)
            away_normalized = self.normalizer.normalize(away_team)
            
            if not home_normalized or not away_normalized:
                return self._create_error_result(
                    home_team, away_team, week,
                    "Invalid team names - could not normalize"
                )
            
            if home_normalized == away_normalized:
                return self._create_error_result(
                    home_team, away_team, week,
                    "Home and away teams cannot be the same"
                )
            
            self.logger.info(f"Generating prediction: {away_normalized} @ {home_normalized} (Week {week})")
            
            # Step 1: Fetch comprehensive game context
            context = self.data_manager.get_game_context(home_normalized, away_normalized, week)
            
            # Step 2: Get Vegas consensus spread
            vegas_spread = context.get('vegas_spread')
            
            # CRITICAL: Cannot generate contrarian prediction without betting line
            if vegas_spread is None:
                self.logger.warning(f"No betting line available for {away_normalized} @ {home_normalized}")
                return self._create_error_result(
                    home_normalized, away_normalized, week,
                    "No betting line available - cannot calculate contrarian prediction"
                )
            
            # Step 2.5: Price the matchup with the in-house power rating (SPEC §6.3/§6.6) BEFORE
            # the factors run, so the L2 confirming-signal gate can read the model-vs-market BASE
            # gap. The gap remains a diagnostic for the model spread itself (§6.6); its NEW job in
            # 3c is to CONFIRM situational factors — and only the BASE gap may (D15: it excludes
            # schedule, so a physical/schedule factor is never confirmed by a gap containing its own
            # signal). The base gap is injected onto the context; the total gap never confirms.
            power_rating = self._compute_power_rating(
                home_normalized, away_normalized, week, vegas_spread, context)
            # The L2 gate needs the base gap in the SAME sign convention as factor values
            # (positive favours home). The diagnostic `model_vs_market_gap` is `base_spread −
            # vegas`, which is NEGATIVE when the model's team-quality read favours home more than
            # the market (a more-negative spread = more home-favoured) — the opposite convention.
            # So the confirmation gap is its negation, `vegas − base_spread`: positive ⇒ the base
            # read favours home, matching a positive situational factor value. (D15: base only.)
            _diag_gap = power_rating.get('model_vs_market_gap') if power_rating else None
            context['base_gap_favors_home'] = None if _diag_gap is None else round(-_diag_gap, 2)

            # Step 3: Calculate all factor adjustments (situational factors are gated by the
            # base gap injected above + physical-factor agreement, inside the registry).
            factor_results = self.factor_registry.calculate_all_factors(
                home_normalized, away_normalized, context
            )

            # Step 4: Generate contrarian prediction
            prediction_result = self._calculate_contrarian_prediction(
                vegas_spread, factor_results, context
            )

            # Step 4.5: Analyze factor variance for disagreement detection
            variance_analysis = variance_detector.analyze_factor_variance(factor_results)

            # Step 5: Build comprehensive result
            result = self._build_prediction_result(
                home_normalized, away_normalized, week,
                vegas_spread, factor_results, prediction_result, context, variance_analysis,
                power_rating
            )
            
            # Track successful prediction
            self.prediction_stats['successful_predictions'] += 1
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_execution_stats(execution_time)
            
            self.logger.info(f"Prediction completed successfully in {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error generating prediction: {e}")
            self.prediction_stats['failed_predictions'] += 1
            
            return self._create_error_result(
                home_team, away_team, week,
                f"Prediction failed: {str(e)}"
            )
        
        finally:
            self.prediction_stats['total_predictions'] += 1
    
    def _compute_power_rating(self, home: str, away: str, week: Optional[int],
                              vegas_spread: Optional[float],
                              context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Price the matchup with the in-house power rating and return the diagnostic
        fields (SPEC §6.3/§6.6). Reads ONLY the snapshot data already on `context`;
        ratings are recomputed (memoized by `snapshot_id`) so reruns are bit-identical.
        Returns None if the context wasn't snapshot-assembled (e.g. minimal test context)."""
        snapshot_id = context.get('snapshot_id')
        games = context.get('games')
        if not snapshot_id or games is None:
            return None
        try:
            from engine.matchup_pricer import compute_ratings_for_snapshot, price
            sp = context.get('sp_ratings', {})
            rp = context.get('returning_production', {})
            snap = {"meta": {"snapshot_id": snapshot_id},
                    "data": {"games": games, "sp_ratings": sp, "returning_production": rp}}
            ratings = compute_ratings_for_snapshot(snap)
            priced = price(
                home, away, ratings=ratings, season_games=games,
                venues=context.get('venues', {}), sp_ratings=sp, returning_production=rp,
                week=week, game_date=context.get('game_date'),
                neutral_site=bool(context.get('neutral_site')))
        except Exception as exc:  # noqa: BLE001 — diagnostic must never break a prediction
            self.logger.warning("Power-rating pricing failed for %s @ %s: %s", away, home, exc)
            return None

        # D15: the model-vs-market GAP used as a diagnostic and as any confirming signal is the
        # BASE gap (team quality only, excludes schedule) — so a schedule factor is never confirmed
        # by a gap containing the same schedule signal. The total gap is logged too, LABELED, and
        # must NOT be used to confirm a schedule/physical factor.
        base_gap = total_gap = None
        if vegas_spread is not None:
            base_gap = round(priced.base_spread - vegas_spread, 2)
            total_gap = round(priced.model_spread - vegas_spread, 2)
        return {
            'power_rating_spread': round(priced.model_spread, 2),        # total (full model spread)
            'power_rating_base_spread': round(priced.base_spread, 2),    # team quality only
            'model_vs_market_gap': base_gap,          # BASE gap (base_spread−vegas); the ONLY gap the L2
                                                      # confirming rule may derive from (it uses the
                                                      # factor-convention NEGATION, base_gap_favors_home)
            'model_vs_market_gap_total': total_gap,   # includes schedule — diagnostic only, never confirms
            'rating_uncertainty': round(priced.rating_uncertainty, 3),
            'power_rating_breakdown': {
                'home_rating': round(priced.home_rating, 1),
                'away_rating': round(priced.away_rating, 1),
                'rating_component': priced.rating_component,
                'home_field': priced.breakdown['hfa_points'],
                'base_margin': round(priced.base_margin, 2),
                'schedule_component': priced.schedule_component,
                'rating_signal_weight': priced.rating_signal_weight,
                'home_prior_source': priced.home_prior_source,
                'away_prior_source': priced.away_prior_source,
            },
            'power_rating_caveats': priced.caveats,
        }

    def _calculate_contrarian_prediction(self, vegas_spread: Optional[float],
                                       factor_results: Dict[str, Any],
                                       context: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate the contrarian prediction using factor adjustments."""
        # Get both additive and multiplicative adjustments
        total_adjustment = factor_results['summary']['total_adjustment']
        multiplicative_adjustment = factor_results['summary'].get('multiplicative_adjustment', 1.0)
        
        # If no Vegas spread available, can't make a contrarian prediction
        if vegas_spread is None:
            return {
                'contrarian_spread': None,
                'edge_size': None,
                'edge_direction': None,
                'has_edge': False,
                'prediction_type': 'NO_BETTING_DATA',
                'explanation': 'No betting line available for contrarian analysis'
            }
        
        # Apply factor adjustments to the Vegas line. The multiplicative modifier scales the
        # model's EDGE (its disagreement with the market), NOT the Vegas baseline (D19): sentiment
        # can amplify/dampen our edge, but it must never rescale the market's own number.
        contrarian_spread = vegas_spread + total_adjustment * multiplicative_adjustment
        
        # Calculate edge size (difference between Vegas and our prediction)
        edge_size = abs(contrarian_spread - vegas_spread)
        
        # Determine edge direction
        adjustment_diff = contrarian_spread - vegas_spread
        if adjustment_diff > 0:
            edge_direction = 'home'  # Our prediction favors home team more than Vegas
        elif adjustment_diff < 0:
            edge_direction = 'away'  # Our prediction favors away team more than Vegas
        else:
            edge_direction = 'neutral'
        
        # Adjust thresholds based on confidence and primary signals
        avg_confidence = factor_results['summary'].get('avg_confidence', 0.5)
        primary_signals = factor_results['summary'].get('primary_signals', 0)
        
        # Dynamic edge threshold based on confidence
        if primary_signals >= 2 and avg_confidence >= 0.7:
            min_edge_threshold = 0.75  # Lower threshold for high-confidence primary signals
        elif primary_signals >= 1 or avg_confidence >= 0.6:
            min_edge_threshold = 1.0  # Standard threshold
        else:
            min_edge_threshold = 1.5  # Higher threshold for low-confidence signals
        
        has_edge = edge_size >= min_edge_threshold
        
        # Classify prediction type with confidence-based adjustments
        if primary_signals >= 2 and edge_size >= 2.5:
            prediction_type = 'VERY_STRONG_CONTRARIAN'
        elif edge_size >= 3.0 or (edge_size >= 2.0 and avg_confidence >= 0.7):
            prediction_type = 'STRONG_CONTRARIAN'
        elif edge_size >= 1.5 or (edge_size >= 1.0 and avg_confidence >= 0.6):
            prediction_type = 'MODERATE_CONTRARIAN'
        elif edge_size >= 0.5:
            prediction_type = 'SLIGHT_CONTRARIAN'
        else:
            prediction_type = 'CONSENSUS_ALIGNMENT'
        
        return {
            'contrarian_spread': contrarian_spread,
            'edge_size': edge_size,
            'adjustment_diff': adjustment_diff,
            'multiplicative_effect': multiplicative_adjustment,
            'edge_direction': edge_direction,
            'has_edge': has_edge,
            'prediction_type': prediction_type,
            'total_adjustment': total_adjustment,
            'min_edge_threshold': min_edge_threshold
        }
    
    def _evaluate_no_bet(self, prediction_result: Dict[str, Any], confidence_score: float,
                         variance_analysis: Optional[Dict[str, Any]]) -> tuple:
        """L4 NO_BET evaluation (SPEC §7.4). Return (no_bet: bool, reasons: List[str]).

        NO_BET fires when ANY floor is breached — it is purely threshold-driven, with NO weekly
        volume target (§16.3): the model bets what clears the bar, whether that's 5 games or 30.
          1. Edge below the (dynamic, confidence-aware) `min_edge_threshold` already computed for
             the pick — i.e. the existing `has_edge` gate says there is no real edge.
          2. Confidence below `NO_BET_CONFIDENCE_FLOOR`.
          3. The variance detector flags hard factor disagreement (extreme variance, a
             primary-factor directional split, or an AVOID recommendation).
        """
        reasons: List[str] = []

        # 1. Edge floor (reuses the existing dynamic threshold; skip the no-line sentinel case).
        if prediction_result.get('edge_size') is not None and not prediction_result.get('has_edge', False):
            thr = prediction_result.get('min_edge_threshold')
            reasons.append(
                f"edge {prediction_result.get('edge_size', 0.0):.2f} below threshold"
                + (f" {thr:.2f}" if isinstance(thr, (int, float)) else ""))

        # 2. Confidence floor.
        if confidence_score < NO_BET_CONFIDENCE_FLOOR:
            reasons.append(f"confidence {confidence_score:.2f} < {NO_BET_CONFIDENCE_FLOOR:.2f}")

        # 3. Variance hard-disagreement gate.
        if variance_analysis:
            level = variance_analysis.get('variance_level', '')
            directional = variance_analysis.get('directional_agreement') or {}
            action = (variance_analysis.get('recommendation') or {}).get('action', '')
            if level in NO_BET_VARIANCE_LEVELS:
                reasons.append(f"{level} factor variance")
            if directional.get('primary_disagreement'):
                reasons.append("primary factors disagree in direction")
            if action in NO_BET_VARIANCE_ACTIONS:
                reasons.append(f"variance recommends {action}")

        return (len(reasons) > 0, reasons)

    def _confidence_tier(self, confidence_score: float, prediction_type: str) -> Optional[str]:
        """L3 A/B/C confidence tier from the confidence score (SPEC §7.5).

        Because the NO_BET confidence floor equals the B/C boundary (`CONFIDENCE_TIER_B_MIN`), a
        prediction with confidence below B is always NO_BET — so **a BET is only ever tier A or B,
        and tier C is a diagnostic grade that never labels a bet**. The tier is still computed for a
        NO_BET game (it explains *why* — a C means "confidence too low", vs a B/A NO_BET which was
        edge/variance-gated), so C is observable in the reports; only a no-line / error prediction
        has no meaningful confidence and returns None. Boundaries are `reasoned` (NOT fit to the
        archive confidence→ATS table, SPEC §3); monotonic-ATS%-by-tier is a structural check on the
        new model's output, measured by Phase-4 attribution.
        """
        if prediction_type in ('NO_BETTING_DATA', 'ERROR'):
            return None
        if confidence_score >= CONFIDENCE_TIER_A_MIN:
            return 'A'
        if confidence_score >= CONFIDENCE_TIER_B_MIN:
            return 'B'
        return 'C'

    def _build_prediction_result(self, home_team: str, away_team: str, week: Optional[int],
                               vegas_spread: Optional[float], factor_results: Dict[str, Any],
                               prediction_result: Dict[str, Any], context: Dict[str, Any],
                               variance_analysis: Optional[Dict[str, Any]] = None,
                               power_rating: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build comprehensive prediction result."""
        # Frozen from the snapshot's build time so `predict rerun` is bit-identical
        # (reproducibility contract, SCHEMA §3). A missing timestamp means the context
        # was not snapshot-assembled — fall back to wall-clock but WARN loudly, since
        # reproducibility is broken for this prediction.
        timestamp = context.get('timestamp')
        if timestamp is None:
            self.logger.warning(
                "Context for %s @ %s has no snapshot timestamp; using wall-clock — "
                "bit-identical rerun is NOT guaranteed for this prediction.",
                away_team, home_team)
            timestamp = datetime.now().isoformat()

        # Confidence, NO_BET (L4) and tier (L3) are decided here, where edge + variance +
        # confidence are all available together.
        confidence_score = self._calculate_confidence_score(
            prediction_result, factor_results, context, variance_analysis)
        base_type = prediction_result.get('prediction_type', 'UNKNOWN')
        no_bet, no_bet_reasons = self._evaluate_no_bet(
            prediction_result, confidence_score, variance_analysis)
        # NO_BET is a first-class verdict layered on top of the contrarian tier: it overrides the
        # prediction type (except when there is no line / an error) BUT the hypothetical pick is
        # preserved (contrarian_spread + edge_*), so NO_BET games are still graded — "what would
        # have happened" (SPEC §7.4 / §16.3). Purely threshold-driven; no weekly volume target.
        if no_bet and base_type not in ('NO_BETTING_DATA', 'ERROR'):
            prediction_type = 'NO_BET'
            has_edge = False
        else:
            prediction_type = base_type
            has_edge = prediction_result.get('has_edge', False)
        confidence_tier = self._confidence_tier(confidence_score, prediction_type)
        recommendation = self._generate_recommendation(
            prediction_result, factor_results, variance_analysis,
            no_bet=no_bet, no_bet_reasons=no_bet_reasons)

        return {
            # Basic game info
            'home_team': home_team,
            'away_team': away_team,
            'week': week,
            'timestamp': timestamp,
            'snapshot_id': context.get('snapshot_id'),

            # Market data
            'vegas_spread': vegas_spread,
            'contrarian_spread': prediction_result.get('contrarian_spread'),

            # Power rating (SPEC §6.3/§6.6) — DIAGNOSTIC ONLY in 2026: logged alongside,
            # does NOT drive the contrarian edge/recommendation.
            'power_rating_spread': (power_rating or {}).get('power_rating_spread'),
            'power_rating_base_spread': (power_rating or {}).get('power_rating_base_spread'),
            'model_vs_market_gap': (power_rating or {}).get('model_vs_market_gap'),
            'model_vs_market_gap_total': (power_rating or {}).get('model_vs_market_gap_total'),
            'rating_uncertainty': (power_rating or {}).get('rating_uncertainty'),
            'power_rating_breakdown': (power_rating or {}).get('power_rating_breakdown'),
            'power_rating_caveats': (power_rating or {}).get('power_rating_caveats'),


            # Edge analysis
            'edge_size': prediction_result.get('edge_size'),
            'edge_direction': prediction_result.get('edge_direction'),
            'has_edge': has_edge,
            'prediction_type': prediction_type,
            'no_bet': no_bet,
            'no_bet_reason': ('; '.join(no_bet_reasons) if no_bet else None),
            'confidence_tier': confidence_tier,

            # Factor analysis
            'total_adjustment': prediction_result.get('total_adjustment', 0.0),
            'factor_breakdown': factor_results.get('factors', {}),
            'category_adjustments': factor_results.get('summary', {}).get('category_adjustments', {}),
            
            # Data quality
            'data_quality': context.get('data_quality', 0.0),
            'data_sources': context.get('data_sources', []),
            'factors_calculated': factor_results.get('summary', {}).get('factors_calculated', 0),
            'factors_successful': factor_results.get('summary', {}).get('factors_successful', 0),
            
            # Variance Analysis
            'variance_analysis': variance_analysis,
            
            # Recommendation (incorporates variance + NO_BET)
            'recommendation': recommendation,
            'confidence_score': confidence_score,
            
            # Context data
            'context': {
                'home_team_data': context.get('home_team_data', {}),
                'away_team_data': context.get('away_team_data', {}),
                'coaching_comparison': context.get('coaching_comparison', {})
            }
        }
    
    def _generate_recommendation(self, prediction_result: Dict[str, Any],
                               factor_results: Dict[str, Any],
                               variance_analysis: Optional[Dict[str, Any]] = None,
                               no_bet: bool = False,
                               no_bet_reasons: Optional[List[str]] = None) -> str:
        """Generate betting recommendation based on prediction results."""
        prediction_type = prediction_result.get('prediction_type', 'UNKNOWN')
        edge_direction = prediction_result.get('edge_direction', 'neutral')
        edge_size = prediction_result.get('edge_size', 0.0)

        # L4: a NO_BET verdict is the recommendation — the hypothetical pick is still logged and
        # graded, but the model is explicitly declining to bet it.
        if no_bet:
            why = ("; ".join(no_bet_reasons) if no_bet_reasons else "below betting floors")
            return f"NO BET - {why}"

        if prediction_type == 'NO_BETTING_DATA':
            return "Cannot provide recommendation - no betting line available"
        
        if prediction_type == 'CONSENSUS_ALIGNMENT':
            return "No contrarian opportunity identified - align with market consensus"
        
        # Generate contrarian recommendation
        if edge_direction == 'home':
            favored_team = factor_results.get('home_team', 'Home team')
            recommendation = f"CONTRARIAN OPPORTUNITY: Consider {favored_team}"
        elif edge_direction == 'away':
            favored_team = factor_results.get('away_team', 'Away team')
            recommendation = f"CONTRARIAN OPPORTUNITY: Consider {favored_team}"
        else:
            recommendation = "Neutral prediction - no clear contrarian edge"
        
        # Add edge size context
        if edge_size >= 3.0:
            recommendation += f" (Strong {edge_size:.1f} point edge)"
        elif edge_size >= 1.5:
            recommendation += f" (Moderate {edge_size:.1f} point edge)"
        else:
            recommendation += f" (Slight {edge_size:.1f} point edge)"
        
        # Add variance analysis warnings/confirmations
        if variance_analysis:
            variance_level = variance_analysis.get('variance_level', '')
            var_recommendation = variance_analysis.get('recommendation', {})
            var_action = var_recommendation.get('action', '')
            
            if variance_level == 'extreme':
                recommendation += " ⚠️ EXTREME FACTOR DISAGREEMENT - AVOID"
            elif variance_level == 'strong':
                recommendation += " ⚠️ High uncertainty - reduce bet size"
            elif variance_level == 'moderate':
                recommendation += " ⚠️ Some factor disagreement - proceed cautiously"
            elif variance_level == 'consensus':
                recommendation += " ✓ Factors align - high confidence"
            
            # Override recommendation if variance suggests avoiding
            if var_action in ['AVOID_OR_MINIMUM', 'REDUCE_EXPOSURE']:
                recommendation = f"VARIANCE WARNING: {recommendation.split('(')[0].strip()}"
                recommendation += f" - Factors disagree ({variance_level} variance)"
        
        return recommendation
    
    def _calculate_confidence_score(self, prediction_result: Dict[str, Any], 
                                  factor_results: Dict[str, Any], 
                                  context: Dict[str, Any],
                                  variance_analysis: Optional[Dict[str, Any]] = None) -> float:
        """Calculate confidence score for the prediction (0.0 to 1.0)."""
        confidence_factors = []
        
        # Data quality factor (0-40% of confidence)
        data_quality = context.get('data_quality', 0.0)
        confidence_factors.append(data_quality * 0.4)
        
        # Factor success rate (0-30% of confidence)
        factor_summary = factor_results.get('summary', {})
        factors_calculated = factor_summary.get('factors_calculated', 1)
        factors_successful = factor_summary.get('factors_successful', 0)
        success_rate = factors_successful / max(factors_calculated, 1)  # Prevent division by zero
        confidence_factors.append(success_rate * 0.3)
        
        # Edge size factor (0-20% of confidence)
        edge_size = prediction_result.get('edge_size', 0.0)
        if edge_size is not None:
            edge_confidence = min(edge_size / 5.0, 1.0)  # Scale edge to 0-1
            confidence_factors.append(edge_confidence * 0.2)
        else:
            confidence_factors.append(0.0)  # No edge data available
        
        # Betting data availability (0-10% of confidence)
        has_betting_data = prediction_result.get('contrarian_spread') is not None
        confidence_factors.append(0.1 if has_betting_data else 0.0)
        
        # Factor variance adjustment (affects confidence by ±0.3)
        variance_adjustment = 0.0
        if variance_analysis:
            variance_level = variance_analysis.get('variance_level', '')
            if variance_level == 'consensus':
                variance_adjustment = 0.25  # High confidence bonus
            elif variance_level == 'mild':
                variance_adjustment = 0.1   # Mild confidence bonus
            elif variance_level == 'moderate':
                variance_adjustment = -0.1  # Mild confidence penalty
            elif variance_level == 'strong':
                variance_adjustment = -0.2  # Strong confidence penalty
            elif variance_level == 'extreme':
                variance_adjustment = -0.3  # Maximum confidence penalty
        
        # Total confidence score
        total_confidence = sum(confidence_factors) + variance_adjustment
        
        # Ensure confidence is between 0.15 and 0.95 (never completely certain/uncertain)
        return max(0.15, min(0.95, total_confidence))
    
    def _create_error_result(self, home_team: str, away_team: str, 
                           week: Optional[int], error_message: str) -> Dict[str, Any]:
        """Create error result structure."""
        return {
            'home_team': home_team,
            'away_team': away_team,
            'week': week,
            'timestamp': datetime.now().isoformat(),
            'error': error_message,
            'prediction_type': 'ERROR',
            'has_edge': False,
            'recommendation': f"Prediction failed: {error_message}",
            'confidence_score': 0.0
        }
    
    def _update_execution_stats(self, execution_time: float) -> None:
        """Update execution time statistics."""
        total_predictions = self.prediction_stats['total_predictions']
        current_avg = self.prediction_stats['avg_execution_time']
        
        # Update running average
        new_avg = (current_avg * total_predictions + execution_time) / (total_predictions + 1)
        self.prediction_stats['avg_execution_time'] = new_avg


# Global prediction engine instance
prediction_engine = PredictionEngine()
