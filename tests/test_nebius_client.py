import unittest

from creature_forge.nebius import BudgetExceeded, Limits, NebiusClient, NebiusError

SECRET = "sk-test-SECRET-123"


def ok_response(content="hi", total=30, **msg):
    return {"model": "m", "choices": [{"message": {"content": content, **msg}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": total - 10, "total_tokens": total}}


class FakeTransport:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, body, timeout))
        if self.error:
            raise self.error
        return 200, {"x-request-id": "rid1"}, self.response


def client(transport, **limits):
    return NebiusClient(transport=transport, api_key=SECRET, base_url="https://example.test/v1", limits=Limits(**limits))


class ClientTests(unittest.TestCase):
    def test_request_shape_and_result(self):
        t = FakeTransport(ok_response())
        r = client(t).chat([{"role": "user", "content": "x"}], max_tokens=50, reasoning_effort="low")
        url, headers, body, timeout = t.calls[0]
        self.assertEqual(url, "https://example.test/v1/chat/completions")
        self.assertEqual((body["max_tokens"], body["reasoning_effort"]), (50, "low"))
        self.assertEqual(timeout, 60.0)
        self.assertEqual((r.content, r.request_id, r.usage["total_tokens"]), ("hi", "rid1", 30))

    def test_reasoning_effort_omitted_when_unset(self):
        t = FakeTransport(ok_response())
        client(t).chat([], max_tokens=10)
        self.assertNotIn("reasoning_effort", t.calls[0][2])

    def test_key_never_in_repr_or_logs(self):
        c = client(FakeTransport(ok_response()))
        c.chat([{"role": "user", "content": "x"}])
        self.assertNotIn(SECRET, repr(c))
        self.assertNotIn(SECRET, str(c.calls))

    def test_no_retry_on_error_and_error_costs_a_request(self):
        t = FakeTransport(error=NebiusError("HTTP 500: boom"))
        c = client(t)
        with self.assertRaises(NebiusError):
            c.chat([{"role": "user", "content": "x"}])
        self.assertEqual(len(t.calls), 1)
        self.assertEqual(c.requests_made, 1)
        self.assertFalse(c.calls[0]["ok"])

    def test_request_limit_blocks_before_network(self):
        t = FakeTransport(ok_response())
        c = client(t, max_requests=1)
        c.chat([{"role": "user", "content": "x"}])
        with self.assertRaises(BudgetExceeded):
            c.chat([{"role": "user", "content": "x"}])
        self.assertEqual(len(t.calls), 1)

    def test_token_budget_blocks_before_network(self):
        t = FakeTransport(ok_response(total=900))
        c = client(t, max_total_tokens=1000)
        c.chat([{"role": "user", "content": "x"}], max_tokens=100)
        with self.assertRaises(BudgetExceeded):
            c.chat([{"role": "user", "content": "x"}], max_tokens=200)
        self.assertEqual(len(t.calls), 1)

    def test_per_request_cap_and_bad_reasoning_value(self):
        c = client(FakeTransport(ok_response()), max_tokens_per_request=100)
        with self.assertRaises(BudgetExceeded):
            c.chat([], max_tokens=101)
        with self.assertRaises(ValueError):
            c.chat([], max_tokens=10, reasoning_effort="turbo")
        self.assertEqual(c.requests_made, 0)

    def test_null_content_is_reported_not_hidden(self):
        r = client(FakeTransport(ok_response(content=None, reasoning_content="thinking"))).chat([], max_tokens=10)
        self.assertIsNone(r.content)
        self.assertTrue(r.reasoning_present)

    def test_malformed_response_raises(self):
        with self.assertRaises(NebiusError):
            client(FakeTransport({"nope": 1})).chat([], max_tokens=10)

    def test_missing_key_raises_without_network(self):
        t = FakeTransport(ok_response())
        c = NebiusClient(transport=t, api_key="")
        with self.assertRaises(NebiusError):
            c.chat([], max_tokens=10)
        self.assertEqual(t.calls, [])


if __name__ == "__main__":
    unittest.main()
