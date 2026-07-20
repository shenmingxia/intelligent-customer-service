from pathlib import Path

from app.services.faq import FaqService


FAQ_PATH = Path(__file__).resolve().parents[1] / "data" / "faq.json"


def test_semantic_faq_matches_shipping_free_delivery_question():
    service = FaqService(FAQ_PATH)
    match = service.search("买多少可以包邮")

    assert match is not None
    assert match["intent"] == "shipping_fee"


def test_semantic_faq_matches_refund_paraphrase():
    service = FaqService(FAQ_PATH)
    match = service.search("钱什么时候能原路退回")

    assert match is not None
    assert match["intent"] == "refund_time"


def test_semantic_faq_matches_invoice_paraphrase():
    service = FaqService(FAQ_PATH)
    match = service.search("订单能不能给我票据和税号抬头")

    assert match is not None
    assert match["intent"] == "invoice"


def test_semantic_faq_ignores_unrelated_question():
    service = FaqService(FAQ_PATH)
    match = service.search("这款商品适合送长辈吗")

    assert match is None


def test_semantic_faq_does_not_steal_refund_workflow_command():
    service = FaqService(FAQ_PATH)
    match = service.search("我要退款")

    assert match is None
