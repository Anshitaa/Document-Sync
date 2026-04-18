"""
Docu-Sync Flask API
Microservice for detecting UI changes and automating README updates using Google Gemini AI.
"""

import os
import base64
import time
import logging
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

# Import our modules
from diff import compute_ssim_and_mask, summarize_change
from llm_client import analyze_visual_changes, generate_documentation
from updater import load_github, replace_image_and_update_markdown
from github import Github

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("docu-sync")

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max


@app.route('/', methods=['GET'])
def index():
    """Serve the web UI for testing."""
    return render_template('index.html')


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "docu-sync"}), 200


@app.route("/detect-change", methods=["POST"])
def detect_change():
    """
    Detect changes between two uploaded images using SSIM.

    Expects:
        - old_image: file upload
        - new_image: file upload

    Returns:
        JSON with SSIM score + bounding boxes (pixel-level) AND
        Gemini Vision semantic analysis (changed_elements, semantic_summary,
        change_type, severity).
    """
    try:
        if 'old_image' not in request.files or 'new_image' not in request.files:
            logger.warning("detect-change called with missing image files")
            return jsonify({"error": "Both old_image and new_image files are required"}), 400

        old = request.files['old_image'].read()
        new = request.files['new_image'].read()

        # Step 1: SSIM — fast pixel-level diff for numeric score and bounding boxes
        logger.info("Running SSIM pixel comparison")
        score, boxes, _, _ = compute_ssim_and_mask(old, new)
        ssim_summary = summarize_change(score, boxes)

        # Step 2: Gemini Vision — semantic understanding of WHAT changed
        logger.info("Running Gemini Vision semantic analysis")
        vision = analyze_visual_changes(old, new)

        logger.info("Change detection complete: SSIM=%.4f regions=%d severity=%s",
                    score, len(boxes), vision.get("severity", "?"))

        return jsonify({
            "success": True,
            # Numeric / pixel-level data (SSIM)
            "ssim": float(score),
            "boxes": boxes,
            "ssim_summary": ssim_summary,
            # Semantic / AI data (Gemini Vision)
            "semantic_summary": vision.get("semantic_summary", ""),
            "changed_elements": vision.get("changed_elements", []),
            "change_type": vision.get("change_type", "mixed"),
            "severity": vision.get("severity", "moderate"),
            # Unified summary for downstream use (e.g. generate-update)
            "summary": vision.get("semantic_summary", ssim_summary),
        }), 200

    except Exception as e:
        logger.error("detect-change failed: %s", str(e), exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/generate-update", methods=["POST"])
def generate_update():
    """
    Generate updated README content using Google Gemini AI.

    Expects JSON:
        {
            "change_summary": "description of changes detected",
            "current_readme": "current README content (optional)"
        }
    
    Returns:
        JSON with documentation text, confidence score (0-1), and reasoning.
    """
    try:
        data = request.get_json()

        if not data or 'change_summary' not in data:
            logger.warning("generate-update called without change_summary")
            return jsonify({"error": "change_summary is required"}), 400

        summary = data['change_summary']
        readme = data.get('current_readme', '')
        logger.info("Generating structured documentation via Gemini AI")

        # Returns documentation + confidence score + reasoning
        result = generate_documentation(summary, readme)

        logger.info(
            "Documentation generated: confidence=%.2f, %d chars",
            result.get("confidence", 0),
            len(result.get("documentation", "")),
        )
        return jsonify({
            "success": True,
            # Kept as new_text for backward compatibility with create-pr
            "new_text": result.get("documentation", ""),
            "documentation": result.get("documentation", ""),
            # Confidence + reasoning
            "confidence": result.get("confidence", 0.75),
            "reasoning": result.get("reasoning", ""),
            # RAG metadata
            "rag_headings": result.get("rag_headings", []),
            "rag_chunks_used": result.get("rag_chunks_used", 0),
        }), 200

    except Exception as e:
        logger.error("generate-update failed: %s", str(e), exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/create-pr", methods=["POST"])
def create_pr():
    """
    Create a GitHub PR with updated README and new image.

    Expects JSON:
        {
            "branch": "branch-name (optional)",
            "new_text": "updated README section text",
            "new_image_b64": "base64-encoded image (optional)",
            "image_path": "path/to/image.png (optional)",
            "readme_path": "README.md (optional)"
        }
    
    Returns:
        JSON with PR URL and details
    """
    try:
        data = request.get_json()

        if not data or 'new_text' not in data:
            logger.warning("create-pr called without new_text")
            return jsonify({"error": "new_text is required"}), 400

        # Generate branch name if not provided
        branch = data.get("branch", f"docu-sync/auto-{int(time.time())}")
        logger.info("Creating GitHub PR on branch: %s", branch)
        new_text = data["new_text"]
        new_image_b64 = data.get("new_image_b64")
        image_path = data.get("image_path", "docs/screenshot.png")
        readme_path = data.get("readme_path", "README.md")
        
        # Load GitHub repository
        repo = load_github()
        
        # Create new branch
        main_ref = repo.get_branch("main")
        try:
            repo.create_git_ref(ref=f"refs/heads/{branch}", sha=main_ref.commit.sha)
        except Exception:
            # Branch might already exist
            pass
        
        # Decode image if provided
        new_image_bytes = base64.b64decode(new_image_b64) if new_image_b64 else None
        
        # Update README and image
        if new_image_bytes:
            replace_image_and_update_markdown(
                repo, branch, new_image_bytes, new_text,
                image_path=image_path, readme_path=readme_path
            )
        else:
            # Update README only
            from updater import ensure_markers_exist, replace_between_markers
            readme_file = repo.get_contents(readme_path, ref=branch)
            current_readme = readme_file.decoded_content.decode('utf-8')
            
            markers_existed, readme_with_markers = ensure_markers_exist(current_readme)
            if not markers_existed:
                repo.update_file(
                    path=readme_path,
                    message="chore: add Docu-Sync markers",
                    content=readme_with_markers,
                    sha=readme_file.sha,
                    branch=branch
                )
                readme_file = repo.get_contents(readme_path, ref=branch)
                current_readme = readme_with_markers
            
            updated_readme = replace_between_markers(current_readme, new_text)
            repo.update_file(
                path=readme_path,
                message="docs: update README via Docu-Sync",
                content=updated_readme,
                sha=readme_file.sha,
                branch=branch
            )
        
        # Create pull request
        pr = repo.create_pull(
            title="docs: auto-update documentation via Docu-Sync",
            body=f"Automated documentation update by Docu-Sync.\n\n**Changes:**\n{new_text}",
            head=branch,
            base="main"
        )
        
        logger.info("PR #%d created: %s", pr.number, pr.html_url)
        return jsonify({
            "success": True,
            "pr_url": pr.html_url,
            "pr_number": pr.number,
            "branch": branch
        }), 200

    except Exception as e:
        logger.error("create-pr failed: %s", str(e), exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large errors."""
    return jsonify({"error": "File too large. Maximum size is 16MB"}), 413


if __name__ == "__main__":
    # For development only - use gunicorn in production
    logger.info("Starting Docu-Sync API on http://0.0.0.0:8080")
    app.run(host="0.0.0.0", port=8080, debug=True)
