import sort_json
import asyncio
import aiohttp
import asyncpraw
import os
from constants import SUBREDDITS, POST_LIMIT
from process_post import process_posts


async def main():
    open("dd_log.jsonl", "w").close()  # clear log file at start
    seen_ids = set()
    sorts = ["new", "hot", "top"]

    reddit = asyncpraw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT"),
    )

    async with reddit:
        async with aiohttp.ClientSession() as session:
            for subreddit in SUBREDDITS:
                sub = await reddit.subreddit(subreddit)
                print(f"\n--- /r/{sub} ---")
                total_processed = 0

                for sort in sorts:
                    print(f"Checking /r/{sub} ({sort})...")
                    try:
                        if sort == "new":
                            posts = sub.new(limit=POST_LIMIT)
                        elif sort == "hot":
                            posts = sub.hot(limit=POST_LIMIT)
                        elif sort == "top":
                            posts = sub.top(time_filter="month", limit=POST_LIMIT)
                        else:
                            raise ValueError(f"Unknown sort type: {sort}")

                        await process_posts(posts, session, seen_ids, subreddit, reddit)

                    except Exception as e:
                        print(f"Error processing /r/{sub} ({sort}): {e}")

                print(f"\nProcessed {total_processed} posts in /r/{sub}")
    sort_json.sort_json()
    print("\nAll done! Check dd_log.jsonl for results.")


if __name__ == "__main__":
    asyncio.run(main())
