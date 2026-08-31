"""Verify a user-selected historical run before restoring its Pages artifact."""
import json
import os
from urllib.request import Request, urlopen


def validate_run(run, repository):
    if run.get("conclusion") != "success" or run.get("head_branch") != "main":
        raise ValueError("Restore requires a successful main-branch deployment run")
    if run.get("path") != ".github/workflows/deploy-pages.yml" or run.get("event") == "pull_request":
        raise ValueError("Only the deployment workflow can supply a release")
    if run.get("head_repository", {}).get("full_name", "").lower() != repository.lower():
        raise ValueError("Cannot restore an artifact from a fork")


def main():
    run_id = os.environ["RESTORE_RUN_ID"]
    if not run_id.isascii() or not run_id.isdigit(): raise ValueError("Run ID must contain digits only")
    repo = os.environ["GITHUB_REPOSITORY"]
    request = Request(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}", headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json"})
    with urlopen(request, timeout=20) as response: run = json.load(response)
    validate_run(run, repo)
    print(f"Validated deployment run {run_id}")


if __name__ == "__main__": main()
