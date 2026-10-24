import json
from pathlib import Path


def test_candidate_architecture_json_structure():
    candidate_path = Path(".archify/architecture-asas-overview/candidate.json")
    assert candidate_path.exists(), "candidate.json must exist in .archify/architecture-asas-overview/"
    
    with open(candidate_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data.get("schema_version") == 1
    assert data.get("diagram_type") == "architecture"
    meta = data.get("meta", {})
    assert "ASAS" in meta.get("title", "")
    assert meta.get("output") == "docs/diagrams/asas_architecture.html"
    
    components = {c["id"]: c for c in data.get("components", [])}
    # Verify core ASAS components
    required_ids = [
        "student",
        "playground",
        "supervisor",
        "tutor",
        "evaluator",
        "planner",
        "quiz_service",
        "flashcard_service",
        "sandbox",
        "search_guardrails",
        "nim_cloud",
        "memory_service",
        "users_db",
        "chats_db",
    ]
    for cid in required_ids:
        assert cid in components, f"Component {cid} must be defined in candidate.json"


def test_generated_html_diagram_exists_and_valid():
    html_path = Path("docs/diagrams/asas_architecture.html")
    assert html_path.exists(), "docs/diagrams/asas_architecture.html must be generated"
    
    content = html_path.read_text(encoding="utf-8")
    assert "<svg" in content
    assert "ASAS" in content
    assert "Trợ lý Điều phối" in content or "Supervisor" in content
    assert "users.db" in content
    assert "chats.db" in content
    assert "Sandbox" in content
