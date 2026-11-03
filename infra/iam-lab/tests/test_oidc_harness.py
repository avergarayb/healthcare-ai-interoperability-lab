"""Offline B (synthetic JWT) and C (trusted policy) cases. Never starts Docker."""
import json
import time
from urllib.parse import urlencode

import pytest

jwt = pytest.importorskip("jwt")
rsa = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.rsa")
import oidc_harness as h
from lab import ROOT, read

POLICY = read(ROOT / "policy.json")
ISSUER = "http://localhost:18090/realms/healthcare-iam-lab"


@pytest.fixture(scope="module")
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def trust(key):
    return h.Trust(ISSUER, {"fixture-key": key.public_key()})


def claims(**changes):
    now = int(time.time())
    result = dict(iss=ISSUER, sub=POLICY["workloads"]["lab-ai-workload"]["subject"],
                  aud=h.AI, iat=now, exp=now + 30, jti="synthetic-jti", azp="lab-ai-workload", typ="Bearer")
    result.update(changes)
    return result


def signed(key, **changes):
    return jwt.encode(claims(**changes), key, algorithm="RS256", headers={"kid": "fixture-key"})


def test_distinct_workload_profiles(key, trust):
    assert trust.access(signed(key), h.AI, POLICY)["principal"] == "fixture-ai-workload"
    binding = POLICY["workloads"]["lab-python-to-java"]
    assert trust.access(signed(key, sub=binding["subject"], aud=h.INTEROP, azp="lab-python-to-java"), h.INTEROP, POLICY) == binding


@pytest.mark.parametrize("changes,reason", [
    ({"iss": ISSUER + "-wrong"}, "issuer_mismatch"),
    ({"aud": h.INTEROP}, "audience_mismatch"),
    ({"exp": int(time.time()) - 5, "iat": int(time.time()) - 40}, "token_expired"),
    ({"iat": int(time.time()) + 60, "exp": int(time.time()) + 90}, "token_invalid"),
    ({"nbf": int(time.time()) + 60}, "token_invalid"),
    ({"exp": int(time.time()) + 600}, "token_lifetime_not_allowed"),
    ({"typ": "ID"}, "access_token_required"),
    ({"azp": "lab-unregistered-workload"}, "workload_unknown"),
    ({"sub": "different-subject"}, "workload_binding_mismatch"),
    ({"aud": [h.AI, h.INTEROP]}, "excess_audience"),
    ({"jti": None}, "token_invalid"),
    ({"iat": True}, "invalid_token_time"),
    ({"azp": ["lab-ai-workload"]}, "workload_unknown"),
])
def test_signed_negative_vectors(key, trust, changes, reason):
    with pytest.raises(h.Denied, match="^" + reason + "$"):
        trust.access(signed(key, **changes), h.AI, POLICY)


@pytest.mark.parametrize("claim", ["iss", "sub", "aud", "exp", "iat", "jti", "azp", "typ"])
def test_missing_required_claim(key, trust, claim):
    payload = claims()
    del payload[claim]
    token = jwt.encode(payload, key, algorithm="RS256", headers={"kid": "fixture-key"})
    with pytest.raises(h.Denied):
        trust.access(token, h.AI, POLICY)


def test_id_token_cannot_be_used_as_api_even_with_added_api_audience(key, trust):
    token = signed(key, typ="ID", aud=[h.WEB, h.AI], nonce="fixture-nonce")
    with pytest.raises(h.Denied, match="access_token_required"):
        trust.access(token, h.AI, POLICY)


def test_id_token_rejections_keep_original_token_and_separate_purpose_from_audience(key, trust):
    from lab import id_token_api_rejections
    payload = claims(typ="ID", sub="00000000-0000-4000-8000-000000000101",
                     aud=h.WEB, nonce="offline-nonce")
    # ID tokens need not have workload-only claims for either control to reject.
    del payload["jti"]
    del payload["azp"]
    token = jwt.encode(payload, key, algorithm="RS256", headers={"kid": "fixture-key"})
    assert trust.identity(token, "offline-nonce", POLICY)["principal"] == "fixture-human-a"
    original = token
    results = id_token_api_rejections(trust, token, POLICY)
    assert token == original
    assert set(results) == {h.AI, h.INTEROP}
    for result in results.values():
        assert result["profile_reason"] == "audience_mismatch"
        assert result["independent_purpose_check"] == "DENIED: access_token_required"


def test_purpose_gate_is_shared_by_access_profile(key, trust, monkeypatch):
    calls = []
    original = h.require_access_purpose
    def purpose(verified):
        calls.append(verified["typ"])
        original(verified)
    monkeypatch.setattr(h, "require_access_purpose", purpose)
    assert trust.access(signed(key), h.AI, POLICY)
    with pytest.raises(h.Denied, match="access_token_required"):
        trust.access(signed(key, typ="ID"), h.AI, POLICY)
    assert calls == ["Bearer", "ID"]


@pytest.mark.parametrize("hosts", [[], ["localhost:18190"], ["127.0.0.1:18191"],
                                   ["127.0.0.1:18190", "127.0.0.1:18190"]])
def test_callback_host_rejects_alias_wrong_port_and_ambiguity(hosts):
    from email.message import Message
    headers = Message()
    for value in hosts:
        headers["Host"] = value
    with pytest.raises(h.Denied, match="invalid_callback_host"):
        h.callback_host(headers, 18190)


def test_callback_host_accepts_only_exact_loopback_host():
    from email.message import Message
    headers = Message()
    headers["Host"] = "127.0.0.1:18190"
    h.callback_host(headers, 18190)


def test_signature_mismatch(trust):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(h.Denied, match="token_invalid"):
        trust.access(signed(other), h.AI, POLICY)


@pytest.mark.parametrize("header,reason", [
    ({"kid": "unknown"}, "unknown_key_id"),
    ({"jku": "https://untrusted.invalid/keys"}, "token_key_source_not_allowed"),
    ({"jwk": {}}, "token_key_source_not_allowed"),
    ({"typ": "unexpected"}, "header_type_not_allowed"),
])
def test_header_restrictions(key, trust, header, reason):
    token = jwt.encode(claims(), key, algorithm="RS256", headers={"kid": "fixture-key", **header})
    with pytest.raises(h.Denied, match=reason):
        trust.access(token, h.AI, POLICY)


def test_algorithm_confusion(trust):
    token = jwt.encode(claims(), "synthetic-test-only-key-of-adequate-length", algorithm="HS256", headers={"kid": "fixture-key"})
    with pytest.raises(h.Denied, match="algorithm_not_allowed"):
        trust.access(token, h.AI, POLICY)


def test_duplicate_claim_rejected_before_decision(trust):
    header = jwt.utils.base64url_encode(b'{"alg":"RS256","typ":"JWT","kid":"fixture-key"}').decode()
    payload = jwt.utils.base64url_encode(b'{"sub":"one","sub":"two"}').decode()
    with pytest.raises(h.Denied, match="duplicate_json_claim"):
        trust.access(header + "." + payload + ".AA", h.AI, POLICY)


@pytest.mark.parametrize("token", ["", "a.b", "a.b.c.d", "A" * 17000, "e30.e30.AA"])
def test_invalid_shapes(trust, token):
    with pytest.raises(h.Denied):
        trust.access(token, h.AI, POLICY)


def test_exact_discovery_and_jwks(key):
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    public.update(kid="fixture-key", alg="RS256", use="sig", key_ops=["verify"])

    class Fake:
        origin = "http://localhost:18090"
        calls = []

        def request(self, url):
            self.calls.append(url)
            if url.endswith("openid-configuration"):
                return {"issuer": ISSUER, "jwks_uri": ISSUER + "/protocol/openid-connect/certs",
                        "token_endpoint": ISSUER + "/protocol/openid-connect/token",
                        "authorization_endpoint": ISSUER + "/protocol/openid-connect/auth"}
            return {"keys": [public]}

    fake = Fake()
    assert h.Trust.load(fake).keys["fixture-key"].key_size == 2048
    public["d"] = "never-accept-private-material"
    with pytest.raises(h.Denied, match="untrusted_key_material"):
        h.Trust.load(fake)


@pytest.mark.parametrize("field", ["issuer", "jwks_uri", "token_endpoint", "authorization_endpoint"])
def test_discovery_mismatch_never_fetches_untrusted_url(field):
    class Fake:
        origin = "http://localhost:18090"
        calls = 0

        def request(self, url):
            self.calls += 1
            assert self.calls == 1
            metadata = {"issuer": ISSUER, "jwks_uri": ISSUER + "/protocol/openid-connect/certs",
                        "token_endpoint": ISSUER + "/protocol/openid-connect/token",
                        "authorization_endpoint": ISSUER + "/protocol/openid-connect/auth"}
            metadata[field] = "http://169.254.169.254/untrusted"
            return metadata

    with pytest.raises(h.Denied, match="discovery_mismatch"):
        h.Trust.load(Fake())


@pytest.mark.parametrize("url", ["http://localhost:8080", "http://127.0.0.1:18090", "https://localhost:18090", "http://localhost:18090/path"])
def test_origin_is_pinned(url):
    with pytest.raises(h.Denied):
        h.Http(url)


def test_endpoint_allowlist_and_redirect_denial():
    http = h.Http("http://localhost:18090")
    with pytest.raises(h.Denied, match="endpoint_not_approved"):
        http.request("http://localhost:18090/admin/realms")
    assert h.NoRedirect().redirect_request(None, None, 302, "", {}, "http://untrusted.invalid") is None


def test_membership_selection_and_no_union():
    both = POLICY["humans"]["00000000-0000-4000-8000-000000000103"]
    with pytest.raises(h.Denied, match="organization_selection_required"):
        h.authorize(both, None, [])
    with pytest.raises(h.Denied, match="permission_not_granted"):
        h.authorize(both, "org-lab-a", ["fixture.interop.read"])
    assert h.authorize(both, "org-lab-b", ["fixture.interop.read"])["permissions"] == ["fixture.interop.read"]
    for suffix, org in (("101", "org-lab-b"), ("102", "org-lab-a"), ("104", "org-lab-a")):
        with pytest.raises(h.Denied, match="organization_not_authorized"):
            h.authorize(POLICY["humans"]["00000000-0000-4000-8000-000000000" + suffix], org, [])


def test_identity_nonce_and_human_binding(key, trust):
    human = "00000000-0000-4000-8000-000000000101"
    token = signed(key, typ="ID", sub=human, aud=h.WEB, azp=h.WEB, nonce="expected-nonce")
    assert trust.identity(token, "expected-nonce", POLICY) == POLICY["humans"][human]
    with pytest.raises(h.Denied, match="id_token_binding_mismatch"):
        trust.identity(token, "wrong-nonce", POLICY)
    with pytest.raises(h.Denied, match="human_unknown"):
        trust.identity(signed(key, typ="ID", aud=h.WEB, azp=h.WEB, nonce="n"), "n", POLICY)
    with pytest.raises(h.Denied, match="id_token_binding_mismatch"):
        trust.identity(signed(key, typ="ID", aud=h.WEB, azp=h.WEB, nonce=["n"]), "n", POLICY)


def test_pkce_callback_transaction_and_replay():
    transaction = h.pkce_transaction(ISSUER, "http://127.0.0.1:18190/callback")
    assert len(transaction["verifier"]) >= 43
    assert transaction["challenge"] != transaction["verifier"]
    path = "/callback?" + urlencode({"state": transaction["state"], "iss": ISSUER, "code": "synthetic-code"})
    assert h.callback_code(path, transaction) == "synthetic-code"
    with pytest.raises(h.Denied, match="callback_expired_or_used"):
        h.callback_code(path, transaction)


@pytest.mark.parametrize("failure", ["state", "issuer", "duplicate", "timeout", "path", "absolute", "unicode"])
def test_callback_failures(failure):
    transaction = h.pkce_transaction(ISSUER, "http://127.0.0.1:18190/callback")
    query = {"state": transaction["state"], "iss": ISSUER, "code": "synthetic-code"}
    if failure == "state":
        query["state"] = "wrong"
    if failure == "unicode":
        query["state"] = "\u00f1"
    if failure == "issuer":
        query["iss"] += "wrong"
    if failure == "timeout":
        transaction["deadline"] = 0
    path = ("/wrong" if failure == "path" else "/callback") + "?" + urlencode(query)
    if failure == "duplicate":
        path += "&code=second-code"
    if failure == "absolute":
        path = "http://untrusted.invalid" + path
    with pytest.raises(h.Denied):
        h.callback_code(path, transaction)
