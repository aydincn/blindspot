from blindspot.risk_models.ai_readiness import AIReadinessEngine


def test_repo_level_detects_agent_rules():
    files = ["CLAUDE.md", "src/main.py", "src/util.py"]
    report = AIReadinessEngine().detect(files)
    assert report.repo.agent_rules is True
    assert report.repo.specs is False


def test_repo_level_detects_cursor_rules():
    files = [".cursor/rules", "src/main.py"]
    report = AIReadinessEngine().detect(files)
    assert report.repo.agent_rules is True


def test_repo_level_detects_copilot_instructions():
    files = [".github/copilot-instructions.md", "src/main.py"]
    report = AIReadinessEngine().detect(files)
    assert report.repo.agent_rules is True


def test_repo_level_detects_specs_and_prompts():
    files = ["specs/v1.md", "prompts/release.md", "src/main.py"]
    report = AIReadinessEngine().detect(files)
    assert report.repo.specs is True
    assert report.repo.prompts is True


def test_repo_level_detects_architecture_in_docs():
    files = ["docs/architecture/overview.md", "src/main.py"]
    report = AIReadinessEngine().detect(files)
    assert report.repo.architecture is True


def test_repo_level_detects_adr_dir():
    files = ["adr/0001-decisions.md", "src/main.py"]
    report = AIReadinessEngine().detect(files)
    assert report.repo.architecture is True


def test_per_service_independent_of_repo_root():
    # service "api" has its own CLAUDE.md, service "web" does not.
    files = [
        "api/CLAUDE.md",
        "api/src/handler.py",
        "web/src/page.tsx",
    ]
    report = AIReadinessEngine().detect(files)
    by_target = {s.target: s for s in report.services}
    assert by_target["api"].agent_rules is True
    assert by_target["web"].agent_rules is False


def test_coverage_ratio_uses_five_categories():
    files = ["CLAUDE.md", "specs/v1.md", "prompts/a.md", "src/main.py"]
    report = AIReadinessEngine().detect(files)
    # 3 of 5 categories matched at repo level.
    assert report.repo.coverage_count == 3
    assert abs(report.repo.coverage_ratio - 0.6) < 1e-6


def test_empty_repo_has_zero_coverage():
    report = AIReadinessEngine().detect([])
    assert report.repo.coverage_count == 0
    assert report.repo.coverage_ratio == 0.0
    assert report.services == ()


def test_config_dotfile_dirs_not_treated_as_services():
    files = [".husky/pre-commit", "src/main.py"]
    report = AIReadinessEngine().detect(files)
    # Service list does not include "(config)" pseudo-services.
    assert all(not s.target.startswith("(") for s in report.services)
