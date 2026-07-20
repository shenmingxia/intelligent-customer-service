from app.services.llm import LlmService


class FailingResponses:
    def create(self, **kwargs):
        raise TimeoutError("timed out")


class FailingClient:
    responses = FailingResponses()


def test_llm_service_returns_none_when_provider_times_out():
    service = LlmService(model="test-model")
    service.enabled = True
    service._client = FailingClient()

    result = service.generate_reply(message="hello", context={}, history=[])

    assert result is None
