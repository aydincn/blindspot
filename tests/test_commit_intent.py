from blindspot.diff_analysis.commit_intent import CommitIntent, classify_commit


def test_conventional_fix_prefix():
    assert classify_commit("fix: handle empty queue") == CommitIntent.FIX
    assert classify_commit("fix(parser): off-by-one") == CommitIntent.FIX
    assert classify_commit("hotfix: prod outage") == CommitIntent.FIX


def test_conventional_feat_prefix():
    assert classify_commit("feat: add export") == CommitIntent.FEATURE
    assert classify_commit("feat(api): bulk endpoint") == CommitIntent.FEATURE


def test_conventional_revert_prefix():
    assert classify_commit("revert: rollback flaky migration") == CommitIntent.REVERT


def test_conventional_other_types_map_to_other():
    assert classify_commit("chore: bump deps") == CommitIntent.OTHER
    assert classify_commit("docs: update README") == CommitIntent.OTHER
    assert classify_commit("refactor: extract helper") == CommitIntent.OTHER
    assert classify_commit("test: add coverage") == CommitIntent.OTHER


def test_git_auto_generated_revert():
    assert classify_commit('Revert "feat: half-finished thing"') == CommitIntent.REVERT


def test_keyword_fix_en():
    assert classify_commit("Fix crash on startup") == CommitIntent.FIX
    assert classify_commit("Bug in date parsing") == CommitIntent.FIX
    assert classify_commit("Typo in error message") == CommitIntent.FIX


def test_keyword_fix_tr():
    assert classify_commit("Hata düzeltildi") == CommitIntent.FIX
    assert classify_commit("Yazım hatası giderildi") == CommitIntent.FIX
    assert classify_commit("Login sorunu gider") == CommitIntent.FIX


def test_no_substring_match_for_fix():
    # "infix" or "prefix" must not match "fix" via substring.
    assert classify_commit("Add infix operator support") == CommitIntent.FEATURE
    assert classify_commit("Refactor prefix logic") == CommitIntent.OTHER


def test_empty_message_is_other():
    assert classify_commit("") == CommitIntent.OTHER
    assert classify_commit("   ") == CommitIntent.OTHER


def test_unknown_subject_defaults_to_other():
    assert classify_commit("WIP") == CommitIntent.OTHER
    assert classify_commit("merge upstream") == CommitIntent.OTHER
