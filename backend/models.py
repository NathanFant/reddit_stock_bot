from pydantic import BaseModel
from typing import List


class Post(BaseModel):
    score: int
    posted_date: str
    tickers: List[str]
    title: str
    author: str
    subreddit: str
    flair: str | None
    upvotes: int
    upvote_ratio: float
    url: str
    body: str
    breakdown: dict
