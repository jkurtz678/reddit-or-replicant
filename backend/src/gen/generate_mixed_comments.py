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
from .comment_archetypes import get_available_archetypes, build_full_prompt, DEBATE_POSITION_PROMPT, DEBATE_POSITION_PROMPT_SAFE, POST_SUMMARIZATION_PROMPT, WRITING_STYLES, apply_writing_style_formatting
from .comment_legacy import generate_ai_comments_legacy

# Constants
MAX_REDDIT_COMMENTS = 12
USE_ARCHETYPE_SYSTEM = True

# Initialize Faker for username generation
fake = Faker()


def select_writing_style() -> str:
    """Select a random writing style based on weights"""
    styles = list(WRITING_STYLES.keys())
    weights = [WRITING_STYLES[style]['weight'] for style in styles]
    return random.choices(styles, weights=weights)[0]


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
    
    prompt = f"""Given this Reddit post from r/{subreddit}, select a diverse mix of comment archetypes that could reasonably appear in the comments.

POST TITLE: {post_title}
POST CONTENT: {post_content}

AVAILABLE ARCHETYPES:
{chr(10).join(archetype_descriptions)}

SELECTION CRITERIA:
- Include a mix of topic-focused AND personality-driven archetypes
- Personality archetypes can comment on ANY topic from their unique perspective
- Only exclude archetypes that would be completely irrelevant (e.g., relationship advice archetypes on tech posts)
- Prioritize diversity - mix serious responses with casual ones, different viewpoints, etc.
- Remember: real Reddit threads have all kinds of people with different personalities commenting

Select 8 archetypes that could reasonably appear. Include personality archetypes even if they're not perfectly "on-topic" - they make comments more realistic. List them exactly as shown above (e.g., "generic:supportive_friend").

Respond with just the archetype keys, one per line."""

    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=300,
            temperature=0.5,
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
            return [arch for arch in available_archetypes if arch.startswith('generic:')][:8]
        
        print(f"Selected archetypes for post: {valid_archetypes}")
        return valid_archetypes
        
    except Exception as e:
        print(f"Error selecting archetypes: {e}")
        # Fallback to generic archetypes
        return [arch for arch in available_archetypes if arch.startswith('generic:')][:8]


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
                              previously_generated: List[Comment] = None,
                              tyrell_agenda: str = "") -> Comment:
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
    # COMMENTED OUT: Previously generated AI comments section - testing if it's necessary with different archetypes
    # if previously_generated:
    #     avoid_repetition_text = "\n\nPREVIOUSLY GENERATED AI COMMENTS (DO NOT REPEAT THESE PATTERNS):\n"
    #     for i, prev_comment in enumerate(previously_generated[-7:]):  # Show up to 7 previous comments to catch patterns
    #         opening = prev_comment.content.split('.')[0] if '.' in prev_comment.content else prev_comment.content[:50]
    #         avoid_repetition_text += f"- AI Comment {i+1} opening: \"{opening}...\"\n"
    #     avoid_repetition_text += "\nIMPORTANT: Avoid starting with similar phrases, structures, or personal anecdotes as the AI comments above.\n"

    # Get length statistics from real TOP-LEVEL comments only (not replies)
    real_word_counts = [len(comment.content.split()) for comment in real_comments if comment.depth == 0]

    if real_word_counts:
        # Use percentiles for more natural distribution
        real_word_counts.sort()
        percentile_25 = real_word_counts[len(real_word_counts) // 4]
        percentile_50 = real_word_counts[len(real_word_counts) // 2]
        percentile_75 = real_word_counts[(len(real_word_counts) * 3) // 4]
        avg_length = sum(real_word_counts) / len(real_word_counts)
        min_length = min(real_word_counts)
        max_length = max(real_word_counts)

        # Select length target based on percentiles with equal distribution
        rand_val = random.random()
        if rand_val < 0.33:  # 33% chance of shorter comments
            base_suggested = percentile_25
        elif rand_val < 0.67:  # 33% chance of medium comments
            base_suggested = percentile_50
        else:  # 33% chance of longer comments
            base_suggested = percentile_75

        # Remove buffer - use percentile directly as suggestion
        suggested_length = base_suggested
        # Tighter maximum - 30% over suggested instead of 50%
        max_allowed = int(suggested_length * 1.3)
        print(f"Top-level comment length guidance: suggested={suggested_length} words, max={max_allowed} words (based on real top-level comment analysis)")
    else:
        # Fallback for threads with no real comments
        suggested_length = 25
        max_allowed = 33
        avg_length = 20
        min_length = 5
        max_length = 50
        print(f"Top-level comment length guidance: suggested={suggested_length} words, max={max_allowed} words (fallback)")

    length_guidance = f"""
LENGTH GUIDANCE:
- Suggested: {suggested_length} words, Maximum: {max_allowed} words
- Real comments here: {min_length}-{max_length} words (avg: {avg_length:.0f})
- Aim for suggested length. Do NOT exceed the maximum."""

    # Randomly assign directive tier (25% tier 1, 37.5% tier 2, 37.5% tier 3)
    rand_val = random.random()
    if rand_val < 0.25:
        directive_tier = 1  # Strong
    elif rand_val < 0.625:  # 0.25 + 0.375
        directive_tier = 2  # Subtle
    else:
        directive_tier = 3  # None

    print(f"Directive tier {directive_tier} assigned to {archetype_key}")

    # Select writing style for this comment
    writing_style = select_writing_style()
    print(f"Writing style '{writing_style}' assigned to {archetype_key}")

    # Build the full prompt using the archetype system with our enhancements
    base_prompt = build_full_prompt(
        archetype_key=archetype_key,
        subreddit=subreddit,
        post_title=post_title,
        post_content=post_content,
        real_comment_examples=examples,
        tyrell_agenda=tyrell_agenda,
        directive_tier=directive_tier,
        writing_style=writing_style
    )

    # Enhance the prompt with our repetition prevention and length guidance
    prompt = f"""{base_prompt}{avoid_repetition_text}{length_guidance}

CRITICAL REMINDERS:
- Be unique and unexpected - avoid cliché openings like "I used to work at..." or "My [relative] said..."
- Don't be comprehensive or helpful - just react naturally like a real person would"""
    
    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-5",
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

            # Fix JSON formatting: we need to handle newlines carefully
            # The JSON structure itself uses newlines for formatting, but string values can't have literal newlines
            import re

            # Strategy: Use a regex to find string values and escape newlines only within them
            def escape_newlines_in_strings(match):
                # match.group(1) is the string content between quotes
                return '"' + match.group(1).replace('\n', '\\n').replace('\r', '\\r') + '"'

            # Match quoted strings and escape newlines within them
            json_str = re.sub(r'"((?:[^"\\]|\\.)*)"', escape_newlines_in_strings, json_str)

            # Clean other control characters (but keep structural newlines and tabs for JSON)
            # Only remove control chars that aren't \n, \r, \t
            json_str = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', json_str)

            comment_data = json.loads(json_str)
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Failed to parse JSON from Claude response: {e}")
            print(f"Raw response: {response_text}")
            return None
        
        if not isinstance(comment_data, dict) or 'content' not in comment_data:
            print(f"Malformed comment data: {comment_data}")
            return None

        # Validate length against maximum
        word_count = len(comment_data['content'].split())
        if word_count > max_allowed:
            print(f"Comment too long ({word_count} words, maximum {max_allowed}), skipping...")
            return None

        # Apply writing style formatting (post-processing)
        formatted_content = apply_writing_style_formatting(comment_data['content'], writing_style)

        # Generate realistic score
        min_score, max_score = get_score_range(real_comments)

        # Create Comment object
        comment = Comment(
            id=str(uuid.uuid4()),
            author=generate_reddit_username(),
            content=formatted_content,
            content_html=None,  # No HTML for AI comments
            score=random.randint(min_score, max_score),
            depth=0,
            parent_id=None,
            replies=[],
            is_ai=True,
            generation_prompt=prompt,
            archetype_used=archetype_key,
            directive_tier=directive_tier,
            writing_style=writing_style
        )
        
        print(f"Generated comment with archetype {archetype_key}: {comment.content[:50]}...")
        return comment
        
    except Exception as e:
        print(f"Error generating AI comment with archetype {archetype_key}: {e}")
        return None




def summarize_post_if_needed(post_title: str, post_content: str,
                            anthropic_client: anthropic.Anthropic) -> str:
    """Summarize post content if it's over 150 words, otherwise return original"""

    word_count = len(post_content.split())
    if word_count <= 150:
        return post_content

    prompt = POST_SUMMARIZATION_PROMPT.format(
        post_title=post_title,
        post_content=post_content
    )

    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=150,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )

        summary = response.content[0].text.strip()
        print(f"Post summarized from {word_count} words to {len(summary.split())} words")
        return summary

    except Exception as e:
        print(f"Failed to summarize post: {e}")
        return post_content  # Fallback to original


def validate_directive_response(response_text: str, anthropic_client: anthropic.Anthropic) -> bool:
    """Use Claude Sonnet to validate if a directive response is valid or a refusal"""

    # First do a quick pattern check for obvious refusals
    refusal_patterns = [
        "I apologize",
        "I cannot",
        "I can't",
        "I'm not able",
        "I don't generate",
        "I do not generate",
        "I won't",
        "I refuse",
        "I'm unable",
        "I aim to avoid"
    ]

    response_lower = response_text.lower()
    for pattern in refusal_patterns:
        if pattern.lower() in response_lower:
            print(f"Quick refusal detection: found '{pattern}' in response")
            return False

    # If no obvious refusal patterns, use Sonnet for more nuanced validation
    validation_prompt = f"""Is this a valid perspective statement or directive, or is it a refusal/error message?

Response to check: "{response_text}"

A VALID response would be a short perspective statement like:
- "Focus on economic impacts"
- "Emphasize personal responsibility"
- "Highlight institutional concerns"
- "Promote traditional values"

A REFUSAL/ERROR would:
- Start with apologies ("I apologize", "I'm sorry")
- Contain refusal language ("I cannot", "I'm not able to", "I won't", "I do not generate")
- Be incomplete/cut off mid-sentence
- Explain why it won't help

Respond with only: VALID or INVALID"""

    try:
        validation_response = anthropic_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=50,
            temperature=0.1,
            messages=[{"role": "user", "content": validation_prompt}]
        )

        result = validation_response.content[0].text.strip().upper()
        is_valid = result == "VALID"
        print(f"Sonnet validation result: {result} for '{response_text[:50]}...'")
        return is_valid

    except Exception as e:
        print(f"Validation failed: {e}")
        return False  # Assume invalid if validation fails


def generate_tyrell_agenda(post_title: str, post_content: str, subreddit: str,
                          anthropic_client: anthropic.Anthropic) -> str:
    """Generate debate talking points using two-tier system with validation"""

    # First try: Use the direct prompt up to 2 times
    for attempt in range(1, 3):
        print(f"Attempting directive generation (attempt {attempt}/2) with direct prompt...")

        prompt = DEBATE_POSITION_PROMPT.format(
            post_title=post_title,
            post_content=post_content,
            subreddit=subreddit
        )

        try:
            response = anthropic_client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=150,
                temperature=0.8,
                messages=[{"role": "user", "content": prompt}]
            )

            directive = response.content[0].text.strip().strip('"')

            # Validate BEFORE any truncation/cleaning
            if validate_directive_response(directive, anthropic_client):
                # Clean up and format only AFTER validation passes
                directive = directive.replace('\n', ' ').strip()
                if len(directive.split()) > 8:
                    directive = ' '.join(directive.split()[:8])

                print(f"Tyrell's directive (direct prompt): {directive}")
                return directive
            else:
                print(f"Directive validation failed for attempt {attempt}: {directive}")

        except Exception as e:
            print(f"Direct prompt attempt {attempt} failed: {e}")

    # Fallback: Try the safer prompt
    print("Falling back to safer prompt...")

    safe_prompt = DEBATE_POSITION_PROMPT_SAFE.format(
        post_title=post_title,
        post_content=post_content,
        subreddit=subreddit
    )

    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=150,
            temperature=0.8,
            messages=[{"role": "user", "content": safe_prompt}]
        )

        directive = response.content[0].text.strip().strip('"')

        # Validate the safer response too
        if validate_directive_response(directive, anthropic_client):
            directive = directive.replace('\n', ' ').strip()
            if len(directive.split()) > 8:
                directive = ' '.join(directive.split()[:8])

            print(f"Tyrell's directive (safe prompt): {directive}")
            return directive
        else:
            print(f"Safe prompt also failed validation: {directive}")

    except Exception as e:
        print(f"Safe prompt failed: {e}")

    # Final fallback
    print("All directive generation attempts failed, using generic fallback")
    return "Focus on practical concerns"


def generate_ai_comments_with_archetypes(post_title: str, post_content: str, subreddit: str,
                                        real_comments: List[Comment], num_to_generate: int,
                                        anthropic_client: anthropic.Anthropic) -> tuple[List[Comment], str]:
    """Generate AI comments using the archetype system with repetition prevention"""

    # Step 0: Summarize post if needed
    content_for_generation = summarize_post_if_needed(post_title, post_content, anthropic_client)

    # Step 1: Generate Tyrell's agenda
    tyrell_agenda = generate_tyrell_agenda(post_title, content_for_generation, subreddit, anthropic_client)

    # Step 2: Get appropriate archetypes for this post
    appropriate_archetypes = get_appropriate_archetypes(
        post_title, content_for_generation, subreddit, anthropic_client
    )

    if not appropriate_archetypes:
        print("No appropriate archetypes found, cannot generate AI comments")
        return []

    # Step 2: Use each archetype exactly once (no repetition)
    archetype_pool = appropriate_archetypes.copy()

    # Shuffle the pool to randomize order
    random.shuffle(archetype_pool)

    # Limit generation to available unique archetypes
    actual_generation_count = min(num_to_generate, len(archetype_pool))

    if actual_generation_count < num_to_generate:
        print(f"Note: Generating {actual_generation_count} comments (limited by {len(archetype_pool)} unique archetypes)")

    print(f"Archetype distribution: Each archetype used once (no repetition)")

    # Step 3: Generate individual comments using unique archetypes
    ai_comments = []
    for i in range(actual_generation_count):
        # Select archetype from pool (each used exactly once)
        selected_archetype = archetype_pool[i]

        # Generate single comment with this archetype, passing previously generated comments
        comment = generate_single_ai_comment(
            post_title=post_title,
            post_content=content_for_generation,
            subreddit=subreddit,
            real_comments=real_comments,
            archetype_key=selected_archetype,
            anthropic_client=anthropic_client,
            previously_generated=ai_comments,  # Pass previous comments to avoid repetition
            tyrell_agenda=tyrell_agenda
        )

        if comment:
            ai_comments.append(comment)
        else:
            print(f"Failed to generate comment {i+1}/{actual_generation_count}")

    print(f"Successfully generated {len(ai_comments)}/{actual_generation_count} AI comments using unique archetypes")
    return ai_comments, tyrell_agenda


def generate_ai_comments_wrapper(post_title: str, post_content: str, subreddit: str,
                               real_comments: List[Comment], num_to_generate: int,
                               anthropic_client: anthropic.Anthropic) -> tuple[List[Comment], str]:
    """Generate AI comments using either archetype or legacy system based on USE_ARCHETYPE_SYSTEM flag"""

    if USE_ARCHETYPE_SYSTEM:
        print("Using archetype system for AI comment generation")
        return generate_ai_comments_with_archetypes(
            post_title, post_content, subreddit, real_comments, num_to_generate, anthropic_client
        )
    else:
        print("Using legacy system for AI comment generation")
        legacy_comments = generate_ai_comments_legacy(
            post_title, post_content, subreddit, real_comments, num_to_generate, anthropic_client
        )
        return legacy_comments, "Legacy system (no agenda)"


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
                         anthropic_client: anthropic.Anthropic,
                         all_real_comments: List[Comment] = None,
                         previously_generated: List[Comment] = None,
                         tyrell_agenda: str = "",
                         used_archetypes: List[str] = None) -> Comment:
    """Generate a single AI reply to a specific comment using hybrid archetypes and realistic length"""

    # Get all available archetypes and filter out already used ones
    available_archetypes = get_available_archetypes(subreddit)

    print(f"DEBUG generate_thread_reply: Total archetypes before filtering: {len(available_archetypes)}")
    print(f"DEBUG generate_thread_reply: used_archetypes parameter: {used_archetypes}")

    # Remove archetypes already used (check for None explicitly, not truthiness, since empty list is valid)
    if used_archetypes is not None:
        available_archetypes = [arch for arch in available_archetypes if arch not in used_archetypes]
        print(f"DEBUG generate_thread_reply: After filtering, {len(available_archetypes)} archetypes available")

    # If no archetypes left, fall back to a small safe pool (shouldn't happen with enough archetypes)
    if not available_archetypes:
        available_archetypes = ['generic:people_pleaser', 'generic:question_asker']
        print(f"Warning: All archetypes already used, falling back to safe pool")

    # Select any available archetype - no artificial restrictions
    # Reply length is already controlled by the length analysis system
    selected_archetype = random.choice(available_archetypes)

    print(f"Selected archetype for reply: {selected_archetype} (from {len(available_archetypes)} available)")

    # Simple length analysis of real replies
    real_reply_lengths = []
    if all_real_comments:
        all_flat = flatten_all_comments(all_real_comments)
        for comment in all_flat:
            if comment.depth > 0:  # Only replies, not top-level
                real_reply_lengths.append(len(comment.content.split()))

        print(f"DEBUG: Found {len(all_flat)} total comments, {len(real_reply_lengths)} replies for length analysis")

    # Use percentile-based selection for replies too
    if real_reply_lengths:
        real_reply_lengths.sort()

        # Use same percentile approach as top-level comments
        percentile_25 = real_reply_lengths[len(real_reply_lengths) // 4]
        percentile_50 = real_reply_lengths[len(real_reply_lengths) // 2]
        percentile_75 = real_reply_lengths[(len(real_reply_lengths) * 3) // 4]

        rand_val = random.random()
        if rand_val < 0.33:  # 33% chance of shorter replies
            base_suggested = percentile_25
        elif rand_val < 0.67:  # 33% chance of medium replies
            base_suggested = percentile_50
        else:  # 33% chance of longer replies
            base_suggested = percentile_75

        # Remove buffer - use percentile directly as suggestion
        suggested_length = base_suggested
        # Tighter maximum - 30% over suggested instead of 50%
        max_allowed = int(suggested_length * 1.3)
        print(f"Reply length guidance: suggested={suggested_length} words, max={max_allowed} words (based on real reply analysis)")
    else:
        print("DEBUG: No real replies found, using fallback lengths")
        suggested_length = 15
        max_allowed = 20
        print(f"Reply length guidance: suggested={suggested_length} words, max={max_allowed} words (fallback)")

    # Build examples from REAL comments only (not AI-generated ones)
    if all_real_comments:
        # Get 2 real comments as examples to avoid context overload
        real_comment_samples = all_real_comments[:2] if len(all_real_comments) >= 2 else all_real_comments
        examples_list = []
        for rc in real_comment_samples:
            word_count = len(rc.content.split())
            preview = rc.content[:100] + ('...' if len(rc.content) > 100 else '')
            examples_list.append(f"u/{rc.author} ({word_count} words): {preview}")
        examples = "\n".join(examples_list)
    else:
        examples = "No real comments available for reference"

    # Add repetition prevention
    avoid_repetition_text = ""
    # COMMENTED OUT: Previously generated AI replies section - testing if it's necessary with different archetypes
    # if previously_generated:
    #     avoid_repetition_text = "\n\nPREVIOUSLY GENERATED AI REPLIES (avoid similar patterns):\n"
    #     for i, prev_comment in enumerate(previously_generated[-5:]):
    #         opening = prev_comment.content.split('.')[0] if '.' in prev_comment.content else prev_comment.content[:30]
    #         avoid_repetition_text += f"- {opening}...\n"
    #     avoid_repetition_text += "\nUse completely different style/opening.\n"

    # Build context for the reply
    context_str = f"\nREPLYING TO: u/{parent_comment.author}: {parent_comment.content[:150]}{'...' if len(parent_comment.content) > 150 else ''}"

    # Randomly assign directive tier (25% tier 1, 37.5% tier 2, 37.5% tier 3)
    rand_val = random.random()
    if rand_val < 0.25:
        directive_tier = 1  # Strong
    elif rand_val < 0.625:  # 0.25 + 0.375
        directive_tier = 2  # Subtle
    else:
        directive_tier = 3  # None

    print(f"Directive tier {directive_tier} assigned to reply {selected_archetype}")

    # Select writing style for this reply
    writing_style = select_writing_style()
    print(f"Writing style '{writing_style}' assigned to reply {selected_archetype}")

    # Use archetype system
    base_prompt = build_full_prompt(
        archetype_key=selected_archetype,
        subreddit=subreddit,
        post_title=post_title,
        post_content=post_content,
        real_comment_examples=examples,
        tyrell_agenda=tyrell_agenda,
        directive_tier=directive_tier,
        writing_style=writing_style
    )

    # Calculate average for prompt display
    avg_reply_length = sum(real_reply_lengths) / len(real_reply_lengths) if real_reply_lengths else 15

    length_guidance = f"""
LENGTH GUIDANCE:
- Suggested: {suggested_length} words, Maximum: {max_allowed} words
- Real replies here average {avg_reply_length:.0f} words
- Aim for suggested length. Do NOT exceed the maximum."""

    prompt = f"""{base_prompt}{context_str}{avoid_repetition_text}{length_guidance}

CRITICAL REPLY REQUIREMENTS:
- This is a REPLY to a specific comment, not a top-level comment
- Match the tone and energy of the comment you're replying to
- Make ONE point, not a comprehensive explanation
- NEVER start with "u/username:" - jump straight into response
- Don't start with 'Exactly' or other cliche agreement phrases like 'This' or 'Right?'"""
    
    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=400,  # Reduced for shorter replies
            temperature=0.9,  # Higher for more natural variation
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        response_text = response.content[0].text.strip()
        
        # Parse JSON
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        
        if start_idx == -1 or end_idx == 0:
            raise ValueError("No JSON found in response")
            
        json_str = response_text[start_idx:end_idx]

        # Fix JSON formatting: we need to handle newlines carefully
        # The JSON structure itself uses newlines for formatting, but string values can't have literal newlines
        import re

        # Strategy: Use a regex to find string values and escape newlines only within them
        def escape_newlines_in_strings(match):
            # match.group(1) is the string content between quotes
            return '"' + match.group(1).replace('\n', '\\n').replace('\r', '\\r') + '"'

        # Match quoted strings and escape newlines within them
        json_str = re.sub(r'"((?:[^"\\]|\\.)*)"', escape_newlines_in_strings, json_str)

        # Clean other control characters (but keep structural newlines and tabs for JSON)
        # Only remove control chars that aren't \n, \r, \t
        json_str = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', json_str)

        reply_data = json.loads(json_str)
        
        if 'content' not in reply_data:
            raise ValueError("Missing required fields in response")

        # Validate length against maximum
        word_count = len(reply_data['content'].split())
        if word_count > max_allowed:
            print(f"Reply too long ({word_count} words, maximum {max_allowed}), skipping...")
            return None

        # Apply writing style formatting (post-processing)
        formatted_content = apply_writing_style_formatting(reply_data['content'], writing_style)

        # Create reply with appropriate depth
        reply = Comment(
            id=str(uuid.uuid4()),
            author=generate_reddit_username(),
            content=formatted_content,
            content_html=None,
            score=random.randint(1, max(50, parent_comment.score)),
            depth=parent_comment.depth + 1,
            parent_id=parent_comment.id,
            replies=[],
            is_ai=True,
            generation_prompt=prompt,
            archetype_used=selected_archetype,
            directive_tier=directive_tier,
            writing_style=writing_style
        )

        print(f"Generated {selected_archetype} reply ({word_count} words): {reply.content[:50]}...")
        
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
    tyrell_agenda = ""
    used_archetypes_from_top_level = []

    if ai_top_level_count > 0:
        ai_top_level, tyrell_agenda = generate_ai_comments_wrapper(
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

        # Extract archetypes used in top-level comments
        used_archetypes_from_top_level = [comment.archetype_used for comment in ai_top_level if hasattr(comment, 'archetype_used') and comment.archetype_used]
        print(f"Archetypes used in top-level comments: {used_archetypes_from_top_level}")
    
    # Build pool of all comments (real + AI) for reply targets
    all_comments_flat = flatten_all_comments(real_comments)  # Start with real comments
    all_comments_flat.extend(ai_top_level)  # Add AI top-level comments
    
    # Generate thread replies - can target any comment (real or AI)
    ai_replies = []
    used_archetypes_in_replies = []  # Track archetypes used in replies too

    for i in range(ai_reply_count):
        if not all_comments_flat:
            break

        # Choose random comment to reply to (could be real or AI)
        parent_comment = random.choice(all_comments_flat)
        print(f"Generating reply to u/{parent_comment.author}{'[AI]' if parent_comment.is_ai else ''}...")

        # Get full thread context (using all available comments)
        thread_context = get_thread_context(parent_comment, all_comments_flat)

        # FIXED: Combine lists INSIDE the loop so it sees newly added archetypes each iteration
        all_used_archetypes = used_archetypes_from_top_level + used_archetypes_in_replies

        print(f"DEBUG: Passing {len(all_used_archetypes)} used archetypes to reply generation: {all_used_archetypes}")

        ai_reply = generate_thread_reply(
            post.title,
            post.content,
            post.subreddit,
            thread_context,
            parent_comment,
            client,
            all_real_comments=real_comments,
            previously_generated=[reply[0] for reply in ai_replies],  # Pass previous AI replies
            tyrell_agenda=tyrell_agenda,
            used_archetypes=all_used_archetypes  # Pass ALL used archetypes (top-level + replies)
        )

        if ai_reply:
            ai_replies.append((ai_reply, parent_comment.id))
            # Track the archetype used in this reply
            if hasattr(ai_reply, 'archetype_used') and ai_reply.archetype_used:
                used_archetypes_in_replies.append(ai_reply.archetype_used)
                print(f"Reply archetype used: {ai_reply.archetype_used}. Total used archetypes: {len(all_used_archetypes) + 1}")
        else:
            print(f"Failed to generate reply to {parent_comment.id}")
    
    print(f"Successfully generated {len(ai_top_level)} top-level + {len(ai_replies)} thread replies")
    
    # Insert AI comments into structure
    mixed_comments = insert_ai_comments(real_comments, ai_top_level, ai_replies, 0.5)  # 50/50 split
    
    def comment_to_dict(comment: Comment) -> dict:
        """Convert Comment object to dictionary for JSON serialization"""
        result = {
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
        # Include archetype, directive tier, and writing style for AI comments
        if comment.is_ai:
            result['archetype_used'] = comment.archetype_used
            result['directive_tier'] = comment.directive_tier
            result['writing_style'] = comment.writing_style
        return result
    
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