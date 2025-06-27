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
SORTS = [
    "new",
    "hot",
    "top",
    "rising",
]  # valid sorting options for Reddit API
DD_LOG_FILE = "dd_log.jsonl"  # file to store posts
