from post_logger import log_post, analyze_comments_with_llm, extract_tickers
from datetime import datetime, timezone
from constants import SCORE_THRESHOLD, FLAIRS_TO_IGNORE
import re
import asyncpraw
import os
from dotenv import load_dotenv

load_dotenv()

reddit = asyncpraw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
    user_agent=os.getenv("REDDIT_USER_AGENT"),
)


async def score_post(post, age_hours):
    score = 0
    text = (post.title + " " + post.selftext).lower()
    breakdown = {}
    tickers = await extract_tickers(post.title, post.selftext)

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


async def fetch_comments(post_id):
    submission = await reddit.submission(id=post_id)
    await submission.load()  # ensure post is fully loaded
    await submission.comments.replace_more(limit=0)  # fetch all comments
    return [comment.body for comment in submission.comments.list()]


async def process_posts(posts, session, seen_ids, subreddit_name):
    async for post in posts:
        if post.id in seen_ids or post.stickied:
            continue
        seen_ids.add(post.id)

        if (
            post.link_flair_text
            and post.link_flair_text.strip().lower() in FLAIRS_TO_IGNORE
        ):
            continue

        created_at = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
        age_hours = (datetime.now(tz=timezone.utc) - created_at).total_seconds() / 3600
        score, breakdown = score_post(post, age_hours)

        if score >= SCORE_THRESHOLD:
            print(f"[{score}] {post.title}")

            comments = await fetch_comments(post.id)
            post_dict = {
                "title": post.title,
                "body": post.selftext,
                "comments": comments,
            }

            try:
                enriched_post = await analyze_comments_with_llm(session, post_dict)
                post.selftext = enriched_post["body"]
                post.sentiment_score = enriched_post["sentiment_score"]
            except Exception as e:
                print(f"LLM analysis failed for {post.id}: {e}")
                post.sentiment_score = None

            await log_post(post, score, breakdown)
