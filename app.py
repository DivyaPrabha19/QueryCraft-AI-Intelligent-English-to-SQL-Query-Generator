import os
import re
import urllib.request
import json
import base64
import secrets
try:
    import pymysql
    import pymysql.cursors
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
from flask import Flask, request, jsonify, render_template, session, redirect, url_for

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

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'cyberpunk_neural_key_1984'

def get_mysql_connection(db_name=None):
    if not MYSQL_AVAILABLE:
        raise Exception("MySQL client library (pymysql) is not available.")
        
    return pymysql.connect(
        host=os.environ.get('MYSQL_HOST', 'localhost'),
        user=os.environ.get('MYSQL_USER', 'root'),
        password=os.environ.get('MYSQL_PASSWORD', ''),
        database=db_name,
        port=int(os.environ.get('MYSQL_PORT', 3306)),
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=6
    )

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
# 2. PAGE SERVING ROUTES
# ==========================================
@app.route('/')
@app.route('/login')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html', google_client_id=os.environ.get('GOOGLE_CLIENT_ID', ''))

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html')

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
    if 'username' in session:
        return jsonify({'authenticated': True, 'username': session['username'], 'email': session['email']})
    return jsonify({'authenticated': False}), 401

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

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
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
            "maxOutputTokens": 250
        }
    }
    
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
        raise Exception(f"Gemini API Error: {str(e)}")

# Get current neural engine config status
@app.route('/api/status/engine', methods=['GET'])
def get_engine_status():
    load_env()
    gemini_key = os.environ.get('GEMINI_API_KEY')
    
    active_engine = "Rule-Based Parser"
    if gemini_key:
        active_engine = "Gemini AI"
        
    return jsonify({
        'gemini_connected': bool(gemini_key),
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

# Translation API supporting Gemini AI and Rule-Based fallback
@app.route('/api/translate', methods=['POST'])
def translate_query():
    load_env()
    data = request.get_json() or {}
    english = data.get('english', '').strip()
    schema_name = data.get('schema', 'ecommerce')
    
    if not english:
        return jsonify({'success': False, 'message': 'Missing english query string.'}), 400

    gemini_key = os.environ.get('GEMINI_API_KEY')

    if gemini_key:
        try:
            raw_text = translate_with_gemini(english, schema_name, gemini_key)
            sql_query, simulated_output = split_sql_and_output(raw_text)
            return jsonify({
                'success': True, 
                'sql': sql_query, 
                'simulated_output': simulated_output, 
                'engine': 'Gemini AI'
            })
        except Exception as e:
            return jsonify({'success': False, 'message': f'Gemini translation error: {str(e)}'}), 500
    else:
        # Fallback to rule-based parser
        sql_query = translate_english_to_sql_python(english, schema_name)
        return jsonify({
            'success': True, 
            'sql': sql_query, 
            'simulated_output': '', 
            'engine': 'Rule-Based Parser'
        })

# Execute generated SQL query on real SQLite database
@app.route('/api/execute', methods=['POST'])
def execute_sql():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data = request.get_json() or {}
    sql = data.get('sql', '').strip()
    schema_name = data.get('schema', 'ecommerce')

    if not sql:
        return jsonify({'success': False, 'message': 'No SQL statement provided.'}), 400

    try:
        conn = get_mysql_connection(db_name=schema_name)
        with conn.cursor() as cursor:
            cursor.execute(sql)
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
                return jsonify({'success': True, 'message': f'Command executed successfully. Rows affected: {affected}'})
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
    tables = []
    schema_cols = {}
    
    if MYSQL_AVAILABLE:
        try:
            conn = get_mysql_connection(db_name=schema_name)
            with conn.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = [list(row.values())[0] for row in cursor.fetchall()]
                for table in tables:
                    cursor.execute(f"DESCRIBE `{table}`")
                    cols = cursor.fetchall()
                    schema_cols[table] = [col['Field'] for col in cols]
            conn.close()
        except Exception as e:
            print(f"Rule-based parser MySQL schema error: {e}")

    if not tables:
        return "SELECT * FROM users;"

    query_clean = english.lower().strip()
    # Strip punctuation
    query_clean = re.sub(r'[?;,]', '', query_clean)

    target_tables = []
    for table in tables:
        # Check table names in text (singular / plural)
        singular = table[:-1] if table.endswith('s') else table
        if table in query_clean or f" {singular} " in f" {query_clean} " or f" {singular}s " in f" {query_clean} ":
            if table not in target_tables:
                target_tables.append(table)

    if not target_tables:
        target_tables.append(tables[0])

    primary_table = target_tables[0]

    # Detect aggregates
    is_count = 'count' in query_clean or 'number of' in query_clean
    is_sum = 'sum of' in query_clean or 'total ' in query_clean
    is_avg = 'average' in query_clean or 'mean of' in query_clean or 'avg of' in query_clean

    # Detect selected columns
    columns_found = []
    aggregate_field = ''
    for t in target_tables:
        if t in schema_cols:
            for col in schema_cols[t]:
                word_match = re.search(r'\b' + col + r'\b', query_clean)
                if word_match:
                    columns_found.append(f"{t}.{col}" if len(target_tables) > 1 else col)
                    if is_sum or is_avg:
                        aggregate_field = f"{t}.{col}" if len(target_tables) > 1 else col

    select_fields = ['*']
    if is_count:
        select_fields = ['COUNT(*)']
    elif is_sum and aggregate_field:
        select_fields = [f"SUM({aggregate_field})"]
    elif is_avg and aggregate_field:
        select_fields = [f"AVG({aggregate_field})"]
    elif columns_found:
        select_fields = list(set(columns_found)) # unique columns

    # Detect Join
    join_clause = ''
    if len(target_tables) > 1 or 'join' in query_clean or 'joined' in query_clean:
        if len(target_tables) == 1:
            # Look up a relation table
            for t in tables:
                if t != primary_table:
                    target_tables.append(t)
                    break
        
        t1 = target_tables[0]
        t2 = target_tables[1]
        
        # Schema-specific join logic
        if schema_name == 'ecommerce':
            if (t1 == 'users' and t2 == 'orders') or (t1 == 'orders' and t2 == 'users'):
                join_clause = f"JOIN orders ON users.id = orders.user_id" if t1 == 'users' else f"JOIN users ON orders.user_id = users.id"
            elif (t1 == 'orders' and t2 == 'order_items') or (t1 == 'order_items' and t2 == 'orders'):
                join_clause = f"JOIN order_items ON orders.id = order_items.order_id" if t1 == 'orders' else f"JOIN orders ON order_items.order_id = orders.id"
            elif (t1 == 'products' and t2 == 'order_items') or (t1 == 'order_items' and t2 == 'products'):
                join_clause = f"JOIN order_items ON products.id = order_items.product_id" if t1 == 'products' else f"JOIN products ON order_items.product_id = products.id"
        elif schema_name == 'saas':
            if t2 in ['page_views', 'events']:
                join_clause = f"JOIN {t2} ON users.id = {t2}.user_id"
            elif t1 in ['page_views', 'events']:
                join_clause = f"JOIN users ON {t1}.user_id = users.id"
        elif schema_name == 'social':
            if t2 in ['posts', 'comments']:
                join_clause = f"JOIN {t2} ON users.id = {t2}.user_id"
            elif t1 in ['posts', 'comments']:
                join_clause = f"JOIN users ON {t1}.user_id = users.id"
        else:
            # Fallback join guess
            join_clause = f"JOIN {t2} ON {t1}.id = {t2}.user_id"

    # Where filters
    where_clauses = []
    for t in target_tables:
        if t in schema_cols:
            for col in schema_cols[t]:
                field_name = f"{t}.{col}" if len(target_tables) > 1 else col
                
                # Setup regex for filters
                gt_match = re.search(r'\b' + col + r'\b\s+(?:is\s+)?(?:greater\s+than|above|>)\s+([0-9a-z_.\-:]+)', query_clean)
                lt_match = re.search(r'\b' + col + r'\b\s+(?:is\s+)?(?:less\s+than|below|<)\s+([0-9a-z_.\-:]+)', query_clean)
                eq_match = re.search(r'\b' + col + r'\b\s+(?:is\s+)?(?:equal\s+to|equals|=)?\s*["\']?([0-9a-zA-Z_.\-:@ ]+)["\']?', query_clean)
                
                if gt_match:
                    val = gt_match.group(1)
                    if val not in ['greater', 'less', 'and', 'limit', 'group', 'order']:
                        where_clauses.append(f"{field_name} > {val}")
                elif lt_match:
                    val = lt_match.group(1)
                    if val not in ['greater', 'less', 'and', 'limit', 'group', 'order']:
                        where_clauses.append(f"{field_name} < {val}")
                elif eq_match:
                    val = eq_match.group(1).strip()
                    # Skip matching keywords
                    if val in ['greater', 'less', 'and', 'limit', 'group', 'order', 'equal', 'is']:
                        continue
                    
                    # Capitalize for matches to databases seed values
                    cap_vals = {'usa': 'USA', 'canada': 'Canada', 'uk': 'UK', 'germany': 'Germany', 
                                'premium': 'Premium', 'free': 'Free', 'enterprise': 'Enterprise', 
                                'active': 'Active', 'inactive': 'Inactive', 'completed': 'Completed', 
                                'pending': 'Pending', 'shipped': 'Shipped', 'electronics': 'Electronics', 
                                'apparel': 'Apparel', 'food': 'Food'}
                    if val in cap_vals:
                        val = cap_vals[val]
                    
                    # Check if column is text (needs quotes in SQL)
                    is_numeric = False
                    if schema_name in ['ecommerce', 'saas', 'social'] and t in schema_cols:
                        # MySQL types. Let's quote strings
                        is_numeric = col in ['id', 'price', 'stock', 'user_id', 'order_id', 'product_id', 'quantity', 'age', 'likes_count', 'follower_id', 'followed_id', 'duration_sec', 'salary']
                    
                    if is_numeric:
                        where_clauses.append(f"{field_name} = {val}")
                    else:
                        where_clauses.append(f"{field_name} = '{val}'")

    # GROUP BY
    group_by = ''
    group_match = re.search(r'(?:grouped|group)\s+by\s+([a-z_0-9]+)', query_clean)
    if group_match:
        group_field = group_match.group(1)
        if len(target_tables) > 1:
            for t in target_tables:
                if t in schema_cols and group_field in schema_cols[t]:
                    group_field = f"{t}.{group_field}"
                    break
        group_by = f"GROUP BY {group_field}"
        # Adjust SELECT columns to contain group field
        if select_fields[0] == '*' or select_fields[0].startswith('COUNT'):
            if select_fields[0].startswith('COUNT'):
                select_fields.insert(0, group_field)
            else:
                select_fields = [group_field, 'COUNT(*)']

    # ORDER BY
    order_by = ''
    order_match = re.search(r'(?:ordered|sorted|order|sort)\s+by\s+([a-z_0-9]+)', query_clean)
    if order_match:
        order_field = order_match.group(1)
        if len(target_tables) > 1:
            for t in target_tables:
                if t in schema_cols and order_field in schema_cols[t]:
                    order_field = f"{t}.{order_field}"
                    break
        direction = 'DESC' if any(w in query_clean for w in ['desc', 'descending', 'highest', 'most', 'recent']) else 'ASC'
        order_by = f"ORDER BY {order_field} {direction}"

    # LIMIT
    limit = ''
    limit_match = re.search(r'(?:limit|top)\s+(\d+)', query_clean)
    if limit_match:
        limit = f"LIMIT {limit_match.group(1)}"
    elif 'top 5' in query_clean or 'recent 5' in query_clean or 'highest 5' in query_clean:
        limit = "LIMIT 5"

    # Assemble query
    sql = f"SELECT {', '.join(select_fields)}\nFROM {primary_table}"
    if join_clause:
        sql += f"\n{join_clause}"
    if where_clauses:
        sql += f"\nWHERE {' AND '.join(where_clauses)}"
    if group_by:
        sql += f"\n{group_by}"
    if order_by:
        sql += f"\n{order_by}"
    if limit:
        sql += f"\n{limit}"

    return sql + ";"

# Start server
if __name__ == '__main__':
    app.run(debug=True, port=5000)
