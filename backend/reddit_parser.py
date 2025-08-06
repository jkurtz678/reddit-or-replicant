import html
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


