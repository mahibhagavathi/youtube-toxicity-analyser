# 🧠 YouTube Comment Analyser (AI Toxicity Detection)

A Streamlit-based AI web app that analyzes YouTube video comments and detects toxicity using deep learning. It classifies comments into **Normal, Borderline, and Toxic**, and breaks down different types of harmful content like insults, threats, and identity attacks.

---

## 🚀 Live Demo
*https://youtube-toxicity-analyser.streamlit.app/*  

---

## 📌 Features

- 🔗 Analyze any YouTube video using URL
- 📥 Fetch real-time comments via YouTube Data API v3
- 🧠 AI-based toxicity detection using `Detoxify`
- 📊 Visual breakdown of:
  - Toxic comments
  - Borderline comments
  - Normal comments
- 🔬 Detailed toxicity classification:
  - Insults
  - Threats
  - Obscene content
  - Identity attacks
- 🚨 “Top Comments to Remove” ranking system
- 📉 Interactive charts using Matplotlib
- 📋 Full dataset view with toxicity scores

---

## 🧠 How It Works

1. User enters a YouTube video URL  
2. App extracts Video ID  
3. Fetches comments using **YouTube Data API v3**  
4. AI model (`Detoxify`) analyzes each comment  
5. Comments are scored across multiple toxicity dimensions  
6. Results are visualized in a Streamlit dashboard  

---

## 🛠️ Tech Stack

- **Frontend:** Streamlit  
- **Backend:** Python  
- **AI Model:** Detoxify (BERT-based toxicity detection)  
- **APIs:** YouTube Data API v3  
- **Data Processing:** Pandas, Regex  
- **Visualization:** Matplotlib  
