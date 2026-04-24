import os

tools = {
    "chatgpt": [
        "login", "password", "notifications", "wrong_orders", "delivery",
        "refund", "status", "discount", "subscription", "feedback"
    ],
    "claude": [
        "long_complaints", "technician_no_show", "billing_disputes",
        "family_issues", "support_failures", "escalation",
        "formal_feedback", "misunderstanding", "business_impact", "delayed_issue"
    ],
    "gemini": [
        "pricing", "packages", "availability", "invoice", "verification",
        "subscription_details", "hours", "coverage", "payment_methods", "features"
    ],
    "copilot": [
        "app_crash", "login_error", "network", "router",
        "update_bug", "server", "payment_error", "api_issue", "feature_bug", "sync"
    ],
    "deepseek": [
        "angry", "urgent_family", "business_loss", "home_issues",
        "frustration", "dramatic", "negative_feedback",
        "outage", "positive_emotional", "critical"
    ]
}

base_path = "data"

for tool, topics in tools.items():
    tool_path = os.path.join(base_path, tool)
    os.makedirs(tool_path, exist_ok=True)

    for i, topic in enumerate(topics, start=1):
        file_path = os.path.join(tool_path, f"batch_{i}_{topic}.json")

        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("[]")

print("All folders & files created!")