"""
README updater and GitHub integration utilities.
Handles marker-based content replacement and PR creation.
"""

import os
import re
import base64
from github import Github, GithubException


def replace_between_markers(content, new_text, start_marker="<!-- DOCU_SYNC_START -->", end_marker="<!-- DOCU_SYNC_END -->"):
    """
    Safely replace content between two markers in a README or markdown file.
    
    Args:
        content: str, the full content of the file
        new_text: str, the new content to insert between markers
        start_marker: str, the opening marker
        end_marker: str, the closing marker
    
    Returns:
        str: updated content with replacement, or None if markers not found
    """
    # Escape special regex characters in markers
    start_escaped = re.escape(start_marker)
    end_escaped = re.escape(end_marker)
    
    # Pattern to match content between markers (including markers)
    pattern = f"({start_escaped}).*?({end_escaped})"
    
    # Check if markers exist
    if not re.search(pattern, content, re.DOTALL):
        return None
    
    # Replace content between markers, preserving the markers themselves
    replacement = f"{start_marker}\n{new_text}\n{end_marker}"
    updated_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    return updated_content


def ensure_markers_exist(content, start_marker="<!-- DOCU_SYNC_START -->", end_marker="<!-- DOCU_SYNC_END -->"):
    """
    Check if markers exist in content, and add them if missing.
    
    Args:
        content: str, the file content
        start_marker: str, the opening marker
        end_marker: str, the closing marker
    
    Returns:
        tuple: (bool, str) - (markers_existed, content_with_markers)
    """
    start_escaped = re.escape(start_marker)
    end_escaped = re.escape(end_marker)
    pattern = f"{start_escaped}.*?{end_escaped}"
    
    if re.search(pattern, content, re.DOTALL):
        return True, content
    
    # Markers don't exist - append them at the end
    if not content.endswith('\n'):
        content += '\n'
    
    content += f"\n{start_marker}\n{end_marker}\n"
    return False, content


def load_github(token=None, repo_name=None):
    """
    Load GitHub repository object.
    
    Args:
        token: GitHub personal access token (or use GITHUB_TOKEN env var)
        repo_name: repository in format "owner/repo" (or use GITHUB_REPO env var)
    
    Returns:
        github.Repository.Repository: repository object
    """
    # REQUIRED: Set GITHUB_TOKEN in your .env file
    token = token or os.getenv("GITHUB_TOKEN")
    # REQUIRED: Set GITHUB_REPO in your .env file (format: "owner/repo")
    repo_name = repo_name or os.getenv("GITHUB_REPO")
    
    if not token:
        raise ValueError("GitHub token is required (GITHUB_TOKEN env var)")
    if not repo_name:
        raise ValueError("Repository name is required (GITHUB_REPO env var)")
    
    github = Github(token)
    repo = github.get_repo(repo_name)
    
    return repo


def replace_image_and_update_markdown(repo, branch, new_image_bytes, new_text, 
                                       image_path="docs/screenshot.png", 
                                       readme_path="README.md"):
    """
    Update both image and README content in a GitHub repository.
    
    Args:
        repo: github.Repository.Repository object
        branch: branch name to commit to
        new_image_bytes: bytes of the new image
        new_text: new text content for README
        image_path: path to image in repo
        readme_path: path to README in repo
    """
    # Get current README
    readme_file = repo.get_contents(readme_path, ref=branch)
    current_readme = readme_file.decoded_content.decode('utf-8')
    
    # Ensure markers exist
    markers_existed, readme_with_markers = ensure_markers_exist(current_readme)
    
    if not markers_existed:
        # Commit the markers first
        repo.update_file(
            path=readme_path,
            message="chore: add Docu-Sync markers to README",
            content=readme_with_markers,
            sha=readme_file.sha,
            branch=branch
        )
        current_readme = readme_with_markers
        # Refresh the file object
        readme_file = repo.get_contents(readme_path, ref=branch)
    
    # Replace content between markers
    updated_readme = replace_between_markers(current_readme, new_text)
    
    if updated_readme is None:
        raise ValueError("Failed to update README - markers not found")
    
    # Commit updated README
    repo.update_file(
        path=readme_path,
        message="docs: update README via Docu-Sync",
        content=updated_readme,
        sha=readme_file.sha,
        branch=branch
    )
    
    # Commit new image
    try:
        image_file = repo.get_contents(image_path, ref=branch)
        repo.update_file(
            path=image_path,
            message="docs: update screenshot",
            content=new_image_bytes,
            sha=image_file.sha,
            branch=branch
        )
    except GithubException:
        # Image doesn't exist, create it
        repo.create_file(
            path=image_path,
            message="docs: add screenshot",
            content=new_image_bytes,
            branch=branch
        )
