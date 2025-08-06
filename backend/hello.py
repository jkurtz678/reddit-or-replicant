from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import json
import os
import httpx
from reddit_parser import parse_reddit_json

app = FastAPI()

# API routes
@app.get("/api")
def read_root():
    return {"Hello": "World"}

@app.get("/api/posts")
def get_posts():
    return {"posts": ["Post 1", "Post 2"]}

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