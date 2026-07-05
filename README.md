# Pal-CustomerAI

**AI-Powered Customer Support Platform for Palestinian Arabic Dialect**

Pal-CustomerAI is a graduation project that provides an intelligent customer support platform for Arabic-speaking users, with a special focus on the Palestinian Arabic dialect.

The platform analyzes customer messages, predicts sentiment, identifies customer intent, detects urgency, matches frequently asked questions, generates automatic replies when possible, and routes complex or critical cases to a human agent or escalation path.

---

## Project Overview

Customer support teams often receive a large number of messages written in informal Arabic dialects, including slang, spelling variations, and mixed language styles. Traditional support systems may struggle to understand these messages accurately.

Pal-CustomerAI addresses this problem by using Natural Language Processing (NLP) and Machine Learning techniques to support customer service operations in Palestinian Arabic.

The system includes:

- Palestinian Arabic text understanding
- Sentiment analysis
- Intent classification
- Urgency detection
- FAQ matching
- Automatic reply generation
- Human agent routing
- Escalation for urgent or critical cases
- FastAPI backend
- Web dashboard frontend
- Instagram integration support

---

## Features

### AI Analysis

- **Sentiment Analysis**
  - Positive
  - Neutral
  - Negative

- **Intent Classification**
  - Inquiry
  - Complaint
  - Request
  - Feedback
  - Other

- **Urgency Detection**
  - Normal - low
  - Urgent - medium 
  - Critical - high

### Customer Support Automation

- FAQ matching
- Automatic response generation
- Routing decisions:
  - Auto Reply
  - Human Agent
  - Escalation

### Platform Features

- FastAPI backend
- SQLite database
- Dashboard frontend interface
- Authentication system
- Instagram setup and integration files
- Realtime support modules
- Database checking and reset scripts

---

## Technologies Used

- Python
- FastAPI
- SQLite
- HTML
- CSS
- JavaScript
- Machine Learning
- Natural Language Processing
- Palestinian Arabic Dialect Processing

---

## Project Structure

```text
GP-Pal-Customer-Platform-AI-Customer-Support-and-Sentiment-Analysis-for-Palestinian-Arabic-Dialect/
├── app/                              # FastAPI backend application
│   ├── data/                         # Dataset and related data files
│   ├── database/                     # Database configuration and models
│   ├── model/                        # AI model inference files
│   ├── routes/                       # API route handlers
│   ├── schemas/                      # Request and response schemas
│   ├── services/                     # Business logic and processing services
│   ├── __init__.py
│   ├── main.py                       # FastAPI application entry point
│   ├── rate_limit.py                 # Rate limiting logic
│   ├── realtime.py                   # Realtime communication support
│   └── security.py                   # Security and authentication utilities
│
├── frontend/                         # Dashboard frontend interface
│   ├── index.html
│   ├── app.js
│   ├── data.js
│   ├── styles.css
│   ├── logo-pl.png
│   ├── README.md
│   ├── README_CONNECT.md
│   └── INSTAGRAM_FRONTEND_NOTES.md
│
├── INSTAGRAM_SETUP.md                # Instagram integration setup guide
├── add_sender_type.py                # Script for adding sender type data
├── check_db.py                       # Database checking script
├── check_token.py                    # Token checking script
├── import_faqs_to_db.py              # FAQ import script
├── make_urgency_three_buckets.sql    # SQL script for urgency bucket updates
├── reset_db.py                       # Database reset script
├── train.py                          # Model training script
├── requirements.txt                  # Python dependencies
├── .gitignore                        # Ignored files and folders
└── README.md                         # Main project documentation
```

---

## Dataset

The dataset was prepared specifically for the graduation project:

**Pal-CustomerAI: AI Customer Support and Sentiment Analysis for Palestinian Arabic Dialect**

The dataset contains customer support messages written mainly in Palestinian Arabic. Each record is labeled for sentiment, intent/category, and urgency.

---

## Data Sources

The dataset was collected from a combination of real-world data and AI-generated data.

### 1. Real Data

The main source of data was collected from social media pages, especially Facebook and Instagram pages related to customer interactions, such as comments, messages, and public discussions.

This data helps capture realistic Palestinian Arabic language usage, including informal expressions, spelling variations, dialect words, and customer-service-related messages.

### 2. AI-Generated Data

Additional data was generated using multiple AI tools to improve dataset diversity and coverage.

The tools used include:

- ChatGPT
- Gemini
- Claude
- DeepSeek
- Microsoft Copilot

### Why Both Sources Were Used

Real data was used to preserve authenticity and reflect real customer behavior.

Generated data was used to improve class balance, increase coverage of different customer support scenarios, and include edge cases that may not appear frequently in real collected data.

---

## Dataset Preprocessing

The following preprocessing steps were applied:

1. Collected real and generated customer messages
2. Merged all dataset files into one collection
3. Removed duplicated records
4. Cleaned text formatting and unnecessary spaces
5. Standardized the JSON structure
6. Reviewed and validated the labels
7. Prepared the final dataset for model training and evaluation

---

## Dataset Format

Each record follows a structured JSON format:

```json
{
  "id": 1,
  "text": "customer message here",
  "sentiment": "Positive / Neutral / Negative",
  "category": "Inquiry / Complaint / Request / Feedback / Other",
  "urgency": "Normal / Urgent / Critical"
}
```

---

## AI Model Workflow

When a customer message is received, the system performs the following steps:

1. Receives the customer message through the backend
2. Sends the message to the AI inference module
3. Predicts:
   - Sentiment
   - Intent/category
   - Urgency
4. Checks whether the message matches an existing FAQ
5. Generates an automatic response if the FAQ match has high confidence
6. Routes the message based on the prediction result

---

## Routing Logic

The system follows these decision rules:

- If the message matches a known FAQ with high confidence and is not critical, the system sends an automatic reply.
- If the message is unclear, complex, or has low confidence, it is routed to a human agent.
- If the message is negative and urgent or critical, it is escalated.

---

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd GP-Pal-Customer-Platform-AI-Customer-Support-and-Sentiment-Analysis-for-Palestinian-Arabic-Dialect
```

Replace `<repository-url>` with the actual GitHub repository link.

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

### 3. Activate the Virtual Environment

For Windows:

```bash
venv\Scripts\activate
```

For macOS/Linux:

```bash
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Running the Project

Start the FastAPI server using:

```bash
python -m uvicorn app.main:app --reload
```

After running the server, the application will be available locally at:

```text
http://127.0.0.1:8000
```

---

## Access the Application

### Dashboard

```text
http://127.0.0.1:8000/dashboard/
```

### Swagger API Documentation

```text
http://127.0.0.1:8000/docs
```

---

## Main API Endpoints

### Authentication

Register a new user:

```text
/auth/register
```

Log in:

```text
/auth/login
```

### Dashboard

```text
/dashboard/
```

### API Documentation

```text
/docs
```

---

## Frontend Integration

The frontend dashboard is served through FastAPI using static files.

```python
from fastapi.staticfiles import StaticFiles

app.mount(
    "/dashboard",
    StaticFiles(directory="frontend", html=True),
    name="dashboard"
)
```

---

## Instagram Integration

The project includes Instagram integration setup files.

For setup instructions, check:

```text
INSTAGRAM_SETUP.md
```

Frontend-related Instagram notes are available in:

```text
frontend/INSTAGRAM_FRONTEND_NOTES.md
```

---

## Database and Utility Scripts

The project includes several helper scripts:

- `check_db.py`  
  Used to inspect and verify the database.

- `reset_db.py`  
  Used to reset or recreate the database during development.

- `check_token.py`  
  Used to verify authentication or integration tokens.

- `import_faqs_to_db.py`  
  Used to import FAQ data into the database.

- `add_sender_type.py`  
  Used to update message records with sender type information.

- `make_urgency_three_buckets.sql`  
  SQL script used to update urgency labels into three buckets.

---

## Files and Folders Not Uploaded to GitHub

The following files and folders should not be uploaded to GitHub:

```text
.env
venv/
.venv/
__pycache__/
*.db
*.sqlite
*.sqlite3
ngrok.exe
app.zip
frontend.zip
.claude/
```

Make sure these files are included in `.gitignore`.

---

## Notes

- The project is designed for educational and research purposes as part of a graduation project.
- The system focuses on text-based customer support.
- The platform is optimized for Palestinian Arabic dialect understanding.
- The backend is implemented using FastAPI.
- The dashboard frontend is stored inside the `frontend/` folder.
- The AI model files and inference logic are located inside the backend application structure.
- The dataset is used for model training, evaluation, and experimentation.

---

## Authors

Graduation Project Team

**Pal-CustomerAI – AI Customer Support and Sentiment Analysis for Palestinian Arabic Dialect**
