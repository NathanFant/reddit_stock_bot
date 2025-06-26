import praw
import re
import json
from datetime import datetime, timezone, date
from sort_json import sort_json
from dotenv import load_dotenv
import os

# ---- CONFIG ----
load_dotenv()
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")
if not all([REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT]):
    raise ValueError(
        "Please set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, and REDDIT_USER_AGENT in your .env file."
    )


SCORE_THRESHOLD = 20  # minimum confidence score to save
SUBREDDITS = ["stocks", "wallstreetbets", "smallstreetbets", "investing"]
FLAIRS_TO_IGNORE = [
    f.strip().lower()
    for f in [
        "macro",
        "off-topic",
        "discussion",
        "question",
        "news",
        "politics",
        "broad market news",
    ]
]
POST_LIMIT = 500  # per subreddit


# ---- SETUP ----
reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT,
)


def score_post(post, age_hours):
    score = 0
    text = (post.title + " " + post.selftext).lower()

    if len(post.selftext.split()) > 400:
        score += 10
    if any(tag in text for tag in ["earnings", "guidance", "catalyst"]):
        score += 10
    if "sec.gov" in text or "10-q" in text or "10-k" in text:
        score += 15
    if any(term in text for term in ["insider buy", "short float", "call volume"]):
        score += 10
    if re.search(r"\$[A-Z]{1,5}", post.title):
        score += 5
    if "yolo" in text or "🚀" in text:
        score -= 15
    if post.upvote_ratio and post.upvote_ratio >= 0.8:
        score += 5
    if age_hours < 1:
        score += 5
    elif age_hours < 3:
        score += 3
    elif age_hours < 6:
        score += 2
    elif age_hours < 12:
        score += 1

    score -= int(age_hours // 24)
    return score


def extract_tickers(title, body):
    title_tickers = re.findall(r"\$[A-Z]{1,5}", title)
    body_tickers = re.findall(r"\$[A-Z]{1,5}", body)
    return list({t[1:] for t in body_tickers + title_tickers})  # remove duplicates


def log_post(post, score):
    data = {
        "score": score,
        "post_date": datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
        .date()
        .isoformat(),
        "title": post.title,
        "author": str(post.author),
        "subreddit": post.subreddit.display_name,
        "flair": post.link_flair_text.strip().lower() if post.link_flair_text else None,
        "url": post.url,
        "tickers": extract_tickers(
            title=post.title.upper(), body=post.selftext.upper()
        ),
        "upvotes": post.score,
        "upvote_ratio": post.upvote_ratio,
        "body": post.selftext[:400],  # truncate long posts
    }
    with open("dd_log.jsonl", "a") as f:
        f.write(json.dumps(data) + "\n")


def main():
    open("dd_log.jsonl", "w").close()  # clear log file at start
    for sub in SUBREDDITS:
        print(f"Checking /r/{sub}...")
        for post in reddit.subreddit(sub).new(limit=POST_LIMIT):
            if post.stickied:
                continue
            elif (
                post.link_flair_text
                and post.link_flair_text.strip().lower() in FLAIRS_TO_IGNORE
            ):
                continue
            created_at = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
            age_hours = (
                datetime.now(tz=timezone.utc) - created_at
            ).total_seconds() / 3600
            score = score_post(post, age_hours)
            if score >= SCORE_THRESHOLD:
                print(f"[{score}] {post.title}")
                log_post(post, score)
    sort_json()


if __name__ == "__main__":
    main()
