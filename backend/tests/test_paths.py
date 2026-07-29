from noname.paths import evaluation_results_dir, knowledge_file, resolve_project_root


def test_project_root_can_be_overridden_for_packaged_deployments(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("REPLAY_PROJECT_ROOT", str(tmp_path))

    assert resolve_project_root() == tmp_path.resolve()
    assert knowledge_file() == tmp_path.resolve() / "knowledge" / "reviewed" / "core.json"
    assert evaluation_results_dir() == tmp_path.resolve() / "evaluation" / "results"
