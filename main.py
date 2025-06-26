import praw
import re
import json
from datetime import datetime, timezone
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
SUBREDDITS = [
    "stocks",
    "wallstreetbets",
    "smallstreetbets",
    "investing",
    "stockmarket",
    "options",
    "daytrading",
    "algotrading",
]
FLAIRS_TO_IGNORE = [
    flair.strip().lower()
    for flair in [
        "off-topic",
        "discussion",
        "question",
        "news",
        "broad market news",
        "shitpost",
        "meme",
    ]
]
POST_LIMIT = 1000  # per subreddit


# ---- SETUP ----
reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT,
)


def score_post(post, age_hours):
    score = 0
    text = (post.title + " " + post.selftext).lower()
    breakdown = {}
    tickers = extract_tickers(post.title, post.selftext)

    if len(post.selftext.split()) > 400:
        score += 10
        breakdown["long_body"] = 10
    else:
        score -= 10
        breakdown["short_body"] = -10
    if any(tag in text for tag in ["earnings", "guidance", "catalyst"]):
        score += 10
        breakdown["financial_terms"] = 10
    if "sec.gov" in text or "10-q" in text or "10-k" in text:
        score += 15
        breakdown["sec_filings"] = 15
    if any(term in text for term in ["insider buy", "short float", "call volume"]):
        score += 10
        breakdown["technical_terms"] = 10
    if re.search(r"\$[A-Z]{1,5}", post.title):
        score += 5
        breakdown["ticker_in_title"] = 5
    if "yolo" in text or "🚀" in text:
        score -= 15
        breakdown["meme_penalty"] = -15
    if post.upvote_ratio and post.upvote_ratio >= 0.8:
        score += 5
        breakdown["high_upvote_ratio"] = 5
    if age_hours < 1:
        score += 4
        breakdown["new_post"] = 4
    if len(tickers) < 1:
        score -= 30
        breakdown["no_tickers"] = -30
    elif age_hours < 3:
        score += 3
        breakdown["recent_post"] = 3
    elif age_hours < 6:
        score += 2
        breakdown["somewhat_recent_post"] = 2
    elif age_hours < 12:
        score += 1
        breakdown["older_post"] = 1
    else:
        score -= int(age_hours // 24)
        breakdown["age_penalty"] = -int(age_hours // 24)
    return score, breakdown


def extract_tickers(title, body):
    title_tickers = re.findall(r"\$[A-Z]{1,5}", title)
    body_tickers = re.findall(r"\$[A-Z]{1,5}", body)
    return list({t[1:] for t in body_tickers + title_tickers})  # remove duplicates


def log_post(post, score, breakdown):
    data = {
        "score": score,
        "posted_date": datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
        .date()
        .isoformat(),
        "tickers": extract_tickers(
            title=post.title.upper(), body=post.selftext.upper()
        ),
        "title": post.title,
        "author": str(post.author),
        "subreddit": post.subreddit.display_name,
        "flair": post.link_flair_text.strip().lower() if post.link_flair_text else None,
        "upvotes": post.score,
        "upvote_ratio": post.upvote_ratio,
        "url": post.url,
        "body": post.selftext[:400],  # truncate long posts
        "breakdown": breakdown,
    }
    with open("dd_log.jsonl", "a") as f:
        f.write(json.dumps(data) + "\n")


def main():
    open("dd_log.jsonl", "w").close()  # clear log file at start
    seen_ids = set()
    sorts = ["new", "hot", "top"]

    for sub in SUBREDDITS:
        print(f"\n--- /r/{sub} ---")
        total_processed = 0

        for sort in sorts:
            print(f"Checking /r/{sub} ({sort})...")
            try:
                if sort == "new":
                    posts = reddit.subreddit(sub).new(limit=POST_LIMIT)
                elif sort == "hot":
                    posts = reddit.subreddit(sub).hot(limit=POST_LIMIT)
                elif sort == "top":
                    posts = reddit.subreddit(sub).top(
                        time_filter="week", limit=POST_LIMIT
                    )
                else:
                    raise ValueError(f"Unknown sort type: {sort}")

                for post in posts:
                    if post.id in seen_ids or post.stickied:
                        continue
                    seen_ids.add(post.id)
                    total_processed += 1

                    if post.stickied:
                        continue
                    elif (
                        post.link_flair_text
                        and post.link_flair_text.strip().lower() in FLAIRS_TO_IGNORE
                    ):
                        continue

                    created_at = datetime.fromtimestamp(
                        post.created_utc, tz=timezone.utc
                    )
                    age_hours = (
                        datetime.now(tz=timezone.utc) - created_at
                    ).total_seconds() / 3600
                    score, breakdown = score_post(post, age_hours)

                    if score >= SCORE_THRESHOLD:
                        print(f"[{score}] {post.title}")
                        log_post(post, score, breakdown)

            except Exception as e:
                print(f"Error processing /r/{sub} ({sort}): {e}")

        print(f"\nProcessed {total_processed} posts in /r/{sub}")
    sort_json()


if __name__ == "__main__":
    main()
