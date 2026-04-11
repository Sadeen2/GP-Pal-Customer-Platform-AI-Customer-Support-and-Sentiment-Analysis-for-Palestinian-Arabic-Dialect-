# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is enabled on this template. See [this documentation](https://react.dev/learn/react-compiler) for more information.

Note: This will impact Vite dev & build performances.

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
# Generated Data — Palestinian Customer Support Dataset

## What is this?

This is the **first source** of three in our dataset pipeline.
Messages were generated using 5 AI tools with carefully engineered prompts
targeting the Palestinian Arabic dialect — the language customers actually use
on WhatsApp and Facebook.

> This file (`generated_data_combined.json`) is **not the final training dataset**.
> It will be merged later with Facebook and GitHub repo data before any training begins.

---

## Files

```
generation_data/
├── ChatGPT_compined_data.json      # 200 records
├── claude_data.json                # 200 records
├── copilot_combined_data.json      # 238 records
├── deepseek_combined_data.json     # 200 records
├── gemini_data.json                # 200 records
├── merge_generated_data.py         # merge script
└── generated_data_combined.json    # final merged output — 1,028 records
```

---

## Record Schema

```json
{
  "id": 1,
  "text": "يا زلمة الطلب تبعي لسا ما وصل، شو صاير؟",
  "sentiment": "Negative",
  "intent": "Complaint",
  "urgency": "Urgent",
  "dialect": "Palestinian",
  "source": "generated_claude"
}
```

| Field | Values |
|-------|--------|
| `sentiment` | `Positive` · `Neutral` · `Negative` |
| `intent` | `Inquiry` · `Complaint` · `Request` · `Feedback` · `Other` |
| `urgency` | `Normal` · `Urgent` · `Critical` |
| `dialect` | `Palestinian` (fixed) |
| `source` | which tool generated it |

---

## Distribution

| Sentiment | Count | % |
|-----------|-------|---|
| Neutral | 429 | 42% |
| Negative | 318 | 31% |
| Positive | 281 | 27% |

| Intent | Count | % |
|--------|-------|---|
| Complaint | 288 | 28% |
| Inquiry | 279 | 27% |
| Feedback | 234 | 23% |
| Request | 167 | 16% |
| Other | 60 | 6% |

| Urgency | Count | % |
|---------|-------|---|
| Normal | 710 | 69% |
| Urgent | 238 | 23% |
| Critical | 80 | 8% |

| Source | Count | % |
|--------|-------|---|
| generated_copilot | 228 | 22% |
| generated_chatgpt | 200 | 19% |
| generated_claude | 200 | 19% |
| generated_deepseek | 200 | 19% |
| generated_gemini | 200 | 19% |

---

## Prompts Used Per Tool

### ChatGPT

**Language:** English  
**Batch size:** 50 messages per call  
**Key design decisions:** compact prompt, inline JSON format, English Palestinian expressions list

```
You are an Arabic NLP data generation expert.

أنت خبير في توليد بيانات تدريب لنماذج NLP عربية.

Generate 50 realistic Palestinian Arabic dialect messages,
as written by Palestinians on WhatsApp or Facebook
to a general services company customer support.

Palestinian expressions to use naturally:
"والله", "يا زلمة", "يسلمو", "ما بزبط", "شو صاير",
"من امبارح", "ما لحقت", "يعطيك العافية", "الله يخليك"

Mix English words naturally: order, delivery, tracking,
cancel, online, code, router, update

Distribution for 50 messages:
- 15 Positive, 20 Neutral, 15 Negative
- 12 Inquiry, 15 Complaint, 10 Request, 8 Feedback, 5 Other
- 30 Normal, 15 Urgent, 5 Critical

Output JSON only, no extra text:
[{"id":1,"text":"...","sentiment":"...","intent":"...","urgency":"...","source":"generated_chatgpt"}]

Generate messages 1 to 50 now.
```

---

### Claude

**Language:** Arabic  
**Batch size:** 200 messages per call  
**Key design decisions:** `═══` separators for structured sections, dialect variation by region, age-group style variation, strict distribution enforcement

```
أنت خبير في توليد بيانات تدريب لنماذج NLP عربية.

مهمتك: توليد 200 رسالة واقعية باللهجة الفلسطينية،
كما يكتبها مواطنون فلسطينيون على واتساب أو فيسبوك
لخدمة عملاء شركة خدمات عامة.

═══════════════════════════════
شروط الرسائل:
═══════════════════════════════
- مكتوبة باللهجة الفلسطينية الدارجة (مش فصحى)
- ممكن تحتوي أخطاء إملائية طبيعية
- متنوعة في الطول: بعض 5 كلمات، بعض 40 كلمة
- لا تبدأ أكثر من 3 رسائل بنفس الكلمة

═══════════════════════════════
تنوع الأساليب (وزّع عليها):
═══════════════════════════════
- شباب (15-25): مختصر، كلمات إنجليزية، مباشر
- كبار (40+): "يا ابني"، "الله يخليك"، أطول
- أمهات: "عندي أولاد"، "البيت"، "الله يرضى عليك"
- أصحاب شركات: "للشركة"، "فاتورة"، أكثر رسمية

═══════════════════════════════
تنوع المواضيع (وزّع عليها):
═══════════════════════════════
انترنت، كهربا، مية، توصيل، فواتير، فنيين،
باقات، خدمة عملاء، بنوك، صحة، متاجر، تليكوم

═══════════════════════════════
تنوع اللهجة الفلسطينية:
═══════════════════════════════
- شمال (نابلس، جنين): "يعطيك العافية"، "ابن الحلال"
- وسط (رام الله، القدس): "والله"، "ما بزبط"، "زلمة"
- جنوب (الخليل): "يسلمو"، "الله يخليك"
- غزة: "يا زلمة"، "والنبي"، "ما لحقنا"

كلمات إنجليزية طبيعية: order, delivery, tracking,
cancel, online, router, update, code, app, login

═══════════════════════════════
التصنيفات لكل رسالة:
═══════════════════════════════
sentiment: Positive / Neutral / Negative
intent: Inquiry / Complaint / Request / Feedback / Other
urgency: Normal / Urgent / Critical

═══════════════════════════════
التوزيع المطلوب (200 رسالة):
═══════════════════════════════
sentiment:  60 Positive (30%) · 80 Neutral (40%) · 60 Negative (30%)
intent:     60 Complaint (30%) · 50 Inquiry (25%) · 40 Request (20%)
            30 Feedback (15%) · 20 Other (10%)
urgency:    120 Normal (60%) · 60 Urgent (30%) · 20 Critical (10%)

═══════════════════════════════
قواعد صارمة:
═══════════════════════════════
- JSON فقط، بدون أي كلام قبل أو بعد
- لا تكرر نفس الفكرة مرتين
- كل رسالة مختلفة في الأسلوب والموضوع
- احترم التوزيع بدقة
- source = "generated_claude"

الصيغة:
[{ "id": 1, "text": "...", "sentiment": "...",
   "intent": "...", "urgency": "...", "source": "generated_claude" }]

اكتب الـ 200 رسالة كاملة الآن. JSON فقط.
```

---

### Copilot (Microsoft)

**Language:** English  
**Batch size:** 50 messages per call × 4 batches  
**Key design decisions:** explicit expressions list, mixed Arabic/English vocabulary list, per-batch ID ranges

```
You are an Arabic NLP data generation expert.

Your task: Generate 50 realistic customer service messages
in Palestinian Arabic dialect, as written on WhatsApp or Facebook
for a general services company.

Message requirements:
- Written in Palestinian colloquial dialect (NOT Modern Standard Arabic)
- May contain natural spelling mistakes
- Varied length: 5 to 50 words
- Diverse topics: Internet/electricity/water problems,
  Delivery and shipping, Price and package inquiries,
  Complaints about delays, Positive feedback

Palestinian expressions to use naturally:
"والله", "جزاك الله خير", "شو هاد", "ما بزبط", "شو صاير",
"من امبارح", "يا زلمة", "ما لحقت", "يسلمو", "شو في",
"بدي اعرف", "ليش ما"

Mix English words Palestinians commonly use:
order, delivery, tracking, cancel, online, code

Required labels per message:
sentiment: Positive / Neutral / Negative
intent: Inquiry / Complaint / Request / Feedback / Other
urgency: Normal / Urgent / Critical

Distribution for each 50-message batch:
- 15 Positive, 20 Neutral, 15 Negative
- 12 Inquiry, 15 Complaint, 10 Request, 8 Feedback, 5 Other
- 30 Normal, 15 Urgent, 5 Critical

Rules:
- JSON only, zero explanation or intro text
- No repeated messages across batches
- Every message must be unique and realistic
- source value = "generated_copilot"

Output format:
[{ "id": 1, "text": "نص الرسالة", "sentiment": "...",
   "intent": "...", "urgency": "...", "source": "generated_copilot" }]

Generate messages 1 to 50 now. JSON only.
```

---

### DeepSeek

**Language:** Bilingual (Arabic + English)  
**Batch size:** 50 messages per call  
**Key design decisions:** age-group personas, geographic dialect variation, topic categories listed explicitly, typo examples

```
You are an expert Arabic NLP data generator specializing in Palestinian dialect.

أنت خبير في توليد بيانات تدريب لنماذج NLP عربية باللهجة الفلسطينية.

مهمتك: توليد 50 رسالة واقعية باللهجة الفلسطينية،
كما يكتبها مواطنون فلسطينيون على واتساب أو فيسبوك
لخدمة عملاء شركة خدمات عامة.

قبل ما تبدأ، فكر بالتنوع:
- أسلوب الشباب (15-25): مختصر، انجليزي كتير، إيموجي أحياناً
- أسلوب الكبار (40+): أطول، عربي أكثر، "يا ابني"، "الله يخليك"
- أسلوب الأمهات: "عندي أولاد"، "البيت"، "الله يرضى عليك"
- أسلوب أصحاب الشركات: رسمي أكثر، "للشركة"، "فاتورة"

مواضيع متنوعة: انترنت وواي فاي، كهربا وفاتورة،
مية وانقطاع، توصيل وtracking، دفع وأسعار،
خدمة عملاء وفنيين، باقات وخصومات

تنوع اللهجة الفلسطينية:
- شمال (نابلس، جنين): "يعطيك العافية"، "ابن الحلال"
- وسط (رام الله، القدس): "والله"، "ما بزبط"، "زلمة"
- جنوب (الخليل): "يسلمو"، "الله يخليك"
- غزة: "يا زلمة"، "ما لحقنا"، "والنبي"

شروط الرسائل:
- مكتوبة باللهجة الفلسطينية الدارجة (مش فصحى)
- ممكن تحتوي أخطاء إملائية مثل: "وصلة" بدل "وصلت"
- متنوعة في الطول: بعض 5 كلمات، بعض 40 كلمة
- لا تبدأ كل الرسائل بنفس الكلمة

التوزيع لهاي الـ 50:
- 15 Positive, 20 Neutral, 15 Negative
- 12 Inquiry, 15 Complaint, 10 Request, 8 Feedback, 5 Other
- 30 Normal, 15 Urgent, 5 Critical

قواعد صارمة:
- JSON فقط، بدون أي كلام قبل أو بعد
- لا تكرر نفس الجملة أو الفكرة مرتين
- source = "generated_deepseek"

الصيغة:
[{ "id": 1, "text": "...", "sentiment": "...",
   "intent": "...", "urgency": "...", "source": "generated_deepseek" }]

اكتب الرسائل من id: 1 حتى id: 50 الآن. JSON فقط.
```

---

### Gemini

**Language:** Arabic  
**Batch size:** 200 messages per call  
**Key design decisions:** requested 1000 total in batches, geographic dialect variation by Palestinian region, explicit Gemini-specific instruction to output directly in Colab/Sheets

```
أنت نموذج ذكاء اصطناعي متخصص في اللغة العربية واللهجات.
أنت خبير في توليد بيانات تدريب لنماذج NLP عربية.

مهمتك: توليد 1000 رسالة واقعية باللهجة الفلسطينية،
كما يكتبها مواطنون فلسطينيون على واتساب أو فيسبوك
لخدمة عملاء شركة خدمات عامة.

شروط الرسائل:
- مكتوبة باللهجة الفلسطينية الدارجة (مش فصحى)
- ممكن تحتوي أخطاء إملائية طبيعية
- متنوعة في الطول (من 5 كلمات لـ 50 كلمة)
- واقعية ومتعددة المواضيع

التصنيفات المطلوبة لكل رسالة:
sentiment: Positive / Neutral / Negative
intent: Inquiry / Complaint / Request / Feedback / Other
urgency: Normal / Urgent / Critical

التوزيع المطلوب (1000 رسالة):
- sentiment: 30% Positive, 40% Neutral, 30% Negative
- intent: 25% Inquiry, 30% Complaint, 20% Request,
          15% Feedback, 10% Other
- urgency: 60% Normal, 30% Urgent, 10% Critical

⚠️ تعليمات خاصة لـ Gemini:
- ركز على التنوع اللهجي الفلسطيني:
  شمال (نابلس، جنين)، وسط (رام الله، القدس)،
  جنوب (الخليل)، غزة
- اكتب 200 رسالة الآن

الصيغة (JSON فقط، بدون أي كلام إضافي):
[{ "id": 1, "text": "نص الرسالة", "sentiment": "...",
   "intent": "...", "urgency": "...", "source": "generated" }]
```

---

## Prompt Design — What Worked

| Technique | Effect |
|-----------|--------|
| Geographic dialect variation (north/center/south/Gaza) | More authentic regional vocabulary |
| Age-group personas (youth / elders / mothers / business) | Natural length and style diversity |
| Explicit expression lists | Consistent Palestinian dialect markers |
| Strict per-batch distribution numbers | Balanced labels across all classes |
| `JSON only` + no preamble instruction | Clean parseable output |
| Bilingual prompt (DeepSeek) | Better instruction following |
| Typo examples (`"وصلة" بدل "وصلت"`) | More realistic spelling variation |

## Prompt Design — What to Improve Next Time

| Issue | Fix |
|-------|-----|
| `Feedback` still over-represented (23%) | Add hard cap: `Feedback ≤ 15%` |
| `Positive + Other` appeared frequently | Explicit ban: `⛔ Positive + Other = forbidden` |
| Some tools ignored distribution exactly | Add verification step after each batch |
| Short messages dominated some batches | Enforce: `at least 30% of messages must be > 15 words` |

---

## How it was built

### Merge pipeline (`merge_generated_data.py`)

1. **Load & normalize** — unified schema across all 5 sources
2. **Clean text** — remove URLs, phone numbers, extra whitespace
   *(emojis intentionally kept — they carry sentiment signal)*
3. **Validate labels** — drop records with invalid or missing labels
4. **Exact dedup** — remove identical messages → 0 removed
5. **Fuzzy dedup** — Jaccard similarity ≥ 0.85 → 10 removed
6. **Stratified shuffle** — round-robin by sentiment, seed=42

### Result

```
1,038 raw → 0 invalid → 0 exact dupes → 10 fuzzy dupes → 1,028 clean
```

---

## How to reproduce

```bash
python merge_generated_data.py
```

Output is deterministic — `random.seed(42)` throughout.

---

## Next steps

- [ ] Add Facebook data source
- [ ] Add GitHub Palestinian dialect repo data
- [ ] Run full merge + deep cleaning + bias check across all 3 sources
