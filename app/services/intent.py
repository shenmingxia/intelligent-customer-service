class IntentClassifier:
    def classify(self, message: str) -> tuple[str, float]:
        text = message.lower()
        rules = {
            "greeting": ["你好", "您好", "hello", "hi"],
            "order_status": ["订单", "物流", "快递", "发货", "到哪"],
            "refund": ["退款", "退货", "取消", "赔付"],
            "complaint": ["投诉", "差评", "生气", "不满意", "太差"],
        }

        for intent, keywords in rules.items():
            if any(keyword in text for keyword in keywords):
                return intent, 0.75

        return "unknown", 0.2
