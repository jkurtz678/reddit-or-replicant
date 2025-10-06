#!/usr/bin/env python3
"""
LLM-as-a-Judge evaluation for AI comment quality
Outputs 3 simple numerical scores (1-10) for optimization
"""

import json
import asyncio
import os
from typing import List, Dict
import anthropic
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

@dataclass
class CommentData:
    id: int
    text: str
    is_ai: bool
    comment_type: str  # 'top_level' or 'reply'

@dataclass
class PostEvaluation:
    post_title: str
    human_comments: List[CommentData]
    ai_comments: List[CommentData]

class CommentEvaluator:
    def __init__(self, anthropic_client: anthropic.Anthropic):
        self.client = anthropic_client

    def _extract_json_from_response(self, response_text: str) -> dict:
        """Extract and clean JSON from Claude's response"""
        import re

        # Find JSON boundaries
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start == -1 or json_end <= json_start:
            raise ValueError("No JSON found in response")

        json_text = response_text[json_start:json_end]

        # Remove JSON comments that Claude sometimes adds
        json_text = re.sub(r'//.*', '', json_text)

        # Remove control characters that can break JSON parsing
        json_text = re.sub(r'[\x00-\x1F\x7F]', '', json_text)

        # Parse JSON
        return json.loads(json_text)

    async def evaluate_post(self, post_data: PostEvaluation) -> Dict[str, float]:
        """
        Evaluate a single post and return 3 simple metrics
        """
        print(f"Evaluating post: {post_data.post_title}")

        # Run all 3 evaluations
        mixed_score = await self._evaluate_mixed_reality(post_data)
        diversity_score = await self._evaluate_diversity(post_data)
        appropriateness_score = await self._evaluate_appropriateness(post_data)

        # Calculate overall score (weighted average)
        overall_score = (mixed_score * 0.5 + diversity_score * 0.3 + appropriateness_score * 0.2)

        return {
            "mixed_reality_score": round(mixed_score, 1),
            "diversity_score": round(diversity_score, 1),
            "appropriateness_score": round(appropriateness_score, 1),
            "overall_score": round(overall_score, 1)
        }

    async def _evaluate_mixed_reality(self, post_data: PostEvaluation) -> float:
        """
        Test: Can judge distinguish AI from human when mixed together?
        Score: How often AI comments are incorrectly identified as human (1-10)
        """
        all_comments = post_data.human_comments + post_data.ai_comments

        # Shuffle comments and create evaluation prompt
        import random
        shuffled = all_comments.copy()
        random.shuffle(shuffled)

        comments_text = "\n\n".join([
            f"Comment {i+1}: {comment.text}"
            for i, comment in enumerate(shuffled)
        ])

        prompt = f"""You are evaluating Reddit comments to identify which ones were AI-generated.

POST CONTEXT: {post_data.post_title}

COMMENTS TO EVALUATE:
{comments_text}

For each comment, rate 1-10 how likely it is to be HUMAN-written:
- 10 = Definitely human (natural Reddit voice, authentic)
- 1 = Definitely AI (too polite, structured, artificial)

Respond in JSON format:
{{
  "comment_scores": [8, 3, 9, 2, 7, 4, 9, 1, 8, 6, 3, 9, 2, 8, 3, 7]
}}"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                temperature=0.1,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = response.content[0].text
            result = self._extract_json_from_response(response_text)
            scores_data = result["comment_scores"]

            # Handle both array and object formats
            if isinstance(scores_data, dict):
                # Convert object {"1": 9, "2": 3} to list [9, 3, ...]
                scores = [scores_data[str(i+1)] for i in range(len(shuffled))]
            else:
                # Already a list
                scores = scores_data

            # Calculate how well AI comments fooled the judge
            ai_scores = []
            for i, comment in enumerate(shuffled):
                if comment.is_ai:
                    ai_scores.append(scores[i])

            # Average score for AI comments (higher = better fooling)
            return sum(ai_scores) / len(ai_scores) if ai_scores else 0

        except (json.JSONDecodeError, KeyError, IndexError, ValueError) as e:
            print(f"Error parsing mixed reality response: {e}")
            print(f"Response text: {response.content[0].text[:200]}...")
            return 0

    async def _evaluate_diversity(self, post_data: PostEvaluation) -> float:
        """
        Test: How varied are the AI comments from each other?
        Score: Diversity and uniqueness of AI comments (1-10)
        """
        ai_comments_text = "\n\n".join([
            f"AI Comment {i+1}: {comment.text}"
            for i, comment in enumerate(post_data.ai_comments)
        ])

        prompt = f"""Evaluate these AI-generated Reddit comments for DIVERSITY and UNIQUENESS.

AI COMMENTS:
{ai_comments_text}

Rate 1-10 how DIVERSE these comments are:
- 10 = Highly diverse (different openings, structures, voices, personalities)
- 1 = Highly repetitive (same phrases, identical patterns, one personality)

Look for:
- Repeated opening phrases
- Identical sentence structures
- Same "voice" or personality
- Similar transition words

Respond in JSON format:
{{
  "diversity_score": 6,
  "main_issue": "3 comments start with same phrase"
}}"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=500,
                temperature=0.1,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = response.content[0].text
            result = self._extract_json_from_response(response_text)
            return float(result["diversity_score"])

        except (json.JSONDecodeError, KeyError, IndexError, ValueError) as e:
            print(f"Error parsing diversity response: {e}")
            print(f"Response text: {response.content[0].text[:200]}...")
            return 0

    async def _evaluate_appropriateness(self, post_data: PostEvaluation) -> float:
        """
        Test: How well do comments fit Reddit context and comment type?
        Score: Appropriateness for Reddit and comment type (1-10)
        """
        top_level_comments = [c for c in post_data.ai_comments if c.comment_type == 'top_level']
        reply_comments = [c for c in post_data.ai_comments if c.comment_type == 'reply']

        top_level_text = "\n".join([f"• {c.text}" for c in top_level_comments])
        reply_text = "\n".join([f"• {c.text}" for c in reply_comments])

        prompt = f"""Evaluate how well these AI comments fit REDDIT CONTEXT and their COMMENT TYPE.

POST: {post_data.post_title}

TOP-LEVEL COMMENTS:
{top_level_text}

REPLY COMMENTS:
{reply_text}

Rate 1-10 how APPROPRIATE these are:
- 10 = Perfect Reddit voice (casual, opinionated, authentic slang)
- 1 = Wrong tone (too formal, polite, helpful, corporate)

Consider:
- Top-level: Should be substantive opinions, hot takes, personal reactions
- Replies: Should be conversational, reactive, building on discussion
- Reddit tone: Casual, direct, sometimes crude, not overly helpful

Respond in JSON format:
{{
  "appropriateness_score": 7,
  "tone_issue": "too polite for Reddit"
}}"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=500,
                temperature=0.1,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = response.content[0].text
            result = self._extract_json_from_response(response_text)
            return float(result["appropriateness_score"])

        except (json.JSONDecodeError, KeyError, IndexError, ValueError) as e:
            print(f"Error parsing appropriateness response: {e}")
            print(f"Response text: {response.content[0].text[:200]}...")
            return 0

async def main():
    """
    Example usage with sample data
    """
    # Get API key from environment
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        return

    # Initialize Anthropic client
    client = anthropic.Anthropic(api_key=api_key)

    # Sample data - replace with your actual post data
    sample_post = PostEvaluation(
        post_title="Wind turbines are eyesores that ruin natural landscapes",
        human_comments=[
            CommentData(1, "God I hate these things. Eyesores.", False, "top_level"),
            CommentData(2, "lol my neighbor complains about these daily", False, "reply"),
            CommentData(3, "they're fine but the noise is annoying af", False, "top_level"),
            CommentData(4, "meh", False, "reply"),
            CommentData(5, "same here, got used to them", False, "reply"),
            CommentData(6, "they look cool at night with the red lights", False, "top_level"),
            CommentData(7, "NIMBY bullshit", False, "top_level"),
            CommentData(8, "depends on location tbh", False, "reply"),
        ],
        ai_comments=[
            CommentData(9, "Interesting how subjective this is. I used to think they were ugly too until I drove through Cowa on a road trip.", True, "top_level"),
            CommentData(10, "I understand both perspectives here. On one hand they provide clean energy, but I can see how they might impact scenic views.", True, "reply"),
            CommentData(11, "This is really fascinating! I never considered the environmental impact versus aesthetic concerns.", True, "top_level"),
            CommentData(12, "Have you considered that different people might have varying reactions to industrial infrastructure in natural settings?", True, "reply"),
            CommentData(13, "Interesting how subjective this is. I live near a wind farm and honestly after the first month I barely even notice them anymore.", True, "top_level"),
            CommentData(14, "I think there's merit to both sides of this discussion. Clean energy is important but so is preserving natural beauty.", True, "reply"),
            CommentData(15, "That's a really thoughtful perspective! I hadn't thought about the psychological adaptation aspect.", True, "reply"),
            CommentData(16, "Interesting how subjective this is - I grew up in Iowa where there are tons of wind farms.", True, "top_level"),
        ]
    )

    # Initialize evaluator
    evaluator = CommentEvaluator(client)

    # Run evaluation
    results = await evaluator.evaluate_post(sample_post)

    # Print clean results
    print("\n" + "="*50)
    print("COMMENT EVALUATION RESULTS")
    print("="*50)
    print(f"Mixed Reality Score: {results['mixed_reality_score']}/10")
    print(f"Diversity Score:     {results['diversity_score']}/10")
    print(f"Appropriateness:     {results['appropriateness_score']}/10")
    print(f"Overall Score:       {results['overall_score']}/10")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())