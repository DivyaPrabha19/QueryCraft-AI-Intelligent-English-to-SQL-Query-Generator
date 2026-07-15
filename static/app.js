/**
 * static/app.js - Dashboard Workspace Orchestrator & SQLite Compiler Bridge
 */

// Local Cache of Schemas (loaded dynamically from server SQLite databases)
let dbSchemas = {};

// Hardcoded Templates for quick-fill selections
const queryTemplates = {
  ecommerce: [
    { label: "List all products", text: "select all products" },
    { label: "Electronics > $100", text: "find products where category is Electronics and price is greater than 100" },
    { label: "US Users by name", text: "get users where country is USA ordered by name ascending" },
    { label: "Orders > $200", text: "show orders where total_amount is greater than 200" },
    { label: "Products count by category", text: "count products grouped by category" },
    { label: "Orders joined with user details", text: "select orders joined with users" }
  ],
  saas: [
    { label: "Premium users list", text: "find users where plan is Premium" },
    { label: "Active Enterprise profiles", text: "get users where plan is Enterprise and status is Active" },
    { label: "Mobile device page views", text: "select page_views where device is Mobile" },
    { label: "Total duration by url", text: "sum duration_sec of page_views grouped by url" },
    { label: "Count events by name", text: "count events grouped by event_name" }
  ],
  social: [
    { label: "Zion users over 30", text: "find users where city is Zion and age is greater than 30" },
    { label: "Posts with high likes", text: "get posts where likes_count is greater than 500 sorted by likes_count desc" },
    { label: "Comments on post #201", text: "select comments where post_id is 201" },
    { label: "Posts count by category", text: "count posts grouped by category" },
    { label: "Users joined with posts", text: "get users joined with posts" }
  ],
  custom: [
    { label: "List employees", text: "select all employees" }
  ],
  mysql: [
    { label: "Show all tables", text: "show all tables" },
    { label: "List rows", text: "select first 10 rows from my table" }
  ]
};

// Global App State
let activeSchema = 'mysql';
let lastGeneratedSQL = '';

// Helper to print messages in the simulated Terminal console on dashboard
function printConsoleLog(msg, color = 'var(--text-secondary)') {
  const consoleLogs = document.getElementById('console-logs');
  if (consoleLogs) {
    consoleLogs.innerHTML += `<div style="color: ${color}; margin-top: 2px;">${msg}</div>`;
    consoleLogs.scrollTop = consoleLogs.scrollHeight;
  }
}

// 1. FETCH DATABASE SCHEMAS DEFINITIONS FROM FLASK SERVER
function populateSchemaSelector() {
  const selector = document.getElementById('schema-selector');
  if (!selector) return;

  const dbNames = Object.keys(dbSchemas);
  if (dbNames.length === 0) {
    selector.innerHTML = '<option value="">No MySQL databases found</option>';
    activeSchema = '';
    return;
  }

  selector.innerHTML = '';
  dbNames.forEach(db => {
    const opt = document.createElement('option');
    opt.value = db;
    opt.textContent = db;
    if (db === activeSchema) {
      opt.selected = true;
    }
    selector.appendChild(opt);
  });

  if (!dbNames.includes(activeSchema)) {
    activeSchema = dbNames[0];
    selector.value = activeSchema;
  }
}

function loadSchemaDefinitions(autoplay = true) {
  printConsoleLog('[SYS] Fetching MySQL database schemas...', 'var(--text-muted)');

  fetch('/api/schema/definitions')
    .then(res => res.json())
    .then(data => {
      dbSchemas = data;
      printConsoleLog('[SYS] MySQL schemas synchronized successfully.', 'var(--neon-green)');

      populateSchemaSelector();
      renderSchemaTree();
      renderTemplates();
      if (autoplay) {
        showDefaultTablePreview();
      }
    })
    .catch(err => {
      printConsoleLog('[ERROR] Failed to map SQL schema definitions.', 'var(--neon-pink)');
      console.error(err);
    });
}

// 2. RENDER ACTIVE SCHEMA TREE SIDEBAR
function renderSchemaTree() {
  const container = document.getElementById('schema-tree-container');
  if (!container) return;

  container.innerHTML = '';
  const schema = dbSchemas[activeSchema];

  if (!schema || Object.keys(schema).length === 0) {
    container.innerHTML = `
      <div style="padding: 20px; font-size:11px; text-align:center; color:var(--text-muted); font-family:var(--font-cyber);">
        NO TABLES DETECTED IN THIS SCHEMA
      </div>
    `;
    return;
  }

  for (const table in schema) {
    const tableItem = document.createElement('div');
    tableItem.className = 'schema-tree-item';

    tableItem.innerHTML = `
      <div class="schema-table-header" data-table="${table}">
        <span class="schema-table-icon">📁</span>
        <span class="schema-table-name">${table}</span>
      </div>
      <div class="schema-columns-list" id="col-list-${table}"></div>
    `;

    container.appendChild(tableItem);

    // Render columns list
    const colListContainer = document.getElementById(`col-list-${table}`);
    const columns = schema[table];

    for (const col in columns) {
      const colType = columns[col];
      const colItem = document.createElement('div');
      colItem.className = 'schema-column-item';
      colItem.setAttribute('data-table', table);
      colItem.setAttribute('data-column', col);

      colItem.innerHTML = `
        <span class="schema-column-name"># ${col}</span>
        <span class="schema-column-type">${colType}</span>
      `;

      colListContainer.appendChild(colItem);
    }
  }

  setupClickToInsert();
}

// Click-to-insert cursor text helper
function setupClickToInsert() {
  const textarea = document.getElementById('english-input');

  // Table headers click
  document.querySelectorAll('.schema-table-header').forEach(header => {
    header.addEventListener('click', () => {
      const tableName = header.getAttribute('data-table');
      insertTextAtCursor(textarea, ` ${tableName} `);
    });
  });

  // Column items click
  document.querySelectorAll('.schema-column-item').forEach(col => {
    col.addEventListener('click', (e) => {
      e.stopPropagation();
      const colName = col.getAttribute('data-column');
      insertTextAtCursor(textarea, ` ${colName} `);
    });
  });
}

function insertTextAtCursor(inputField, textToInsert) {
  if (!inputField) return;

  const startPos = inputField.selectionStart;
  const endPos = inputField.selectionEnd;
  const currentText = inputField.value;

  inputField.value = currentText.substring(0, startPos) + textToInsert + currentText.substring(endPos);

  inputField.focus();
  const nextCursorPos = startPos + textToInsert.length;
  inputField.setSelectionRange(nextCursorPos, nextCursorPos);
}

// 3. RENDER QUICK TEMPLATE PILLS
function renderTemplates() {
  const bar = document.getElementById('templates-bar');
  if (!bar) return;

  bar.innerHTML = '';
  const templates = queryTemplates[activeSchema] || queryTemplates['mysql'] || [];

  templates.forEach(t => {
    const btn = document.createElement('button');
    btn.className = 'btn-template';
    btn.textContent = t.label;
    btn.addEventListener('click', () => {
      const input = document.getElementById('english-input');
      if (input) {
        input.value = t.text;
        input.focus();
      }
    });
    bar.appendChild(btn);
  });
}

// 4. SYNTAX HIGHLIGHTER FOR SQL TERMINAL DISPLAY
function highlightSQL(sql) {
  const keywords = [
    'SELECT', 'FROM', 'WHERE', 'JOIN', 'ON', 'GROUP BY', 'ORDER BY',
    'LIMIT', 'AND', 'OR', 'ASC', 'DESC', 'COUNT', 'SUM', 'AVG', 'MAX', 'MIN',
    'INSERT', 'INTO', 'VALUES', 'UPDATE', 'SET', 'DELETE'
  ];

  let formatted = sql;

  formatted = formatted.replace(/(['"].*?['"])/g, '<span class="sql-string">$1</span>');
  formatted = formatted.replace(/\b(\d+)\b/g, '<span class="sql-number">$1</span>');

  keywords.forEach(keyword => {
    const reg = new RegExp(`\\b${keyword}\\b`, 'g');
    formatted = formatted.replace(reg, `<span class="sql-keyword">${keyword}</span>`);
  });

  const operators = ['=', '>=', '<=', '!=', '+', '-', '*', '/'];
  operators.forEach(op => {
    if (op === '=') {
      formatted = formatted.replace(/(?<!class=["'])\b=\b/g, `<span class="sql-operator">=</span>`);
    }
  });

  return formatted;
}

// Helper to parse markdown table from LLM output into column/data arrays
function parseMarkdownTable(markdown) {
  if (!markdown) return null;
  const lines = markdown.trim().split('\n').map(line => line.trim());
  if (lines.length < 2) return null;

  // Filter lines that contain a pipe character
  const tableLines = lines.filter(line => line.includes('|'));
  if (tableLines.length < 2) return null;

  // Check if a line is a markdown separator (dashes and pipes)
  const isSeparator = line => /^\|?\s*:?-+:?\s*(\|?\s*:?-+:?\s*)*\|?$/.test(line) && line.includes('-');
  
  let headerIndex = -1;
  for (let i = 0; i < tableLines.length - 1; i++) {
    const nextLine = tableLines[i + 1];
    if (isSeparator(nextLine)) {
      headerIndex = i;
      break;
    }
  }

  if (headerIndex === -1) return null;

  // Clean and split row by pipe
  const splitRow = line => {
    let clean = line;
    if (clean.startsWith('|')) clean = clean.slice(1);
    if (clean.endsWith('|')) clean = clean.slice(0, -1);
    return clean.split('|').map(cell => cell.trim());
  };

  const columns = splitRow(tableLines[headerIndex]);
  const data = [];

  for (let i = headerIndex + 2; i < tableLines.length; i++) {
    const cells = splitRow(tableLines[i]);
    if (cells.length === 0 || (cells.length === 1 && cells[0] === '')) continue;
    
    const rowObj = {};
    columns.forEach((col, idx) => {
      rowObj[col] = cells[idx] !== undefined ? cells[idx] : '';
    });
    data.push(rowObj);
  }

  return { columns, data };
}

// 5. SHOW DATABASE RECORDS TABLE VIEWER (Renders Flask server outputs)
function renderDbPreviewTable(columnsArray, dataArray, optionalTableName = '') {
  const container = document.getElementById('db-table-preview');
  const badge = document.getElementById('active-table-badge');
  if (!container) return;

  if (optionalTableName && badge) {
    badge.textContent = `TABLE: ${optionalTableName}`;
  } else if (badge) {
    badge.textContent = `QUERY OUTPUT`;
  }

  if (!dataArray || dataArray.length === 0) {
    container.innerHTML = `
      <div class="simulator-empty">
        <span>EMPTY SET // 0 ROWS RETURNED</span>
      </div>
    `;
    return;
  }

  // Create Table elements
  let html = `<table class="neon-table"><thead><tr>`;

  // Headers
  columnsArray.forEach(col => {
    html += `<th>${col}</th>`;
  });
  html += `</tr></thead><tbody>`;

  // Rows
  dataArray.forEach(row => {
    html += `<tr>`;
    columnsArray.forEach(col => {
      let cellVal = row[col];
      if (cellVal === null || cellVal === undefined) cellVal = '<span style="color:var(--text-muted)">NULL</span>';
      html += `<td>${cellVal}</td>`;
    });
    html += `</tr>`;
  });

  html += `</tbody></table>`;
  container.innerHTML = html;
}

// Show active database default primary table on load
function showDefaultTablePreview() {
  const schema = dbSchemas[activeSchema];
  if (!schema) return;

  const firstTable = Object.keys(schema)[0];
  if (firstTable) {
    printConsoleLog(`[SYS] Seeding grid viewer with default table: "${firstTable}"`, 'var(--text-muted)');

    // Execute a simple SELECT query to fetch default table rows
    fetch('/api/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql: `SELECT * FROM ${firstTable} LIMIT 10;`, schema: activeSchema })
    })
      .then(res => res.json())
      .then(res => {
        if (res.success) {
          renderDbPreviewTable(res.columns, res.data, firstTable);
        }
      })
      .catch(err => console.error(err));
  }
}

// 6. RENDER RECENT TRANSLATION HISTORY
function renderHistory() {
  const container = document.getElementById('history-container');
  if (!container) return;

  container.innerHTML = '';

  fetch('/api/history')
    .then(res => res.json())
    .then(history => {
      if (!history || history.length === 0) {
        container.innerHTML = `
          <div style="text-align:center; padding:20px; font-size:11px; color:var(--text-muted); font-family:var(--font-cyber); letter-spacing:1px;">
            LOGS EMPTY
          </div>
        `;
        return;
      }

      history.forEach((item) => {
        const div = document.createElement('div');
        div.className = 'history-item';
        div.innerHTML = `
          <div class="history-item-english">${item.english}</div>
          <div class="history-item-sql">${item.sql}</div>
        `;

        div.addEventListener('click', () => {
          const input = document.getElementById('english-input');
          const terminal = document.getElementById('sql-terminal');

          if (input) input.value = item.english;
          if (terminal) {
            lastGeneratedSQL = item.sql;
            terminal.innerHTML = `
              <div class="terminal-line cmd">sql_engine --loaded_history</div>
              <div class="terminal-line sql-code-block">${highlightSQL(item.sql)}</div>
            `;
          }
        });

        container.appendChild(div);
      });
    })
    .catch(err => {
      console.error('Error fetching history:', err);
      container.innerHTML = `
        <div style="text-align:center; padding:20px; font-size:11px; color:var(--neon-pink); font-family:var(--font-cyber);">
          ERROR LOADING HISTORY
        </div>
      `;
    });
}

function addToHistory(english, sql, engine) {
  fetch('/api/history', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ english, sql, schema: activeSchema, engine })
  })
    .then(res => res.json())
    .then(res => {
      if (res.success) {
        renderHistory();
      }
    })
    .catch(err => console.error('Error saving history:', err));
}

// Helper to query backend translation engine status
function checkEngineStatus() {
  fetch('/api/status/engine')
    .then(res => res.json())
    .then(data => {
      if (data.active_engine === 'Gemini AI') {
        printConsoleLog('[SYS] Neural Engine: Gemini AI Connected (gemini-2.5-flash) // Status: ACTIVE', 'var(--neon-cyan)');
        const statusSpan = document.querySelector('.dash-status span:last-child');
        if (statusSpan) statusSpan.textContent = 'GEMINI_NEURAL_ENGINE // ONLINE';
      } else {
        printConsoleLog('[WARN] Neural Engine: API Key not found. Mode: RULE_BASED_PARSER', 'var(--neon-pink)');
        printConsoleLog('[INFO] Configure GEMINI_API_KEY in .env file to activate Neural LLM mode.', 'var(--text-muted)');
        const statusSpan = document.querySelector('.dash-status span:last-child');
        if (statusSpan) statusSpan.textContent = 'RULE_BASED_ENGINE // ACTIVE';
      }
    })
    .catch(() => {
      printConsoleLog('[ERROR] Failed to query Neural status variables.', 'var(--neon-pink)');
    });
}

// DOM Setup
document.addEventListener('DOMContentLoaded', () => {
  // Only execute dashboard logic if on dashboard page
  const pathname = window.location.pathname;
  const isDashboardPage = pathname.startsWith('/dashboard') || pathname.endsWith('dashboard.html');
  if (!isDashboardPage) return;

  // Initialize view
  loadSchemaDefinitions(true);
  checkEngineStatus();
  renderHistory();

  // Active Schema Selector handler
  const schemaSelector = document.getElementById('schema-selector');
  if (schemaSelector) {
    schemaSelector.value = activeSchema;
    schemaSelector.addEventListener('change', (e) => {
      activeSchema = e.target.value;

      // Update displays
      renderSchemaTree();
      renderTemplates();
      showDefaultTablePreview();

      printConsoleLog(`[SYS] Switched to database schema: "${activeSchema.toUpperCase()}".`, 'var(--neon-cyan)');
      
      const hasTables = dbSchemas[activeSchema] && Object.keys(dbSchemas[activeSchema]).length > 0;
      if (!hasTables) {
        printConsoleLog(`[WARN] Database "${activeSchema}" is selected but no tables were retrieved.`, 'var(--neon-pink)');
      } else {
        printConsoleLog(`[SYS] Database "${activeSchema}" connected successfully. Retrieved ${Object.keys(dbSchemas[activeSchema]).length} tables.`, 'var(--neon-green)');
      }
    });
  }

  // TRANSLATE BUTTON HANDLER (Talks to Flask API)
  const btnTranslate = document.getElementById('btn-translate');
  const englishInput = document.getElementById('english-input');
  const sqlTerminal = document.getElementById('sql-terminal');

  if (btnTranslate && englishInput && sqlTerminal) {
    btnTranslate.addEventListener('click', () => {
      const englishText = englishInput.value.trim();
      if (!englishText) {
        showNotification('Enter query description first!', 'error');
        return;
      }

      printConsoleLog(`[NLP] Sending English statement to neural compiler...`, 'var(--text-muted)');

      fetch('/api/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ english: englishText, schema: activeSchema })
      })
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            const sqlQuery = data.sql;
            const engineName = data.engine || 'Rule-Based Parser';
            lastGeneratedSQL = sqlQuery;

            // Cyberpunk matrix hacking terminal simulation
            let timer = 0;
            sqlTerminal.innerHTML = `<div class="terminal-line loading">[0.00s] INITIALIZING COMPILER BRIDGE...</div>`;

            let lines = [];
            if (engineName !== 'Rule-Based Parser') {
              lines = [
                `[0.08s] ENCODING DYNAMIC SCHEMA STRUCTS [${activeSchema.toUpperCase()}]...`,
                `[0.22s] ESTABLISHING API CONNECTIVITY TO ${engineName.toUpperCase()}...`,
                `[0.38s] SUBMITTING COGNITIVE SYNTAX MAP TO NEURAL LAYERS...`,
                `[0.55s] DECODING LLM TRANSLATED SQL RAW STRING...`,
                `[0.68s] SYNTAX COMPILATION COMPLETED.`
              ];
            } else {
              lines = [
                `[0.08s] DECONSTRUCTING STATEMENT GRAMMAR (REGEX PYTHON)...`,
                `[0.18s] ALIGNING RELATIONS IN SQLITE SCHEMA [${activeSchema.toUpperCase()}]...`,
                `[0.32s] MAP-BUILDING JOIN CHANNELS...`,
                `[0.45s] CONVERTING CONSTRAINTS AND WHERE ARGUMENTS...`,
                `[0.55s] PACKING COMPILED SQL SYNTAX BLOCKS...`,
                `[0.60s] TRANSLATION INJECTED SUCCESSFULLY.`
              ];
            }

            lines.forEach((line) => {
              timer += 80 + Math.random() * 40;
              setTimeout(() => {
                sqlTerminal.innerHTML += `<div class="terminal-line loading">${line}</div>`;
                sqlTerminal.scrollTop = sqlTerminal.scrollHeight;
              }, timer);
            });

            setTimeout(() => {
              sqlTerminal.innerHTML = `
                <div class="terminal-line cmd">sql_engine --engine="${engineName}"</div>
                <div class="terminal-line sql-code-block">${highlightSQL(sqlQuery)}</div>
              `;
              sqlTerminal.scrollTop = 0;
              printConsoleLog(`[NLP] Compiled SQL string generated via ${engineName}.`, 'var(--neon-green)');
              addToHistory(englishText, sqlQuery, engineName);

              // Render simulated output on the right-hand panel if available
              if (data.simulated_output) {
                const parsedTable = parseMarkdownTable(data.simulated_output);
                const dbTablePreview = document.getElementById('db-table-preview');
                const badge = document.getElementById('active-table-badge');
                
                if (parsedTable) {
                  renderDbPreviewTable(parsedTable.columns, parsedTable.data);
                  if (badge) badge.textContent = 'SIMULATION OUTPUT';
                } else {
                  if (dbTablePreview) {
                    if (badge) badge.textContent = 'SIMULATION OUTPUT';
                    dbTablePreview.innerHTML = `
                      <div style="padding: 20px; font-family: var(--font-mono); color: var(--neon-green); font-size: 13px; text-transform: uppercase; letter-spacing: 1px;">
                        <div style="border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 8px; margin-bottom: 12px; font-weight: bold; color: var(--neon-cyan);">[SYS] RUN COMPILATION SUCCESS</div>
                        <div>${data.simulated_output.replace(/\n/g, '<br>')}</div>
                      </div>
                    `;
                  }
                }
              }
            }, timer + 100);

          } else {
            showNotification(data.message || 'Translation failed.', 'error');
            printConsoleLog(`[ERROR] Translation pipeline failed: ${data.message}`, 'var(--neon-pink)');
          }
        })
        .catch(err => {
          showNotification('Translation pipeline unavailable.', 'error');
          printConsoleLog(`[ERROR] Connection refused to translation API gateway.`, 'var(--neon-pink)');
          console.error(err);
        });
    });
  }

  // CLEAR INPUT BUTTON
  const btnClearInput = document.getElementById('btn-clear-input');
  if (btnClearInput && englishInput) {
    btnClearInput.addEventListener('click', () => {
      englishInput.value = '';
      englishInput.focus();
    });
  }

  // CLEAR GRID BUTTON
  const btnClearGrid = document.getElementById('btn-clear-grid');
  if (btnClearGrid) {
    btnClearGrid.addEventListener('click', () => {
      const activeTableBadge = document.getElementById('active-table-badge');
      if (activeTableBadge) {
        activeTableBadge.textContent = '';
      }
      const dbTablePreview = document.getElementById('db-table-preview');
      if (dbTablePreview) {
        dbTablePreview.innerHTML = `
          <div class="simulator-empty">
            <svg class="icon-svg" viewBox="0 0 24 24" width="32" height="32" fill="currentColor" style="opacity: 0.3;">
              <path d="M12 2C6.48 2 2 4.02 2 6.5v11c0 2.48 4.48 4.5 10 4.5s10-2.02 10-4.5v-11C22 4.02 17.52 2 12 2zm0 3c4.13 0 7.5 1.25 7.5 2.5S16.13 10 12 10s-7.5-1.25-7.5-2.5S7.87 5 12 5zm0 14c-4.13 0-7.5-1.25-7.5-2.5V14c1.61 1.2 4.39 2 7.5 2s5.89-.8 7.5-2v2.5c0 1.25-3.37 2.5-7.5 2.5zm0-4.5c-4.13 0-7.5-1.25-7.5-2.5V9.5c1.61 1.2 4.39 2 7.5 2s5.89-.8 7.5-2v2.5c0 1.25-3.37 2.5-7.5 2.5z"/>
            </svg>
            <span>RUN SQL QUERY TO GENERATE OUTPUT RECORDS</span>
          </div>
        `;
      }
      showNotification('Grid cleared and returned to original state.', 'success');
      printConsoleLog('[SYS] Execution table grid cleared.', 'var(--text-muted)');
    });
  }

  // COPY SQL BUTTON
  const btnCopySql = document.getElementById('btn-copy-sql');
  if (btnCopySql) {
    btnCopySql.addEventListener('click', () => {
      if (!lastGeneratedSQL) {
        showNotification('Compile SQL query first.', 'error');
        return;
      }
      navigator.clipboard.writeText(lastGeneratedSQL).then(() => {
        showNotification('SQL copied to clipboard!', 'success');
      }).catch(() => {
        showNotification('Failed to copy text.', 'error');
      });
    });
  }

  // RUN SQL BUTTON (Executes query against SQLite backend database)
  const btnRunSql = document.getElementById('btn-run-sql');
  if (btnRunSql) {
    btnRunSql.addEventListener('click', () => {
      if (!lastGeneratedSQL) {
        showNotification('Compile SQL query first.', 'error');
        return;
      }

      printConsoleLog(`[SQL] Compiling generated query string...`, 'var(--text-muted)');
      showNotification('Compiling query in database...', 'info');

      fetch('/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sql: lastGeneratedSQL, schema: activeSchema })
      })
        .then(res => res.json())
        .then(res => {
          if (res.success) {
            if (res.columns && res.data) {
              renderDbPreviewTable(res.columns, res.data);
              printConsoleLog(`[SUCCESS] Database returned ${res.rows_count} rows. (200 OK)`, 'var(--neon-green)');
            } else {
              // Write direct success message for insert/update/delete
              printConsoleLog(`[SUCCESS] ${res.message}`, 'var(--neon-green)');
              showDefaultTablePreview(); // refresh default table preview
            }
            showNotification('SQL statement compiled and run!', 'success');
          } else {
            printConsoleLog(`[ERROR] execution failed: ${res.message}`, 'var(--neon-pink)');
            showNotification(`SQL compilation failed. Check logs.`, 'error');
          }
        })
        .catch(err => {
          showNotification('Database execution server offline.', 'error');
          console.error(err);
        });
    });
  }

  // CLEAR LOG HISTORY BUTTON
  const btnClearHistory = document.getElementById('btn-clear-history');
  if (btnClearHistory) {
    btnClearHistory.addEventListener('click', () => {
      fetch('/api/history/clear', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
      .then(res => res.json())
      .then(res => {
        if (res.success) {
          renderHistory();
          showNotification('Translation logs cleared from database.', 'info');
        } else {
          showNotification('Failed to clear logs.', 'error');
        }
      })
      .catch(err => {
        console.error('Error clearing history:', err);
        showNotification('Failed to clear logs.', 'error');
      });
    });
  }

  // CUSTOM SCHEMA CREATOR FORM TOGGLE
  const btnToggleCreator = document.getElementById('btn-toggle-creator');
  const creatorForm = document.getElementById('schema-creator-form');

  if (btnToggleCreator && creatorForm) {
    btnToggleCreator.addEventListener('click', () => {
      creatorForm.classList.toggle('open');
    });
  }

  const btnCancelSchema = document.getElementById('btn-cancel-schema');
  if (btnCancelSchema && creatorForm) {
    btnCancelSchema.addEventListener('click', () => {
      creatorForm.classList.remove('open');
    });
  }

  // CUSTOM SCHEMA FORM SAVE SUBMISSION (Saves table on Flask server database!)
  const btnSaveSchema = document.getElementById('btn-save-schema');
  if (btnSaveSchema) {
    btnSaveSchema.addEventListener('click', () => {
      const tableName = document.getElementById('new-table-name').value.trim().toLowerCase();
      const columnsCsv = document.getElementById('new-table-columns').value.trim();

      if (!tableName || !columnsCsv) {
        showNotification('Please fill in all fields!', 'error');
        return;
      }

      const cols = columnsCsv.split(',').map(c => c.trim().toLowerCase());
      if (cols.length === 0 || cols[0] === "") {
        showNotification('Table needs at least one column!', 'error');
        return;
      }

      printConsoleLog(`[SYS] Creating custom schema table: "${tableName}"`, 'var(--text-muted)');

      fetch('/api/schema/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ table: tableName, columns: cols })
      })
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            activeSchema = 'custom';
            if (schemaSelector) {
              schemaSelector.value = 'custom';
            }

            // Reset inputs
            document.getElementById('new-table-name').value = '';
            document.getElementById('new-table-columns').value = '';
            creatorForm.classList.remove('open');

            // Re-fetch everything and redraw
            loadSchemaDefinitions(true);

            showNotification(data.message, 'success');
          } else {
            showNotification(data.message || 'Failed to create table.', 'error');
          }
        })
        .catch(err => {
          showNotification('Failed to connect to schema creator.', 'error');
          console.error(err);
        });
    });
  }

});
