"""Skills package for the workflow application."""

from pathlib import Path

script_dir = Path(__file__).parent

skills = [script_dir / skill for skill in [
    "consulting-analysis", "data-analysis", "github-deep-research", "skill-creator", "web-design-guidelines",
    "chart-visualization", "deep-research", "image-generation", "surprise-me", "find-skills",
    "podcast-generation", "frontend-design", "ppt-generation", "video-generation",
]]

__all__ = [
    "skills",
]