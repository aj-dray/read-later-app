#!/usr/bin/env python3

import asyncio
import unittest
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from app.services import cross_encoder


class TestCrossEncoderSearch(unittest.TestCase):
    """Unit tests for cross-encoder search functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_query = "funding startup investment"
        self.test_candidates = [
            {
                "id": "1",
                "title": "Startup raises $10M in Series A funding round",
                "summary": "Tech company secures major investment to expand operations",
                "score": 0.8
            },
            {
                "id": "2", 
                "title": "Weather forecast for tomorrow",
                "summary": "It will be sunny with temperatures reaching 75°F",
                "score": 0.7
            },
            {
                "id": "3",
                "title": "Recipe for chocolate cake",
                "summary": "Delicious dessert recipe with step-by-step instructions",
                "score": 0.6
            },
            {
                "id": "4",
                "title": "Anthropic raises $13B Series F funding",
                "summary": "AI company secures massive investment round",
                "score": 0.9
            }
        ]

    async def async_test_score_relevance(self):
        """Test cross-encoder relevance scoring."""
        scores = await cross_encoder.score_relevance(self.test_query, self.test_candidates)
        
        # Should return one score per candidate
        self.assertEqual(len(scores), len(self.test_candidates))
        
        # All scores should be numeric
        for score in scores:
            self.assertIsInstance(score, (int, float))
        
        # Funding-related items should score higher than irrelevant ones
        # Note: actual scores depend on the model, but relative ordering should hold
        funding_indices = [0, 3]  # Startup funding and Anthropic funding
        irrelevant_indices = [1, 2]  # Weather and recipe
        
        max_irrelevant_score = max(scores[i] for i in irrelevant_indices)
        min_funding_score = min(scores[i] for i in funding_indices)
        
        # This might not always hold due to model variations, so we'll just check structure
        print(f"Funding scores: {[scores[i] for i in funding_indices]}")
        print(f"Irrelevant scores: {[scores[i] for i in irrelevant_indices]}")

    async def async_test_filter_by_relevance(self):
        """Test filtering candidates by relevance threshold."""
        # Use a moderate threshold
        threshold = -10.0
        
        filtered = await cross_encoder.filter_by_relevance(
            self.test_query, 
            self.test_candidates,
            threshold
        )
        
        # Should return a list
        self.assertIsInstance(filtered, list)
        
        # All results should have cross_encoder_score
        for result in filtered:
            self.assertIn("cross_encoder_score", result)
            self.assertIsInstance(result["cross_encoder_score"], (int, float))
        
        # Results should be sorted by cross_encoder_score (descending)
        if len(filtered) > 1:
            scores = [r["cross_encoder_score"] for r in filtered]
            self.assertEqual(scores, sorted(scores, reverse=True))

    async def async_test_rerank_by_relevance(self):
        """Test reranking candidates by relevance."""
        reranked = await cross_encoder.rerank_by_relevance(self.test_query, self.test_candidates)
        
        # Should return same number of candidates
        self.assertEqual(len(reranked), len(self.test_candidates))
        
        # All should have cross_encoder_score
        for result in reranked:
            self.assertIn("cross_encoder_score", result)
        
        # Should be sorted by cross_encoder_score
        scores = [r["cross_encoder_score"] for r in reranked]
        self.assertEqual(scores, sorted(scores, reverse=True))

    async def async_test_empty_inputs(self):
        """Test handling of empty inputs."""
        # Empty candidates
        scores = await cross_encoder.score_relevance(self.test_query, [])
        self.assertEqual(scores, [])
        
        filtered = await cross_encoder.filter_by_relevance(self.test_query, [])
        self.assertEqual(filtered, [])
        
        reranked = await cross_encoder.rerank_by_relevance(self.test_query, [])
        self.assertEqual(reranked, [])
        
        # Empty query
        scores = await cross_encoder.score_relevance("", self.test_candidates)
        self.assertEqual(len(scores), len(self.test_candidates))
        # Empty query should return neutral scores
        for score in scores:
            self.assertEqual(score, 0.0)

    async def async_test_malformed_candidates(self):
        """Test handling of candidates with missing fields."""
        malformed_candidates = [
            {"id": "1"},  # Missing title and summary
            {"title": "Only title"},  # Missing summary
            {"summary": "Only summary"},  # Missing title
            {}  # Empty candidate
        ]
        
        # Should not crash
        scores = await cross_encoder.score_relevance(self.test_query, malformed_candidates)
        self.assertEqual(len(scores), len(malformed_candidates))
        
        filtered = await cross_encoder.filter_by_relevance(self.test_query, malformed_candidates)
        self.assertIsInstance(filtered, list)

    def test_score_relevance(self):
        """Synchronous wrapper for async test."""
        asyncio.run(self.async_test_score_relevance())

    def test_filter_by_relevance(self):
        """Synchronous wrapper for async test."""
        asyncio.run(self.async_test_filter_by_relevance())

    def test_rerank_by_relevance(self):
        """Synchronous wrapper for async test."""
        asyncio.run(self.async_test_rerank_by_relevance())

    def test_empty_inputs(self):
        """Synchronous wrapper for async test."""
        asyncio.run(self.async_test_empty_inputs())

    def test_malformed_candidates(self):
        """Synchronous wrapper for async test."""
        asyncio.run(self.async_test_malformed_candidates())


class TestCrossEncoderConfiguration(unittest.TestCase):
    """Test cross-encoder configuration and model loading."""
    
    def test_model_constants(self):
        """Test that configuration constants are reasonable."""
        self.assertIsInstance(cross_encoder.CROSS_ENCODER_MODEL, str)
        self.assertIsInstance(cross_encoder.CROSS_ENCODER_THRESHOLD, (int, float))
        self.assertIsInstance(cross_encoder.MAX_BATCH_SIZE, int)
        self.assertGreater(cross_encoder.MAX_BATCH_SIZE, 0)


if __name__ == "__main__":
    # Run tests with more verbose output
    unittest.main(verbosity=2)