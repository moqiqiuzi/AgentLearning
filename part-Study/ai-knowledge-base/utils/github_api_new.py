import requests


def get_repo_info(owner: str, repo: str) -> dict:
    url = f"https://api.github.com/repos/{owner}/{repo}"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    return {
        "full_name": data["full_name"],
        "description": data["description"],
        "stars": data["stargazers_count"],
        "forks": data["forks_count"],
        "language": data["language"],
        "open_issues": data["open_issues_count"],
        "url": data["html_url"],
    }


if __name__ == "__main__":
    import json

    info = get_repo_info("modelcontextprotocol", "python-sdk")
    print(json.dumps(info, indent=2, ensure_ascii=False))
