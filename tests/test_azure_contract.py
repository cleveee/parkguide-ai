"""No paid calls: verify mapping and safe failure at the provider boundary."""

import numpy as np
import pytest

from parkguide.azure import embed

APPROVED = {"endpoint": "https://example.invalid", "deployment": "test-model", "dimension": 2}


def configure(monkeypatch, payload, status=200):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.invalid")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "test-model")

    class Response:
        status_code = status

        def json(self):
            return payload

    def post(url, **kwargs):
        assert url == "https://example.invalid/openai/v1/embeddings"
        assert kwargs["allow_redirects"] is False
        assert kwargs["headers"]["api-key"] == "synthetic-test-key"
        assert kwargs["json"]["model"] == "test-model"
        assert kwargs["json"]["encoding_format"] == "float"
        return Response()

    from types import SimpleNamespace
    monkeypatch.setattr("parkguide.azure._session", lambda: SimpleNamespace(post=post))


def test_provider_order_is_restored_and_vectors_normalized(monkeypatch):
    configure(monkeypatch, {
        "model": "test-model",
        "data": [{"index": 1, "embedding": [0, 4]}, {"index": 0, "embedding": [3, 0]}],
        "usage": {"prompt_tokens": 2, "total_tokens": 2},
    })
    batch = embed(["first", "second"], expected_dimension=2, approved_config=APPROVED)
    np.testing.assert_allclose(batch.vectors, np.eye(2, dtype=np.float32))
    assert batch.vectors.dtype == np.float32


@pytest.mark.parametrize("rows", [
    [{"index": 0, "embedding": [1, 0]}],
    [{"index": 0, "embedding": [1, 0]}, {"index": 0, "embedding": [1, 0]}],
    [{"index": 0, "embedding": [float("nan"), 0]}, {"index": 1, "embedding": [1, 0]}],
    [{"index": 0, "embedding": [0, 0]}, {"index": 1, "embedding": [1, 0]}],
])
def test_partial_or_invalid_output_cannot_be_imported(monkeypatch, rows):
    configure(monkeypatch, {"model": "test-model", "data": rows})
    with pytest.raises(RuntimeError, match="schema/vector validation"):
        embed(["first", "second"], expected_dimension=2, approved_config=APPROVED)


def test_provider_error_body_is_not_exposed(monkeypatch):
    class SecretBearingBody:
        def __getitem__(self, key):
            raise AssertionError("HTTP failure bodies must not be inspected")

    configure(monkeypatch, SecretBearingBody(), status=401)
    with pytest.raises(RuntimeError) as error:
        embed(["first"], expected_dimension=2, approved_config=APPROVED)
    assert str(error.value) == "Azure embedding HTTP 401; response body not logged"


@pytest.mark.parametrize("name,value", [
    ("AZURE_OPENAI_ENDPOINT", "https://unapproved.invalid"),
    ("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "other-deployment"),
])
def test_configuration_mismatch_never_makes_a_request(monkeypatch, name, value):
    configure(monkeypatch, {})
    monkeypatch.setenv(name, value)

    def forbidden_request(*args, **kwargs):
        raise AssertionError("Unapproved target must not be called")

    from types import SimpleNamespace
    monkeypatch.setattr("parkguide.azure._session", lambda: SimpleNamespace(post=forbidden_request))
    with pytest.raises(RuntimeError, match="no request sent"):
        embed(["first"], expected_dimension=2, approved_config=APPROVED)


def test_generation_deployment_does_not_change_embedding_model_or_shared_credentials(monkeypatch):
    configure(monkeypatch, {"model": "test-model", "data": [{"index": 0, "embedding": [3, 0]}],
                           "usage": {"prompt_tokens": 2, "total_tokens": 2}})
    monkeypatch.setenv("AZURE_OPENAI_GENERATION_DEPLOYMENT", "gpt-6-luna")
    monkeypatch.setenv("OPENAI_API_KEY", "unused-direct-provider-key")
    batch = embed(["first"], expected_dimension=2, approved_config=APPROVED)
    assert batch.model == "test-model" and batch.usage == {"prompt_tokens": 2, "total_tokens": 2}


def test_missing_shared_azure_key_cannot_use_other_credentials(monkeypatch):
    configure(monkeypatch, {})
    monkeypatch.delenv("AZURE_OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "unused-direct-provider-key")
    monkeypatch.setenv("AZURE_OPENAI_GENERATION_API_KEY", "unused-other-generation-key")
    with pytest.raises(RuntimeError, match="configuration is incomplete"):
        embed(["first"], expected_dimension=2, approved_config=APPROVED)


def test_redirect_is_rejected_without_inspecting_or_following_its_body(monkeypatch):
    class ForbiddenBody:
        def __getitem__(self, key):
            raise AssertionError("A redirect cannot supply vectors or reveal its body")

    configure(monkeypatch, ForbiddenBody(), status=302)
    with pytest.raises(RuntimeError) as error:
        embed(["first"], expected_dimension=2, approved_config=APPROVED)
    assert str(error.value) == "Azure embedding HTTP 302; response body not logged"


def test_text_generation_response_model_cannot_be_imported_as_embedding_vectors(monkeypatch):
    configure(monkeypatch, {"model": "gpt-6-luna-2026-09-22", "data": [{"index": 0, "embedding": [3, 0]}]})
    with pytest.raises(RuntimeError, match="schema/vector validation"):
        embed(["first"], expected_dimension=2, approved_config=APPROVED)
