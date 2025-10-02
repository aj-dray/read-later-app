#!/usr/bin/env python3

import asyncio
import sys
import os
import statistics

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app import database as db
from app.services import embedding, cross_encoder


async def analyze_cross_encoder_threshold():
    """Analyze cross-encoder score distribution to find optimal threshold."""
    
    # Initialize database
    await db.init_pool()
    await db.init_database()
    
    try:
        # Get real user ID
        user_id = "f62ba213-24b2-47bf-b51e-e690fd6a5a0d"  # adray user from login
        
        # Test queries with expected relevance
        test_cases = [
            {
                "query": "AI agents artificial intelligence",
                "relevant_keywords": ["AI", "artificial", "intelligence", "agents", "machine", "learning"]
            },
            {
                "query": "news about raising sport",
                "relevant_keywords": ["money", "funding", "raise", "tax", "financial", "investment"]
            },
            {
                "query": "article about shoe engineer",
                "relevant_keywords": ["Nike"]
            }
        ]
        
        all_relevant_scores = []
        all_irrelevant_scores = []
        
        for test_case in test_cases:
            query = test_case["query"]
            relevant_keywords = test_case["relevant_keywords"]
            
            print(f"\n{'='*60}")
            print(f"Analyzing query: '{query}'")
            print('='*60)
            
            # Get semantic search candidates
            query_vec = await embedding.embed_query(query)
            candidates = await db.semantic_search_items(
                user_id=user_id,
                query_vector=query_vec,
                columns=None,
                limit=20
            )
            
            if not candidates:
                print("No candidates found")
                continue
            
            # Score with cross-encoder
            cross_scores = await cross_encoder.score_relevance(query, candidates)
            
            # Classify as relevant/irrelevant based on keywords
            relevant_scores = []
            irrelevant_scores = []
            
            print("\nClassification and scores:")
            for candidate, score in zip(candidates, cross_scores):
                title = candidate.get('title', '').lower()
                summary = candidate.get('summary', '').lower()
                content = title + ' ' + summary
                
                # Check if any relevant keywords appear
                is_relevant = any(keyword.lower() in content for keyword in relevant_keywords)
                
                if is_relevant:
                    relevant_scores.append(score)
                    classification = "RELEVANT  "
                else:
                    irrelevant_scores.append(score)
                    classification = "IRRELEVANT"
                
                print(f"  {classification} | Score: {score:7.3f} | {candidate.get('title', 'No title')[:60]}")
            
            all_relevant_scores.extend(relevant_scores)
            all_irrelevant_scores.extend(irrelevant_scores)
            
            print(f"\nQuery stats:")
            if relevant_scores:
                print(f"  Relevant scores   - Count: {len(relevant_scores):2d}, Mean: {statistics.mean(relevant_scores):7.3f}, Min: {min(relevant_scores):7.3f}, Max: {max(relevant_scores):7.3f}")
            if irrelevant_scores:
                print(f"  Irrelevant scores - Count: {len(irrelevant_scores):2d}, Mean: {statistics.mean(irrelevant_scores):7.3f}, Min: {min(irrelevant_scores):7.3f}, Max: {max(irrelevant_scores):7.3f}")
        
        # Overall statistics
        print(f"\n{'='*60}")
        print("OVERALL STATISTICS")
        print('='*60)
        
        if all_relevant_scores:
            relevant_mean = statistics.mean(all_relevant_scores)
            relevant_median = statistics.median(all_relevant_scores)
            relevant_min = min(all_relevant_scores)
            relevant_max = max(all_relevant_scores)
            print(f"Relevant scores   ({len(all_relevant_scores):2d} items):")
            print(f"  Mean: {relevant_mean:7.3f}, Median: {relevant_median:7.3f}")
            print(f"  Min:  {relevant_min:7.3f}, Max:    {relevant_max:7.3f}")
        
        if all_irrelevant_scores:
            irrelevant_mean = statistics.mean(all_irrelevant_scores)
            irrelevant_median = statistics.median(all_irrelevant_scores)
            irrelevant_min = min(all_irrelevant_scores)
            irrelevant_max = max(all_irrelevant_scores)
            print(f"Irrelevant scores ({len(all_irrelevant_scores):2d} items):")
            print(f"  Mean: {irrelevant_mean:7.3f}, Median: {irrelevant_median:7.3f}")
            print(f"  Min:  {irrelevant_min:7.3f}, Max:    {irrelevant_max:7.3f}")
        
        # Threshold recommendations
        print(f"\n{'='*60}")
        print("THRESHOLD RECOMMENDATIONS")
        print('='*60)
        
        if all_relevant_scores and all_irrelevant_scores:
            # Find threshold that maximizes precision while maintaining good recall
            sorted_relevant = sorted(all_relevant_scores, reverse=True)
            sorted_irrelevant = sorted(all_irrelevant_scores, reverse=True)
            
            # Try different percentiles of relevant scores as thresholds
            percentiles = [10, 25, 50, 75, 90]
            
            print("Threshold analysis (using relevant score percentiles):")
            print("Threshold | Relevant Kept | Irrelevant Kept | Precision | Recall")
            print("-" * 65)
            
            for p in percentiles:
                if len(sorted_relevant) > 0:
                    threshold_idx = int((p / 100) * len(sorted_relevant))
                    threshold = sorted_relevant[min(threshold_idx, len(sorted_relevant) - 1)]
                    
                    relevant_kept = sum(1 for score in all_relevant_scores if score >= threshold)
                    irrelevant_kept = sum(1 for score in all_irrelevant_scores if score >= threshold)
                    total_kept = relevant_kept + irrelevant_kept
                    
                    precision = relevant_kept / total_kept if total_kept > 0 else 0
                    recall = relevant_kept / len(all_relevant_scores) if len(all_relevant_scores) > 0 else 0
                    
                    print(f"{threshold:8.3f}  |      {relevant_kept:2d}       |        {irrelevant_kept:2d}        |   {precision:5.3f}   |  {recall:5.3f}")
            
            # Conservative recommendation: threshold that keeps 75% of relevant items
            if len(sorted_relevant) > 0:
                conservative_threshold = sorted_relevant[int(0.25 * len(sorted_relevant))]
                print(f"\nConservative recommendation (keeps 75% of relevant): {conservative_threshold:.3f}")
            
            # Aggressive recommendation: threshold that achieves high precision
            combined_scores = [(score, 'relevant') for score in all_relevant_scores] + \
                            [(score, 'irrelevant') for score in all_irrelevant_scores]
            combined_scores.sort(reverse=True)
            
            best_threshold = -float('inf')
            best_f1 = 0
            
            for i, (threshold, _) in enumerate(combined_scores):
                relevant_kept = sum(1 for score in all_relevant_scores if score >= threshold)
                irrelevant_kept = sum(1 for score in all_irrelevant_scores if score >= threshold)
                total_kept = relevant_kept + irrelevant_kept
                
                if total_kept > 0:
                    precision = relevant_kept / total_kept
                    recall = relevant_kept / len(all_relevant_scores) if len(all_relevant_scores) > 0 else 0
                    
                    if precision > 0 and recall > 0:
                        f1 = 2 * (precision * recall) / (precision + recall)
                        if f1 > best_f1:
                            best_f1 = f1
                            best_threshold = threshold
            
            if best_threshold > -float('inf'):
                print(f"Optimal F1 threshold (F1={best_f1:.3f}): {best_threshold:.3f}")
        
        else:
            print("Insufficient data for threshold analysis")
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await db.close_pool()


if __name__ == "__main__":
    asyncio.run(analyze_cross_encoder_threshold())