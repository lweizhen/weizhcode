from dataclasses import replace
import pytest

from weizhcode.models import CacheCounterTotals, TokenUsage, UsageCounter, UsageTotals
from weizhcode.providers.base import UsageAccumulator, merge_usage_snapshot


@pytest.mark.parametrize("value", [True, -1, "2", 1.5])
def test_contract_bad_cache_counts(value):
    with pytest.raises(ValueError):
        UsageCounter(value, "reported")


def test_contract_zero_missing_and_not_applicable():
    assert UsageCounter(0, "reported") != UsageCounter()
    assert UsageCounter(None, "not_applicable").value is None
    with pytest.raises(ValueError):
        UsageCounter(0, "missing")
    assert TokenUsage(1, 2, True, "test").cache_read == UsageCounter()


def test_anthropic_cache_total_and_missing():
    acc = UsageAccumulator("anthropic")
    acc.update({"input_tokens": 100, "output_tokens": 0, "cache_read_input_tokens": 20,
                "cache_creation_input_tokens": 30})
    acc.update({"output_tokens": 4})
    result = acc.snapshot(complete=True)
    assert result.input_tokens == 150 and result.uncached_input_tokens == 100
    assert result.cache_read.value == 20 and result.cache_write.value == 30 and result.complete
    acc = UsageAccumulator("anthropic")
    acc.update({"input_tokens": 0, "output_tokens": 0})
    assert acc.snapshot(complete=True).input_tokens is None
    assert acc.snapshot().cache_read.availability == "missing"
    acc.update({"cache_read_input_tokens": 0, "cache_creation_input_tokens": 0})
    assert acc.snapshot(complete=True).input_tokens == 0
    assert acc.snapshot(complete=True).complete


@pytest.mark.parametrize("protocol", ["openai", "qwen"])
def test_openai_qwen_inclusive_totals(protocol):
    acc = UsageAccumulator(protocol)
    if protocol == "openai":
        acc.update({"input_tokens": 150, "output_tokens": 4,
                    "input_tokens_details": {"cached_tokens": 30, "cache_write_tokens": 20}})
    else:
        acc.update({"prompt_tokens": 150, "completion_tokens": 4,
                    "prompt_tokens_details": {"cached_tokens": 30}})
    acc.update({})
    result = acc.snapshot(complete=True)
    assert result.input_tokens == 150 and result.cache_read.value == 30 and result.complete
    assert result.cache_write.value == (20 if protocol == "openai" else None)


@pytest.mark.parametrize("bad", [None, True, -1, "4", 1.5])
def test_openai_invalid_preserves_trusted_values(bad):
    acc = UsageAccumulator("openai")
    acc.update({"input_tokens": 100, "output_tokens": 2, "input_tokens_details": {"cached_tokens": 5}})
    acc.update({"input_tokens_details": {"cached_tokens": bad}})
    acc.update({"input_tokens_details": {"cached_tokens": 4}})
    result = acc.snapshot(complete=True)
    assert result.input_tokens == 100 and result.cache_read.value == 5
    assert result.cache_read.invalid and not result.complete


def test_openai_details_invalid_and_conflicting_final_only():
    acc = UsageAccumulator("openai")
    acc.update({"input_tokens": 1, "output_tokens": 1, "input_tokens_details": {"cached_tokens": 10}})
    assert not acc.snapshot().cache_read.invalid
    acc.update({"input_tokens": 15})
    assert acc.snapshot(complete=True).complete
    acc.update({"input_tokens_details": {"cache_write_tokens": 10}})
    assert acc.snapshot(complete=True).cache_write.invalid
    acc = UsageAccumulator("qwen")
    acc.update({"prompt_tokens_details": None})
    assert acc.snapshot().cache_read.invalid


def test_merge_keeps_fields_and_invalid_sticky():
    old = TokenUsage(100, 2, False, "openai", UsageCounter(20, "reported"),
                     UsageCounter(None, "not_applicable"))
    new = TokenUsage(100, 4, True, "openai", UsageCounter(10, "reported"))
    merged = merge_usage_snapshot(old, new)
    assert merged.cache_read.value == 20 and merged.cache_read.invalid
    assert merged.cache_write.availability == "not_applicable" and not merged.complete
    final = merge_usage_snapshot(merged, TokenUsage(100, 5, True, "openai", UsageCounter(30, "reported")))
    assert final.cache_read.invalid and not final.complete
    assert merge_usage_snapshot(old, TokenUsage(90, 4, True)).input_tokens == 100


def test_totals_coverage_no_double_add():
    totals = UsageTotals()
    samples = [TokenUsage(150, 4, True, "openai", UsageCounter(30, "reported")),
               TokenUsage(0, 0, True, "openai", UsageCounter(0, "reported")),
               TokenUsage(), TokenUsage(cache_read=UsageCounter(None, "not_applicable")),
               TokenUsage(cache_read=UsageCounter(5, "reported", True))]
    for sample in samples:
        totals = totals.add(sample)
    assert totals.input_tokens == 150 and totals.request_count == 5
    assert totals.cache_read == CacheCounterTotals(35, 3, 1, 1)
    assert totals.request_count - totals.cache_read.reported_requests - totals.cache_read.not_applicable_requests == 1
