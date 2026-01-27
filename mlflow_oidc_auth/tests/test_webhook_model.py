import pytest
from pydantic import ValidationError

from mlflow_oidc_auth.models import WebhookCreateRequest, WebhookUpdateRequest

VALID_EVENT = ["registered_model.created"]


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "https://example.com/path?query=1#frag",
        "HTTPS://EXAMPLE.COM/UPPER",
        "https://example.com:8080/path",
    ],
)
def test_create_request_accepts_valid_https_urls(url):
    req = WebhookCreateRequest(name="n", url=url, events=VALID_EVENT)
    assert req.url == url


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",  # wrong scheme
        "https://",  # missing host
        "https://user:pass@example.com",  # credentials not allowed
        "https:// example.com",  # whitespace
        "",  # empty
        "ftp://example.com",  # wrong scheme
    ],
)
def test_create_request_rejects_invalid_urls(url):
    with pytest.raises(ValidationError):
        WebhookCreateRequest(name="n", url=url, events=VALID_EVENT)


def test_update_request_allows_none_but_validates_if_present():
    # None is allowed
    req = WebhookUpdateRequest(url=None)
    assert req.url is None

    # invalid url raises
    with pytest.raises(ValidationError):
        WebhookUpdateRequest(url="http://example.com")


def test_webhook_test_request_event_type_validation():
    # None allowed
    WebhookUpdateRequest(events=None)

    # Valid single event via the test request
    from mlflow_oidc_auth.models import WebhookTestRequest

    valid = WebhookTestRequest(event_type="registered_model.created")
    assert valid.event_type == "registered_model.created"

    # Invalid event
    with pytest.raises(ValidationError):
        WebhookTestRequest(event_type="invalid.event")

    # None is allowed
    req = WebhookTestRequest(event_type=None)
    assert req.event_type is None


def test_create_request_validates_events_and_status():
    # valid
    req = WebhookCreateRequest(name="n", url="https://example.com", events=["registered_model.created"], status="ACTIVE")
    assert req.status == "ACTIVE"

    # invalid event
    with pytest.raises(ValidationError):
        WebhookCreateRequest(name="n", url="https://example.com", events=["invalid.event"])

    # invalid status
    with pytest.raises(ValidationError):
        WebhookCreateRequest(name="n", url="https://example.com", events=["registered_model.created"], status="BAD")


def test_update_request_validates_events_and_status_when_present():
    # None allowed
    req = WebhookUpdateRequest(events=None, status=None)
    assert req.events is None and req.status is None

    with pytest.raises(ValidationError):
        WebhookUpdateRequest(events=[])
    with pytest.raises(ValidationError):
        WebhookUpdateRequest(status="BAD")
