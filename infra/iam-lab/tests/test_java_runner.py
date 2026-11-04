"""Offline harness safety checks, no Java/Keycloak/container operations."""
import json
from types import SimpleNamespace
import pytest
import lab
import verify_java_resource_server as runner


@pytest.mark.parametrize("status", [401, 200])
def test_duplicate_headers_are_really_separate_and_connection_closed(monkeypatch, status):
    headers, closed, results = [], [], []
    connection = SimpleNamespace(putrequest=lambda *_: None, putheader=lambda *args: headers.append(args),
        endheaders=lambda: None, getresponse=lambda: SimpleNamespace(status=status, read=lambda _: b""),
        close=lambda: closed.append(True))
    monkeypatch.setattr(runner.http_client, "HTTPConnection", lambda *args, **kwargs: connection)
    if status == 401:
        runner.check_duplicate(18397, "synthetic-token", results)
        assert results[0]["http_status"] == 401
    else:
        with pytest.raises(lab.Denied):
            runner.check_duplicate(18397, "synthetic-token", results)
        assert not results
    assert headers == [("Authorization", "Bearer synthetic-token")] * 2
    assert closed == [True]
    assert "synthetic-token" not in json.dumps(results)


def test_default_start_drops_inherited_application_credentials_and_iam_flag(tmp_path, monkeypatch):
    observed = {}
    monkeypatch.setenv("IAM_JAVA_WORKLOAD_LAB_ENABLED", "true")
    monkeypatch.setenv("MODEL_BOUNDARY_SERVICE_TOKEN", "synthetic-inherited-secret")
    monkeypatch.setenv("JAVA_TOOL_OPTIONS", "synthetic-not-inherited")
    monkeypatch.setattr(lab, "free_port", lambda *_: None)
    process = SimpleNamespace(poll=lambda: None, terminate=lambda: None, wait=lambda **_: None)
    def spawn(arguments, **kwargs):
        observed.update(arguments=arguments, **kwargs)
        return process
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_): pass
    monkeypatch.setattr(runner.subprocess, "Popen", spawn)
    monkeypatch.setattr(runner.urllib.request, "build_opener", lambda *_: SimpleNamespace(open=lambda *args, **kwargs: Response()))
    child, log, _ = runner.start(tmp_path, "disabled", 18396)
    try:
        assert "IAM_JAVA_WORKLOAD_LAB_ENABLED" not in observed["env"]
        assert "MODEL_BOUNDARY_SERVICE_TOKEN" not in observed["env"]
        assert "JAVA_TOOL_OPTIONS" not in observed["env"]
        assert not any(arg.endswith("enabled=true") for arg in observed["arguments"])
        assert observed["cwd"].resolve().parent == tmp_path.resolve()
        assert all("synthetic-inherited-secret" not in arg for arg in observed["arguments"])
    finally:
        runner.stop(child, log)


def test_context_projection_check_does_not_accept_raw_external_identity():
    class Response:
        status = 200
        def read(self, _): return b'{"external_subject":"synthetic"}'
        def __enter__(self): return self
        def __exit__(self, *_): pass
    with pytest.raises(lab.Denied, match="unexpected_Java_context"):
        runner.check(SimpleNamespace(open=lambda *args, **kwargs: Response()), 18397, "test", 200, [], token="synthetic-token")
