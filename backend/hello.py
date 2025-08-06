from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/posts")
def get_posts():
    return {"posts": ["Post 1", "Post 2"]}