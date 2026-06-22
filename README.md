# Pal-CustomerAI

AI-powered Customer Support Platform for Palestinian Arabic Dialect.

This project was developed as part of a graduation project to build an intelligent customer support platform that understands Palestinian Arabic dialect and assists customer service operations using Natural Language Processing (NLP) and Machine Learning techniques.

## Features

* Sentiment Analysis (Positive, Neutral, Negative)
* Intent Classification (Inquiry, Complaint, Request, Feedback, Other)
* Urgency Detection (Normal, Urgent, Critical)
* FAQ Matching and automatic reply generation
* Routing decisions (Auto Reply, Human Agent, Escalation)
* FastAPI backend
* Dashboard frontend interface

## Project Structure

```text
GP/
├── app/                  # FastAPI backend
├── frontend/             # Dashboard interface
├── saved_model/          # Trained model files
├── dataset.json          # Dataset
├── clean_dataset.json    # Cleaned dataset
├── train.py              # Model training script
├── import_faqs_to_db.py  # FAQ import script
├── requirements.txt      # Python dependencies
└── README.md
```

## Technologies Used

* Python
* FastAPI
* HTML
* CSS
* JavaScript
* Machine Learning
* Natural Language Processing (NLP)
* SQLite

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd GP
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

### 3. Activate the virtual environment

Windows:

```bash
venv\Scripts\activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

## Running the Project

Start the FastAPI server:

```bash
python -m uvicorn app.main:app --reload
```

## Access the Application

Dashboard:

```text
http://127.0.0.1:8000/dashboard/
```

Swagger Documentation:

```text
http://127.0.0.1:8000/docs
```

## Frontend Integration

The frontend is mounted through FastAPI using:

```python
from fastapi.staticfiles import StaticFiles

app.mount(
    "/dashboard",
    StaticFiles(directory="frontend", html=True),
    name="dashboard"
)
```

## Authentication

Users can register using:

```text
/auth/register
```

Users can log in using:

```text
/ auth/login
```

# Palestinian Arabic Customer Support Dataset

This repository contains the dataset preparation work for our graduation project:
**Pal-Customer Platform: AI Customer Support and Sentiment Analysis for Palestinian Arabic Dialect**.

## Dataset Status

The dataset preparation stage is completed.  
The final cleaned and merged dataset is located at:

`data/final/dataset.json`


---

## Data Sources

The dataset was collected from a combination of **real-world data** and **AI-generated data**, then cleaned and merged into a unified final dataset.

### 1. Real Data (Primary Source)
The majority of the dataset was collected from **Facebook & Instagram pages** related to customer interactions (e.g., comments, messages, and public discussions).  
This provides realistic language usage, especially for the **Palestinian Arabic dialect**.

### 2. Generated Data (Secondary Source)
To enrich the dataset and improve coverage, additional data was generated using multiple AI tools:

- ChatGPT  
- Gemini  
- Claude  
- DeepSeek
- copilot 

### Why Both?

- Real data → ensures authenticity and real user behavior  
- Generated data → improves diversity, balance, and edge-case coverage  
---

## Preprocessing Steps

The following preprocessing steps were applied:

1. Merged all dataset files into one collection  
2. Removed duplicated records  
3. Cleaned text formatting and unnecessary spaces  
4. Standardized the JSON structure  
5. Validated the final dataset format  
6. Saved the final version as `dataset.json`  

---

## Final Dataset Format

Each record in the final dataset follows a structured JSON format:

```json
{
  "id": 1,
  "text": "customer message here",
  "sentiment": "positive / neutral / negative",
  "category": "complaint / inquiry / feedback / other",
  "urgency": "low / normal / high"
}

## Notes

The following files and folders should not be uploaded to GitHub:

```text
.env
venv/
__pycache__/
*.db
ngrok.exe
```

## Authors

Graduation Project Team

Pal-CustomerAI – AI Customer Support and Sentiment Analysis for Palestinian Arabic Dialect.

