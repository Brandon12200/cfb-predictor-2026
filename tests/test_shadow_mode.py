"""
Shadow mode testing infrastructure for College Football Market Edge Platform.
Allows tracking predictions and outcomes without affecting user experience.
"""

import unittest
import json
import sqlite3
import tempfile
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, MagicMock
import statistics

from engine.prediction_engine import prediction_engine
from engine.confidence_calculator import confidence_calculator


class ShadowModeTracker:
    """
    Tracks predictions in shadow mode for later validation against actual outcomes.
    
    Features:
    - Store predictions with timestamps
    - Track actual game outcomes
    - Calculate accuracy metrics
    - Identify model performance patterns
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize shadow mode tracker."""
        self.db_path = db_path or ":memory:"
        self.setup_database()
    
    def setup_database(self):
        """Set up SQLite database for tracking."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS shadow_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                week INTEGER,
                vegas_spread REAL,
                contrarian_spread REAL,
                edge_size REAL,
                confidence_score REAL,
                prediction_type TEXT,
                factor_breakdown TEXT,
                category_adjustments TEXT,
                data_quality REAL,
                prediction_json TEXT,
                game_date TEXT,
                completed BOOLEAN DEFAULT FALSE,
                actual_home_score INTEGER,
                actual_away_score INTEGER,
                actual_margin REAL,
                home_covered_vegas BOOLEAN,
                home_covered_contrarian BOOLEAN,
                prediction_correct BOOLEAN,
                edge_correct BOOLEAN
            )
        ''')
        
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS accuracy_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                calculation_date TEXT NOT NULL,
                total_predictions INTEGER,
                completed_games INTEGER,
                overall_accuracy REAL,
                edge_accuracy REAL,
                confidence_calibration TEXT,
                category_performance TEXT,
                weekly_performance TEXT
            )
        ''')
        
        self.conn.commit()
    
    def store_prediction(self, home_team: str, away_team: str, prediction_result: Dict[str, Any],
                        week: Optional[int] = None, game_date: Optional[str] = None) -> int:
        """Store a prediction in shadow mode."""
        timestamp = datetime.now().isoformat()
        
        # Extract key metrics
        vegas_spread = prediction_result.get('vegas_spread')
        contrarian_spread = prediction_result.get('contrarian_spread')
        edge_size = prediction_result.get('edge_size', 0.0)
        confidence_score = prediction_result.get('confidence_score', 0.0)
        prediction_type = prediction_result.get('prediction_type', 'UNKNOWN')
        data_quality = prediction_result.get('data_quality', 0.0)
        
        # Serialize complex data
        factor_breakdown = json.dumps(prediction_result.get('factor_breakdown', {}))
        category_adjustments = json.dumps(prediction_result.get('category_adjustments', {}))
        prediction_json = json.dumps(prediction_result)
        
        cursor = self.conn.execute('''
            INSERT INTO shadow_predictions (
                timestamp, home_team, away_team, week, vegas_spread, contrarian_spread,
                edge_size, confidence_score, prediction_type, factor_breakdown,
                category_adjustments, data_quality, prediction_json, game_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp, home_team, away_team, week, vegas_spread, contrarian_spread,
            edge_size, confidence_score, prediction_type, factor_breakdown,
            category_adjustments, data_quality, prediction_json, game_date
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def update_game_outcome(self, prediction_id: int, home_score: int, away_score: int):
        """Update a prediction with actual game outcome."""
        actual_margin = home_score - away_score
        
        # Get the original prediction
        cursor = self.conn.execute(
            'SELECT vegas_spread, contrarian_spread, edge_size FROM shadow_predictions WHERE id = ?',
            (prediction_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            raise ValueError(f"Prediction {prediction_id} not found")
        
        vegas_spread, contrarian_spread, edge_size = row
        
        # Calculate outcomes
        home_covered_vegas = actual_margin > vegas_spread if vegas_spread is not None else None
        home_covered_contrarian = actual_margin > contrarian_spread if contrarian_spread is not None else None
        
        # Determine if prediction was correct
        prediction_correct = False
        edge_correct = False
        
        if edge_size >= 1.0 and contrarian_spread is not None:
            # We made a contrarian prediction
            edge_correct = home_covered_contrarian
            prediction_correct = edge_correct
        elif vegas_spread is not None:
            # No significant edge, follow Vegas
            prediction_correct = home_covered_vegas
        
        # Update database
        self.conn.execute('''
            UPDATE shadow_predictions SET
                completed = TRUE,
                actual_home_score = ?,
                actual_away_score = ?,
                actual_margin = ?,
                home_covered_vegas = ?,
                home_covered_contrarian = ?,
                prediction_correct = ?,
                edge_correct = ?
            WHERE id = ?
        ''', (
            home_score, away_score, actual_margin,
            home_covered_vegas, home_covered_contrarian,
            prediction_correct, edge_correct, prediction_id
        ))
        
        self.conn.commit()
    
    def calculate_accuracy_metrics(self, days_back: int = 30) -> Dict[str, Any]:
        """Calculate accuracy metrics for recent predictions."""
        cutoff_date = (datetime.now() - timedelta(days=days_back)).isoformat()
        
        # Get completed predictions
        cursor = self.conn.execute('''
            SELECT * FROM shadow_predictions 
            WHERE completed = TRUE AND timestamp > ?
            ORDER BY timestamp DESC
        ''', (cutoff_date,))
        
        predictions = cursor.fetchall()
        
        if not predictions:
            return {'error': 'No completed predictions in specified time period'}
        
        # Column names for easier access
        columns = [desc[0] for desc in cursor.description]
        predictions = [dict(zip(columns, row)) for row in predictions]
        
        metrics = {
            'total_predictions': len(predictions),
            'time_period_days': days_back,
            'overall_accuracy': self._calculate_overall_accuracy(predictions),
            'edge_accuracy': self._calculate_edge_accuracy(predictions),
            'confidence_calibration': self._calculate_confidence_calibration(predictions),
            'category_performance': self._calculate_category_performance(predictions),
            'weekly_performance': self._calculate_weekly_performance(predictions),
            'beat_vegas_rate': self._calculate_beat_vegas_rate(predictions),
            'edge_detection_stats': self._calculate_edge_detection_stats(predictions)
        }
        
        # Store metrics
        self._store_accuracy_metrics(metrics)
        
        return metrics
    
    def _calculate_overall_accuracy(self, predictions: List[Dict]) -> float:
        """Calculate overall prediction accuracy."""
        correct_predictions = sum(1 for p in predictions if p['prediction_correct'])
        return correct_predictions / len(predictions) if predictions else 0.0
    
    def _calculate_edge_accuracy(self, predictions: List[Dict]) -> Dict[str, Any]:
        """Calculate accuracy for edge predictions."""
        edge_predictions = [p for p in predictions if p['edge_size'] >= 1.0]
        
        if not edge_predictions:
            return {'edge_predictions': 0, 'edge_accuracy': 0.0}
        
        correct_edges = sum(1 for p in edge_predictions if p['edge_correct'])
        
        return {
            'edge_predictions': len(edge_predictions),
            'edge_accuracy': correct_edges / len(edge_predictions),
            'edge_detection_rate': len(edge_predictions) / len(predictions)
        }
    
    def _calculate_confidence_calibration(self, predictions: List[Dict]) -> Dict[str, Any]:
        """Calculate confidence calibration metrics."""
        confidence_buckets = {
            'low': (0.0, 0.4),
            'medium': (0.4, 0.7),
            'high': (0.7, 1.0)
        }
        
        calibration = {}
        
        for bucket_name, (min_conf, max_conf) in confidence_buckets.items():
            bucket_predictions = [
                p for p in predictions
                if min_conf <= p['confidence_score'] < max_conf
            ]
            
            if bucket_predictions:
                correct_count = sum(1 for p in bucket_predictions if p['prediction_correct'])
                calibration[f'{bucket_name}_accuracy'] = correct_count / len(bucket_predictions)
                calibration[f'{bucket_name}_count'] = len(bucket_predictions)
                calibration[f'{bucket_name}_avg_confidence'] = statistics.mean(
                    p['confidence_score'] for p in bucket_predictions
                )
            else:
                calibration[f'{bucket_name}_accuracy'] = 0.0
                calibration[f'{bucket_name}_count'] = 0
                calibration[f'{bucket_name}_avg_confidence'] = 0.0
        
        return calibration
    
    def _calculate_category_performance(self, predictions: List[Dict]) -> Dict[str, Any]:
        """Calculate performance by factor category."""
        category_performance = {}
        
        for prediction in predictions:
            try:
                adjustments = json.loads(prediction['category_adjustments'])
                
                # Find dominant category
                if adjustments:
                    dominant_category = max(adjustments.items(), key=lambda x: abs(x[1]))
                    category_name = dominant_category[0]
                    
                    if category_name not in category_performance:
                        category_performance[category_name] = {
                            'predictions': 0,
                            'correct': 0,
                            'total_adjustment': 0.0
                        }
                    
                    category_performance[category_name]['predictions'] += 1
                    category_performance[category_name]['total_adjustment'] += abs(dominant_category[1])
                    
                    if prediction['prediction_correct']:
                        category_performance[category_name]['correct'] += 1
                        
            except (json.JSONDecodeError, KeyError):
                continue
        
        # Calculate accuracy rates
        for category in category_performance:
            stats = category_performance[category]
            stats['accuracy'] = stats['correct'] / stats['predictions']
            stats['avg_adjustment'] = stats['total_adjustment'] / stats['predictions']
        
        return category_performance
    
    def _calculate_weekly_performance(self, predictions: List[Dict]) -> Dict[str, Any]:
        """Calculate performance by week."""
        weekly_performance = {}
        
        for prediction in predictions:
            week = prediction['week']
            if week is None:
                continue
            
            if week not in weekly_performance:
                weekly_performance[week] = {
                    'predictions': 0,
                    'correct': 0,
                    'edges': 0,
                    'edge_correct': 0
                }
            
            weekly_performance[week]['predictions'] += 1
            
            if prediction['prediction_correct']:
                weekly_performance[week]['correct'] += 1
            
            if prediction['edge_size'] >= 1.0:
                weekly_performance[week]['edges'] += 1
                if prediction['edge_correct']:
                    weekly_performance[week]['edge_correct'] += 1
        
        # Calculate rates
        for week in weekly_performance:
            stats = weekly_performance[week]
            stats['accuracy'] = stats['correct'] / stats['predictions']
            if stats['edges'] > 0:
                stats['edge_accuracy'] = stats['edge_correct'] / stats['edges']
            else:
                stats['edge_accuracy'] = 0.0
        
        return weekly_performance
    
    def _calculate_beat_vegas_rate(self, predictions: List[Dict]) -> Dict[str, Any]:
        """Calculate how often we beat Vegas when we detect an edge."""
        edge_predictions = [p for p in predictions if p['edge_size'] >= 1.0]
        
        if not edge_predictions:
            return {'beat_vegas_opportunities': 0, 'beat_vegas_rate': 0.0}
        
        beat_vegas_count = 0
        
        for prediction in edge_predictions:
            # We beat Vegas if our contrarian prediction was right and Vegas was wrong
            contrarian_correct = prediction['edge_correct']
            vegas_correct = prediction['home_covered_vegas']
            
            if contrarian_correct and not vegas_correct:
                beat_vegas_count += 1
        
        return {
            'beat_vegas_opportunities': len(edge_predictions),
            'beat_vegas_count': beat_vegas_count,
            'beat_vegas_rate': beat_vegas_count / len(edge_predictions)
        }
    
    def _calculate_edge_detection_stats(self, predictions: List[Dict]) -> Dict[str, Any]:
        """Calculate edge detection statistics."""
        edge_buckets = {
            'small': (1.0, 2.0),
            'medium': (2.0, 3.0),
            'large': (3.0, float('inf'))
        }
        
        edge_stats = {}
        
        for bucket_name, (min_edge, max_edge) in edge_buckets.items():
            bucket_predictions = [
                p for p in predictions
                if min_edge <= p['edge_size'] < max_edge
            ]
            
            if bucket_predictions:
                correct_count = sum(1 for p in bucket_predictions if p['edge_correct'])
                edge_stats[bucket_name] = {
                    'count': len(bucket_predictions),
                    'accuracy': correct_count / len(bucket_predictions),
                    'avg_confidence': statistics.mean(p['confidence_score'] for p in bucket_predictions)
                }
            else:
                edge_stats[bucket_name] = {
                    'count': 0,
                    'accuracy': 0.0,
                    'avg_confidence': 0.0
                }
        
        return edge_stats
    
    def _store_accuracy_metrics(self, metrics: Dict[str, Any]):
        """Store calculated metrics in database."""
        calculation_date = datetime.now().isoformat()
        
        self.conn.execute('''
            INSERT INTO accuracy_metrics (
                calculation_date, total_predictions, completed_games,
                overall_accuracy, edge_accuracy, confidence_calibration,
                category_performance, weekly_performance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            calculation_date,
            metrics['total_predictions'],
            metrics['total_predictions'],  # All are completed in this calculation
            metrics['overall_accuracy'],
            metrics['edge_accuracy']['edge_accuracy'],
            json.dumps(metrics['confidence_calibration']),
            json.dumps(metrics['category_performance']),
            json.dumps(metrics['weekly_performance'])
        ))
        
        self.conn.commit()
    
    def get_recent_predictions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent predictions for review."""
        cursor = self.conn.execute('''
            SELECT * FROM shadow_predictions 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        
        columns = [desc[0] for desc in cursor.description]
        predictions = cursor.fetchall()
        
        return [dict(zip(columns, row)) for row in predictions]
    
    def export_prediction_data(self, filename: str):
        """Export prediction data to JSON file."""
        cursor = self.conn.execute('SELECT * FROM shadow_predictions ORDER BY timestamp')
        columns = [desc[0] for desc in cursor.description]
        predictions = cursor.fetchall()
        
        data = {
            'export_date': datetime.now().isoformat(),
            'total_predictions': len(predictions),
            'predictions': [dict(zip(columns, row)) for row in predictions]
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
    
    def close(self):
        """Close database connection."""
        if hasattr(self, 'conn'):
            self.conn.close()


class TestShadowModeTracker(unittest.TestCase):
    """Test the shadow mode tracking functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Use temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        self.tracker = ShadowModeTracker(self.temp_db.name)
    
    def tearDown(self):
        """Clean up test environment."""
        self.tracker.close()
        os.unlink(self.temp_db.name)
    
    def test_database_setup(self):
        """Test database initialization."""
        # Check tables exist
        cursor = self.tracker.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row[0] for row in cursor.fetchall()]
        
        self.assertIn('shadow_predictions', tables)
        self.assertIn('accuracy_metrics', tables)
    
    def test_store_prediction(self):
        """Test storing a prediction."""
        prediction_result = {
            'vegas_spread': -3.5,
            'contrarian_spread': -1.0,
            'edge_size': 2.5,
            'confidence_score': 0.75,
            'prediction_type': 'MODERATE_CONTRARIAN',
            'data_quality': 0.85,
            'factor_breakdown': {
                'ExperienceDifferential': {'success': True, 'value': 1.2}
            },
            'category_adjustments': {
                'coaching_edge': 1.5,
                'situational_context': 1.0
            }
        }
        
        prediction_id = self.tracker.store_prediction(
            "GEORGIA", "ALABAMA", prediction_result, week=8
        )
        
        self.assertIsInstance(prediction_id, int)
        self.assertGreater(prediction_id, 0)
        
        # Verify stored data
        cursor = self.tracker.conn.execute(
            'SELECT * FROM shadow_predictions WHERE id = ?',
            (prediction_id,)
        )
        row = cursor.fetchone()
        
        self.assertIsNotNone(row)
        self.assertEqual(row[2], "GEORGIA")  # home_team
        self.assertEqual(row[3], "ALABAMA")  # away_team
        self.assertEqual(row[6], -1.0)       # contrarian_spread
        self.assertEqual(row[7], 2.5)        # edge_size
    
    def test_update_game_outcome(self):
        """Test updating with game outcome."""
        # Store prediction
        prediction_result = {
            'vegas_spread': -3.5,
            'contrarian_spread': -1.0,
            'edge_size': 2.5,
            'confidence_score': 0.75
        }
        
        prediction_id = self.tracker.store_prediction(
            "GEORGIA", "ALABAMA", prediction_result
        )
        
        # Update with outcome (home team wins by 7)
        self.tracker.update_game_outcome(prediction_id, 28, 21)
        
        # Verify outcome calculation
        cursor = self.tracker.conn.execute(
            'SELECT completed, actual_margin, home_covered_vegas, home_covered_contrarian, prediction_correct FROM shadow_predictions WHERE id = ?',
            (prediction_id,)
        )
        row = cursor.fetchone()
        
        self.assertTrue(row[0])   # completed
        self.assertEqual(row[1], 7.0)  # actual_margin
        self.assertTrue(row[2])  # home_covered_vegas (7 > -3.5 is True, home covered)
        self.assertTrue(row[3])   # home_covered_contrarian (7 > -1.0)
        self.assertTrue(row[4])   # prediction_correct (edge was correct)
    
    def test_accuracy_calculation_no_data(self):
        """Test accuracy calculation with no data."""
        metrics = self.tracker.calculate_accuracy_metrics()
        
        self.assertIn('error', metrics)
        self.assertIn('No completed predictions', metrics['error'])
    
    def test_accuracy_calculation_with_data(self):
        """Test accuracy calculation with sample data."""
        # Store and complete several predictions
        test_predictions = [
            # Correct edge prediction
            {
                'home_team': 'GEORGIA', 'away_team': 'ALABAMA',
                'prediction': {'vegas_spread': -3.5, 'contrarian_spread': -1.0, 'edge_size': 2.5, 'confidence_score': 0.8},
                'outcome': (28, 21)  # Home wins by 7, covers contrarian
            },
            # Incorrect edge prediction
            {
                'home_team': 'TEXAS', 'away_team': 'OKLAHOMA',
                'prediction': {'vegas_spread': -7.0, 'contrarian_spread': -3.0, 'edge_size': 4.0, 'confidence_score': 0.7},
                'outcome': (14, 21)  # Away wins, edge wrong
            },
            # No edge, follow Vegas (correct)
            {
                'home_team': 'MICHIGAN', 'away_team': 'OHIO STATE',
                'prediction': {'vegas_spread': -2.5, 'contrarian_spread': -2.0, 'edge_size': 0.5, 'confidence_score': 0.5},
                'outcome': (24, 17)  # Home wins by 7, covers Vegas
            }
        ]
        
        prediction_ids = []
        for test_pred in test_predictions:
            pred_id = self.tracker.store_prediction(
                test_pred['home_team'], test_pred['away_team'], 
                test_pred['prediction'], week=8
            )
            prediction_ids.append(pred_id)
            
            # Update with outcome
            home_score, away_score = test_pred['outcome']
            self.tracker.update_game_outcome(pred_id, home_score, away_score)
        
        # Calculate metrics
        metrics = self.tracker.calculate_accuracy_metrics()
        
        # Verify metrics structure
        self.assertEqual(metrics['total_predictions'], 3)
        self.assertIn('overall_accuracy', metrics)
        self.assertIn('edge_accuracy', metrics)
        self.assertIn('confidence_calibration', metrics)
        
        # Check edge accuracy (1 correct out of 2 edge predictions)
        edge_accuracy = metrics['edge_accuracy']
        self.assertEqual(edge_accuracy['edge_predictions'], 2)
        self.assertEqual(edge_accuracy['edge_accuracy'], 0.5)
    
    def test_confidence_calibration(self):
        """Test confidence calibration calculation."""
        # Create predictions with known confidence levels
        test_data = [
            # Low confidence, should be wrong
            {'confidence': 0.3, 'correct': False},
            {'confidence': 0.3, 'correct': False},
            # High confidence, should be right
            {'confidence': 0.8, 'correct': True},
            {'confidence': 0.8, 'correct': True},
        ]
        
        for i, data in enumerate(test_data):
            prediction_result = {
                'vegas_spread': -3.0,
                'contrarian_spread': -1.0 if data['correct'] else -5.0,
                'edge_size': 2.0,
                'confidence_score': data['confidence']
            }
            
            pred_id = self.tracker.store_prediction(
                "TEAM_A", "TEAM_B", prediction_result
            )
            
            # Outcome based on whether prediction should be correct
            if data['correct']:
                self.tracker.update_game_outcome(pred_id, 21, 14)  # Home covers
            else:
                self.tracker.update_game_outcome(pred_id, 14, 28)  # Away wins big
        
        metrics = self.tracker.calculate_accuracy_metrics()
        calibration = metrics['confidence_calibration']
        
        # Low confidence should have low accuracy
        self.assertEqual(calibration['low_accuracy'], 0.0)
        self.assertEqual(calibration['low_count'], 2)
        
        # High confidence should have high accuracy
        self.assertEqual(calibration['high_accuracy'], 1.0)
        self.assertEqual(calibration['high_count'], 2)
    
    def test_export_import_functionality(self):
        """Test exporting prediction data."""
        # Store a prediction
        prediction_result = {
            'vegas_spread': -3.5,
            'edge_size': 2.5,
            'confidence_score': 0.75
        }
        
        self.tracker.store_prediction("GEORGIA", "ALABAMA", prediction_result)
        
        # Export to temporary file
        temp_export = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        temp_export.close()
        
        try:
            self.tracker.export_prediction_data(temp_export.name)
            
            # Verify export file
            with open(temp_export.name, 'r') as f:
                data = json.load(f)
            
            self.assertIn('export_date', data)
            self.assertEqual(data['total_predictions'], 1)
            self.assertIn('predictions', data)
            self.assertEqual(len(data['predictions']), 1)
            
            # Check prediction data
            prediction = data['predictions'][0]
            self.assertEqual(prediction['home_team'], 'GEORGIA')
            self.assertEqual(prediction['away_team'], 'ALABAMA')
            
        finally:
            os.unlink(temp_export.name)
    
    def test_recent_predictions_retrieval(self):
        """Test retrieving recent predictions."""
        # Store multiple predictions
        for i in range(5):
            prediction_result = {
                'vegas_spread': -3.5 + i,
                'edge_size': 1.0 + i,
                'confidence_score': 0.5 + i * 0.1
            }
            
            self.tracker.store_prediction(f"TEAM_{i}", f"OPPONENT_{i}", prediction_result)
        
        # Get recent predictions
        recent = self.tracker.get_recent_predictions(limit=3)
        
        self.assertEqual(len(recent), 3)
        
        # Should be in reverse chronological order
        self.assertEqual(recent[0]['home_team'], 'TEAM_4')  # Most recent
        self.assertEqual(recent[1]['home_team'], 'TEAM_3')
        self.assertEqual(recent[2]['home_team'], 'TEAM_2')
    
    def test_edge_detection_stats(self):
        """Test edge detection statistics calculation."""
        test_predictions = [
            # Small edge, correct
            {'edge_size': 1.5, 'confidence': 0.6, 'correct': True},
            # Medium edge, correct
            {'edge_size': 2.5, 'confidence': 0.7, 'correct': True},
            # Large edge, incorrect
            {'edge_size': 4.0, 'confidence': 0.8, 'correct': False},
        ]
        
        for data in test_predictions:
            prediction_result = {
                'vegas_spread': -3.0,
                'contrarian_spread': -1.0,
                'edge_size': data['edge_size'],
                'confidence_score': data['confidence']
            }
            
            pred_id = self.tracker.store_prediction("TEAM_A", "TEAM_B", prediction_result)
            
            # Set outcome based on correctness
            if data['correct']:
                self.tracker.update_game_outcome(pred_id, 21, 14)
            else:
                self.tracker.update_game_outcome(pred_id, 14, 21)
        
        metrics = self.tracker.calculate_accuracy_metrics()
        edge_stats = metrics['edge_detection_stats']
        
        # Verify edge bucket statistics
        self.assertEqual(edge_stats['small']['count'], 1)
        self.assertEqual(edge_stats['small']['accuracy'], 1.0)
        
        self.assertEqual(edge_stats['medium']['count'], 1)
        self.assertEqual(edge_stats['medium']['accuracy'], 1.0)
        
        self.assertEqual(edge_stats['large']['count'], 1)
        self.assertEqual(edge_stats['large']['accuracy'], 0.0)


class TestShadowModeIntegration(unittest.TestCase):
    """Test shadow mode integration with prediction engine."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        self.tracker = ShadowModeTracker(self.temp_db.name)
    
    def tearDown(self):
        """Clean up test environment."""
        self.tracker.close()
        os.unlink(self.temp_db.name)
    
    def test_shadow_mode_prediction_tracking(self):
        """Test tracking predictions generated by the prediction engine."""
        with patch('data.odds_client.OddsAPIClient.get_consensus_spread') as mock_odds, \
             patch('data.espn_client.ESPNStatsClient.get_team_info') as mock_espn:
            
            mock_odds.return_value = -3.5
            mock_espn.return_value = {
                'info': {'conference': {'name': 'SEC'}},
                'derived_metrics': {
                    'current_record': {'wins': 8, 'losses': 2, 'win_percentage': 0.8},
                    'venue_performance': {'home_record': {'win_percentage': 0.85}}
                }
            }
            
            # Generate prediction
            prediction = prediction_engine.generate_prediction("GEORGIA", "ALABAMA", week=8)
            
            # Store in shadow mode
            if not prediction.get('error'):
                prediction_id = self.tracker.store_prediction(
                    "GEORGIA", "ALABAMA", prediction, week=8
                )
                
                self.assertIsInstance(prediction_id, int)
                
                # Simulate game outcome
                self.tracker.update_game_outcome(prediction_id, 28, 21)
                
                # Verify stored correctly
                recent = self.tracker.get_recent_predictions(limit=1)
                self.assertEqual(len(recent), 1)
                self.assertTrue(recent[0]['completed'])


if __name__ == '__main__':
    print("Running shadow mode testing infrastructure tests...")
    unittest.main()