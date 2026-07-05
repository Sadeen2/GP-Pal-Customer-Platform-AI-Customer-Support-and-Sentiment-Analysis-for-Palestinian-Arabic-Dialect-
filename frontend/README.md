# Pal CustomerAI — Frontend

> AI-powered Arabic Customer Support Dashboard  
> Graduation Project — Frontend Branch

---

## 📌 Overview

Pal CustomerAI is a web-based customer support dashboard powered by AI. It is designed to handle Arabic-speaking customers (Palestinian dialect focus) and automate message routing, sentiment analysis, and auto-replies.

---

## ✨ Features

- 🔐 **Login Page** — Email/password authentication with Arabic/English toggle
- 📊 **Dashboard** — Overview of messages, sentiment, urgency, and resolved cases
- 💬 **Messages Inbox** — Filterable list of incoming customer messages
- 🔍 **Message Details** — Full AI analysis: sentiment, intent, urgency, confidence score
- 🤖 **Auto-Reply System** — AI automatically replies when confidence ≥ 70% and urgency is not High; otherwise routes to a human agent
- 🔀 **Routing & Assignment** — Assign messages to agents, escalate critical cases
- ❓ **FAQ Management** — Add, edit, and delete FAQ entries (persisted in localStorage)
- 📈 **Analytics** — Sentiment breakdown, urgency distribution, top intents, message volume over time
- 🌙 **Dark / Light Mode** — Persistent theme toggle
- 🌐 **Arabic / English i18n** — Full bilingual support with RTL layout switching

---

## 🗂️ Project Structure

```
Frontend_Part_GP/
├── index.html        # Main HTML shell
├── app.js            # Core application logic & view rendering
├── data.js           # Mock messages data
├── styles.css        # All styles (light + dark mode, RTL support)
├── logo-pl.png       # Brand logo
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites
- Node.js (for local dev server via Vite)

### Run locally
```bash
npm install
npm run dev
```
Then open `http://localhost:5500` in your browser.

### Test credentials
```
Email:    admin@pal.ai
Password: any password (mock auth)
```

---

## 🤖 Auto-Reply Logic

| Condition | Action |
|-----------|--------|
| Confidence ≥ 70% + Urgency is Low/Medium | ✅ AI replies automatically |
| Urgency is High | 🔴 Routed to human agent |
| Confidence < 70% | 👤 Routed to human agent |

---

## 🌐 Internationalization (i18n)

The app supports full Arabic/English switching from the top navbar.  
Switching to Arabic enables RTL layout automatically across all views.

---

## 👥 Team

- Sadeen Ryahi
- Malik Arquob
- Mohammed Obaid

---

## 📄 License

This project is built for academic purposes as part of a graduation project.