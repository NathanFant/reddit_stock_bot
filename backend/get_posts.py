import json
import re
from datetime import datetime, timezone
from reddit import reddit
from config import SUBREDDITS, POST_LIMIT, SCORE_THRESHOLD
from config import FLAIRS_TO_IGNORE, SORTS, DD_LOG_FILE


def extract_tickers(title: str, body: str) -> list[str]:
    title_tickers = re.findall(r"\$([A-Z]{1,5})", title)
    body_tickers = re.findall(r"\$([A-Z]{1,5})", body)
    return list(set(title_tickers + body_tickers))


def score_post(post, age_hours: int) -> tuple[int, dict, list[str]]:
    score = 0
    breakdown = {}
    text = (post.title + " " + post.selftext).lower()
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


def log_post(post, score, breakdown):
    post_data = {
        "score": score,
        "posted_date": post.created_utc,
        "tickers": extract_tickers(post.title, post.selftext),
        "title": post.title,
        "author": str(post.author),
        "subreddit": str(post.subreddit),
        "flair": post.link_flair_text,
        "upvotes": post.ups,
        "upvote_ratio": post.upvote_ratio,
        "url": post.url,
        "body": post.selftext,
        "breakdown": breakdown,
    }

    with open(DD_LOG_FILE, "a") as f:
        f.write(json.dumps(post_data) + "\n")


def scrape_and_save():
    open(DD_LOG_FILE, "w").close()  # Clear the log file
    seen_ids = set()

    for sub in SUBREDDITS:
        print(sub)
        for sort in SORTS:
            print(sort)
            try:
                posts = (
                    getattr(reddit.subreddit(sub), sort)(limit=POST_LIMIT)
                    if sort in SORTS
                    else reddit.subreddit(sub).new(limit=POST_LIMIT)
                )

                for post in posts:
                    if post.id in seen_ids:
                        continue

                    seen_ids.add(post.id)

                    if post.score < SCORE_THRESHOLD:
                        continue

                    if (
                        post.link_flair_text
                        and post.link_flair_text.strip().lower() in FLAIRS_TO_IGNORE
                    ):
                        continue

                    created_at = datetime.fromtimestamp(
                        post.created_utc, tz=timezone.utc
                    )
                    age_hours = (
                        datetime.now(timezone.utc) - created_at
                    ).total_seconds() / 3600

                    score, breakdown = score_post(post, int(age_hours))

                    if score >= SCORE_THRESHOLD:
                        log_post(post[:400], score, breakdown)
                        print(f"Logged post: {post.title} (Score: {score})")

            except Exception as e:
                print(f"Error processing {sub} ({sort}): {e}")
                continue


if __name__ == "__main__":
    scrape_and_save()
    print(f"Posts scraped and saved")
