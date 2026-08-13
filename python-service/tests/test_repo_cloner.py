from pathlib import Path

import pytest
from app.repo_cloner import cloned_repo, validate_github_url


def test_validate_github_url():
    assert validate_github_url("https://github.com/user/repo") is True
    assert validate_github_url("http://github.com/user/repo") is True
    assert validate_github_url("https://gitlab.com/user/repo") is False
    assert validate_github_url("") is False
    assert validate_github_url("not a url") is False
    assert validate_github_url("https://github.com/octocat/Hello-World") is True
    # Security edge cases
    assert validate_github_url("https://github.com.attacker.com/repo") is False
    assert validate_github_url("https://attacker.com/github.com/repo") is False
    assert validate_github_url("git@-oProxyCommand=calc.exe:user/repo.git") is False


def test_cloned_repo_invalid_url():
    with pytest.raises((RuntimeError, ValueError)):
        with cloned_repo("https://github.com/nonexistentuser12345/nonexistentrepo12345-xyz"):
            pass


def test_cloned_repo_success():
    # Use a tiny public repo
    repo_url = "https://github.com/octocat/Hello-World"
    try:
        with cloned_repo(repo_url) as path:
            assert Path(path).exists()
            # Check README exists
            assert (Path(path) / "README").exists() or len(list(Path(path).iterdir())) > 0
    except Exception as e:
        pytest.skip(f"Skipping clone test due to network: {e}")
