import json

FILE_PATH = "dd_log.jsonl"


def load_posts(filepath):
    with open(filepath, "r") as f:
        return [json.loads(line) for line in f]


def save_posts(posts, filepath):
    with open(filepath, "w") as f:
        for post in posts:
            f.write(json.dumps(post) + "\n")


def sort_json():
    """Sorts the posts in the JSONL file by score in descending order."""
    try:
        posts = load_posts(FILE_PATH)
        sorted_posts = sorted(posts, key=lambda p: p.get("score", 0), reverse=True)
        save_posts(sorted_posts, FILE_PATH)
        print(
            f"Sorted {len(sorted_posts)} posts by score and saved back to '{FILE_PATH}'"
        )
    except FileNotFoundError:
        print(f"File '{FILE_PATH}' not found. Make sure it's in the same directory.")


if __name__ == "__main__":
    sort_json()
