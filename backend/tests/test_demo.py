from noname.demo import list_demo_scenarios


def test_demo_scenarios_are_fictional_and_include_readiness_path() -> None:
    payload = list_demo_scenarios()
    sleep_demo = next(item for item in payload.scenarios if item.id == "sleep-belonging")
    safety_demo = next(item for item in payload.scenarios if item.id == "safety-routing")

    assert len(payload.scenarios) == 5
    assert sleep_demo.messages[2] == "1"
    assert "READINESS_RULER" in sleep_demo.reviewer_highlights
    assert safety_demo.high_risk is True
    assert "虚构" in payload.notice
