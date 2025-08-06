#!/usr/bin/env python3
"""
Generate AI comments and mix them with real Reddit comments.

Usage:
    python generate_mixed_comments.py

Requirements:
    - Set ANTHROPIC_API_KEY environment variable
    - Input: test-reddit.json
    - Output: mixed-comments.json
"""

import json
import os
import random
import uuid
from typing import List, Dict, Any
import anthropic
from reddit_parser import parse_reddit_json, Comment


def get_score_range(real_comments: List[Comment]) -> tuple[int, int]:
    """Get the score range from real comments to generate realistic AI scores"""
    scores = [comment.score for comment in real_comments if comment.score > 0]
    if not scores:
        return 1, 50
    
    min_score = max(1, min(scores))
    max_score = max(scores)
    return min_score, max_score


def create_generation_prompt(post_title: str, post_content: str, subreddit: str, 
                           real_comments: List[Comment], num_to_generate: int) -> str:
    """Create the prompt for Claude to generate realistic comments"""
    
    # Sample a few real comments for context
    sample_comments = random.sample(real_comments, min(3, len(real_comments)))
    
    examples = "\n".join([
        f"- u/{comment.author}: {comment.content[:150]}{'...' if len(comment.content) > 150 else ''}"
        for comment in sample_comments
    ])
    
    # Extract just the usernames for examples
    real_usernames = [comment.author for comment in sample_comments]
    username_examples = ", ".join(real_usernames)
    
    prompt = f"""You are generating realistic Reddit comments for r/{subreddit}. 

POST TITLE: {post_title}

POST CONTENT: {post_content}

EXAMPLES OF REAL COMMENTS FROM THIS THREAD:
{examples}

Generate {num_to_generate} realistic Reddit comments that would naturally appear in this thread.

CRITICAL REQUIREMENTS:

USERNAMES: Create completely generic, unrelated usernames like the real ones above ({username_examples}). 
- DO NOT make usernames relate to the post topic or content
- Use random combinations like: numbers, random words, gaming terms, etc.
- Examples of good generic usernames: mikejones234, xXgamerXx, throwaway_acc, techbro99

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

Format as JSON array:
- "username": generic Reddit username (NOT topic-related)
- "content": natural human comment

Make these truly indistinguishable from real humans. Focus on sounding natural rather than "Reddit-y".
"""
    
    return prompt


def generate_ai_comments(post_title: str, post_content: str, subreddit: str,
                        real_comments: List[Comment], num_to_generate: int,
                        anthropic_client: anthropic.Anthropic) -> List[Comment]:
    """Generate AI comments using Claude"""
    
    prompt = create_generation_prompt(post_title, post_content, subreddit, 
                                    real_comments, num_to_generate)
    
    try:
        response = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            temperature=0.8,  # Higher temperature for more variety
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        # Parse the JSON response
        response_text = response.content[0].text
        print(f"Claude response: {response_text[:500]}...")  # Debug output
        
        # Try to extract JSON from the response
        try:
            # Look for JSON array in the response
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON array found in response")
                
            json_str = response_text[start_idx:end_idx]
            generated_data = json.loads(json_str)
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Failed to parse JSON from Claude response: {e}")
            print(f"Raw response: {response_text}")
            return []
        
        # Convert to Comment objects
        ai_comments = []
        min_score, max_score = get_score_range(real_comments)
        
        for item in generated_data:
            if not isinstance(item, dict) or 'username' not in item or 'content' not in item:
                print(f"Skipping malformed comment: {item}")
                continue
                
            comment = Comment(
                id=str(uuid.uuid4()),
                author=item['username'],
                content=item['content'],
                content_html=None,  # No HTML for AI comments
                score=random.randint(min_score, max_score),
                depth=0,
                parent_id=None,
                replies=[],
                is_ai=True
            )
            ai_comments.append(comment)
        
        print(f"Generated {len(ai_comments)} AI comments")
        return ai_comments
        
    except Exception as e:
        print(f"Error generating AI comments: {e}")
        return []


def mix_comments(real_comments: List[Comment], ai_comments: List[Comment], 
                ai_percentage: float = 0.2) -> List[Comment]:
    """Mix AI comments with real comments randomly"""
    
    total_real = len(real_comments)
    target_ai_count = int(total_real * ai_percentage)
    
    # Use only the number of AI comments we need
    ai_to_use = ai_comments[:target_ai_count]
    
    # Combine and shuffle
    mixed = real_comments + ai_to_use
    random.shuffle(mixed)
    
    print(f"Mixed {len(real_comments)} real + {len(ai_to_use)} AI = {len(mixed)} total comments")
    return mixed


def main():
    """Main function to generate mixed comments"""
    
    # Check for API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        print("Set it with: export ANTHROPIC_API_KEY=your_key_here")
        return
    
    # Initialize Anthropic client
    client = anthropic.Anthropic(api_key=api_key)
    
    # Load original Reddit data
    try:
        with open('test-reddit.json', 'r') as f:
            raw_data = json.load(f)
        print("Loaded original Reddit data")
    except FileNotFoundError:
        print("Error: test-reddit.json not found")
        return
    except json.JSONDecodeError:
        print("Error: Invalid JSON in test-reddit.json")
        return
    
    # Parse into clean structure
    try:
        parsed_data = parse_reddit_json(raw_data)
        post = parsed_data['post']
        real_comments = parsed_data['comments']
        
        if not post or not real_comments:
            print("Error: No post or comments found in data")
            return
            
        print(f"Parsed {len(real_comments)} real comments")
        
    except Exception as e:
        print(f"Error parsing Reddit data: {e}")
        return
    
    # Calculate how many AI comments to generate
    ai_percentage = 0.5  # 50%
    num_ai_comments = int(len(real_comments) * ai_percentage)
    
    if num_ai_comments == 0:
        print("Not enough real comments to generate AI comments")
        return
        
    print(f"Generating {num_ai_comments} AI comments ({ai_percentage*100}% of {len(real_comments)} real comments)")
    
    # Generate AI comments
    ai_comments = generate_ai_comments(
        post.title,
        post.content,
        post.subreddit,
        real_comments,
        num_ai_comments,
        client
    )
    
    if not ai_comments:
        print("Failed to generate AI comments")
        return
    
    # Mix comments
    mixed_comments = mix_comments(real_comments, ai_comments, ai_percentage)
    
    def comment_to_dict(comment: Comment) -> dict:
        """Convert Comment object to dictionary for JSON serialization"""
        return {
            'id': comment.id,
            'author': comment.author,
            'content': comment.content,
            'content_html': comment.content_html,
            'score': comment.score,
            'depth': comment.depth,
            'parent_id': comment.parent_id,
            'replies': [comment_to_dict(reply) for reply in comment.replies],
            'is_ai': comment.is_ai
        }
    
    # Create final data structure
    final_data = {
        'post': {
            'id': post.id,
            'title': post.title,
            'content': post.content,
            'author': post.author,
            'subreddit': post.subreddit,
            'score': post.score,
            'comment_count': len(mixed_comments)  # Update count
        },
        'comments': [comment_to_dict(comment) for comment in mixed_comments]
    }
    
    # Save mixed data
    try:
        with open('mixed-comments.json', 'w') as f:
            json.dump(final_data, f, indent=2)
        print(f"Saved mixed comments to mixed-comments.json")
        print(f"Total: {len(mixed_comments)} comments ({sum(1 for c in mixed_comments if c.is_ai)} AI)")
        
    except Exception as e:
        print(f"Error saving mixed comments: {e}")


if __name__ == "__main__":
    main()