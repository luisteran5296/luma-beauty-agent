from scripts.cost_estimate import estimate


def test_estimate_repeated_tokens_and_compute():
    small = estimate(100)
    assert small['model_usd'] == 2.15
    assert small['runtime_usd'] == 0
    assert estimate(100,free_tier=False)['runtime_usd'] == .3361
    assert estimate(10000)['runtime_usd'] > 0
