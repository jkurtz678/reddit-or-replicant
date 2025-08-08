#!/usr/bin/env python3
"""
Reddit API fetcher for retrieving post and comment data.
"""

import httpx
import json
import re
from typing import Dict, Any, Optional
from urllib.parse import urlparse, parse_qs

def normalize_reddit_url(url: str) -> str:
    """
    Normalize a Reddit URL to the standard format.
    
    Handles various Reddit URL formats:
    - https://www.reddit.com/r/subreddit/comments/xyz/title/
    - https://reddit.com/r/subreddit/comments/xyz/title/
    - https://old.reddit.com/r/subreddit/comments/xyz/title/
    - URLs with query parameters, fragments, etc.
    """
    # Remove any query parameters and fragments
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    # Ensure it ends with / for consistency
    if not base_url.endswith('/'):
        base_url += '/'
    
    # Convert to www.reddit.com format
    base_url = base_url.replace('old.reddit.com', 'www.reddit.com')
    base_url = base_url.replace('//reddit.com', '//www.reddit.com')
    
    return base_url

def reddit_url_to_json_url(url: str) -> str:
    """Convert a Reddit post URL to its JSON API endpoint"""
    normalized = normalize_reddit_url(url)
    return f"{normalized}.json"

def validate_reddit_url(url: str) -> bool:
    """Validate if the URL is a valid Reddit post URL"""
    # Check if it's a Reddit URL with the correct format
    pattern = r'https?://(?:www\.|old\.)?reddit\.com/r/\w+/comments/\w+/'
    return bool(re.match(pattern, url))

async def fetch_reddit_post(url: str) -> Optional[Dict[Any, Any]]:
    """
    Fetch Reddit post data from a Reddit URL.
    
    Args:
        url: Reddit post URL
        
    Returns:
        Reddit JSON data or None if failed
    """
    if not validate_reddit_url(url):
        raise ValueError("Invalid Reddit URL format")
    
    json_url = reddit_url_to_json_url(url)
    
    # Set a user agent to avoid being blocked
    headers = {
        'User-Agent': 'Replicant Bot 1.0 (for educational purposes)'
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(json_url, headers=headers)
            response.raise_for_status()
            
            # Reddit returns JSON
            reddit_data = response.json()
            
            # Validate the response structure
            if not isinstance(reddit_data, list) or len(reddit_data) < 2:
                raise ValueError("Invalid Reddit API response format")
            
            # Check if it has the expected structure
            if (reddit_data[0].get('kind') != 'Listing' or 
                reddit_data[1].get('kind') != 'Listing'):
                raise ValueError("Unexpected Reddit API response structure")
            
            return reddit_data
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise ValueError("Reddit post not found")
        elif e.response.status_code == 403:
            raise ValueError("Access forbidden - Reddit may be blocking requests")
        else:
            raise ValueError(f"HTTP error {e.response.status_code}: {e.response.text}")
    except httpx.TimeoutException:
        raise ValueError("Request timeout - Reddit server may be slow")
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON response from Reddit")
    except Exception as e:
        raise ValueError(f"Failed to fetch Reddit post: {str(e)}")

def extract_post_info(reddit_data: Dict[Any, Any]) -> Dict[str, str]:
    """
    Extract basic post information from Reddit JSON data.
    
    Returns:
        Dictionary with title, subreddit, author
    """
    try:
        post_data = reddit_data[0]['data']['children'][0]['data']
        return {
            'title': post_data.get('title', ''),
            'subreddit': post_data.get('subreddit', ''),
            'author': post_data.get('author', ''),
            'id': post_data.get('id', '')
        }
    except (KeyError, IndexError, TypeError):
        raise ValueError("Could not extract post information from Reddit data")