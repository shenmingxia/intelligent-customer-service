class PolicyService:
    def should_transfer_to_human(self, message: str, human_keywords: list[str]) -> bool:
        text = message.lower()
        return any(keyword.lower() in text for keyword in human_keywords)
