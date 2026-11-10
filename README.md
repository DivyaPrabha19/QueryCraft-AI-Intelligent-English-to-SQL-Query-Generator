# QueryCraft AI — Intelligent English-to-SQL Query Generator

QueryCraft AI is an advanced, full-stack database interface and neural translation engine designed with a retro-futuristic, cyberpunk dark neon theme. It translates plain English instructions into clean, executable SQL syntax, inspects active database schemas, tracks translation histories inside a centralized MySQL server, and lets you run commands live.

---

## 🚀 Key Features

*   **⚡ ADAPTIVE CONFIDENCE-GUIDED MULTI-AGENT ORCHESTRATION**: Flagship multi-agent engine that dynamically decides at each step whether to stop reasoning (Fast-Path Early Exit) or hand off to specialized agents based on multi-signal confidence ($C_{\text{model}}$, $C_{\text{exec}}$, $C_{\text{verifier}}$, $C_{\text{agreement}}$), query complexity, and token budget.
*   **5️⃣ 5 SELECTABLE ORCHESTRATION PARADIGMS**:
    1.  **Adaptive Confidence-Guided Multi-Agent** (Novel Proposal with Fast-Path early exit)
    2.  **Fixed 5-Stage Multi-Agent Pipeline** (Sequential baseline running all 5 agents)
    3.  **Single-Model Direct LLM Generation** (Monolithic zero-shot baseline)
    4.  **Multi-Candidate Consensus Voting** (Agreement-driven ensemble baseline)
    5.  **Deterministic Rule-Based Parser** (Offline zero-cost grammar baseline)
*   **🤖 5 SPECIALIZED AGENTS**:
    -   *Agent 1 (Complexity Router)*: Query difficulty assessment and dynamic thresholding ($\tau_{\text{exit}}$)
    -   *Agent 2 (Schema Linker)*: Semantic pruning of tables and foreign key graph mapping
    -   *Agent 3 (SQL Generator)*: Candidate generation with self-consistency
    -   *Agent 4 (Execution Verifier)*: MySQL AST validation and dry-run execution feedback
    -   *Agent 5 (Self-Correction Repair)*: Automated diagnosis and iterative SQL refinement
*   **📊 COMPARATIVE BENCHMARK MATRIX**: Run queries across all 5 orchestration modes simultaneously to compare accuracy, tokens consumed, latency, and early-exit savings.
*   **🧠 Neural Compiler**: Seamless translation powered by **Google Gemini AI (2.5-Flash)**, with a rule-based Python parsing engine as a local fallback.
*   **💾 CENTRALIZED DATABASE HISTORY**: Centralizes user accounts and translation logs inside a dedicated MySQL `history` database, automatically created and seeded on startup.
*   **🔍 DYNAMIC SCHEMA DISCOVERY**: Automatically discovers all available database schemas (e.g. `farmers_easeuse`, `world`, etc.) on your MySQL server and populates an interactive schema explorer.
*   **💻 INTEGRATED SQL COMPILER TERMINAL**: Display syntax-highlighted SQL queries, and execute them directly against selected databases with results rendered in a modern data preview grid.

---

## 🛠️ Technology Stack

*   **Frontend**: HTML5, Vanilla CSS3 (Custom Cyberpunk Glassmorphism and Neon theme variables), JavaScript (ES6+ AJAX flow, interactive visual agent pipeline, real-time telemetry meters)
*   **Backend**: Python, Flask, PyMySQL
*   **Orchestration**: Multi-Agent System, Multi-Signal Confidence Engine, Dynamic Routing
*   **AI Integration**: Google Generative Language API (Gemini 2.5-Flash)
*   **Configuration**: Dotenv configuration loading

---

## ⚙️ Project Structure

```
├── backend/
│   ├── app.py                  # Core Flask server and API routes
│   ├── orchestration/          # 5-Agent Adaptive Orchestration Package
│   │   ├── __init__.py         # Package exports
│   │   ├── agents.py           # 5 Specialized Agents (Router, Schema, Generator, Verifier, Repair)
│   │   ├── confidence.py       # Multi-Signal Confidence Engine (C_model, C_exec, C_verifier, C_agree)
│   │   └── orchestrator.py     # Central Controller & 5 Orchestration Modes
│   ├── static/
│   │   ├── js/app.js           # Visual trajectory flow, telemetry HUD, and benchmark logic
│   │   └── css/styles.css      # Cyberpunk neon styles, pulse animations, pipeline grid
│   └── templates/
│       └── dashboard.html      # Control Center with 5-Agent Pipeline & Confidence HUD
└── README.md
```

---

## 🏁 Quick Start Guide

### 1. Prerequisites
Ensure you have Python 3.8+ and a running MySQL server.

### 2. Clone and Setup Environment
```bash
# Clone the repository
git clone https://github.com/DivyaPrabha19/QueryCraft-AI-Intelligent-English-to-SQL-Query-Generator.git
cd QueryCraft-AI-Intelligent-English-to-SQL-Query-Generator

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in the root directory and copy variables from `.env.example`:

```ini
FLASK_PORT=5000
FLASK_DEBUG=True

# Database Credentials
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_PORT=3306
MYSQL_DB=db

# AI Engine Keys
GEMINI_API_KEY=your_gemini_api_key

# Google OAuth Client
GOOGLE_CLIENT_ID=your_google_client_id
```

### 4. Running the Application
```bash
python app.py
```
Open your browser and navigate to `http://127.0.0.1:5000/`.

---

## 🔑 Demo Account
To quickly test the dashboard interface, you can connect using the default operator profile loaded on database creation:
*   **User Identity**: `neo@matrix.com`
*   **Access Cipher**: `password123`

---

## 📄 License
This project is licensed under the MIT License - see the LICENSE file for details.
