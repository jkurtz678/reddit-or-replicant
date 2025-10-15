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
from ..reddit_parser import parse_reddit_json, Comment, select_representative_comments
from .comment_archetypes import get_available_archetypes, build_full_prompt
from .comment_legacy import generate_ai_comments_legacy

# Constants
MAX_REDDIT_COMMENTS = 12
USE_ARCHETYPE_SYSTEM = True

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


def get_appropriate_archetypes(post_title: str, post_content: str, subreddit: str,
                              anthropic_client: anthropic.Anthropic) -> List[str]:
    """
    Use AI to determine which archetypes are appropriate for this specific post
    """
    available_archetypes = get_available_archetypes(subreddit)
    
    # Create archetype descriptions for the AI to understand
    archetype_descriptions = []
    for archetype_key in available_archetypes:
        from .comment_archetypes import get_archetype_prompt
        archetype_data = get_archetype_prompt(archetype_key)
        if archetype_data:
            archetype_descriptions.append(f"- {archetype_key}: {archetype_data['description']}")
    
    prompt = f"""Given this Reddit post from r/{subreddit}, which comment archetypes would be most appropriate?

POST TITLE: {post_title}
POST CONTENT: {post_content}

AVAILABLE ARCHETYPES:
{chr(10).join(archetype_descriptions)}

Consider:
- The tone and seriousness of the post
- What types of responses would naturally occur in r/{subreddit}
- The emotional context and subject matter

Select 4-6 archetypes that would be most appropriate for this post. List them exactly as shown above (e.g., "generic:supportive_friend").

Respond with just the archetype keys, one per line."""

    try:
        response = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=300,
            temperature=0.3,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        response_text = response.content[0].text.strip()
        selected_archetypes = [line.strip() for line in response_text.split('\n') if line.strip()]
        
        # Validate that selected archetypes exist
        valid_archetypes = [arch for arch in selected_archetypes if arch in available_archetypes]
        
        if not valid_archetypes:
            print(f"No valid archetypes selected, using fallback")
            # Fallback to generic archetypes
            return [arch for arch in available_archetypes if arch.startswith('generic:')][:4]
        
        print(f"Selected archetypes for post: {valid_archetypes}")
        return valid_archetypes
        
    except Exception as e:
        print(f"Error selecting archetypes: {e}")
        # Fallback to generic archetypes
        return [arch for arch in available_archetypes if arch.startswith('generic:')][:4]


def get_score_range(real_comments: List[Comment]) -> tuple[int, int]:
    """Get the score range from real comments to generate realistic AI scores"""
    scores = [comment.score for comment in real_comments if comment.score > 0]
    if not scores:
        return 1, 50
    
    min_score = max(1, min(scores))
    max_score = max(scores)
    return min_score, max_score


def generate_single_ai_comment(post_title: str, post_content: str, subreddit: str,
                              real_comments: List[Comment], archetype_key: str,
                              anthropic_client: anthropic.Anthropic,
                              previously_generated: List[Comment] = None) -> Comment:
    """Generate a single AI comment using a specific archetype"""
    
    # Sample a few real comments for context and length examples
    sample_comments = random.sample(real_comments, min(3, len(real_comments)))

    # Create examples showing the variety of real comment lengths
    examples = "\n".join([
        f"- u/{comment.author} ({len(comment.content.split())} words): {comment.content[:150]}{'...' if len(comment.content) > 150 else ''}"
        for comment in sample_comments
    ])

    # Add previously generated comments to avoid repetition
    avoid_repetition_text = ""
    if previously_generated:
        avoid_repetition_text = "\n\nPREVIOUSLY GENERATED AI COMMENTS (DO NOT REPEAT THESE PATTERNS):\n"
        for i, prev_comment in enumerate(previously_generated[-7:]):  # Show up to 7 previous comments to catch patterns
            opening = prev_comment.content.split('.')[0] if '.' in prev_comment.content else prev_comment.content[:50]
            avoid_repetition_text += f"- AI Comment {i+1} opening: \"{opening}...\"\n"
        avoid_repetition_text += "\nIMPORTANT: Avoid starting with similar phrases, structures, or personal anecdotes as the AI comments above.\n"

    # Get length statistics from real comments for guidance
    real_word_counts = [len(comment.content.split()) for comment in flatten_all_comments(real_comments)]
    avg_length = sum(real_word_counts) / len(real_word_counts) if real_word_counts else 20
    min_length = min(real_word_counts) if real_word_counts else 5
    max_length = max(real_word_counts) if real_word_counts else 50

    # Pick a target length based on the real comment distribution
    # Bias toward shorter comments (most Reddit comments are brief)
    rand_val = random.random()
    if rand_val < 0.4:  # 40% chance of very short
        target_length = min(15, max_length)
    elif rand_val < 0.7:  # 30% chance of medium
        target_length = min(30, max_length)
    else:  # 30% chance of longer
        target_length = min(max_length, 50)  # Cap at 50 words max

    length_guidance = f"""
CRITICAL LENGTH REQUIREMENT:
- Your response MUST be {target_length} words or fewer
- Real comments here: {min_length}-{max_length} words (avg: {avg_length:.0f})
- TARGET FOR THIS COMMENT: {target_length} words maximum
- Count your words carefully - responses over {target_length} words will be rejected
- Most Reddit comments are brief and to the point, not explanatory essays"""

    # Build the full prompt using the archetype system with our enhancements
    base_prompt = build_full_prompt(
        archetype_key=archetype_key,
        subreddit=subreddit,
        post_title=post_title,
        post_content=post_content,
        real_comment_examples=examples
    )

    # Enhance the prompt with our repetition prevention and length guidance
    prompt = f"""{base_prompt}{avoid_repetition_text}{length_guidance}

CRITICAL REMINDERS:
- Be unique and unexpected - avoid cliché openings like "I used to work at..." or "My [relative] said..."
- Vary your comment length to match real Reddit patterns
- Don't repeat patterns from previously generated AI comments
- Sound natural and human, not like you're trying to be comprehensive or helpful"""
    
    try:
        response = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=800,  # Reduced since we're generating single comments
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
            is_ai=True,
            generation_prompt=prompt,
            archetype_used=archetype_key
        )
        
        print(f"Generated comment with archetype {archetype_key}: {comment.content[:50]}...")
        return comment
        
    except Exception as e:
        print(f"Error generating AI comment with archetype {archetype_key}: {e}")
        return None




def generate_ai_comments_with_archetypes(post_title: str, post_content: str, subreddit: str,
                                        real_comments: List[Comment], num_to_generate: int,
                                        anthropic_client: anthropic.Anthropic) -> List[Comment]:
    """Generate AI comments using the archetype system with repetition prevention"""

    # Step 1: Get appropriate archetypes for this post
    appropriate_archetypes = get_appropriate_archetypes(
        post_title, post_content, subreddit, anthropic_client
    )

    if not appropriate_archetypes:
        print("No appropriate archetypes found, cannot generate AI comments")
        return []

    # Step 2: Create a pool of archetypes with limited repetition
    # Allow each archetype to be used at most twice to prevent over-repetition
    archetype_pool = []
    max_uses_per_archetype = min(2, max(1, num_to_generate // len(appropriate_archetypes)))

    for archetype in appropriate_archetypes:
        archetype_pool.extend([archetype] * max_uses_per_archetype)

    # If we need more archetypes than available, add extras randomly
    while len(archetype_pool) < num_to_generate:
        archetype_pool.append(random.choice(appropriate_archetypes))

    # Shuffle the pool
    random.shuffle(archetype_pool)

    print(f"Archetype distribution: {max_uses_per_archetype} uses per archetype max")

    # Step 3: Generate individual comments using archetypes from the pool
    ai_comments = []
    for i in range(num_to_generate):
        # Select archetype from pool (no repeats beyond our limit)
        selected_archetype = archetype_pool[i] if i < len(archetype_pool) else random.choice(appropriate_archetypes)

        # Generate single comment with this archetype, passing previously generated comments
        comment = generate_single_ai_comment(
            post_title=post_title,
            post_content=post_content,
            subreddit=subreddit,
            real_comments=real_comments,
            archetype_key=selected_archetype,
            anthropic_client=anthropic_client,
            previously_generated=ai_comments  # Pass previous comments to avoid repetition
        )

        if comment:
            ai_comments.append(comment)
        else:
            print(f"Failed to generate comment {i+1}/{num_to_generate}")

    print(f"Successfully generated {len(ai_comments)}/{num_to_generate} AI comments using archetypes")
    return ai_comments


def generate_ai_comments_wrapper(post_title: str, post_content: str, subreddit: str,
                               real_comments: List[Comment], num_to_generate: int,
                               anthropic_client: anthropic.Anthropic) -> List[Comment]:
    """Generate AI comments using either archetype or legacy system based on USE_ARCHETYPE_SYSTEM flag"""
    
    if USE_ARCHETYPE_SYSTEM:
        print("Using archetype system for AI comment generation")
        return generate_ai_comments_with_archetypes(
            post_title, post_content, subreddit, real_comments, num_to_generate, anthropic_client
        )
    else:
        print("Using legacy system for AI comment generation")
        return generate_ai_comments_legacy(
            post_title, post_content, subreddit, real_comments, num_to_generate, anthropic_client
        )


# Keep old function for backwards compatibility, but mark as deprecated
def generate_ai_comments(post_title: str, post_content: str, subreddit: str,
                        real_comments: List[Comment], num_to_generate: int,
                        anthropic_client: anthropic.Anthropic) -> List[Comment]:
    """Generate AI comments using Claude (DEPRECATED - use generate_ai_comments_wrapper)"""
    print("Warning: Using deprecated generate_ai_comments function")
    return generate_ai_comments_wrapper(
        post_title, post_content, subreddit, real_comments, num_to_generate, anthropic_client
    )


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

CRITICAL REPLY FORMATTING:
- NEVER start with "u/username:" - real Reddit replies don't do this
- Jump straight into your response without addressing the username
- Real examples: "Yeah, exactly this." NOT "u/someone: Yeah, exactly this."
- If you need to reference them, use "you" or just reply directly

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
        ai_top_level = generate_ai_comments_wrapper(
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
    mixed_comments = insert_ai_comments(real_comments, ai_top_level, ai_replies, 0.5)  # 50/50 split
    
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