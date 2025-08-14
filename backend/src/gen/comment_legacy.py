"""
Legacy comment generation system using original prompts.
This module contains the original prompt-based comment generation logic.
"""

import json
import random
import uuid
from typing import List
import anthropic
from ..reddit_parser import Comment


def create_generation_prompt(post_title: str, post_content: str, subreddit: str, 
                           real_comments: List[Comment]) -> str:
    """Create the prompt for Claude to generate a single realistic comment"""
    
    # Sample a few real comments for context
    sample_comments = random.sample(real_comments, min(3, len(real_comments)))
    
    examples = "\n".join([
        f"- u/{comment.author}: {comment.content[:150]}{'...' if len(comment.content) > 150 else ''}"
        for comment in sample_comments
    ])
    
    prompt = f"""You are generating realistic Reddit comments for r/{subreddit}. 

POST TITLE: {post_title}

POST CONTENT: {post_content}

EXAMPLES OF REAL COMMENTS FROM THIS THREAD:
{examples}

Generate 1 realistic Reddit comment that would naturally appear in this thread.

CRITICAL REQUIREMENTS:

COMMENT STYLE: Write like real humans, not like you're trying to sound like Reddit:
- Don't force slang or try too hard to sound casual - be naturally conversational
- Don't be overly helpful or informative - mix in casual reactions too
- Some people just leave short reactions, others tell stories
- Natural writing but don't overdo typos or internet speak
- Avoid sounding like an expert giving advice unless it fits naturally

Vary between:
- Quick reactions ("oh no", "that sucks", "been there")  
- Personal anecdotes (brief, natural)
- Casual sympathy/humor
- Sometimes just acknowledgment

Format as JSON:
{{"content": "natural human comment"}}

DO NOT include usernames - just the comment content. Make this truly indistinguishable from a real human.
"""
    
    return prompt


def get_score_range(real_comments: List[Comment]) -> tuple[int, int]:
    """Get the score range from real comments to generate realistic AI scores"""
    scores = [comment.score for comment in real_comments if comment.score > 0]
    if not scores:
        return 1, 50
    
    min_score = max(1, min(scores))
    max_score = max(scores)
    return min_score, max_score


def generate_reddit_username() -> str:
    """Generate a realistic Reddit-style username using Faker"""
    from faker import Faker
    fake = Faker()
    
    patterns = [
        # Basic username patterns
        lambda: fake.user_name(),
        lambda: f"{fake.first_name().lower()}{random.randint(1, 999)}",
        lambda: f"{fake.last_name().lower()}{random.randint(10, 99)}",
        
        # Compound patterns  
        lambda: f"{fake.word()}_{fake.word()}",
        lambda: f"{fake.word()}{random.randint(1, 999)}",
        lambda: f"throwaway_{random.randint(1000, 9999)}",
        
        # Gaming/internet style
        lambda: f"x{fake.word().capitalize()}x",
        lambda: f"{fake.word()}_guy_{random.randint(1, 99)}",
        lambda: f"random_{fake.word()}_{random.randint(1, 999)}",
        
        # Reddit-specific patterns
        lambda: f"deleted_user_{random.randint(1000, 9999)}",
        lambda: f"{fake.color_name().lower()}{fake.word().capitalize()}{random.randint(1, 99)}",
        lambda: f"{fake.word()}lover{random.randint(1, 999)}",
    ]
    
    # Choose random pattern and generate
    pattern = random.choice(patterns)
    username = pattern()
    
    # Clean up username (remove invalid characters, ensure reasonable length)
    username = ''.join(c for c in username if c.isalnum() or c in '_-')
    username = username[:20]  # Max Reddit username length
    
    return username


def generate_single_ai_comment_legacy(post_title: str, post_content: str, subreddit: str,
                                     real_comments: List[Comment], anthropic_client: anthropic.Anthropic) -> Comment:
    """Generate a single AI comment using the legacy prompt system"""
    
    # Build the legacy prompt
    prompt = create_generation_prompt(post_title, post_content, subreddit, real_comments)
    
    try:
        response = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=800,
            temperature=0.8,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        response_text = response.content[0].text.strip()
        
        # Try to extract JSON from the response
        try:
            # Look for JSON object in the response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON object found in response")
                
            json_str = response_text[start_idx:end_idx]
            
            # Clean control characters that can break JSON parsing
            import re
            json_str = re.sub(r'[\x00-\x1F\x7F]', '', json_str)
            
            comment_data = json.loads(json_str)
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Failed to parse JSON from Claude response: {e}")
            print(f"Raw response: {response_text}")
            return None
        
        if not isinstance(comment_data, dict) or 'content' not in comment_data:
            print(f"Malformed comment data: {comment_data}")
            return None
        
        # Generate realistic score
        min_score, max_score = get_score_range(real_comments)
        
        # Create Comment object
        comment = Comment(
            id=str(uuid.uuid4()),
            author=generate_reddit_username(),
            content=comment_data['content'],
            content_html=None,  # No HTML for AI comments
            score=random.randint(min_score, max_score),
            depth=0,
            parent_id=None,
            replies=[],
            is_ai=True
        )
        
        print(f"Generated legacy comment: {comment.content[:50]}...")
        return comment
        
    except Exception as e:
        print(f"Error generating AI comment with legacy system: {e}")
        return None


def generate_ai_comments_legacy(post_title: str, post_content: str, subreddit: str,
                               real_comments: List[Comment], num_to_generate: int,
                               anthropic_client: anthropic.Anthropic) -> List[Comment]:
    """Generate AI comments using the legacy prompt system"""
    
    ai_comments = []
    for i in range(num_to_generate):
        comment = generate_single_ai_comment_legacy(
            post_title=post_title,
            post_content=post_content,
            subreddit=subreddit,
            real_comments=real_comments,
            anthropic_client=anthropic_client
        )
        
        if comment:
            ai_comments.append(comment)
        else:
            print(f"Failed to generate legacy comment {i+1}/{num_to_generate}")
    
    print(f"Successfully generated {len(ai_comments)}/{num_to_generate} AI comments using legacy system")
    return ai_comments