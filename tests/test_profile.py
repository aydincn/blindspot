from blindspot.resilience.profile import (
    PROFILE_DOC_ONLY,
    PROFILE_SINGLE_MAINTAINER,
    PROFILE_FOUNDER_LED,
    PROFILE_TEAM,
    PROFILE_MULTI_ORG,
    PROFILE_UNKNOWN,
    detect_profile,
)


def test_detect_doc_only_when_no_code_files():
    files = [f"docs/page_{i}.md" for i in range(50)] + ["README.md"]
    assert detect_profile(
        commit_count=100, author_count=5, files=files,
        services_count=2, top_author_coverage=0.3,
    ) == PROFILE_DOC_ONLY


def test_detect_single_maintainer_two_authors():
    files = [f"src/x_{i}.py" for i in range(30)]
    assert detect_profile(
        commit_count=200, author_count=2, files=files,
        services_count=4, top_author_coverage=0.8,
    ) == PROFILE_SINGLE_MAINTAINER


def test_detect_founder_led_dominant_author_small_team():
    files = [f"src/x_{i}.py" for i in range(80)]
    assert detect_profile(
        commit_count=500, author_count=12, files=files,
        services_count=5, top_author_coverage=0.65,
    ) == PROFILE_FOUNDER_LED


def test_detect_team_when_multiple_authors_no_dominator():
    files = [f"src/x_{i}.py" for i in range(60)]
    assert detect_profile(
        commit_count=400, author_count=10, files=files,
        services_count=4, top_author_coverage=0.25,
    ) == PROFILE_TEAM


def test_detect_multi_org_when_many_authors_many_services():
    files = [f"src/x_{i}.py" for i in range(500)]
    assert detect_profile(
        commit_count=10000, author_count=200, files=files,
        services_count=12, top_author_coverage=0.10,
    ) == PROFILE_MULTI_ORG


def test_detect_unknown_for_3_authors_no_clear_signal():
    files = [f"src/x_{i}.py" for i in range(20)]
    # 3 authors, no dominant — below team threshold (4)
    assert detect_profile(
        commit_count=50, author_count=3, files=files,
        services_count=2, top_author_coverage=0.40,
    ) == PROFILE_UNKNOWN
