import html
import random
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class Post:
    id: str
    title: str
    content: str
    author: str
    subreddit: str
    score: int
    comment_count: int


@dataclass 
class Comment:
    id: str
    author: str
    content: str
    content_html: Optional[str]
    score: int
    depth: int
    parent_id: Optional[str]
    replies: List['Comment']
    is_ai: bool = False
    generation_prompt: Optional[str] = None
    archetype_used: Optional[str] = None
    directive_tier: Optional[int] = None  # 1=strong, 2=subtle, 3=none


def clean_html_content(html_content: str) -> str:
    """Decode Reddit's HTML-encoded content but preserve HTML structure"""
    if not html_content:
        return ""
    
    # Decode HTML entities (convert &lt; back to <, &gt; back to >, etc.)
    decoded = html.unescape(html_content)
    return decoded.strip()


def parse_comment(comment_data: Dict[str, Any], depth: int = 0, parent_id: Optional[str] = None) -> Comment:
    """Parse a single Reddit comment into our clean format"""
    
    # Get replies
    replies = []
    if comment_data.get('replies') and isinstance(comment_data['replies'], dict):
        replies_data = comment_data['replies'].get('data', {}).get('children', [])
        for reply in replies_data:
            if reply.get('kind') == 't1':  # Only actual comments
                replies.append(parse_comment(reply['data'], depth + 1, comment_data['id']))
    
    # Use HTML content if available, otherwise fall back to plain text
    content = comment_data.get('body', '')
    if comment_data.get('body_html'):
        content = clean_html_content(comment_data['body_html'])
    
    # Store both HTML and text versions
    content_html = content if comment_data.get('body_html') else None
    content_text = comment_data.get('body', '')
    
    return Comment(
        id=comment_data['id'],
        author=comment_data.get('author', '[deleted]'),
        content=content_text,
        content_html=content_html,
        score=comment_data.get('score', 0),
        depth=depth,
        parent_id=parent_id,
        replies=replies,
        is_ai=False
    )


def parse_post(post_data: Dict[str, Any]) -> Post:
    """Parse a Reddit post into our clean format"""
    # For link posts, include the URL when selftext is empty
    content = post_data.get('selftext', '')
    if not content and not post_data.get('is_self', True):
        # This is a link post with no selftext, include the URL as clickable link
        url = post_data.get('url', '')
        if url:
            content = f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="text-blue-400 hover:text-blue-300 underline">{url}</a>'

    return Post(
        id=post_data['id'],
        title=post_data.get('title', ''),
        content=content,
        author=post_data.get('author', '[deleted]'),
        subreddit=post_data.get('subreddit', ''),
        score=post_data.get('score', 0),
        comment_count=post_data.get('num_comments', 0)
    )


def parse_reddit_json(reddit_json: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Parse Reddit JSON into clean post + comments structure
    
    Args:
        reddit_json: The raw Reddit JSON (list of 2 Listings)
    
    Returns:
        Dict with 'post' and 'comments' keys
    """
    result = {
        'post': None,
        'comments': []
    }
    
    # First listing contains the post
    if (reddit_json[0]['kind'] == 'Listing' and 
        reddit_json[0]['data']['children']):
        
        post_item = reddit_json[0]['data']['children'][0]
        if post_item['kind'] == 't3':  # Post
            result['post'] = parse_post(post_item['data'])
    
    # Second listing contains comments
    if (len(reddit_json) > 1 and 
        reddit_json[1]['kind'] == 'Listing' and 
        reddit_json[1]['data']['children']):
        
        comments_data = reddit_json[1]['data']['children']
        for comment_item in comments_data:
            if comment_item['kind'] == 't1':  # Comment
                result['comments'].append(parse_comment(comment_item['data']))
    
    return result


def select_representative_comments(comments: List[Comment], max_comments: int = 12) -> List[Comment]:
    """
    Select a representative subset of comments from a Reddit thread.
    
    Algorithm:
    1. Sort top-level comments by score
    2. Take up to max_comments/3 from the very top scorers
    3. Fill remaining top-level slots randomly from the rest
    4. For each selected top-level comment, consider adding highest-scoring replies
    5. Stop when we hit max_comments total
    
    Args:
        comments: List of top-level Comment objects (with nested replies)
        max_comments: Maximum number of comments to select (default 12)
    
    Returns:
        List of selected Comment objects with their reply structures intact
    """
    print(f"DEBUG: select_representative_comments called with {len(comments)} comments")

    # Filter out deleted/removed comments first (always do this)
    def is_valid_comment(comment):
        """Check if comment has valid content (not deleted/removed) and reasonable length"""
        content = comment.content.strip().lower()
        if content in ['[deleted]', '[removed]', '', 'deleted', 'removed']:
            return False

        # Check word count - reject if over 180 words
        word_count = len(comment.content.split())
        if word_count > 180:
            return False

        return True

    def filter_comments_recursive(comment_list):
        """Recursively filter out deleted comments"""
        filtered = []
        for comment in comment_list:
            if is_valid_comment(comment):
                # Create copy with filtered replies
                filtered_comment = Comment(
                    id=comment.id,
                    author=comment.author,
                    content=comment.content,
                    content_html=comment.content_html,
                    score=comment.score,
                    depth=comment.depth,
                    parent_id=comment.parent_id,
                    replies=filter_comments_recursive(comment.replies),
                    is_ai=comment.is_ai
                )
                filtered.append(filtered_comment)
        return filtered

    # Always filter out deleted comments first
    comments = filter_comments_recursive(comments)
    print(f"DEBUG: After filtering, have {len(comments)} valid comments")

    if len(comments) <= max_comments:
        print(f"EXIT EARLY BECAUSE NOT ENOUGH COMMENTS AFTER FILTERING")
        return comments
    
    # Separate top-level comments, filter valid ones, and sort by score
    top_level_comments = [c for c in comments if c.depth == 0 and is_valid_comment(c)]
    top_level_comments.sort(key=lambda x: x.score, reverse=True)
    
    selected_comments = []
    total_count = 0
    
    # Create weighted selection probabilities based on rank
    def get_selection_weight(rank):
        if rank == 0: return 40    # Top comment: 40%
        elif rank == 1: return 25  # 2nd comment: 25%
        elif rank == 2: return 15  # 3rd comment: 15%
        elif rank == 3: return 10  # 4th comment: 10%
        elif rank <= 9: return 6   # 5th-10th comments: 6% each
        else: return 3             # Everything else: 3% each

    # Select top-level comments using weighted random selection
    while total_count < max_comments and top_level_comments:
        # Create weighted list for selection
        weights = [get_selection_weight(i) for i in range(len(top_level_comments))]

        # Weighted random selection
        selected_idx = random.choices(range(len(top_level_comments)), weights=weights)[0]
        comment = top_level_comments.pop(selected_idx)

        # Add the selected comment
        selected_comment = Comment(
            id=comment.id,
            author=comment.author,
            content=comment.content,
            content_html=comment.content_html,
            score=comment.score,
            depth=comment.depth,
            parent_id=comment.parent_id,
            replies=[],
            is_ai=comment.is_ai
        )
        selected_comments.append(selected_comment)
        total_count += 1

        # Maybe add a reply (90% chance, but always if we need more replies for minimum)
        valid_replies = [r for r in comment.replies if is_valid_comment(r)]
        replies_selected_so_far = sum(1 for c in selected_comments if any(c.replies))
        force_reply = replies_selected_so_far < 2  # Force until we have 2 reply threads

        if valid_replies and total_count < max_comments and (force_reply or random.random() < 0.9):
            # Use weighted selection for replies too
            reply_weights = [get_selection_weight(i) for i in range(len(valid_replies))]
            selected_reply_idx = random.choices(range(len(valid_replies)), weights=reply_weights)[0]
            selected_reply = valid_replies[selected_reply_idx]

            reply_copy = Comment(
                id=selected_reply.id,
                author=selected_reply.author,
                content=selected_reply.content,
                content_html=selected_reply.content_html,
                score=selected_reply.score,
                depth=selected_reply.depth,
                parent_id=selected_reply.parent_id,
                replies=[],
                is_ai=selected_reply.is_ai
            )
            selected_comment.replies.append(reply_copy)
            total_count += 1
    
    return selected_comments


def count_comments_recursive(comments: List[Comment]) -> int:
    """Count total comments including nested replies"""
    total = 0
    for comment in comments:
        total += 1
        total += count_comments_recursive(comment.replies)
    return total


