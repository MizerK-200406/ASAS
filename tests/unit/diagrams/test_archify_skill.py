"""Unit tests verifying the installation and structure of the Archify skill."""

import os
import re
from pathlib import Path
import pytest


def test_archify_skill_structure_and_frontmatter():
    """Kiểm tra tệp SKILL.md của archify tồn tại và có frontmatter chuẩn Antigravity."""
    repo_root = Path(__file__).resolve().parents[3]
    skill_dir = repo_root / ".agents" / "skills" / "archify"
    skill_md = skill_dir / "SKILL.md"

    assert skill_dir.is_dir(), f"Thư mục skill không tồn tại: {skill_dir}"
    assert skill_md.is_file(), f"Tệp SKILL.md không tồn tại: {skill_md}"

    content = skill_md.read_text(encoding="utf-8")
    
    # Kiểm tra YAML frontmatter
    assert content.startswith("---"), "SKILL.md phải bắt đầu bằng YAML frontmatter '---'"
    match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    assert match is not None, "Không tìm thấy khối YAML frontmatter hợp lệ"

    frontmatter = match.group(1)
    assert "name: archify" in frontmatter, "Frontmatter phải chứa 'name: archify'"
    assert "description:" in frontmatter, "Frontmatter phải chứa 'description:'"

    # Kiểm tra các thư mục tham chiếu cần thiết
    assert (skill_dir / "references").is_dir(), "Thiếu thư mục references trong archify skill"
    assert (skill_dir / "schemas").is_dir(), "Thiếu thư mục schemas trong archify skill"
