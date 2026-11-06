from contracts import SCHEMA_VERSION, Verdict


def test_schema_version_is_semver() -> None:
    assert len(SCHEMA_VERSION.split(".")) == 3


def test_verdict_values() -> None:
    assert {v.value for v in Verdict} == {"ALLOWED", "BLOCKED", "NEEDS_REVIEW"}
