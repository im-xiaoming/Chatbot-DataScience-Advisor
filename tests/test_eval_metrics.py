from eval.metrics import hit_at_k, mrr, recall_at_k


def test_metrics():
    gold, got = {"b", "x"}, ["a", "b", "c"]
    assert hit_at_k(gold, got, 1) == 0 and hit_at_k(gold, got, 2) == 1
    assert recall_at_k(gold, got, 3) == 0.5
    assert mrr(gold, got) == 0.5
