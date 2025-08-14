from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import os
import httpx
import asyncio
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
from src.reddit_parser import parse_reddit_json, select_representative_comments
from src.reddit_fetcher import fetch_reddit_post, extract_post_info, validate_reddit_url
from src.database import save_post, get_post_by_id, get_all_posts, post_exists
import anthropic
from src.gen.generate_mixed_comments import (
    anonymize_usernames, apply_username_anonymization, count_all_comments,
    flatten_all_comments, generate_ai_comments_wrapper, generate_thread_reply, 
    get_thread_context, insert_ai_comments, MAX_REDDIT_COMMENTS
)
from src.reddit_parser import Comment

app = FastAPI()

# Pydantic models for request/response
class SubmitURLRequest(BaseModel):
    url: str

class PostResponse(BaseModel):
    id: int
    reddit_url: str
    title: str
    subreddit: str
    ai_count: int
    total_count: int
    created_at: str

# Helper functions
def comment_to_dict(comment) -> dict:
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

async def generate_mixed_comments_for_post(post, real_comments, client):
    """Generate mixed AI and real comments for a post"""
    from src.gen.generate_mixed_comments import generate_reddit_username
    import random
    import uuid
    
    # Fixed counts: 8 human + 8 AI comments for balanced gameplay
    target_human_count = 8
    target_ai_count = 8
    
    # Step 1: Limit real comments to exactly 8 total (including nested)
    # We need to carefully trim the tree to keep exactly 8 comments while preserving structure
    all_real_flat = flatten_all_comments(real_comments)
    if len(all_real_flat) > target_human_count:
        # Take first 8 comments and rebuild a tree structure
        limited_real_flat = all_real_flat[:target_human_count]
        # Convert back to tree structure by filtering original tree
        limited_real_comments = filter_comments_to_subset(real_comments, limited_real_flat)
    else:
        limited_real_comments = real_comments
    
    # Step 2: Generate AI comments (mix of top-level and replies)
    ai_top_level_count = min(4, target_ai_count)  # At most 4 top-level AI comments
    ai_reply_count = target_ai_count - ai_top_level_count
    
    # Generate top-level AI comments
    ai_top_level = []
    if ai_top_level_count > 0:
        ai_top_level = generate_ai_comments_wrapper(
            post.title,
            post.content,
            post.subreddit,
            flatten_all_comments(limited_real_comments),
            ai_top_level_count,
            client
        )
    
    # If we didn't get enough top-level AI comments, adjust the reply count to compensate
    actual_top_level_count = len(ai_top_level)
    remaining_ai_needed = target_ai_count - actual_top_level_count
    ai_reply_count = remaining_ai_needed
    
    print(f"Generated {actual_top_level_count} top-level AI comments, need {ai_reply_count} more as replies")
    
    # Generate AI replies
    ai_replies = []
    all_comments_for_replies = flatten_all_comments(limited_real_comments) + ai_top_level
    
    for i in range(ai_reply_count):
        if not all_comments_for_replies:
            break
        
        parent_comment = random.choice(all_comments_for_replies)
        thread_context = get_thread_context(parent_comment, all_comments_for_replies)
        
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
    
    # Final check: if we still don't have enough AI comments, generate more top-level ones
    total_ai_generated = len(ai_top_level) + len(ai_replies)
    if total_ai_generated < target_ai_count:
        additional_needed = target_ai_count - total_ai_generated
        print(f"Still need {additional_needed} more AI comments, generating additional top-level comments")
        
        additional_ai = generate_ai_comments_wrapper(
            post.title,
            post.content,
            post.subreddit,
            flatten_all_comments(limited_real_comments),
            additional_needed,
            client
        )
        ai_top_level.extend(additional_ai)
    
    # Step 3: Insert AI comments into the tree structure (preserving hierarchy)
    mixed_comments = insert_ai_comments(limited_real_comments, ai_top_level, ai_replies, 0.5)
    
    return mixed_comments


def filter_comments_to_subset(comment_tree, target_flat_list):
    """Filter a comment tree to only include comments that are in the target flat list"""
    target_ids = {comment.id for comment in target_flat_list}
    
    def filter_recursive(comments):
        filtered = []
        for comment in comments:
            if comment.id in target_ids:
                # Keep this comment and filter its replies
                filtered_comment = Comment(
                    id=comment.id,
                    author=comment.author,
                    content=comment.content,
                    content_html=comment.content_html,
                    score=comment.score,
                    depth=comment.depth,
                    parent_id=comment.parent_id,
                    replies=filter_recursive(comment.replies),
                    is_ai=comment.is_ai
                )
                filtered.append(filtered_comment)
        return filtered
    
    return filter_recursive(comment_tree)

# API routes
@app.get("/api")
def read_root():
    return {"Hello": "World"}

@app.get("/api/posts")
def get_posts():
    """Get all saved posts"""
    posts = get_all_posts()
    return {"posts": posts}

@app.post("/api/posts/submit")
async def submit_reddit_url(request: SubmitURLRequest):
    """Submit a Reddit URL for processing"""
    
    # Validate URL format
    if not validate_reddit_url(request.url):
        raise HTTPException(status_code=400, detail="Invalid Reddit URL format")
    
    # Check if already processed
    if post_exists(request.url):
        raise HTTPException(status_code=400, detail="This Reddit post has already been processed")
    
    # Check for API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY environment variable not set")
    
    try:
        # Fetch Reddit data
        reddit_data = await fetch_reddit_post(request.url)
        
        # Extract basic post info for response
        post_info = extract_post_info(reddit_data)
        
        # Parse and process the data
        parsed_data = parse_reddit_json(reddit_data)
        post = parsed_data['post']
        real_comments = parsed_data['comments']
        
        if not post or not real_comments:
            raise HTTPException(status_code=400, detail="No post or comments found in Reddit data")
        
        # Select representative comments
        real_comments = select_representative_comments(real_comments, MAX_REDDIT_COMMENTS)
        
        # Anonymize usernames
        username_mapping = anonymize_usernames(real_comments)
        apply_username_anonymization(real_comments, username_mapping)
        
        # Also anonymize post author
        if post.author in username_mapping:
            post.author = username_mapping[post.author]
        else:
            from src.gen.generate_mixed_comments import generate_reddit_username
            post.author = generate_reddit_username()
        
        # Generate AI comments
        client = anthropic.Anthropic(api_key=api_key)
        mixed_comments = await generate_mixed_comments_for_post(
            post, real_comments, client
        )
        
        # Count final stats
        total_final_comments = count_all_comments(mixed_comments)
        total_ai_final = sum(1 for c in flatten_all_comments(mixed_comments) if c.is_ai)
        
        # Create final data structure
        final_data = {
            'post': {
                'id': post.id,
                'title': post.title,
                'content': post.content,
                'author': post.author,
                'subreddit': post.subreddit,
                'score': post.score,
                'comment_count': len(mixed_comments)
            },
            'comments': [comment_to_dict(comment) for comment in mixed_comments]
        }
        
        # Save to database
        post_id = save_post(
            reddit_url=request.url,
            title=post.title,
            subreddit=post.subreddit,
            mixed_comments_data=final_data,
            ai_count=total_ai_final,
            total_count=total_final_comments
        )
        
        return {
            "id": post_id,
            "message": "Reddit post processed successfully",
            "stats": {
                "total_comments": total_final_comments,
                "ai_comments": total_ai_final,
                "ai_percentage": round(total_ai_final/total_final_comments*100, 1)
            }
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process Reddit post: {str(e)}")

@app.get("/api/posts/{post_id}")
def get_post(post_id: int):
    """Get a specific post with mixed comments"""
    post_data = get_post_by_id(post_id)
    if not post_data:
        raise HTTPException(status_code=404, detail="Post not found")
    
    return post_data['mixed_comments']

@app.get("/api/test-reddit")
def get_test_reddit():
    json_file_path = os.path.join(os.path.dirname(__file__), "test-reddit.json")
    with open(json_file_path, "r") as file:
        raw_data = json.load(file)
    
    # Parse into clean nested structure
    parsed_data = parse_reddit_json(raw_data)
    return parsed_data

@app.get("/api/test-reddit-raw")
def get_test_reddit_raw():
    """Keep the raw endpoint for debugging"""
    json_file_path = os.path.join(os.path.dirname(__file__), "test-reddit.json")
    with open(json_file_path, "r") as file:
        data = json.load(file)
    return data

@app.get("/api/mixed-comments/{post_id}")
def get_mixed_comments(post_id: int):
    """Get the mixed real + AI comments for a specific post"""
    post_data = get_post_by_id(post_id)
    if not post_data:
        raise HTTPException(status_code=404, detail="Post not found")
    
    return post_data['mixed_comments']

# Proxy all other requests to SvelteKit dev server
@app.get("/{full_path:path}")
async def proxy_to_frontend(full_path: str, request: Request):
    frontend_url = f"http://localhost:5173/{full_path}"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            frontend_url,
            headers=dict(request.headers),
            params=dict(request.query_params)
        )
        return StreamingResponse(
            iter([response.content]),
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.headers.get("content-type")
        )