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
