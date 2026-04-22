import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com/repos"


def fetch_repo_info(owner: str, repo: str, token: Optional[str] = None) -> Optional[dict]:
    """从 GitHub API 获取指定仓库的基本信息。

    Args:
        owner: 仓库所有者，如 "langchain-ai"。
        repo: 仓库名称，如 "langgraph"。
        token: 可选的 GitHub Personal Access Token，未提供时尝试从
               环境变量 GITHUB_TOKEN 读取。

    Returns:
        包含仓库信息的字典，结构为::

            {
                "full_name": "owner/repo",
                "description": "仓库描述",
                "stars": 1234,
                "forks": 56,
                "language": "Python",
                "url": "https://github.com/owner/repo",
            }

        请求失败时返回 None。
    """
    resolved_token = token or os.environ.get("GITHUB_TOKEN")
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    if resolved_token:
        headers["Authorization"] = f"Bearer {resolved_token}"

    url = f"{GITHUB_API_BASE}/{owner}/{repo}"

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("获取仓库 %s/%s 信息失败: %s", owner, repo, exc)
        return None

    data = response.json()
    info = {
        "full_name": data.get("full_name", f"{owner}/{repo}"),
        "description": data.get("description") or "",
        "stars": data.get("stargazers_count", 0),
        "forks": data.get("forks_count", 0),
        "language": data.get("language") or "",
        "url": data.get("html_url", f"https://github.com/{owner}/{repo}"),
    }

    logger.info("获取仓库 %s/%s 成功: stars=%d, forks=%d", owner, repo, info["stars"], info["forks"])
    return info
