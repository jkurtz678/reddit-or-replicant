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
from faker import Faker
from .reddit_parser import parse_reddit_json, Comment, select_representative_comments

# Constants
MAX_REDDIT_COMMENTS = 12

# Initialize Faker for username generation
fake = Faker()


def generate_reddit_username() -> str:
    """Generate a realistic Reddit-style username using Faker"""
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


def anonymize_usernames(comments: List[Comment]) -> Dict[str, str]:
    """Create mapping of real usernames to anonymized ones"""
    # Get all unique usernames from the comment tree
    def collect_usernames(comments_list):
        usernames = set()
        for comment in comments_list:
            usernames.add(comment.author)
            usernames.update(collect_usernames(comment.replies))
        return usernames
    
    all_usernames = collect_usernames(comments)
    
    # Generate anonymized mapping
    username_mapping = {}
    for original_username in all_usernames:
        # Generate unique anonymized username
        while True:
            new_username = generate_reddit_username()
            if new_username not in username_mapping.values():
                username_mapping[original_username] = new_username
                break
    
    return username_mapping


def apply_username_anonymization(comments: List[Comment], username_mapping: Dict[str, str]):
    """Apply username anonymization to comment tree"""
    for comment in comments:
        if comment.author in username_mapping:
            comment.author = username_mapping[comment.author]
        apply_username_anonymization(comment.replies, username_mapping)


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

Format as JSON array where each comment has:
- "content": natural human comment

DO NOT include usernames - just the comment content. Make these truly indistinguishable from real humans.
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
        #print(f"Claude response: {response_text[:500]}...")  # Debug output
        
        # Try to extract JSON from the response
        try:
            # Look for JSON array in the response
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON array found in response")
                
            json_str = response_text[start_idx:end_idx]
            
            # Clean control characters that can break JSON parsing
            import re
            json_str = re.sub(r'[\x00-\x1F\x7F]', '', json_str)
            
            generated_data = json.loads(json_str)
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Failed to parse JSON from Claude response: {e}")
            print(f"Raw response: {response_text}")
            return []
        
        # Convert to Comment objects
        ai_comments = []
        min_score, max_score = get_score_range(real_comments)
        
        for item in generated_data:
            if not isinstance(item, dict) or 'content' not in item:
                print(f"Skipping malformed comment: {item}")
                continue
                
            comment = Comment(
                id=str(uuid.uuid4()),
                author=generate_reddit_username(),  # Use Faker for username
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


def count_all_comments(comments: List[Comment]) -> int:
    """Count all comments including nested replies"""
    total = 0
    for comment in comments:
        total += 1  # Count this comment
        total += count_all_comments(comment.replies)  # Count all replies recursively
    return total


def flatten_all_comments(comments: List[Comment]) -> List[Comment]:
    """Flatten all comments into a single list"""
    flattened = []
    for comment in comments:
        flattened.append(comment)
        flattened.extend(flatten_all_comments(comment.replies))
    return flattened


def get_thread_context(comment: Comment, all_comments_flat: List[Comment]) -> List[Comment]:
    """Get the full thread chain leading to a comment"""
    thread = []
    current = comment
    
    # Walk up the parent chain
    while current.parent_id:
        parent = next((c for c in all_comments_flat if c.id == current.parent_id), None)
        if parent:
            thread.insert(0, parent)  # Insert at beginning to maintain order
            current = parent
        else:
            break
    
    return thread


def generate_thread_reply(post_title: str, post_content: str, subreddit: str,
                         thread_context: List[Comment], parent_comment: Comment,
                         anthropic_client: anthropic.Anthropic) -> Comment:
    """Generate a single AI reply to a specific comment with full thread context"""
    
    # Build thread context string
    context_str = ""
    if thread_context:
        context_str = "THREAD CONTEXT (conversation so far):\n"
        for i, ctx_comment in enumerate(thread_context):
            context_str += f"{i+1}. u/{ctx_comment.author}: {ctx_comment.content[:200]}{'...' if len(ctx_comment.content) > 200 else ''}\n"
        context_str += "\n"
    
    prompt = f"""You are generating a realistic Reddit reply for r/{subreddit}.

POST TITLE: {post_title}

POST CONTENT: {post_content}

{context_str}COMMENT YOU'RE REPLYING TO:
u/{parent_comment.author}: {parent_comment.content}

Generate 1 realistic Reddit reply to this comment. The reply should:

1. Be contextually relevant to the immediate parent comment
2. Consider the broader thread context if provided
3. Sound natural and human-written
4. Use a generic, unrelated username (NOT topic-related)
5. Vary in style (could be short reaction, longer response, question, anecdote, etc.)

CRITICAL: Make this indistinguishable from a real human reply. Don't try too hard to sound "Reddit-y".

Format as JSON:
{{"content": "reply text"}}
"""
    
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
        
        response_text = response.content[0].text
        # print(f"Generated thread reply: {response_text[:200]}...")
        
        # Parse JSON
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        
        if start_idx == -1 or end_idx == 0:
            raise ValueError("No JSON found in response")
            
        json_str = response_text[start_idx:end_idx]
        
        # Clean control characters that can break JSON parsing
        import re
        json_str = re.sub(r'[\x00-\x1F\x7F]', '', json_str)
        
        reply_data = json.loads(json_str)
        
        if 'content' not in reply_data:
            raise ValueError("Missing required fields in response")
        
        # Create reply with appropriate depth
        reply = Comment(
            id=str(uuid.uuid4()),
            author=generate_reddit_username(),  # Use Faker for username
            content=reply_data['content'],
            content_html=None,
            score=random.randint(1, max(50, parent_comment.score)),
            depth=parent_comment.depth + 1,
            parent_id=parent_comment.id,
            replies=[],
            is_ai=True
        )
        
        return reply
        
    except Exception as e:
        print(f"Error generating thread reply: {e}")
        return None


def insert_ai_comments(real_comments: List[Comment], ai_top_level: List[Comment], 
                      ai_replies: List[tuple[Comment, str]], ai_percentage: float) -> List[Comment]:
    """Insert AI comments into the real comment structure"""
    
    # Combine all top-level comments (real + AI) and shuffle them randomly
    all_top_level = real_comments.copy() + ai_top_level
    random.shuffle(all_top_level)
    
    # Insert AI replies into threads
    for ai_reply, parent_id in ai_replies:
        # Find the parent comment in the mixed structure
        def find_and_insert(comments):
            for comment in comments:
                if comment.id == parent_id:
                    # Insert randomly among existing replies
                    insert_pos = random.randint(0, len(comment.replies))
                    comment.replies.insert(insert_pos, ai_reply)
                    return True
                elif find_and_insert(comment.replies):
                    return True
            return False
        
        find_and_insert(all_top_level)
    
    return all_top_level


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
        with open('test-posts/test-reddit.json', 'r') as f:
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
        
        # Select representative comments to limit size
        print(f"Selecting representative comments (max {MAX_REDDIT_COMMENTS})...")
        real_comments = select_representative_comments(real_comments, MAX_REDDIT_COMMENTS)
        print(f"Selected {len(real_comments)} top-level comments with {count_all_comments(real_comments)} total comments")
        
        # Anonymize real usernames
        print("Anonymizing usernames...")
        username_mapping = anonymize_usernames(real_comments)
        apply_username_anonymization(real_comments, username_mapping)
        
        # Also anonymize post author
        if post.author in username_mapping:
            post.author = username_mapping[post.author]
        else:
            post.author = generate_reddit_username()
            
        print(f"Anonymized {len(username_mapping)} usernames")
        
    except Exception as e:
        print(f"Error parsing Reddit data: {e}")
        return
    
    # Generate equal number of AI comments to match real comments (50/50 split)
    total_real_comments = count_all_comments(real_comments)
    target_ai_count = total_real_comments  # 1:1 ratio for balanced gameplay
    
    if target_ai_count == 0:
        print("Not enough real comments to generate AI comments")
        return
        
    print(f"Total real comments (including nested): {total_real_comments}")
    print(f"Target AI comments (50/50 split): {target_ai_count}")
    
    # Decide how many top-level vs reply AI comments
    ai_top_level_count = 0
    ai_reply_count = 0
    
    for i in range(target_ai_count):
        if random.random() < 0.5 and ai_top_level_count < 15:  # 50% chance of top-level vs reply, but max 15 top-level
            ai_top_level_count += 1
        else:
            ai_reply_count += 1
    
    print(f"Will generate: {ai_top_level_count} top-level AI comments, {ai_reply_count} thread replies")
    
    # Generate top-level AI comments first
    ai_top_level = []
    if ai_top_level_count > 0:
        ai_top_level = generate_ai_comments(
            post.title,
            post.content,
            post.subreddit,
            real_comments,
            ai_top_level_count,
            client
        )
        
        if not ai_top_level:
            print("Failed to generate top-level AI comments")
            return
    
    # Build pool of all comments (real + AI) for reply targets
    all_comments_flat = flatten_all_comments(real_comments)  # Start with real comments
    all_comments_flat.extend(ai_top_level)  # Add AI top-level comments
    
    # Generate thread replies - can target any comment (real or AI)
    ai_replies = []
    for i in range(ai_reply_count):
        if not all_comments_flat:
            break
            
        # Choose random comment to reply to (could be real or AI)
        parent_comment = random.choice(all_comments_flat)
        print(f"Generating reply to u/{parent_comment.author}{'[AI]' if parent_comment.is_ai else ''}...")
        
        # Get full thread context (using all available comments)
        thread_context = get_thread_context(parent_comment, all_comments_flat)
        
        ai_reply = generate_thread_reply(
            post.title,
            post.content,
            post.subreddit,
            thread_context,
            parent_comment,
            client
        )
        
        if ai_reply:
            ai_replies.append((ai_reply, parent_comment.id))
        else:
            print(f"Failed to generate reply to {parent_comment.id}")
    
    print(f"Successfully generated {len(ai_top_level)} top-level + {len(ai_replies)} thread replies")
    
    # Insert AI comments into structure
    mixed_comments = insert_ai_comments(real_comments, ai_top_level, ai_replies, ai_percentage)
    
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
        
        # Count final results
        total_final_comments = count_all_comments(mixed_comments)
        total_ai_final = sum(1 for c in flatten_all_comments(mixed_comments) if c.is_ai)
        
        print(f"Saved mixed comments to mixed-comments.json")
        print(f"Final stats:")
        print(f"  Total comments (all levels): {total_final_comments}")
        print(f"  AI comments: {total_ai_final}")
        print(f"  Actual AI percentage: {total_ai_final/total_final_comments*100:.1f}%")
        
    except Exception as e:
        print(f"Error saving mixed comments: {e}")


if __name__ == "__main__":
    main()