import os
import json
import re
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()


# ------------------------
# Ticker extraction helper
# ------------------------
async def extract_tickers(title, body):
    """
    Extract stock tickers from the title and body of a post.
    Tickers are assumed to be uppercase letters, 1-5 characters long.
    """
    title_tickers = re.findall(r"\$[A-Z]{1,5}", title)
    body_tickers = re.findall(r"\$[A-Z]{1,5}", body)
    return list({t[1:] for t in body_tickers + title_tickers})  # removes duplicates


# async def log_post(post, score, breakdown):
#     data = {
#         "score": score,
#         "posted_date": datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
#         .date()
#         .isoformat(),
#         "tickers": extract_tickers(
#             title=post.title.upper(), body=post.selftext.upper()
#         ),
#         "title": post.title,
#         "author": str(post.author),
#         "subreddit": post.subreddit.display_name,
#         "flair": post.link_flair_text.strip().lower() if post.link_flair_text else None,
#         "upvotes": post.score,
#         "upvote_ratio": post.upvote_ratio,
#         "url": post.url,
#         "body": post.selftext,
#         "breakdown": breakdown,
#     }
#     with open("dd_log.jsonl", "a") as f:
#         f.write(json.dumps(data) + "\n")


# ------------------------
# Main LLM sentiment analyzer
# ------------------------
async def analyze_comments_with_llm(session, post):
    prompt = f"""
You are a strictly JSON-based LLM that summarizes Reddit posts and analyzes sentiment.
You will receive a Reddit post with its title, body, and comments.
Only respond with valid JSON. Do not add code fences, explanations, or extra text.

JSON format:
{{
  "summary": "short rewritten body",
  "sentiment_score": integer between 0 (negative) and 100 (positive)
}}

Title: {post["title"]}
Body: {post["body"]}
Comments: {" ".join(post["comments"])}

Respond with JSON only, no additional text or formatting.
"""

    async with session.post(
        "http://localhost:11434/api/generate",
        headers={
            "Content-Type": "application/json",
        },
        json={
            "model": "llama3",
            "temperature": 0.2,
            "stream": False,
            "options": {
                "num_ctx": 4096,
                "temperature": 0.2,
                "top_p": 0.9,
                "top_k": 40,
                "repeat_penalty": 1.1,
                "seed": 1337,
                "stop": ["}\n", "\n\n"],
            },
            "prompt": prompt,
        },
    ) as response:
        if response.status != 200:
            raise Exception(
                f"Ollama API error: {response.status} {await response.text()}"
            )
        content = ""
        async for line in response.content:
            line = line.decode("utf-8").strip()
            if not line:
                continue
            try:
                chunk = json.loads(line)
                if "response" in chunk:
                    content += chunk["response"]
            except json.JSONDecodeError as e:
                print("BAD JSON:", line, e)
        print("LLM response:", content)

    try:
        parsed = json.loads(content)
        post["body"] = parsed.get("summary", post["body"])
        post["sentiment_score"] = parsed.get("sentiment_score", 50)
    except Exception as e:
        print("Failed to parse LLM response:", content, e)
        post["sentiment_score"] = 50  # fallback neutral

    return post


# ------------------------
# Log updated post to file
# ------------------------
async def log_post(post, score, breakdown):
    data = {
        "score": score,
        "sentiment_score": getattr(post, "sentiment_score", 50),
        "posted_date": datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
        .date()
        .isoformat(),
        "tickers": await extract_tickers(
            title=post.title.upper(), body=post.selftext.upper()
        ),
        "title": post.title,
        "subreddit": post.subreddit.display_name,
        "flair": post.link_flair_text.strip().lower() if post.link_flair_text else None,
        "upvote_ratio": post.upvote_ratio,
        "url": post.url,
        "body": getattr(post, "body", post.selftext[:400]),  # limit body length
        "breakdown": breakdown,
    }
    with open("dd_log.jsonl", "a") as f:
        f.write(json.dumps(data) + "\n")
