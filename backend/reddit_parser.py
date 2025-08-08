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
    return Post(
        id=post_data['id'],
        title=post_data.get('title', ''),
        content=post_data.get('selftext', ''),
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
    if len(comments) <= max_comments:
        return comments.copy()
    
    # Separate top-level comments and sort by score
    top_level_comments = [c for c in comments if c.depth == 0]
    top_level_comments.sort(key=lambda x: x.score, reverse=True)
    
    selected_comments = []
    total_count = 0
    
    # Step 1: Take up to max_comments/3 from very top scorers
    max_from_top = max_comments // 3  # For 12 comments, this is 4
    top_scorers = top_level_comments[:min(max_from_top, len(top_level_comments))]
    
    # Add top scorers with limited replies
    for comment in top_scorers:
        if total_count >= max_comments:
            break
            
        # Create a copy of the comment
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
        
        # Add the best reply if we have space and this comment has replies
        if comment.replies and total_count < max_comments:
            best_reply = max(comment.replies, key=lambda x: x.score)
            # Create a copy without sub-replies to keep it simple
            reply_copy = Comment(
                id=best_reply.id,
                author=best_reply.author,
                content=best_reply.content,
                content_html=best_reply.content_html,
                score=best_reply.score,
                depth=best_reply.depth,
                parent_id=best_reply.parent_id,
                replies=[],  # No sub-replies for now
                is_ai=best_reply.is_ai
            )
            selected_comment.replies.append(reply_copy)
            total_count += 1
    
    # Step 2: Fill remaining slots with random top-level comments
    remaining_slots = max_comments - total_count
    remaining_top_level = top_level_comments[max_from_top:]
    
    if remaining_slots > 0 and remaining_top_level:
        # Randomly select from the remaining comments
        random.shuffle(remaining_top_level)
        
        for comment in remaining_top_level:
            if total_count >= max_comments:
                break
                
            # Add the top-level comment
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
            
            # Add one reply if we have space and this comment has replies
            if comment.replies and total_count < max_comments:
                best_reply = max(comment.replies, key=lambda x: x.score)
                reply_copy = Comment(
                    id=best_reply.id,
                    author=best_reply.author,
                    content=best_reply.content,
                    content_html=best_reply.content_html,
                    score=best_reply.score,
                    depth=best_reply.depth,
                    parent_id=best_reply.parent_id,
                    replies=[],
                    is_ai=best_reply.is_ai
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


