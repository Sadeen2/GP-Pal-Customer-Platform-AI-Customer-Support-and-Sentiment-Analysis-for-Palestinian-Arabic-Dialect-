def get_score(item: dict) -> float:
    label = item["label"]
    return item["scores"].get(label, 0)


def decide_route(prediction: dict):
    sentiment = prediction["sentiment"]["label"]
    category = prediction["category"]["label"]
    urgency = prediction["urgency"]["label"]

    sentiment_conf = get_score(prediction["sentiment"])
    category_conf = get_score(prediction["category"])
    urgency_conf = get_score(prediction["urgency"])

    min_confidence = min(sentiment_conf, category_conf, urgency_conf)

    if urgency == "critical":
        return {
            "action": "escalation",
            "reason": "Critical urgency detected"
        }

    if sentiment == "negative" and urgency == "urgent":
        return {
            "action": "escalation",
            "reason": "Negative urgent message"
        }

    if min_confidence < 0.60:
        return {
            "action": "human_handoff",
            "reason": "Low model confidence"
        }

    if category in ["inquiry", "request"] and urgency == "normal":
        return {
            "action": "auto_reply",
            "reason": "Normal inquiry/request can be handled automatically"
        }

    if sentiment == "positive" or category == "feedback":
        return {
            "action": "auto_reply",
            "reason": "Positive or feedback message"
        }

    return {
        "action": "human_handoff",
        "reason": "Needs human review"
    }