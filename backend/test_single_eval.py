#!/usr/bin/env python3
"""
Quick test script to run evaluation on a single post
Usage: python test_single_eval.py <post_id>
"""

import sys
import asyncio
import os
from dotenv import load_dotenv
import anthropic
from evaluate_comments import CommentEvaluator, CommentData, PostEvaluation
from src.database import get_post_by_id, get_db_connection

# Load environment variables
load_dotenv()

def flatten_comments(comments):
    """Flatten nested comment structure"""
    flat = []
    for comment in comments:
        flat.append(comment)
        if comment.get('replies'):
            flat.extend(flatten_comments(comment['replies']))
    return flat

async def test_evaluation(post_id: int):
    """Test evaluation on a specific post"""

    # Get API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        return

    # Get post from database
    print(f"Loading post {post_id} from database...")
    post_data = get_post_by_id(post_id)

    if not post_data:
        print(f"Post {post_id} not found in database")
        return

    # Extract comments
    all_comments = flatten_comments(post_data['mixed_comments']['comments'])

    # Separate AI and human comments
    ai_comments = [
        CommentData(
            id=i,
            text=comment['content'],
            is_ai=True,
            comment_type='top_level' if comment['depth'] == 0 else 'reply'
        )
        for i, comment in enumerate(all_comments) if comment.get('is_ai', False)
    ]

    human_comments = [
        CommentData(
            id=i,
            text=comment['content'],
            is_ai=False,
            comment_type='top_level' if comment['depth'] == 0 else 'reply'
        )
        for i, comment in enumerate(all_comments) if not comment.get('is_ai', False)
    ]

    print(f"Found {len(ai_comments)} AI comments and {len(human_comments)} human comments")

    # Show AI comments for reference
    print("\nAI COMMENTS:")
    for i, comment in enumerate(ai_comments):
        words = len(comment.text.split())
        print(f"{i+1}. ({words} words) {comment.text[:80]}...")

    # Create evaluation object
    post_evaluation = PostEvaluation(
        post_title=post_data['title'],
        human_comments=human_comments,
        ai_comments=ai_comments
    )

    # Initialize evaluator and run
    client = anthropic.Anthropic(api_key=api_key)
    evaluator = CommentEvaluator(client)

    print(f"\nRunning evaluation on post: '{post_data['title']}'...")
    print("="*80)

    results = await evaluator.evaluate_post(post_evaluation)

    print(f"\nEVALUATION RESULTS:")
    print(f"Mixed Reality Score:  {results['mixed_reality_score']}/10")
    print(f"Diversity Score:      {results['diversity_score']}/10")
    print(f"Appropriateness:      {results['appropriateness_score']}/10")
    print(f"Overall Score:        {results['overall_score']}/10")
    print("="*80)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_single_eval.py <post_id>")
        sys.exit(1)

    try:
        post_id = int(sys.argv[1])
        asyncio.run(test_evaluation(post_id))
    except ValueError:
        print("Error: post_id must be an integer")
        sys.exit(1)