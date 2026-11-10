import os
import re
import time
import urllib.request
import urllib.error
import json
import base64
import secrets
try:
    import pymysql
    import pymysql.cursors
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
from flask import Flask, request, jsonify, session, render_template
from flask_cors import CORS
try:
    from orchestration import MultiAgentOrchestrator
    from orchestration.compiler import SemanticSQLCompiler
except ImportError:
    from backend.orchestration import MultiAgentOrchestrator
    from backend.orchestration.compiler import SemanticSQLCompiler

# Load environment variables from .env file
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    os.environ[key.strip()] = val.strip().strip('"').strip("'")

load_env()

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)
# Enable CORS with credentials support
CORS(app, supports_credentials=True)
app.secret_key = 'cyberpunk_neural_key_1984'

is_production = os.environ.get('RENDER') is not None or os.environ.get('FLASK_ENV') == 'production'
app.config.update(
    SESSION_COOKIE_SAMESITE='None' if is_production else 'Lax',
    SESSION_COOKIE_SECURE=True if is_production else False,
    SESSION_COOKIE_HTTPONLY=True
)

_SCHEMA_CACHE = {}
_SCHEMA_CACHE_TIMESTAMP = {}
_CACHE_TTL = 180.0
_MYSQL_LAST_ERROR = 0.0
_MYSQL_ERROR_COOLDOWN = 15.0

def get_mysql_connection(db_name=None):
    global _MYSQL_LAST_ERROR
    if not MYSQL_AVAILABLE:
        raise Exception("MySQL client library (pymysql) is not available.")
        
    # Fast-fail without stalling server threads if MySQL is in failure cooldown
    if time.time() - _MYSQL_LAST_ERROR < _MYSQL_ERROR_COOLDOWN:
        raise Exception("MySQL connection currently in fast-fail cooldown due to recent error.")

    try:
        return pymysql.connect(
            host=os.environ.get('MYSQL_HOST', 'localhost'),
            user=os.environ.get('MYSQL_USER', 'root'),
            password=os.environ.get('MYSQL_PASSWORD', ''),
            database=db_name,
            port=int(os.environ.get('MYSQL_PORT', 3306)),
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=2
        )
    except Exception as e:
        _MYSQL_LAST_ERROR = time.time()
        raise e

def get_schema_dict(schema_name):
    if not schema_name:
        return {}

    now = time.time()
    if schema_name in _SCHEMA_CACHE and (now - _SCHEMA_CACHE_TIMESTAMP.get(schema_name, 0)) < _CACHE_TTL:
        return _SCHEMA_CACHE[schema_name]

    schema_dict = {}
    if not MYSQL_AVAILABLE:
        return schema_dict

    try:
        conn = get_mysql_connection(db_name=schema_name)
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [list(row.values())[0] for row in cursor.fetchall()]
            for table in tables:
                cursor.execute(f"DESCRIBE `{table}`")
                cols = cursor.fetchall()
                schema_dict[table] = {col['Field']: col['Type'] for col in cols}
        conn.close()
        _SCHEMA_CACHE[schema_name] = schema_dict
        _SCHEMA_CACHE_TIMESTAMP[schema_name] = now
    except Exception:
        pass
    return schema_dict

# Initialize Central Multi-Agent Adaptive Orchestrator
orchestrator = MultiAgentOrchestrator(mysql_connector_fn=get_mysql_connection)

# ==========================================
# 1. DATABASE INITIALIZATION & SEEDING
# ==========================================
def init_databases():
    # MySQL authentication & history tables (Primary SQL Database)
    if MYSQL_AVAILABLE:
        try:
            # First, connect to MySQL without selecting a database and create 'history' database
            conn_root = get_mysql_connection()
            with conn_root.cursor() as cursor_root:
                cursor_root.execute("CREATE DATABASE IF NOT EXISTS history")
            conn_root.commit()
            conn_root.close()

            # Connect to 'history' database and initialize the tables
            conn = get_mysql_connection('history')
            with conn.cursor() as cursor:
                # Create users table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        username VARCHAR(255) NOT NULL,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        password VARCHAR(255) NOT NULL
                    )
                ''')
                # Seed default user if not exists
                cursor.execute("SELECT * FROM users WHERE email='neo@matrix.com'")
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", 
                                   ('Neo', 'neo@matrix.com', 'password123'))
                
                # Create query_history table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS query_history (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_email VARCHAR(255) NOT NULL,
                        english_query TEXT NOT NULL,
                        sql_query TEXT NOT NULL,
                        schema_name VARCHAR(255) NOT NULL,
                        engine VARCHAR(255) NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            conn.commit()
            conn.close()
            print("MySQL 'history' database and tables initialized successfully.")
        except Exception as e:
            print(f"MySQL database tables init error: {e}")

# Run init DBs
init_databases()

# ==========================================
# 2. ROUTING & TEMPLATE SERVING
# ==========================================
@app.before_request
def ensure_default_session():
    if 'username' not in session:
        session['username'] = 'Operator'
        session['email'] = 'operator@querycraft.ai'

@app.route('/')
@app.route('/index.html')
def index():
    return render_template('dashboard.html')

@app.route('/dashboard')
@app.route('/dashboard/')
@app.route('/dashboard.html')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/status')
def api_status():
    return jsonify({
        'status': 'online',
        'message': 'QueryCraft AI Unified Service',
        'mysql_available': MYSQL_AVAILABLE
    })

# ==========================================
# 3. AUTHENTICATION API
# ==========================================
@app.route('/api/auth/signup', methods=['POST'])
def signup():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not username or not email or not password:
        return jsonify({'success': False, 'message': 'Missing user parameters.'}), 400

    # Write to MySQL
    if MYSQL_AVAILABLE:
        try:
            conn = get_mysql_connection('history')
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", 
                               (username, email, password))
            conn.commit()
            conn.close()
            session['username'] = username
            session['email'] = email
            return jsonify({'success': True, 'username': username})
        except Exception as e:
            err_str = str(e)
            if '1062' in err_str or 'Duplicate' in err_str:
                return jsonify({'success': False, 'message': 'Email already registered.'}), 409
            return jsonify({'success': False, 'message': f"Database registration error: {str(e)}"}), 500
    else:
        return jsonify({'success': False, 'message': 'Database service unavailable.'}), 503

@app.route('/api/auth/signin', methods=['POST'])
def signin():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'success': False, 'message': 'Missing credentials.'}), 400

    user = None
    if MYSQL_AVAILABLE:
        try:
            conn = get_mysql_connection('history')
            with conn.cursor() as cursor:
                cursor.execute("SELECT username, email FROM users WHERE email=%s AND password=%s", (email, password))
                user = cursor.fetchone()
            conn.close()
        except Exception as e:
            return jsonify({'success': False, 'message': f"Database connection error: {str(e)}"}), 500
    else:
        return jsonify({'success': False, 'message': 'Database service unavailable.'}), 503

    if user:
        session['username'] = user['username']
        session['email'] = user['email']
        return jsonify({'success': True, 'username': user['username']})
    else:
        return jsonify({'success': False, 'message': 'Invalid credentials.'}), 401

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.pop('username', None)
    session.pop('email', None)
    return jsonify({'success': True})

@app.route('/api/auth/me', methods=['GET'])
def get_me():
    username = session.get('username', 'Operator')
    email = session.get('email', 'operator@querycraft.ai')
    return jsonify({'authenticated': True, 'username': username, 'email': email})

@app.route('/api/auth/google', methods=['POST'])
def google_auth():
    data = request.get_json() or {}
    credential = data.get('credential')
    if not credential:
        return jsonify({'success': False, 'message': 'Missing Google credential token.'}), 400

    try:
        parts = credential.split('.')
        if len(parts) != 3:
            return jsonify({'success': False, 'message': 'Invalid JWT token format.'}), 400
        
        payload_b64 = parts[1]
        payload_b64 += '=' * (-len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64).decode('utf-8')
        user_info = json.loads(payload_json)
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to decode Google token: {str(e)}'}), 400

    email = user_info.get('email', '').strip().lower()
    name = user_info.get('name', '').strip() or user_info.get('given_name', '').strip() or 'Google User'

    if not email:
        return jsonify({'success': False, 'message': 'Google token did not contain email.'}), 400

    user = None
    # Try MySQL
    if MYSQL_AVAILABLE:
        try:
            conn = get_mysql_connection('history')
            with conn.cursor() as cursor:
                cursor.execute("SELECT username, email FROM users WHERE email=%s", (email,))
                user = cursor.fetchone()
                
                if not user:
                    random_password = secrets.token_hex(16)
                    cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", 
                                   (name, email, random_password))
                    conn.commit()
                    user = {'username': name, 'email': email}
            conn.close()
        except Exception as e:
            return jsonify({'success': False, 'message': f"Google auth database error: {str(e)}"}), 500
    else:
        return jsonify({'success': False, 'message': 'Database service unavailable.'}), 503

    if user:
        session['username'] = user['username']
        session['email'] = user['email']
        return jsonify({'success': True, 'username': user['username']})
    else:
        return jsonify({'success': False, 'message': 'Authentication failed.'}), 500

# ==========================================
# 4. TRANSLATION & EXECUTION API
# ==========================================

# Dynamic schema context generator to feed into LLMs
def get_schema_context(schema_name):
    context = []
    try:
        conn = get_mysql_connection(db_name=schema_name)
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [list(row.values())[0] for row in cursor.fetchall()]
            for table in tables:
                cursor.execute(f"DESCRIBE `{table}`")
                cols = cursor.fetchall()
                col_desc = [f"{col['Field']} {col['Type']}" for col in cols]
                context.append(f"Table '{table}' columns: {', '.join(col_desc)}")
        conn.close()
    except Exception as e:
        context.append(f"MySQL connection error: {str(e)}")
    return "\n".join(context)

# Helper to split raw LLM output into clean SQL and simulated output
def split_sql_and_output(text):
    text = text.replace('\r\n', '\n').strip()
    
    # Try regex matching first for code block split
    pattern = r'^```(?:sql)?\n(.*?)\n```(.*)$'
    match = re.match(pattern, text, re.DOTALL | re.IGNORECASE)
    
    if match:
        sql_part = match.group(1).strip()
        output_part = match.group(2).strip()
    else:
        # Split at common result delimiters
        parts = re.split(r'(?mi)(?:\n|^)\s*(?:result|output|simulated|response|execution)\b:?|\n\s*```|\n\s*\|', text, maxsplit=1)
        if len(parts) == 2:
            sql_part = parts[0].strip()
            sep_match = re.search(r'(?mi)(?:\n|^)\s*(?:result|output|simulated|response|execution)\b:?|\n\s*```|\n\s*\|', text)
            sep = sep_match.group(0) if sep_match else ""
            if '|' in sep:
                output_part = ('|' + parts[1]).strip()
            else:
                output_part = parts[1].strip()
        else:
            # Fallback split on semicolon
            semicolon_parts = text.split(';', 1)
            if len(semicolon_parts) == 2 and len(semicolon_parts[1].strip()) > 0:
                sql_part = semicolon_parts[0].strip() + ";"
                output_part = semicolon_parts[1].strip()
            else:
                sql_part = text
                output_part = ""

    # Clean up closing backticks and extra spacing from sql_part
    sql_part = sql_part.strip()
    if sql_part.startswith("```"):
        sql_part = re.sub(r'^```sql\s*', '', sql_part, flags=re.IGNORECASE)
        sql_part = re.sub(r'^```\s*', '', sql_part)
    if sql_part.endswith("```"):
        sql_part = re.sub(r'\s*```$', '', sql_part)
    sql_part = sql_part.strip()
    
    # Clean up output_part
    output_part = output_part.strip()
    output_part = re.sub(r'^(?i)(?:result|output|simulated|response|execution)\b:?\s*', '', output_part)
    output_part = re.sub(r'^```(?:markdown|text|sql)?\s*', '', output_part, flags=re.IGNORECASE)
    output_part = re.sub(r'\s*```$', '', output_part)
    output_part = output_part.strip()
    
    return sql_part, output_part

# Translate English to SQL using Google Gemini API beta endpoint
def translate_with_gemini(english, schema_name, api_key):
    schema_context = get_schema_context(schema_name)
    system_prompt = os.environ.get('SYSTEM_PROMPT', 'You are a precise English-to-SQL translator for a SQLite database. Given the database schema, translate the English query into a single valid SQLite query. Return ONLY the raw SQL code. Do not include markdown code blocks, backticks, or any conversational text.').strip()
    system_prompt = system_prompt.replace('SQLite', 'MySQL').replace('sqlite', 'mysql')
    
    user_prompt = f"""Database Schema:
{schema_context}

English Request: "{english}"

SQL Query:"""

    candidate_models = [
        os.environ.get('GEMINI_MODEL', 'gemini-flash-latest'),
        "gemini-flash-latest",
        "gemini-2.5-flash",
    ]
    unique_models = []
    for m in candidate_models:
        if m and m not in unique_models:
            unique_models.append(m)

    data = {
        "contents": [{
            "parts": [{
                "text": user_prompt
            }]
        }],
        "systemInstruction": {
            "parts": [{
                "text": system_prompt
            }]
        },
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 400
        }
    }

    last_err = None
    for model in unique_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                text = res_data['candidates'][0]['content']['parts'][0]['text']
                return text.strip()
        except Exception as e:
            last_err = e
            continue

    raise Exception(f"Gemini API Error: {str(last_err)}")

def request_gemini_key():
    """Gemini key for this request: a key pasted in the browser (X-Gemini-Key header) wins,
    otherwise the server key from .env. The key is never logged or stored on the server."""
    k = (request.headers.get('X-Gemini-Key') or '').strip()
    if k and re.fullmatch(r'[A-Za-z0-9._\-]{20,200}', k):
        return k, 'browser'
    return os.environ.get('GEMINI_API_KEY'), 'server'


# Check that the key in use can reach Gemini (lists models only: no tokens are spent)
@app.route('/api/status/check-key', methods=['POST'])
def check_gemini_key():
    load_env()
    key, source = request_gemini_key()
    if not key:
        return jsonify({'ok': False, 'key_source': 'none', 'message': 'No API key set.'})
    try:
        req = urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models?pageSize=1',
                                     headers={'x-goog-api-key': key})
        with urllib.request.urlopen(req, timeout=10) as r:
            ok = r.status == 200
        return jsonify({'ok': ok, 'key_source': source, 'message': 'Key works.' if ok else 'Key was rejected.'})
    except urllib.error.HTTPError as e:
        msg = 'Key was rejected by Google.' if e.code in (400, 401, 403) else 'Gemini returned HTTP %d.' % e.code
        return jsonify({'ok': False, 'key_source': source, 'message': msg})
    except Exception:
        return jsonify({'ok': False, 'key_source': source, 'message': 'Could not reach Gemini (network).'})


# Get current neural engine config status
@app.route('/api/status/engine', methods=['GET'])
def get_engine_status():
    load_env()
    gemini_key, key_source = request_gemini_key()
    
    active_engine = "Rule-Based Parser"
    if gemini_key:
        active_engine = "Gemini AI"
        

        
    return jsonify({
        'gemini_connected': bool(gemini_key),
        'key_source': key_source if gemini_key else 'none',
        'active_engine': active_engine
    })

# API to fetch user's query history from database
@app.route('/api/history', methods=['GET'])
def get_user_history():
    if 'email' not in session:
        return jsonify([])
        
    rows = []
    if MYSQL_AVAILABLE:
        try:
            conn = get_mysql_connection('history')
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT english_query, sql_query, schema_name, engine, timestamp FROM query_history WHERE user_email = %s ORDER BY id DESC LIMIT 10",
                    (session['email'],)
                )
                rows = cursor.fetchall()
            conn.close()
        except Exception as e:
            print(f"MySQL get_user_history error: {e}")

    history = []
    for row in rows:
        history.append({
            'english': row['english_query'],
            'sql': row['sql_query'],
            'schema': row['schema_name'],
            'engine': row['engine'],
            'timestamp': str(row['timestamp']) if row['timestamp'] else ''
        })
    return jsonify(history)

# API to save a new query history item
@app.route('/api/history', methods=['POST'])
def save_query_history():
    if 'email' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    data = request.get_json() or {}
    english = data.get('english', '').strip()
    sql = data.get('sql', '').strip()
    schema_name = data.get('schema', '').strip()
    engine = data.get('engine', '').strip()
    
    if not english or not sql:
        return jsonify({'success': False, 'message': 'Missing query data.'}), 400
        
    # Write to MySQL
    if MYSQL_AVAILABLE:
        try:
            conn = get_mysql_connection('history')
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM query_history WHERE user_email = %s AND LOWER(english_query) = LOWER(%s)",
                    (session['email'], english)
                )
                cursor.execute(
                    "INSERT INTO query_history (user_email, english_query, sql_query, schema_name, engine) VALUES (%s, %s, %s, %s, %s)",
                    (session['email'], english, sql, schema_name, engine)
                )
            conn.commit()
            conn.close()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'message': f"Database save error: {str(e)}"}), 500
    else:
        return jsonify({'success': False, 'message': 'Database service unavailable.'}), 503

# API to clear user's query history from database
@app.route('/api/history/clear', methods=['POST'])
def clear_query_history():
    if 'email' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    # Clear in MySQL
    if MYSQL_AVAILABLE:
        try:
            conn = get_mysql_connection('history')
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM query_history WHERE user_email = %s", (session['email'],))
            conn.commit()
            conn.close()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'message': f"Database clear error: {str(e)}"}), 500
    else:
        return jsonify({'success': False, 'message': 'Database service unavailable.'}), 503

# ==========================================
# 4.1 MULTI-AGENT ORCHESTRATION APIS (5 MODES)
# ==========================================
@app.route('/api/orchestrate/modes', methods=['GET'])
def get_orchestration_modes():
    return jsonify({
        'success': True,
        'modes': orchestrator.MODES
    })

@app.route('/api/orchestrate', methods=['POST'])
def orchestrate_query():
    load_env()
    data = request.get_json() or {}
    english = data.get('english', '').strip()
    schema_name = data.get('schema', 'farmers_easeuse')
    mode = data.get('mode', 'ADAPTIVE_CONFIDENCE')
    constraints = data.get('constraints', {'token_budget': 500, 'latency_budget_ms': 2500})
    
    if not english:
        return jsonify({'success': False, 'message': 'Missing English query string.'}), 400

    gemini_key, key_source = request_gemini_key()
    full_schema = get_schema_dict(schema_name)

    try:
        result = orchestrator.run(
            english=english,
            schema_name=schema_name,
            full_schema=full_schema,
            mode=mode,
            api_key=gemini_key,
            constraints=constraints
        )

        # Reuse records if already fetched by VerifierAgent to avoid duplicate database roundtrips
        if result.get('rows_preview') is not None and result.get('columns'):
            result['data'] = result['rows_preview']
            result['rows_count'] = len(result['data'])
        elif result.get('sql') and MYSQL_AVAILABLE:
            try:
                conn = get_mysql_connection(db_name=schema_name)
                with conn.cursor() as cursor:
                    sql_to_run = result['sql'].strip().rstrip(';')
                    clean_stmts = [s.strip() for s in sql_to_run.split(';') if s.strip()]
                    exec_stmt = clean_stmts[0] if clean_stmts else sql_to_run
                    cursor.execute(exec_stmt)
                    if cursor.description:
                        result['columns'] = [col[0] for col in cursor.description]
                        result['data'] = cursor.fetchall()
                        result['rows_count'] = len(result['data'])
                    else:
                        conn.commit()
                        result['affected_rows'] = cursor.rowcount
                        result['columns'] = ['STATUS']
                        result['data'] = [{'STATUS': f'Command executed successfully. Rows affected: {cursor.rowcount}'}]
                        result['rows_count'] = 1
                conn.close()
            except Exception as ex:
                result['exec_error'] = str(ex)

        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': f'Orchestration error: {str(e)}'}), 500

@app.route('/api/orchestrate/compare', methods=['POST'])
def compare_orchestrations():
    load_env()
    data = request.get_json() or {}
    english = data.get('english', '').strip()
    schema_name = data.get('schema', 'farmers_easeuse')
    
    if not english:
        return jsonify({'success': False, 'message': 'Missing English query string.'}), 400

    gemini_key, key_source = request_gemini_key()
    full_schema = get_schema_dict(schema_name)

    try:
        comparison_res = orchestrator.compare_all_modes(
            english=english,
            schema_name=schema_name,
            full_schema=full_schema,
            api_key=gemini_key
        )
        return jsonify({'success': True, **comparison_res})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Benchmark comparison error: {str(e)}'}), 500

# Translation API supporting Adaptive Multi-Agent Orchestration & fallbacks
@app.route('/api/translate', methods=['POST'])
def translate_query():
    load_env()
    data = request.get_json() or {}
    english = data.get('english', '').strip()
    schema_name = data.get('schema', 'farmers_easeuse')
    mode = data.get('mode', 'ADAPTIVE_CONFIDENCE')
    constraints = data.get('constraints', {'token_budget': 500, 'latency_budget_ms': 2500})
    
    if not english:
        return jsonify({'success': False, 'message': 'Missing english query string.'}), 400

    gemini_key, key_source = request_gemini_key()
    full_schema = get_schema_dict(schema_name)

    try:
        orch_res = orchestrator.run(
            english=english,
            schema_name=schema_name,
            full_schema=full_schema,
            mode=mode,
            api_key=gemini_key,
            constraints=constraints
        )
        engine_label = orch_res['mode_meta']['name']
        if orch_res.get('early_exit_taken'):
            engine_label += " (⚡ Fast-Path Exit)"

        # Auto-execute for immediate result rendering
        query_columns = []
        query_data = []
        if orch_res.get('sql') and MYSQL_AVAILABLE:
            try:
                conn = get_mysql_connection(db_name=schema_name)
                with conn.cursor() as cursor:
                    sql_to_run = orch_res['sql'].strip().rstrip(';')
                    clean_stmts = [s.strip() for s in sql_to_run.split(';') if s.strip()]
                    exec_stmt = clean_stmts[0] if clean_stmts else sql_to_run
                    cursor.execute(exec_stmt)
                    if cursor.description:
                        query_columns = [col[0] for col in cursor.description]
                        query_data = cursor.fetchall()
                conn.close()
            except Exception:
                pass

        return jsonify({
            'success': True,
            'sql': orch_res['sql'],
            'simulated_output': '',
            'columns': query_columns,
            'data': query_data,
            'rows_count': len(query_data),
            'engine': engine_label,
            'original_english': orch_res.get('original_english', english),
            'corrected_english': orch_res.get('corrected_english', english),
            'was_corrected': orch_res.get('was_corrected', False),
            'corrections_made': orch_res.get('corrections_made', []),
            'detected_intent': orch_res.get('detected_intent', 'QUERY'),
            'action': orch_res.get('action', 'STOP'),
            'action_policy_table': orch_res.get('action_policy_table', []),
            'orchestration': orch_res
        })
    except Exception as e:
        # Fallback to local rule-based parser if unexpected error occurs
        sql_query = translate_english_to_sql_python(english, schema_name)
        return jsonify({
            'success': True,
            'sql': sql_query,
            'simulated_output': '',
            'engine': 'Rule-Based Parser (Fallback)',
            'original_english': english,
            'corrected_english': english,
            'was_corrected': False
        })

# Execute generated SQL query on real database
@app.route('/api/execute', methods=['POST'])
def execute_sql():
    data = request.get_json() or {}
    sql = data.get('sql', '').strip()
    schema_name = data.get('schema', 'farmers_easeuse')

    if not sql:
        return jsonify({'success': False, 'message': 'No SQL statement provided.'}), 400

    if not MYSQL_AVAILABLE:
        return jsonify({'success': False, 'message': 'MySQL database client unavailable.'}), 503

    try:
        conn = get_mysql_connection(db_name=schema_name)
        with conn.cursor() as cursor:
            clean_sql = sql.strip().rstrip(';')
            clean_stmts = [s.strip() for s in clean_sql.split(';') if s.strip()]
            main_sql = clean_stmts[0] if clean_stmts else clean_sql
            cursor.execute(main_sql)
            if cursor.description:
                columns = [col[0] for col in cursor.description]
                results = cursor.fetchall()
                conn.commit()
                conn.close()
                return jsonify({'success': True, 'columns': columns, 'data': results, 'rows_count': len(results)})
            else:
                conn.commit()
                affected = cursor.rowcount
                conn.close()
                return jsonify({
                    'success': True,
                    'message': f'Command executed successfully. Rows affected: {affected}',
                    'columns': ['STATUS'],
                    'data': [{'STATUS': f'Command executed successfully. Rows affected: {affected}'}],
                    'rows_count': 1
                })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Database MySQL Compiler Error: {str(e)}'}), 500

# Create custom table schema
@app.route('/api/schema/create', methods=['POST'])
def create_custom_schema():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data = request.get_json() or {}
    table_name = data.get('table', '').strip().lower()
    columns_list = data.get('columns', []) # Array of field names

    if not table_name or not columns_list:
        return jsonify({'success': False, 'message': 'Missing table name or columns definitions.'}), 400

    # Sanitize inputs
    table_name = re.sub(r'[^a-z0-9_]', '', table_name)
    sanitized_cols = []
    for col in columns_list:
        clean_col = re.sub(r'[^a-z0-9_]', '', col.strip().lower())
        if clean_col and clean_col != 'id':
            sanitized_cols.append(f"{clean_col} VARCHAR(255)")

    if not sanitized_cols:
         return jsonify({'success': False, 'message': 'Columns must contain valid names.'}), 400

    # Build SQL definition for MySQL
    sql_create = f"CREATE TABLE IF NOT EXISTS {table_name} (id INT AUTO_INCREMENT PRIMARY KEY, {', '.join(sanitized_cols)});"
    
    try:
        # Create 'custom' database in MySQL if not exists
        conn_root = get_mysql_connection()
        with conn_root.cursor() as cursor_root:
            cursor_root.execute("CREATE DATABASE IF NOT EXISTS custom")
        conn_root.commit()
        conn_root.close()

        # Connect to 'custom' database in MySQL
        conn = get_mysql_connection('custom')
        with conn.cursor() as cursor:
            cursor.execute(sql_create)
            
            # Seed 2 mock rows automatically for the user to query
            dummy_row_fields = [c.split(' ')[0] for c in sanitized_cols]
            fields_placeholders = ', '.join(['%s'] * len(dummy_row_fields))
            fields_csv = ', '.join(dummy_row_fields)
            
            seed_vals_1 = [f"val_{f}_1" for f in dummy_row_fields]
            seed_vals_2 = [f"val_{f}_2" for f in dummy_row_fields]
            
            cursor.execute(f"INSERT INTO {table_name} ({fields_csv}) VALUES ({fields_placeholders})", seed_vals_1)
            cursor.execute(f"INSERT INTO {table_name} ({fields_csv}) VALUES ({fields_placeholders})", seed_vals_2)
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f'Table "{table_name}" created and preseeded in Custom DB.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Get active schema definitions dynamically
@app.route('/api/schema/definitions', methods=['GET'])
def get_schemas():
    definitions = {}
    
    if not MYSQL_AVAILABLE:
        return jsonify(definitions)
        
    try:
        # Connect to MySQL server level (no specific database)
        conn = get_mysql_connection()
        with conn.cursor() as cursor:
            cursor.execute("SHOW DATABASES")
            all_dbs = [list(row.values())[0] for row in cursor.fetchall()]
            
            system_dbs = {'information_schema', 'mysql', 'performance_schema', 'sys'}
            user_dbs = [db for db in all_dbs if db not in system_dbs]
            
        conn.close()
        
        for db in user_dbs:
            try:
                db_conn = get_mysql_connection(db_name=db)
                with db_conn.cursor() as db_cursor:
                    db_cursor.execute("SHOW TABLES")
                    tables = [list(row.values())[0] for row in db_cursor.fetchall()]
                    
                    definitions[db] = {}
                    for table in tables:
                        db_cursor.execute(f"DESCRIBE `{table}`")
                        cols = db_cursor.fetchall()
                        definitions[db][table] = {col['Field']: col['Type'] for col in cols}
                db_conn.close()
            except Exception as e:
                print(f"Error fetching schema for MySQL DB '{db}': {str(e)}")
                
    except Exception as e:
        print(f"MySQL connection error: {str(e)}")
        
    return jsonify(definitions)


# ==========================================
# 5. PYTHON NLP RULE-BASED TRANSLATION LOGIC
# ==========================================
def translate_english_to_sql_python(english, schema_name):
    schema_dict = get_schema_dict(schema_name)
    if not schema_dict:
        schema_dict = {"products": ["id", "name", "category", "price", "stock"]}
    try:
        refiner_res = orchestrator.refiner_agent.execute(english, schema_dict, schema_name)
        effective_english = refiner_res.get("refined_english", english)
    except Exception:
        effective_english = english
    return SemanticSQLCompiler.compile(effective_english, schema_dict, schema_name)


# Start server
if __name__ == '__main__':
    app.run(debug=True, port=5000)
