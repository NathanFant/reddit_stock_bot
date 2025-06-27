from fastapi import FastAPI
from models import Post
import json
from typing import List

app = FastAPI()

POSTS_FILE = "dd_log.jsonl"
POSTS: list[Post] = []


@app.on_event("startup")
def load_posts():
    global POSTS
    with open(POSTS_FILE, "r") as f:
        POSTS = [Post(**json.loads(line)) for line in f if line.strip()]


@app.get("/posts", response_model=List[Post])
def get_posts():
    return POSTS
