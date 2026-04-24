# Palestinian Arabic Customer Support Dataset

This repository contains generated Palestinian Arabic customer-support messages for our graduation project.

The dataset is built using multiple AI tools with scenario-based prompts to reduce repetition and improve diversity.

## Current Status

Completed source:

- DeepSeek emotional dataset

DeepSeek output:

- Raw batches: 600 records
- After validation: 600
- Invalid removed: 0
- Exact duplicates removed: 0
- Semantic duplicates removed: 36
- Final clean records: 564

Final file:

```text
data/deepseek/deepseek_clean.json
```

## DeepSeek Batch Topics

| Batch | Topic |
| --- | --- |
| batch_1_angry | Angry customer complaints caused by repeated service failures |
| batch_2_urgent_family | Urgent family situations affected by the service |
| batch_3_business_loss | Business loss caused by service issues |
| batch_4_home_issues | Home-life problems caused by the service |
| batch_5_frustration | Frustrated users who tried multiple times without success |
| batch_6_dramatic | Dramatic but realistic emotional situations |
| batch_7_negative_feedback | Strong negative feedback about bad service experience |
| batch_8_outage | Stressful service outage situations affecting daily life |
| batch_9_positive_emotional | Emotional positive feedback after problems were solved |
| batch_10_critical | Critical escalation cases requiring immediate action |

## Record Schema

```json
{
	"id": 1,
	"text": "والله تعبت، الخدمة مقطوعة من يومين وما حدا برد.",
	"sentiment": "Negative",
	"intent": "Complaint",
	"urgency": "Critical",
	"source": "generated_deepseek_v3"
}
```

## Labels

| Field | Allowed Values |
| --- | --- |
| sentiment | Positive, Neutral, Negative |
| intent | Inquiry, Complaint, Request, Feedback, Other |
| urgency | Normal, Urgent, Critical |

## Cleaning Pipeline

The DeepSeek batches were processed using:

1. Load all batch JSON files
2. Validate required labels
3. Clean extra whitespace
4. Remove exact duplicates
5. Remove semantic duplicates using sentence embeddings
6. Shuffle records using seed = 42
7. Re-index IDs
8. Save final clean JSON file

## DeepSeek Distribution After Cleaning

| Category | Distribution |
| --- | --- |
| Sentiment | Negative: 236, Positive: 191, Neutral: 137 |
| Intent | Feedback: 212, Complaint: 212, Inquiry: 77, Request: 51, Other: 12 |
| Urgency | Normal: 271, Critical: 173, Urgent: 120 |

## How to Reproduce

```bash
python merge_deepseek.py
```

Output:

```text
data/deepseek/deepseek_clean.json
```

## Notes

- Emojis were intentionally kept because they help capture sentiment and urgency.
- DeepSeek is intentionally emotional-heavy, so the distribution is not fully balanced.
- Other tools will be used to balance Inquiry, Request, and Neutral samples later.

