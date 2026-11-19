from types import SimpleNamespace
from weizhcode.compact.estimator import TokenEstimator, projected_tokens
from weizhcode.providers.request import prepare_body, RequestOptions
from weizhcode.models import TokenUsage


def test_ctx_t38_ctx_t39_actual_body_and_anchor_invalidation():
    runtime = SimpleNamespace(anchor=None, context_window=128000)
    estimator = TokenEstimator(runtime)
    def request(text, tools=()):
        return prepare_body({'messages': [{'content': text}], 'tools': tools, 'max_tokens': 4096},
                            protocol='qwen', options=RequestOptions())
    first = request('abc')
    assert estimator.estimate(first) == projected_tokens(first)
    assert estimator.observe(first, TokenUsage(100, 20, True), completed=True)
    assert estimator.estimate(first) == 120
    changed = request('xyz')
    previous_anchor = runtime.anchor
    assert estimator.estimate(changed, invalidate=False) == projected_tokens(changed)
    assert runtime.anchor is previous_anchor
    assert estimator.estimate(changed) == projected_tokens(changed)
    changed = request('abc', [{'name': 'a', 'schema': 'x'*1000}])
    assert estimator.estimate(changed) == projected_tokens(changed) > projected_tokens(first)
    for value in (200, 300, 400):
        assert estimator.observe(first, TokenUsage(value, 20, True), completed=True)
        assert estimator.estimate(first) == value + 20
    assert not estimator.observe(first, TokenUsage(10, None, False), completed=False)
    assert runtime.anchor is None
