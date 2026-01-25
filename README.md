# AI News Curator Agent

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Groq](https://img.shields.io/badge/AI-Groq%20Llama%203-orange)](https://groq.com)
[![Docker](https://img.shields.io/badge/Docker-Enabled-blue)](https://www.docker.com/)

**An autonomous AI agent that curates personalized technical news digests.**

This project implements a sophisticated daily data pipeline that scrapes multi-modal content (YouTube transcripts, RSS feeds), processes it using high-performance LLMs (Llama 3 70B via Groq), and ranks it against a specific user profile to deliver highly relevant insights via email.

## 🚀 Key Features

- **Multi-Modal Data Ingestion**:
  - **YouTube**: Extracts video transcripts to analyze video content as text.
  - **RSS Feeds**: Monitors detailed engineering blogs (e.g., Anthropic, OpenAI).
- **Agentic Architecture**:
  - **Curator Agent**: Uses RAG-like ranking principles to score content against a user persona.
  - **Digest Agent**: Generates concise, technical summaries without marketing fluff.
- **Cost-Optimized AI**:
  - Migrated from paid OpenAI APIs to **Groq (Llama 3)** for ultra-fast, free inference.
  - Enforces **JSON Structured Outputs** for reliable downstream processing.
- **Production Ready**:
  - Dockerized for easy deployment.
  - Configured for background execution (Cron) on platforms like Render.

## 🛠️ Tech Stack

- **Core**: Python 3.12, Pydantic, SQLAlchemy
- **AI/LLM**: Groq API, Llama 3 70B, Prompt Engineering
- **Data**: PostgreSQL, Feedparser, YouTube Transcript API
- **Infrastructure**: Docker, Docker Compose

## 🏗️ Architecture

1.  **Scraper Layer**: modular scrapers fetch raw content.
2.  **Processing Layer**: cleans text, handles fallbacks (e.g., missing transcripts).
3.  **Intel Layer**:
    - `DigestAgent`: Summarization.
    - `CuratorAgent`: Relevance Scoring (0-10) based on `user_profile.py`.
4.  **Delivery Layer**: Formats Markdown/HTML and sends via SMTP.

## ⚡ Quick Start

### Prerequisites

- Python 3.12+
- Groq API Key (Free)
- PostgreSQL (or Docker)

### Installation

1.  **Clone & Install**

    ```bash
    git clone https://github.com/yourusername/ai-news-curator.git
    cd ai-news-curator
    uv sync
    ```

2.  **Configure Environment**
    Create a `.env` file:

    ```bash
    GROQ_API_KEY=your_groq_key
    MY_EMAIL=your_email@gmail.com
    APP_PASSWORD=your_app_password
    DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_news_aggregator
    ```

3.  **Run Locally**

    ```bash
    # Start DB
    docker compose up -d

    # Run Pipeline
    uv run main.py
    ```

## 📦 Deployment

This project is designed to run as a **Daily Cron Job** on Render.com (Free Tier).
See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for full instructions.

## 📄 License

MIT
