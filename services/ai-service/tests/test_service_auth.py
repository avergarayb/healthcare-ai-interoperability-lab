from __future__ import annotations

import hmac
from itertools import combinations

import pytest
from starlette.requests import Request

from app import service_auth
from app.config import Settings


TOKEN = "synthetic-model-boundary-token"
SECURITY_VARIABLES = (
    "MODEL_BOUNDARY_SERVICE_TOKEN",
    "HUMAN_REVIEW_FORM_SIGNING_SECRET",
    "HUMAN_REVIEW_DEVELOPMENT_AUTH_SECRET",
    "AI_FEDERATION_PARTICIPANT_TOKEN",
)


def _settings(token: str = TOKEN, **overrides) -> Settings:
    values = dict(
        model_boundary_base_url="http://java.test",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=5,
        model_boundary_service_token=token,
        host="127.0.0.1",
        port=8090,
        human_review_form_signing_secret="synthetic-form-signing-secret",
        human_review_development_auth_secret="synthetic-development-secret-32chars",
        federation_participant_token="synthetic-federation-participant-token",
    )
    values.update(overrides)
    return Settings(**values)


def _request(*values: str) -> Request:
    headers = [(b"x-service-token", value.encode("latin-1")) for value in values]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


@pytest.mark.parametrize(
    ("configured", "presented"),
    [
        (TOKEN, ()),
        (TOKEN, ("",)),
        (TOKEN, ("   ",)),
        (TOKEN, ("invalid-token",)),
        (TOKEN, ("tökén-inválido",)),
        (TOKEN, (f" {TOKEN} ",)),
        (TOKEN, (TOKEN, TOKEN)),
        ("", (TOKEN,)),
        ("   ", (TOKEN,)),
    ],
)
def test_service_auth_rejects_invalid_or_ambiguous_credentials(configured, presented):
    assert service_auth.authenticate(_request(*presented), _settings(configured)) is False


def test_service_auth_accepts_one_exact_token_with_constant_time_primitive(monkeypatch):
    original = hmac.compare_digest
    compared = []

    def capture(left, right):
        compared.append((left, right))
        return original(left, right)

    monkeypatch.setattr(service_auth.hmac, "compare_digest", capture)

    assert service_auth.authenticate(_request(TOKEN), _settings()) is True
    assert len(compared) == 1
    assert all(isinstance(value, bytes) and len(value) == 32 for value in compared[0])
    assert TOKEN.encode("utf-8") not in compared[0]


def test_settings_repr_omits_all_security_secrets():
    settings = _settings(
        token="model-secret-marker",
        human_review_form_signing_secret="form-secret-marker",
        human_review_development_auth_secret="development-secret-marker",
        federation_participant_token="federation-secret-marker",
        gemini_api_key="provider-secret-marker",
    )

    rendered = repr(settings)

    for marker in (
        "model-secret-marker",
        "form-secret-marker",
        "development-secret-marker",
        "federation-secret-marker",
        "provider-secret-marker",
    ):
        assert marker not in rendered


@pytest.mark.parametrize(("left_name", "right_name"), combinations(SECURITY_VARIABLES, 2))
def test_environment_rejects_every_reused_security_credential_pair_without_exposing_value(
    monkeypatch, left_name, right_name
):
    repeated = "reused-secret-value-must-not-escape"
    for index, name in enumerate(SECURITY_VARIABLES):
        monkeypatch.setenv(name, f"unique-security-secret-{index}")
    monkeypatch.setenv(left_name, repeated)
    monkeypatch.setenv(right_name, repeated)

    with pytest.raises(ValueError) as raised:
        Settings.from_env()

    message = str(raised.value)
    assert left_name in message
    assert right_name in message
    assert repeated not in message


def test_environment_accepts_absent_or_pairwise_distinct_security_credentials(monkeypatch):
    for name in SECURITY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    absent = Settings.from_env()
    assert all(
        value == ""
        for value in (
            absent.model_boundary_service_token,
            absent.human_review_form_signing_secret,
            absent.human_review_development_auth_secret,
            absent.federation_participant_token,
        )
    )

    for index, name in enumerate(SECURITY_VARIABLES):
        monkeypatch.setenv(name, f"distinct-security-secret-{index}")
    distinct = Settings.from_env()
    assert len(
        {
            distinct.model_boundary_service_token,
            distinct.human_review_form_signing_secret,
            distinct.human_review_development_auth_secret,
            distinct.federation_participant_token,
        }
    ) == len(SECURITY_VARIABLES)
