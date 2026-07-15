# QueryCraft AI — Intelligent English-to-SQL Query Generator

QueryCraft AI is an advanced, full-stack database interface and neural translation engine designed with a retro-futuristic, cyberpunk dark neon theme. It translates plain English instructions into clean, executable SQL syntax, inspects active database schemas, tracks translation histories inside a centralized MySQL server (with automatic SQLite fallback), and lets you run commands live.

---

## 🚀 Key Features

*   **🧠 Dual Neural Compilers**: Seamless translation powered by **Google Gemini AI (2.5-Flash)** and **OpenAI GPT** models, with a rule-based Python parsing engine as a local fallback.
*   **💾 CENTRALIZED DATABASE HISTORY**: centralizes user accounts and translation logs inside a dedicated MySQL `history` database, automatically created and seeded on startup.
*   **🛡️ MULTI-DATABASE FAILOVER SYNC**: Integrates a robust failover architecture. If the primary MySQL database goes offline, operations automatically fallback to local SQLite files (`users.db` and `history.db`) to guarantee 100% uptime.
*   **🔍 DYNAMIC SCHEMA DISCOVERY**: Automatically discovers all available database schemas (e.g. `farmers_easeuse`, `sakila`, `world`, etc.) on your MySQL server and populates an interactive schema explorer.
*   **💻 INTEGRATED SQL COMPILER TERMINAL**: Display syntax-highlighted SQL queries, and execute them directly against selected databases with results rendered in a modern data preview grid.
*   **🌐 GOOGLE OAUTH SIMULATION**: Complete Google Sign-In and registration flow with support for simulated mock credentials for rapid localized testing.

---

## 🛠️ Technology Stack

*   **Frontend**: HTML5, Vanilla CSS3 (Custom Glassmorphism and Neon theme variables), JavaScript (ES6+ AJAX flow)
*   **Backend**: Python, Flask, PyMySQL, SQLite3
*   **AI Integration**: Google Generative Language API, OpenAI API
*   **Configuration**: Dotenv configuration loading

---

## ⚙️ Project Structure

```
├── app.py                  # Core Flask server and database models
├── requirements.txt        # Python dependency manifest
├── static/
│   ├── app.js              # Translation events, database execution, and table parsers
│   ├── auth.js             # Authentication routing and token management
│   └── styles.css          # Cyberpunk variables, animations, and layouts
├── templates/
│   ├── index.html          # Gateway auth portal (Sign in / register / simulator)
│   └── dashboard.html      # Main query generator workspace and results terminal
└── .env.example            # Environment variables template
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
OPENAI_API_KEY=your_openai_api_key

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
