from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
import httpx
import asyncio
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
from src.reddit_parser import parse_reddit_json, select_representative_comments
from src.reddit_fetcher import fetch_reddit_post, extract_post_info, validate_reddit_url
from src.database import (
    save_post, get_post_by_id, get_all_posts, get_posts_by_subreddit, post_exists, soft_delete_post, restore_post,
    get_or_create_user, save_user_guess, get_user_progress, get_user_all_progress, reset_user_progress,
    save_evaluation_result, flag_comment_as_obvious, get_aggregate_stats
)
import anthropic
from src.gen.generate_mixed_comments import (
    anonymize_usernames, apply_username_anonymization, count_all_comments,
    flatten_all_comments, generate_ai_comments_wrapper, generate_thread_reply,
    get_thread_context, insert_ai_comments, MAX_REDDIT_COMMENTS, summarize_post_if_needed
)
from src.reddit_parser import Comment
from evaluate_comments import CommentEvaluator, CommentData, PostEvaluation

app = FastAPI()

# Add CORS middleware for frontend-backend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, you'd want to restrict this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class SubmitURLRequest(BaseModel):
    url: str
    overwrite_existing: bool = False

class AdminLoginRequest(BaseModel):
    password: str

class AdminLoginResponse(BaseModel):
    token: str
    message: str

class UserRegisterRequest(BaseModel):
    anonymous_id: str

class UserGuessRequest(BaseModel):
    anonymous_id: str
    post_id: int
    comment_id: str
    guess: str
    is_correct: bool

class UserProgressRequest(BaseModel):
    anonymous_id: str
    post_id: int

class ResetProgressRequest(BaseModel):
    anonymous_id: str
    post_id: int

class FlagObviousRequest(BaseModel):
    anonymous_id: str
    post_id: int
    comment_id: str

class PostResponse(BaseModel):
    id: int
    reddit_url: str
    title: str
    subreddit: str
    ai_count: int
    total_count: int
    created_at: str

# Helper functions
def parse_admin_environment(x_admin_env: str = None) -> bool:
    """Parse admin environment header and return force_turso flag"""
    if x_admin_env == 'live':
        return True
    elif x_admin_env == 'local':
        return False
    else:
        return None  # Use default behavior

def comment_to_dict(comment) -> dict:
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

    # Add AI generation fields if they exist
    if hasattr(comment, 'generation_prompt') and comment.generation_prompt is not None:
        result['generation_prompt'] = comment.generation_prompt
    if hasattr(comment, 'archetype_used') and comment.archetype_used is not None:
        result['archetype_used'] = comment.archetype_used
    if hasattr(comment, 'directive_tier') and comment.directive_tier is not None:
        result['directive_tier'] = comment.directive_tier
    if hasattr(comment, 'writing_style') and comment.writing_style is not None:
        result['writing_style'] = comment.writing_style

    return result

async def generate_mixed_comments_for_post(post, real_comments, client):
    """Generate mixed AI and real comments for a post"""
    from src.gen.generate_mixed_comments import generate_reddit_username
    import random
    import uuid

    # Summarize post content if needed for consistent generation
    summarized_content = summarize_post_if_needed(post.title, post.content, client)
    
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
    tyrell_agenda = ""

    # Always generate agenda if we're making any AI content
    if target_ai_count > 0:
        if ai_top_level_count > 0:
            ai_top_level, tyrell_agenda = generate_ai_comments_wrapper(
                post.title,
                post.content,
                post.subreddit,
                flatten_all_comments(limited_real_comments),
                ai_top_level_count,
                client
            )
        else:
            # Generate agenda even if no top-level comments, for replies
            from src.gen.generate_mixed_comments import generate_tyrell_agenda
            tyrell_agenda = generate_tyrell_agenda(post.title, post.content, post.subreddit, client)
    
    # If we didn't get enough top-level AI comments, adjust the reply count to compensate
    actual_top_level_count = len(ai_top_level)
    remaining_ai_needed = target_ai_count - actual_top_level_count
    ai_reply_count = remaining_ai_needed
    
    print(f"Generated {actual_top_level_count} top-level AI comments, need {ai_reply_count} more as replies")

    # Track archetypes used in top-level comments
    used_archetypes_from_top_level = [comment.archetype_used for comment in ai_top_level if hasattr(comment, 'archetype_used') and comment.archetype_used]
    print(f"Archetypes used in top-level comments: {used_archetypes_from_top_level}")

    # Generate AI replies
    ai_replies = []
    used_archetypes_in_replies = []  # Track archetypes used in replies
    all_comments_for_replies = flatten_all_comments(limited_real_comments) + ai_top_level

    # Track how many AI replies we've added to each parent (by parent ID)
    ai_replies_per_parent = {}

    for i in range(ai_reply_count):
        if not all_comments_for_replies:
            break

        # Only reply to comments at depth 0 or 1 (to enforce max depth of 2)
        # AND that don't already have 2 or more TOTAL replies (real + AI we're adding)
        eligible_parents = [
            c for c in all_comments_for_replies
            if c.depth <= 1 and (len(c.replies) + ai_replies_per_parent.get(c.id, 0)) < 2
        ]
        if not eligible_parents:
            print(f"No eligible parent comments (depth <= 1 and < 2 total replies), skipping remaining AI replies")
            break

        parent_comment = random.choice(eligible_parents)
        thread_context = get_thread_context(parent_comment, all_comments_for_replies)

        # Combine all used archetypes (top-level + previous replies)
        all_used_archetypes = used_archetypes_from_top_level + used_archetypes_in_replies

        ai_reply = generate_thread_reply(
            post.title,
            summarized_content,
            post.subreddit,
            thread_context,
            parent_comment,
            client,
            all_real_comments=limited_real_comments,
            tyrell_agenda=tyrell_agenda,
            used_archetypes=all_used_archetypes  # Pass all used archetypes
        )

        if ai_reply:
            ai_replies.append((ai_reply, parent_comment.id))
            # Track the archetype used in this reply
            if hasattr(ai_reply, 'archetype_used') and ai_reply.archetype_used:
                used_archetypes_in_replies.append(ai_reply.archetype_used)
                print(f"Reply archetype used: {ai_reply.archetype_used}")

            # Track that we've added an AI reply to this parent
            ai_replies_per_parent[parent_comment.id] = ai_replies_per_parent.get(parent_comment.id, 0) + 1
    
    # Final check: if we still don't have enough AI comments, generate more top-level ones
    total_ai_generated = len(ai_top_level) + len(ai_replies)
    if total_ai_generated < target_ai_count:
        additional_needed = target_ai_count - total_ai_generated
        print(f"Still need {additional_needed} more AI comments, generating additional top-level comments")
        
        additional_ai, _ = generate_ai_comments_wrapper(
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
    
    return mixed_comments, tyrell_agenda


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

@app.post("/api/admin/login")
def admin_login(request: AdminLoginRequest):
    """Admin login endpoint"""
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")  # Default for development
    
    if request.password == admin_password:
        return AdminLoginResponse(
            token="admin_authenticated",
            message="Login successful"
        )
    else:
        raise HTTPException(status_code=401, detail="Invalid admin password")

@app.get("/api/posts")
def get_posts(include_deleted: bool = False, x_admin_env: str = Header(None)):
    """Get all saved posts"""
    force_turso = parse_admin_environment(x_admin_env)
    posts = get_all_posts(include_deleted=include_deleted, force_turso=force_turso)
    return {"posts": posts}

@app.get("/api/posts/subreddit/{subreddit}")
def get_posts_by_subreddit_endpoint(subreddit: str, include_deleted: bool = False, x_admin_env: str = Header(None)):
    """Get posts filtered by subreddit"""
    start_time = time.time()
    print(f"[TIMING] GET /api/posts/subreddit/{subreddit} - Request started")

    force_turso = parse_admin_environment(x_admin_env)

    db_start = time.time()
    posts = get_posts_by_subreddit(subreddit, include_deleted=include_deleted, force_turso=force_turso)
    db_time = time.time() - db_start
    print(f"[TIMING] GET /api/posts/subreddit/{subreddit} - DB query took {db_time:.3f}s")

    total_time = time.time() - start_time
    print(f"[TIMING] GET /api/posts/subreddit/{subreddit} - Total request took {total_time:.3f}s")

    return {"posts": posts, "subreddit": subreddit}

@app.post("/api/admin/posts/{post_id}/delete")
def admin_delete_post(post_id: int, x_admin_env: str = Header(None)):
    """Soft delete a post (admin only)"""
    force_turso = parse_admin_environment(x_admin_env)
    if soft_delete_post(post_id, force_turso=force_turso):
        return {"message": "Post deleted successfully", "post_id": post_id}
    else:
        raise HTTPException(status_code=404, detail="Post not found or already deleted")

@app.post("/api/admin/posts/{post_id}/restore")
def admin_restore_post(post_id: int, x_admin_env: str = Header(None)):
    """Restore a soft-deleted post (admin only)"""
    force_turso = parse_admin_environment(x_admin_env)
    if restore_post(post_id, force_turso=force_turso):
        return {"message": "Post restored successfully", "post_id": post_id}
    else:
        raise HTTPException(status_code=404, detail="Post not found or not deleted")

# User tracking endpoints

@app.post("/api/users/register")
def register_user(request: UserRegisterRequest, x_admin_env: str = Header(None)):
    """Register a new anonymous user"""
    try:
        force_turso = parse_admin_environment(x_admin_env)
        user_id = get_or_create_user(request.anonymous_id, force_turso)
        return {"message": "User registered successfully", "user_id": user_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register user: {str(e)}")

@app.post("/api/users/guess")
def save_guess(request: UserGuessRequest, x_admin_env: str = Header(None)):
    """Save a user's guess for a comment"""
    try:
        force_turso = parse_admin_environment(x_admin_env)
        # Get or create user
        user_id = get_or_create_user(request.anonymous_id, force_turso)

        # Save the guess
        success = save_user_guess(
            user_id=user_id,
            post_id=request.post_id,
            comment_id=request.comment_id,
            guess=request.guess,
            is_correct=request.is_correct,
            force_turso=force_turso
        )

        if success:
            return {"message": "Guess saved successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save guess")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save guess: {str(e)}")

@app.post("/api/users/progress")
def get_progress(request: UserProgressRequest, x_admin_env: str = Header(None)):
    """Get user's progress on a specific post"""
    start_time = time.time()
    print(f"[TIMING] POST /api/users/progress - Request started (post_id={request.post_id})")

    try:
        force_turso = parse_admin_environment(x_admin_env)

        db_start = time.time()
        user_id = get_or_create_user(request.anonymous_id, force_turso)
        db_time = time.time() - db_start
        print(f"[TIMING] POST /api/users/progress - get_or_create_user took {db_time:.3f}s")

        db_start = time.time()
        progress = get_user_progress(user_id, request.post_id, force_turso)
        db_time = time.time() - db_start
        print(f"[TIMING] POST /api/users/progress - get_user_progress took {db_time:.3f}s")

        total_time = time.time() - start_time
        print(f"[TIMING] POST /api/users/progress - Total request took {total_time:.3f}s")

        return progress
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get progress: {str(e)}")

@app.get("/api/users/{anonymous_id}/progress")
def get_all_progress(anonymous_id: str, x_admin_env: str = Header(None)):
    """Get user's progress across all posts"""
    start_time = time.time()
    print(f"[TIMING] GET /api/users/{anonymous_id}/progress - Request started")

    try:
        force_turso = parse_admin_environment(x_admin_env)

        db_start = time.time()
        user_id = get_or_create_user(anonymous_id, force_turso)
        db_time = time.time() - db_start
        print(f"[TIMING] GET /api/users/{anonymous_id}/progress - get_or_create_user took {db_time:.3f}s")

        db_start = time.time()
        progress = get_user_all_progress(user_id, force_turso)
        db_time = time.time() - db_start
        print(f"[TIMING] GET /api/users/{anonymous_id}/progress - get_user_all_progress took {db_time:.3f}s")

        total_time = time.time() - start_time
        print(f"[TIMING] GET /api/users/{anonymous_id}/progress - Total request took {total_time:.3f}s")

        return {"progress": progress}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get progress: {str(e)}")

@app.post("/api/users/reset-progress")
def reset_progress(request: ResetProgressRequest, x_admin_env: str = Header(None)):
    """Reset user's progress on a specific post"""
    try:
        force_turso = parse_admin_environment(x_admin_env)
        user_id = get_or_create_user(request.anonymous_id, force_turso)
        success = reset_user_progress(user_id, request.post_id, force_turso)

        if success:
            return {"message": "Progress reset successfully"}
        else:
            return {"message": "No progress found to reset"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset progress: {str(e)}")

@app.post("/api/users/flag-obvious")
def flag_obvious(request: FlagObviousRequest, x_admin_env: str = Header(None)):
    """Flag a comment as too obvious for a user"""
    try:
        force_turso = parse_admin_environment(x_admin_env)
        user_id = get_or_create_user(request.anonymous_id, force_turso)
        success = flag_comment_as_obvious(user_id, request.post_id, request.comment_id, force_turso)

        if success:
            return {"message": "Comment flagged as obvious successfully"}
        else:
            raise HTTPException(status_code=404, detail="Guess not found or already flagged")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to flag comment: {str(e)}")

@app.post("/api/posts/submit")
async def submit_reddit_url(request: SubmitURLRequest, x_admin_env: str = Header(None)):
    """Submit a Reddit URL for processing"""
    
    # Validate URL format
    if not validate_reddit_url(request.url):
        raise HTTPException(status_code=400, detail="Invalid Reddit URL format")
    
    # Parse admin environment
    force_turso = parse_admin_environment(x_admin_env)

    # Check if already processed (unless overwrite is enabled)
    if not request.overwrite_existing and post_exists(request.url, force_turso=force_turso):
        raise HTTPException(status_code=400, detail="This Reddit post has already been processed")

    # Check for API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY environment variable not set")
    
    try:
        # Fetch Reddit data
        print(f"Attempting to fetch Reddit URL: {request.url}")
        reddit_data = await fetch_reddit_post(request.url)
        print(f"Successfully fetched Reddit data")
        
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
        mixed_comments, tyrell_agenda = await generate_mixed_comments_for_post(
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
            total_count=total_final_comments,
            force_turso=force_turso,
            overwrite_existing=request.overwrite_existing,
            tyrell_agenda=tyrell_agenda
        )

        # Run LLM-as-a-judge evaluation
        try:
            print("Running LLM-as-a-judge evaluation...")
            evaluator = CommentEvaluator(client)

            # Convert comments to evaluation format
            all_flat_comments = flatten_all_comments(mixed_comments)
            human_comments = [
                CommentData(
                    id=i,
                    text=comment.content,
                    is_ai=False,
                    comment_type='top_level' if comment.depth == 0 else 'reply'
                )
                for i, comment in enumerate(all_flat_comments) if not comment.is_ai
            ]

            ai_comments = [
                CommentData(
                    id=i,
                    text=comment.content,
                    is_ai=True,
                    comment_type='top_level' if comment.depth == 0 else 'reply'
                )
                for i, comment in enumerate(all_flat_comments) if comment.is_ai
            ]

            post_evaluation = PostEvaluation(
                post_title=post.title,
                human_comments=human_comments,
                ai_comments=ai_comments
            )

            # Run evaluation
            eval_results = await evaluator.evaluate_post(post_evaluation)

            # Save evaluation results to database
            save_evaluation_result(
                post_id=post_id,
                mixed_reality_score=eval_results['mixed_reality_score'],
                diversity_score=eval_results['diversity_score'],
                appropriateness_score=eval_results['appropriateness_score'],
                overall_score=eval_results['overall_score'],
                generation_version="v1.3",  # Simple hardcoded version
                evaluation_version="v1.1",  # Simple hardcoded version
                force_turso=force_turso
            )

            print(f"Evaluation completed: {eval_results}")

        except Exception as e:
            print(f"Evaluation failed, continuing without evaluation: {str(e)}")
            # Don't fail the entire post creation if evaluation fails
        
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
        print(f"ValueError in submit endpoint: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process Reddit post: {str(e)}")

@app.get("/api/posts/{post_id}")
def get_post(post_id: int, x_admin_env: str = Header(None)):
    """Get a specific post with mixed comments"""
    force_turso = parse_admin_environment(x_admin_env)
    post_data = get_post_by_id(post_id, force_turso=force_turso)
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

@app.get("/api/stats")
def get_stats(x_admin_env: str = Header(None)):
    """Get aggregate statistics for all guesses"""
    force_turso = parse_admin_environment(x_admin_env)
    stats = get_aggregate_stats(force_turso=force_turso)
    return stats

@app.get("/api/mixed-comments/{post_id}")
def get_mixed_comments(post_id: int, x_admin_env: str = Header(None)):
    """Get the mixed real + AI comments for a specific post"""
    start_time = time.time()
    print(f"[TIMING] GET /api/mixed-comments/{post_id} - Request started")

    force_turso = parse_admin_environment(x_admin_env)

    db_start = time.time()
    post_data = get_post_by_id(post_id, force_turso=force_turso)
    db_time = time.time() - db_start
    print(f"[TIMING] GET /api/mixed-comments/{post_id} - get_post_by_id took {db_time:.3f}s")

    if not post_data:
        raise HTTPException(status_code=404, detail="Post not found")

    # Return data in the format expected by frontend
    response = post_data['mixed_comments'].copy()
    response['tyrell_agenda'] = post_data.get('tyrell_agenda')

    total_time = time.time() - start_time
    print(f"[TIMING] GET /api/mixed-comments/{post_id} - Total request took {total_time:.3f}s")

    return response

# Simple root endpoint for API status
@app.get("/")
async def root():
    return {"message": "Reddit or Replicant API", "status": "running"}