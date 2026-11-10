/**
 * static/app.js - Dashboard Workspace Orchestrator & MySQL Compiler Bridge
 */

// Local Cache of Schemas (loaded dynamically from server MySQL databases)
let dbSchemas = {};

// Hardcoded Templates for quick-fill selections
const queryTemplates = {
  farmers_easeuse: [
    { label: "Show all products", text: "show all products" },
    { label: "Products > $50", text: "find products with price greater than 50" },
    { label: "List farmers", text: "list all farmers" },
    { label: "Pending orders", text: "show pending orders" },
    { label: "Count total orders", text: "how many orders are there" },
    { label: "Average product price", text: "what is the average price of products" },
    { label: "Cheapest product", text: "find cheapest product" },
    { label: "Transporter details", text: "show all transportation" }
  ],
  db: [
    { label: "List all employees", text: "list all employees" },
    { label: "Workers salary > 50000", text: "find workers with salary greater than 50000" },
    { label: "CS Students", text: "find students in computer science department" },
    { label: "Active machines", text: "select machines with status active" },
    { label: "Movies with Rating A", text: "find movies with rating A" },
    { label: "Highest salary employee", text: "who is the highest paid employee" },
    { label: "Count machines", text: "how many machines" }
  ],
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
let activeOrchestrationMode = 'ADAPTIVE_CONFIDENCE';
let lastOrchestrationResult = null;
let currentTableColumns = [];
let currentTableData = [];

const orchestrationDescriptions = {
  ADAPTIVE_CONFIDENCE: "Decides dynamically at each step whether to stop reasoning or hand off to specialized agents based on multi-signal confidence, query complexity, and token budget.",
  FIXED_PIPELINE: "Unconditionally routes every query through all 5 specialized agents (Router -> Schema -> Generator -> Verifier -> Repair) regardless of query difficulty.",
  SINGLE_MODEL: "Direct monolithic single-pass prompt to Gemini AI without multi-agent decomposition, schema pruning, or self-correction.",
  CONSENSUS_VOTING: "Generates multiple candidate queries across temperature variations and selects the consensus majority based on token agreement.",
  RULE_BASED: "Local regex grammar engine operating with zero LLM API dependency and deterministic syntax rules."
};

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

  fetch(`${API_URL}/api/schema/definitions`, { credentials: 'include' })
    .then(res => res.json())
    .then(data => {
      dbSchemas = data;
      printConsoleLog('[SYS] MySQL schemas synchronized successfully.', 'var(--neon-green)');

      populateSchemaSelector();
      renderSchemaTree();
      renderTemplates();
      renderQuickTableChips();
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
  inputField.dispatchEvent(new Event('input'));

  inputField.focus();
  const nextCursorPos = startPos + textToInsert.length;
  inputField.setSelectionRange(nextCursorPos, nextCursorPos);
}

// 3. RENDER QUICK TEMPLATE PILLS
function renderTemplates() {
  const bar = document.getElementById('templates-bar');
  if (!bar) return;

  bar.innerHTML = '';
  let templates = queryTemplates[activeSchema];

  // Dynamic template generation for any MySQL database
  if (!templates && dbSchemas[activeSchema]) {
    templates = [];
    const tables = Object.keys(dbSchemas[activeSchema]);
    if (tables.length > 0) {
      const t1 = tables[0];
      templates.push({ label: `Show ${t1}`, text: `show all ${t1}` });
      templates.push({ label: `Count ${t1}`, text: `how many ${t1} are there` });
      if (tables.length > 1) {
        const t2 = tables[1];
        templates.push({ label: `List ${t2}`, text: `select all ${t2}` });
        templates.push({ label: `Count ${t2}`, text: `count ${t2}` });
      }
      const firstCols = dbSchemas[activeSchema][t1];
      if (firstCols) {
        for (const colName in firstCols) {
          const typeStr = String(firstCols[colName]).toLowerCase();
          if (colName.toLowerCase() !== 'id' && (typeStr.includes('int') || typeStr.includes('decimal') || typeStr.includes('float'))) {
            templates.push({ label: `${t1} with ${colName} > 10`, text: `find ${t1} with ${colName} greater than 10` });
            templates.push({ label: `Highest ${colName}`, text: `highest ${colName} in ${t1}` });
            break;
          }
        }
      }
    }
  }

  if (!templates || templates.length === 0) {
    templates = queryTemplates['mysql'] || [];
  }

  templates.forEach(t => {
    const btn = document.createElement('button');
    btn.className = 'btn-template';
    btn.textContent = t.label;
    btn.addEventListener('click', () => {
      const input = document.getElementById('english-input');
      if (input) {
        input.value = t.text;
        input.dispatchEvent(new Event('input'));
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

// 5. SHOW DATABASE RECORDS TABLE VIEWER (Renders live rows and columns)
function renderDbPreviewTable(columnsArray, dataArray, optionalTableName = '') {
  currentTableColumns = columnsArray || [];
  currentTableData = dataArray || [];

  const container = document.getElementById('db-table-preview');
  const badge = document.getElementById('active-table-badge');
  const filterInput = document.getElementById('grid-filter-input');
  const btnExport = document.getElementById('btn-export-csv');
  const footerBar = document.getElementById('grid-footer-bar');
  const footerDb = document.getElementById('footer-db-name');
  const footerRows = document.getElementById('footer-row-count');
  const footerCols = document.getElementById('footer-col-count');

  if (!container) return;

  const count = currentTableData ? currentTableData.length : 0;
  const colCount = currentTableColumns ? currentTableColumns.length : 0;

  if (badge) {
    if (optionalTableName) {
      badge.innerHTML = `
        <span class="grid-stat-badge" style="color:var(--neon-purple); border-color:rgba(157,13,247,0.4);">TABLE: <strong>${optionalTableName.toUpperCase()}</strong></span>
        <span class="grid-stat-badge">FIELDS: <strong>${colCount}</strong></span>
        <span class="grid-stat-badge green">ROWS: <strong>${count}</strong></span>
      `;
    } else {
      badge.innerHTML = `
        <span class="grid-stat-badge">COLUMNS: <strong>${colCount}</strong></span>
        <span class="grid-stat-badge green">ROWS: <strong>${count}</strong></span>
      `;
    }
  }

  if (footerBar) footerBar.style.display = 'flex';
  if (footerDb) {
    const valSpan = footerDb.querySelector('.val');
    if (valSpan) valSpan.textContent = activeSchema ? activeSchema.toUpperCase() : 'MYSQL';
  }
  if (footerRows) {
    const valSpan = footerRows.querySelector('.val');
    if (valSpan) valSpan.textContent = count;
  }
  if (footerCols) {
    const valSpan = footerCols.querySelector('.val');
    if (valSpan) valSpan.textContent = colCount;
  }

  if (filterInput) {
    filterInput.style.display = count > 0 ? 'inline-block' : 'none';
    filterInput.value = '';
  }
  if (btnExport) {
    btnExport.style.display = count > 0 ? 'inline-flex' : 'none';
  }

  if (!currentTableData || currentTableData.length === 0) {
    container.innerHTML = `
      <div class="simulator-empty">
        <svg class="icon-svg" viewBox="0 0 24 24" width="32" height="32" fill="currentColor" style="opacity: 0.3;">
          <path d="M12 2C6.48 2 2 4.02 2 6.5v11c0 2.48 4.48 4.5 10 4.5s10-2.02 10-4.5v-11C22 4.02 17.52 2 12 2zm0 3c4.13 0 7.5 1.25 7.5 2.5S16.13 10 12 10s-7.5-1.25-7.5-2.5S7.87 5 12 5zm0 14c-4.13 0-7.5-1.25-7.5-2.5V14c1.61 1.2 4.39 2 7.5 2s5.89-.8 7.5-2v2.5c0 1.25-3.37 2.5-7.5 2.5zm0-4.5c-4.13 0-7.5-1.25-7.5-2.5V9.5c1.61 1.2 4.39 2 7.5 2s5.89-.8 7.5-2v2.5c0 1.25-3.37 2.5-7.5 2.5z"/>
        </svg>
        <span>EMPTY SET // 0 RECORDS MATCHING QUERY</span>
      </div>
    `;
    return;
  }

  renderTableRows(currentTableColumns, currentTableData);
}

// Render HTML rows for active data set
function renderTableRows(columnsArray, dataArray) {
  const container = document.getElementById('db-table-preview');
  if (!container) return;

  if (!dataArray || dataArray.length === 0) {
    container.innerHTML = `
      <div class="simulator-empty">
        <span>NO MATCHING ROWS FOUND FOR FILTER</span>
      </div>
    `;
    return;
  }

  let html = `<table class="neon-table"><thead><tr>`;
  html += `<th class="th-index">#</th>`;
  columnsArray.forEach(col => {
    html += `<th>${col}</th>`;
  });
  html += `</tr></thead><tbody>`;

  dataArray.forEach((row, idx) => {
    html += `<tr>`;
    html += `<td class="td-index">${idx + 1}</td>`;
    columnsArray.forEach(col => {
      let cellVal = row[col];
      if (cellVal === null || cellVal === undefined) {
        cellVal = '<span style="color:var(--text-muted); font-size:10px;">NULL</span>';
      }
      html += `<td>${cellVal}</td>`;
    });
    html += `</tr>`;
  });

  html += `</tbody></table>`;
  container.innerHTML = html;
}

// Export active table dataset to CSV file
function exportTableToCSV(columnsArray, dataArray, filename = 'query_results.csv') {
  if (!dataArray || dataArray.length === 0) return;
  const headers = columnsArray.join(',');
  const rows = dataArray.map(row => 
    columnsArray.map(col => {
      let val = row[col] === null || row[col] === undefined ? '' : String(row[col]);
      if (val.includes(',') || val.includes('"') || val.includes('\n')) {
        val = `"${val.replace(/"/g, '""')}"`;
      }
      return val;
    }).join(',')
  );
  const csvContent = 'data:text/csv;charset=utf-8,' + [headers, ...rows].join('\n');
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement('a');
  link.setAttribute('href', encodedUri);
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// Render quick table chips in right sidebar
function renderQuickTableChips() {
  const container = document.getElementById('quick-tables-chips');
  if (!container) return;
  container.innerHTML = '';

  const schema = dbSchemas[activeSchema];
  if (!schema || Object.keys(schema).length === 0) {
    container.innerHTML = '<span style="font-size:10px; color:var(--text-muted); font-family:var(--font-mono);">No tables detected</span>';
    return;
  }

  Object.keys(schema).forEach(table => {
    const btn = document.createElement('button');
    btn.className = 'quick-table-btn';
    btn.textContent = table;
    btn.title = `Fetch all rows & columns for "${table}"`;
    btn.addEventListener('click', () => {
      document.querySelectorAll('.quick-table-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      printConsoleLog(`[TABLE] Fetching table rows: "${table}"`, 'var(--neon-purple)');
      
      fetch(`${API_URL}/api/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sql: `SELECT * FROM ${table} LIMIT 50;`, schema: activeSchema }),
        credentials: 'include'
      })
        .then(r => r.json())
        .then(r => {
          if (r.success && r.data && r.columns) {
            renderDbPreviewTable(r.columns, r.data, table);
            printConsoleLog(`[DB] Retrieved ${r.data.length} records from "${table}".`, 'var(--neon-green)');
            const previewCard = document.getElementById('db-preview-card');
            if (previewCard) previewCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }
        })
        .catch(err => console.error(err));
    });
    container.appendChild(btn);
  });
}

// Show active database default primary table on load
function showDefaultTablePreview() {
  const schema = dbSchemas[activeSchema];
  if (!schema) return;

  const firstTable = Object.keys(schema)[0];
  if (firstTable) {
    printConsoleLog(`[SYS] Seeding grid viewer with default table: "${firstTable}"`, 'var(--text-muted)');

    // Execute a simple SELECT query to fetch default table rows
    fetch(`${API_URL}/api/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql: `SELECT * FROM ${firstTable} LIMIT 20;`, schema: activeSchema }),
      credentials: 'include'
    })
      .then(res => res.json())
      .then(res => {
        if (res.success && res.columns && res.data) {
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

  fetch(`${API_URL}/api/history`, { credentials: 'include' })
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
  fetch(`${API_URL}/api/history`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ english, sql, schema: activeSchema, engine }),
    credentials: 'include'
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
  fetch(`${API_URL}/api/status/engine`, { credentials: 'include' })
    .then(res => res.json())
    .then(data => {
      if (data.active_engine === 'Gemini AI') {
        printConsoleLog('[SYS] Neural Engine: Gemini AI Connected (' + (data.key_source === 'browser' ? 'your key' : 'server key') + ') // Status: ACTIVE', 'var(--neon-cyan)');
        const statusSpan = document.querySelector('.dash-status span:last-child');
        if (statusSpan) statusSpan.textContent = 'GEMINI_NEURAL_ENGINE // ONLINE';
      } else {
        printConsoleLog('[WARN] Neural Engine: API Key not found. Mode: RULE_BASED_PARSER', 'var(--neon-pink)');
        printConsoleLog('[INFO] Paste a Gemini API key in the top bar, or set GEMINI_API_KEY in .env, to activate Neural LLM mode.', 'var(--text-muted)');
        const statusSpan = document.querySelector('.dash-status span:last-child');
        if (statusSpan) statusSpan.textContent = 'RULE_BASED_ENGINE // ACTIVE';
      }
    })
    .catch(() => {
      printConsoleLog('[ERROR] Failed to query Neural status variables.', 'var(--neon-pink)');
    });
}

// ==========================================================================
// MULTI-AGENT ORCHESTRATION HELPERS & VISUAL TRAJECTORY ENGINE
// ==========================================================================

function setupOrchestrationControls() {
  const modeTabs = document.querySelectorAll('.btn-mode-tab');
  const descText = document.getElementById('mode-desc-text');
  const engineBadge = document.getElementById('output-engine-badge');

  modeTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      modeTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      activeOrchestrationMode = tab.dataset.mode;

      if (descText && orchestrationDescriptions[activeOrchestrationMode]) {
        descText.textContent = orchestrationDescriptions[activeOrchestrationMode];
      }

      const modeTitle = tab.querySelector('.mode-tab-title');
      if (engineBadge && modeTitle) {
        engineBadge.textContent = modeTitle.textContent.toUpperCase();
      }

      printConsoleLog(`[ORCHESTRATOR] Paradigm selected: ${activeOrchestrationMode}`, 'var(--neon-cyan)');
    });
  });

  // Modal close handlers
  const btnCloseBenchmark = document.getElementById('btn-close-benchmark');
  const benchmarkModal = document.getElementById('benchmark-modal');
  if (btnCloseBenchmark && benchmarkModal) {
    btnCloseBenchmark.addEventListener('click', () => {
      benchmarkModal.style.display = 'none';
    });
  }

  const btnCloseInspector = document.getElementById('btn-close-inspector');
  const inspectorModal = document.getElementById('inspector-modal');
  if (btnCloseInspector && inspectorModal) {
    btnCloseInspector.addEventListener('click', () => {
      inspectorModal.style.display = 'none';
    });
  }

  // Benchmark button handler
  const btnOpenBenchmark = document.getElementById('btn-open-benchmark');
  if (btnOpenBenchmark) {
    btnOpenBenchmark.addEventListener('click', () => {
      const englishInput = document.getElementById('english-input');
      const query = (englishInput && englishInput.value.trim()) || 'Find all users from USA ordered by name';
      runBenchmarkComparison(query);
    });
  }

  // Agent Node Click Listeners for Inspection
  const agentNodes = document.querySelectorAll('.agent-node');
  agentNodes.forEach(node => {
    node.addEventListener('click', () => {
      const agentKey = node.dataset.agent;
      openAgentInspector(agentKey);
    });
  });

  // Diagnostics Drawer Toggle Handler
  const btnToggleDiag = document.getElementById('btn-toggle-diagnostics');
  const diagDrawer = document.getElementById('agent-diagnostics-drawer');
  const diagArrow = document.getElementById('diag-toggle-arrow');
  if (btnToggleDiag && diagDrawer) {
    btnToggleDiag.addEventListener('click', () => {
      const isHidden = diagDrawer.style.display === 'none' || !diagDrawer.style.display;
      diagDrawer.style.display = isHidden ? 'block' : 'none';
      if (diagArrow) diagArrow.textContent = isHidden ? '▴' : '▾';
    });
  }

  // Live Word & Character Counter for English Query Writing Studio
  const englishInputArea = document.getElementById('english-input');
  const charWordCount = document.getElementById('char-word-count');
  if (englishInputArea && charWordCount) {
    const updateCount = () => {
      const text = englishInputArea.value;
      const chars = text.length;
      const words = text.trim() ? text.trim().split(/\s+/).length : 0;
      charWordCount.textContent = `${chars} characters (${words} words)`;
    };
    englishInputArea.addEventListener('input', updateCount);
    updateCount();

    // Ctrl + Enter shortcut to trigger translation
    englishInputArea.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        const btnTranslate = document.getElementById('btn-translate');
        if (btnTranslate) btnTranslate.click();
      }
    });
  }
}

function resetPipelineUI() {
  // 1. Reset background diagnostics nodes
  const nodeIds = ['router', 'schema', 'generator', 'verifier', 'repair'];
  nodeIds.forEach(id => {
    const node = document.getElementById(`node-agent-${id}`);
    const badge = document.getElementById(`badge-agent-${id}`);
    const meta = document.getElementById(`meta-agent-${id}`);
    if (node) {
      node.className = 'agent-node status-pending';
    }
    if (badge) badge.textContent = 'IDLE';
    if (meta) meta.textContent = '0.0ms';
  });

  const connectors = document.querySelectorAll('.pipeline-connector');
  connectors.forEach(c => c.classList.remove('active'));

  const statusBadge = document.getElementById('pipeline-status-badge');
  if (statusBadge) {
    statusBadge.textContent = 'RUNNING';
    statusBadge.className = 'badge-mini';
  }

  // 2. Reset Live Working Monitor (Shows only the working of the agents)
  const workingCard = document.getElementById('agent-working-card');
  if (workingCard) workingCard.classList.add('working-active');

  const idleMsg = document.getElementById('working-idle-msg');
  if (idleMsg) idleMsg.style.display = 'none';

  const workingStepper = document.getElementById('working-stepper');
  if (workingStepper) workingStepper.style.display = 'flex';

  const workingLiveLine = document.getElementById('working-live-line');
  if (workingLiveLine) workingLiveLine.style.display = 'flex';

  const workingStatusBadge = document.getElementById('working-status-badge');
  if (workingStatusBadge) {
    workingStatusBadge.textContent = 'WORKING...';
    workingStatusBadge.className = 'working-status-badge working';
  }

  const workingPulseDot = document.getElementById('working-pulse-dot');
  if (workingPulseDot) workingPulseDot.className = 'working-pulse-dot pulsing';

  const workingTelemetry = document.getElementById('working-telemetry-compact');
  if (workingTelemetry) workingTelemetry.style.display = 'flex';

  nodeIds.forEach(id => {
    const wstep = document.getElementById(`wstep-${id}`);
    const wstate = document.getElementById(`wstate-${id}`);
    if (wstep) wstep.className = 'working-step status-pending';
    if (wstate) wstate.textContent = 'QUEUED';
  });

  for (let i = 1; i <= 4; i++) {
    const wconn = document.getElementById(`wconn-${i}`);
    if (wconn) wconn.classList.remove('active');
  }

  const workingLiveText = document.getElementById('working-live-text');
  if (workingLiveText) {
    workingLiveText.textContent = `[Step 1/5] Dispatching query to Router Agent (${activeOrchestrationMode})...`;
  }

  // 3. Reset Confidence HUD elements
  const totalConf = document.getElementById('hud-total-confidence');
  if (totalConf) totalConf.textContent = '--%';
  const thresholdTag = document.getElementById('hud-threshold-tag');
  if (thresholdTag) thresholdTag.textContent = 'Threshold: --%';

  const pillComplexity = document.getElementById('pill-complexity');
  if (pillComplexity) pillComplexity.textContent = 'ANALYZING...';
  const pillTokens = document.getElementById('pill-tokens-saved');
  if (pillTokens) pillTokens.textContent = '--%';
  const pillLatency = document.getElementById('pill-latency-saved');
  if (pillLatency) pillLatency.textContent = '--%';
  const pillDecision = document.getElementById('pill-decision');
  if (pillDecision) pillDecision.textContent = 'EVALUATING';

  ['model', 'exec', 'verifier', 'agreement'].forEach(k => {
    const fill = document.getElementById(`meter-fill-${k}`);
    const val = document.getElementById(`sig-val-${k}`);
    if (fill) fill.style.width = '0%';
    if (val) val.textContent = '--%';
  });
}

function animatePipelineTrajectory(data) {
  if (!data || !data.trajectory) return;

  const agentMap = {
    'router': 'router',
    'schema_linker': 'schema',
    'sql_generator': 'generator',
    'verifier': 'verifier',
    'repair': 'repair',
    'single_model': 'generator',
    'voting_generator': 'generator',
    'rule_parser': 'generator'
  };

  data.trajectory.forEach((step, idx) => {
    const domKey = agentMap[step.agent_id] || 'generator';
    const node = document.getElementById(`node-agent-${domKey}`);
    const badge = document.getElementById(`badge-agent-${domKey}`);
    const meta = document.getElementById(`meta-agent-${domKey}`);
    const conn = document.getElementById(`conn-${idx}-${idx+1}`);

    // Live working stepper elements
    const wstep = document.getElementById(`wstep-${domKey}`);
    const wstate = document.getElementById(`wstate-${domKey}`);
    const wconn = document.getElementById(`wconn-${idx}`);
    const workingLiveText = document.getElementById('working-live-text');

    setTimeout(() => {
      // 1. Update background diagnostics card
      if (node && badge) {
        if (step.status === 'PASSED') {
          node.className = 'agent-node status-passed';
          badge.textContent = 'PASSED';
        } else if (step.status === 'STOP_SATISFIED' || step.status.startsWith('VERIFY_PASS')) {
          // the verifier ran and its check passed (STOP_SATISFIED = all stopping conditions met)
          node.className = 'agent-node status-passed';
          badge.textContent = step.status === 'STOP_SATISFIED' ? 'PASSED · STOP' : 'PASSED';
        } else if (step.status === 'BYPASSED_EARLY_EXIT') {
          node.className = 'agent-node status-bypassed';
          badge.textContent = '⚡ FAST EXIT';
        } else if (step.status === 'BYPASSED_NOT_NEEDED') {
          node.className = 'agent-node status-bypassed';
          badge.textContent = 'BYPASSED';
        } else if (step.status.includes('ERROR') || step.status.includes('ESCALATED')) {
          node.className = 'agent-node status-escalated';
          badge.textContent = '🚨 DEFECT';
        } else if (step.status === 'CORRECTED') {
          node.className = 'agent-node status-corrected';
          badge.textContent = '✅ REPAIRED';
        }
        if (meta) meta.textContent = `${step.duration_ms}ms`;
      }
      if (conn) conn.classList.add('active');

      // 2. Update visible Live Working Monitor (shows only the working of them!)
      if (wstep && wstate) {
        if (step.status === 'PASSED') {
          wstep.className = 'working-step status-passed';
          wstate.textContent = `PASSED (${step.duration_ms}ms)`;
        } else if (step.status === 'STOP_SATISFIED' || step.status.startsWith('VERIFY_PASS')) {
          wstep.className = 'working-step status-passed';
          wstate.textContent = step.status === 'STOP_SATISFIED' ? `PASSED · STOP (${step.duration_ms}ms)` : `PASSED (${step.duration_ms}ms)`;
        } else if (step.status === 'BYPASSED_EARLY_EXIT') {
          wstep.className = 'working-step status-bypassed';
          wstate.textContent = '⚡ FAST EXIT';
        } else if (step.status === 'BYPASSED_NOT_NEEDED') {
          wstep.className = 'working-step status-bypassed';
          wstate.textContent = 'BYPASSED';
        } else if (step.status.includes('ERROR') || step.status.includes('ESCALATED')) {
          wstep.className = 'working-step status-escalated';
          wstate.textContent = 'DEFECT DETECTED';
        } else if (step.status === 'CORRECTED') {
          wstep.className = 'working-step status-repaired';
          wstate.textContent = `REPAIRED (${step.duration_ms}ms)`;
        }
      }
      if (wconn) wconn.classList.add('active');

      // Update live status line with the active action being performed
      if (workingLiveText) {
        const actionSnippet = step.action || 'Executing reasoning phase...';
        workingLiveText.textContent = `▶ [Agent ${idx + 1}: ${step.agent_name}] ${actionSnippet} (${step.duration_ms}ms, ${step.tokens_used} tok)`;
      }
    }, idx * 10);
  });

  const finalDelay = data.trajectory.length * 10 + 5;
  setTimeout(() => {
    const statusBadge = document.getElementById('pipeline-status-badge');
    const workingStatusBadge = document.getElementById('working-status-badge');
    const workingPulseDot = document.getElementById('working-pulse-dot');
    const workingLiveText = document.getElementById('working-live-text');
    const workingCard = document.getElementById('agent-working-card');

    if (workingPulseDot) workingPulseDot.className = 'working-pulse-dot';
    if (workingCard) workingCard.classList.remove('working-active');

    let summaryMsg = '';
    const durationSec = ((data.metrics?.duration_ms || 350) / 1000).toFixed(2);
    const tokensSaved = data.metrics?.tokens_saved_pct || 0;

    if (data.early_exit_taken) {
      if (statusBadge) {
        statusBadge.textContent = `⚡ FAST-PATH EXIT (SAVED ${tokensSaved}%)`;
        statusBadge.style.color = 'var(--neon-green)';
      }
      if (workingStatusBadge) {
        workingStatusBadge.textContent = '⚡ FAST-PATH EXIT';
        workingStatusBadge.className = 'working-status-badge passed';
      }
      summaryMsg = `✅ Collaborative synthesis complete in ${durationSec}s // Early-exit triggered at step 3 (Saved ${tokensSaved}% tokens) // Confidence: ${((data.confidence?.total_confidence || 0.95) * 100).toFixed(1)}%`;
    } else if (data.repaired) {
      if (statusBadge) {
        statusBadge.textContent = '✅ REPAIRED & VERIFIED';
        statusBadge.style.color = '#ffd700';
      }
      if (workingStatusBadge) {
        workingStatusBadge.textContent = '✅ REPAIRED & VERIFIED';
        workingStatusBadge.className = 'working-status-badge repaired';
      }
      summaryMsg = `✅ Collaborative synthesis complete in ${durationSec}s // Defect autonomously detected and self-corrected by Repair Agent.`;
    } else {
      if (statusBadge) {
        statusBadge.textContent = '✅ PIPELINE COMPLETE';
        statusBadge.style.color = 'var(--neon-cyan)';
      }
      if (workingStatusBadge) {
        workingStatusBadge.textContent = '✅ COMPLETED';
        workingStatusBadge.className = 'working-status-badge passed';
      }
      summaryMsg = `✅ Multi-Agent Collaboration complete in ${durationSec}s // All active specialized agents verified query syntax & execution plan.`;
    }

    if (workingLiveText) {
      workingLiveText.textContent = summaryMsg;
    }
  }, finalDelay);
}

function updateConfidenceHUD(data) {
  if (!data) return;

  const conf = data.confidence || {};
  const metrics = data.metrics || {};
  const complexity = data.complexity || {};

  // Update visible compact telemetry in the live working monitor
  const workingConfVal = document.getElementById('working-conf-val');
  if (workingConfVal && conf.total_confidence !== undefined) {
    workingConfVal.textContent = `${(conf.total_confidence * 100).toFixed(1)}%`;
  }
  const workingTokensVal = document.getElementById('working-tokens-val');
  if (workingTokensVal && metrics.tokens_saved_pct !== undefined) {
    workingTokensVal.textContent = `${metrics.tokens_saved_pct}%`;
  }
  const workingLatencyVal = document.getElementById('working-latency-val');
  if (workingLatencyVal && metrics.duration_ms !== undefined) {
    workingLatencyVal.textContent = `${metrics.duration_ms}ms`;
  }

  // Total Confidence
  const hudTotal = document.getElementById('hud-total-confidence');
  if (hudTotal && conf.total_confidence !== undefined) {
    hudTotal.textContent = `${(conf.total_confidence * 100).toFixed(1)}%`;
  }

  // Threshold Tag
  const hudThreshold = document.getElementById('hud-threshold-tag');
  if (hudThreshold && conf.threshold !== undefined) {
    hudThreshold.textContent = `Exit Threshold: ${(conf.threshold * 100).toFixed(1)}%`;
  }

  // Telemetry Pills
  const pillComplexity = document.getElementById('pill-complexity');
  if (pillComplexity && complexity.category) {
    pillComplexity.textContent = `${complexity.category} (${complexity.complexity_score || '0.2'})`;
  }

  const pillTokens = document.getElementById('pill-tokens-saved');
  if (pillTokens && metrics.tokens_saved_pct !== undefined) {
    pillTokens.textContent = `${metrics.tokens_saved_pct}% (${metrics.total_tokens || 0} tok)`;
  }

  const pillLatency = document.getElementById('pill-latency-saved');
  if (pillLatency && metrics.latency_saved_pct !== undefined) {
    pillLatency.textContent = `${metrics.latency_saved_pct}% (${metrics.duration_ms || 0}ms)`;
  }

  const pillDecision = document.getElementById('pill-decision');
  if (pillDecision && conf.action) {
    pillDecision.textContent = conf.action.replace(/_/g, ' ');
    pillDecision.className = 'pill-value';
    const actionUpper = conf.action.toUpperCase();
    if (actionUpper === 'STOP') {
      pillDecision.classList.add('green');
      pillDecision.title = 'STOP: Confidence ≥ 0.85, execution successful, verifier ≥ 0.85 (Return final SQL answer)';
    } else if (actionUpper === 'VERIFY') {
      pillDecision.classList.add('cyan');
      pillDecision.title = 'VERIFY: Confidence 0.50–0.84, execution successful (Check semantic correctness)';
    } else if (actionUpper === 'RETRIEVE') {
      pillDecision.classList.add('yellow');
      pillDecision.title = 'RETRIEVE: Schema relevance < 0.60 (Refine schema context)';
    } else if (actionUpper === 'REPAIR') {
      pillDecision.classList.add('pink');
      pillDecision.title = 'REPAIR: Execution error or confidence < 0.50 (Correct SQL errors)';
    } else if (actionUpper.includes('MULTIPLE')) {
      pillDecision.classList.add('purple');
      pillDecision.title = 'GENERATE MULTIPLE: Confidence 0.50–0.70 with ambiguity (Generate and compare candidates)';
    } else {
      pillDecision.classList.add('cyan');
      pillDecision.title = 'GENERATE: Initial call or after retrieval update (Generate a new SQL candidate)';
    }
  }

  // Micro Meters
  const signals = [
    { key: 'model', val: conf.c_model },
    { key: 'exec', val: conf.c_exec },
    { key: 'verifier', val: conf.c_verifier },
    { key: 'agreement', val: conf.c_agreement }
  ];

  signals.forEach(s => {
    const fill = document.getElementById(`meter-fill-${s.key}`);
    const valTag = document.getElementById(`sig-val-${s.key}`);
    const pct = s.val !== undefined ? Math.round(s.val * 100) : 0;
    if (fill) fill.style.width = `${pct}%`;
    if (valTag) valTag.textContent = `${pct}%`;
  });
}

function openAgentInspector(agentKey) {
  if (!lastOrchestrationResult || !lastOrchestrationResult.trajectory) {
    showNotification('Run an orchestration query first to inspect agent traces.', 'info');
    return;
  }

  const modal = document.getElementById('inspector-modal');
  const title = document.getElementById('inspector-title');
  const content = document.getElementById('inspector-content-body');
  if (!modal || !title || !content) return;

  const agentMap = {
    'router': ['router'],
    'schema_linker': ['schema_linker', 'schema'],
    'sql_generator': ['sql_generator', 'generator', 'single_model', 'voting_generator', 'rule_parser'],
    'verifier': ['verifier'],
    'repair': ['repair']
  };

  const allowedIds = agentMap[agentKey] || [agentKey];
  const step = lastOrchestrationResult.trajectory.find(t => allowedIds.includes(t.agent_id)) || lastOrchestrationResult.trajectory[0];

  title.textContent = `[AGENT TRACE] ${step.agent_name.toUpperCase()}`;

  content.innerHTML = `
    <div class="inspector-section">
      <div class="inspector-section-title">AGENT STATUS & EXECUTION TELEMETRY</div>
      <div style="display: flex; gap: 10px; margin-bottom: 8px;">
        <span class="badge-mini" style="background: rgba(0, 242, 254, 0.2); border-color: var(--neon-cyan);">${step.status}</span>
        <span style="color: var(--text-muted);">Step: ${step.step}</span>
        <span style="color: var(--neon-green);">${step.duration_ms} ms</span>
        <span style="color: var(--neon-cyan);">${step.tokens_used} tokens</span>
      </div>
    </div>

    <div class="inspector-section">
      <div class="inspector-section-title">ACTION & REASONING SUMMARY</div>
      <div class="inspector-code-box" style="color: var(--neon-cyan);">${step.action}</div>
    </div>

    <div class="inspector-section">
      <div class="inspector-section-title">DIAGNOSTIC DETAILS & ARTIFACTS</div>
      <div class="inspector-code-box">${step.details || 'No detailed diagnostic logs available.'}</div>
    </div>

    <div class="inspector-section">
      <div class="inspector-section-title">ACTIVE CONSTRAINTS & THRESHOLDS</div>
      <div style="color: var(--text-secondary); line-height: 1.6;">
        <div>- Complexity: <strong>${lastOrchestrationResult.complexity?.category || 'MODERATE'}</strong> (Score: ${lastOrchestrationResult.complexity?.complexity_score || 0.5})</div>
        <div>- Exit Threshold (tau): <strong>${((lastOrchestrationResult.confidence?.threshold || 0.8) * 100).toFixed(1)}%</strong></div>
        <div>- Total Composite Confidence: <strong>${((lastOrchestrationResult.confidence?.total_confidence || 0.8) * 100).toFixed(1)}%</strong></div>
        <div>- Active Action: <strong style="color: var(--neon-cyan);">${lastOrchestrationResult.confidence?.action || 'STOP'}</strong> (${lastOrchestrationResult.confidence?.action_purpose || 'Return final SQL answer'})</div>
      </div>
    </div>

    <div class="inspector-section">
      <div class="inspector-section-title">ADAPTIVE ACTION POLICY MATRIX</div>
      <div style="overflow-x: auto; margin-top: 6px;">
        <table style="width: 100%; border-collapse: collapse; font-size: 11px; font-family: var(--font-mono);">
          <thead>
            <tr style="border-bottom: 1px solid var(--border-cyan); color: var(--neon-cyan); text-align: left;">
              <th style="padding: 4px 8px;">Action</th>
              <th style="padding: 4px 8px;">Trigger Condition</th>
              <th style="padding: 4px 8px;">Priority / Conflict Resolution</th>
              <th style="padding: 4px 8px;">Purpose</th>
            </tr>
          </thead>
          <tbody>
            ${(lastOrchestrationResult.action_policy_table || []).map(p => {
              const isCurrent = (lastOrchestrationResult.confidence?.action === p.action);
              return `
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.06); ${isCurrent ? 'background: rgba(0, 242, 254, 0.12); font-weight: bold;' : ''}">
                  <td style="padding: 6px 8px; color: ${isCurrent ? 'var(--neon-green)' : 'var(--neon-pink)'};">${isCurrent ? '▶ ' : ''}${p.action}</td>
                  <td style="padding: 6px 8px; color: var(--text-primary);">${p.trigger_condition}</td>
                  <td style="padding: 6px 8px; color: var(--text-secondary);">${p.priority}</td>
                  <td style="padding: 6px 8px; color: var(--neon-cyan);">${p.purpose}</td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;

  modal.style.display = 'flex';
}

function runBenchmarkComparison(queryText) {
  const modal = document.getElementById('benchmark-modal');
  const queryDisplay = document.getElementById('benchmark-query-display');
  const resultsContainer = document.getElementById('benchmark-results-container');
  if (!modal || !resultsContainer) return;

  if (queryDisplay) queryDisplay.textContent = `"${queryText}"`;
  resultsContainer.innerHTML = `
    <div style="text-align: center; padding: 30px; color: var(--text-muted); font-family: var(--font-cyber);">
      <span class="status-pulse-dot" style="margin-right: 8px;"></span>
      EVALUATING 5 ORCHESTRATION MODES IN PARALLEL...
    </div>
  `;
  modal.style.display = 'flex';

  fetch(`${API_URL}/api/orchestrate/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ english: queryText, schema: activeSchema }),
    credentials: 'include'
  })
    .then(res => res.json())
    .then(data => {
      if (data.success && data.comparison) {
        let html = `
          <table class="benchmark-table">
            <thead>
              <tr>
                <th>ORCHESTRATION MODE</th>
                <th>CONFIDENCE</th>
                <th>TOKENS</th>
                <th>LATENCY</th>
                <th>SAVINGS (%)</th>
                <th>EARLY EXIT</th>
                <th>GENERATED SQL</th>
              </tr>
            </thead>
            <tbody>
        `;

        data.comparison.forEach(item => {
          const isAdaptive = item.mode_key === 'ADAPTIVE_CONFIDENCE';
          const rowClass = isAdaptive ? 'highlight-row' : '';
          const earlyExitBadge = item.early_exit 
            ? `<span style="color: var(--neon-green); font-weight: bold;">⚡ ${item.early_exit_stage}</span>` 
            : `<span style="color: var(--text-muted);">None</span>`;

          html += `
            <tr class="${rowClass}">
              <td>
                <div style="font-weight: 700; color: ${isAdaptive ? 'var(--neon-cyan)' : 'var(--text-primary)'};">${item.mode_name}</div>
                <span class="badge-mini" style="font-size: 8px;">${item.badge}</span>
              </td>
              <td style="color: var(--neon-green); font-weight: 700;">${item.confidence_pct}%</td>
              <td>${item.tokens_used} tok</td>
              <td>${item.latency_ms} ms</td>
              <td style="color: ${item.tokens_saved_pct > 0 ? 'var(--neon-cyan)' : 'var(--text-muted)'}; font-weight: 700;">
                ${item.tokens_saved_pct > 0 ? '+' : ''}${item.tokens_saved_pct}%
              </td>
              <td>${earlyExitBadge}</td>
              <td style="font-size: 10px; color: var(--text-secondary); max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${item.sql}">
                <code>${item.sql}</code>
              </td>
            </tr>
          `;
        });

        html += `</tbody></table>`;
        resultsContainer.innerHTML = html;
      } else {
        resultsContainer.innerHTML = `<div style="color: var(--neon-pink); padding: 20px; text-align: center;">Benchmark comparison failed: ${data.message || 'Unknown error'}</div>`;
      }
    })
    .catch(err => {
      resultsContainer.innerHTML = `<div style="color: var(--neon-pink); padding: 20px; text-align: center;">Failed to connect to benchmark API.</div>`;
      console.error(err);
    });
}

// High-Visibility Bright / Cyber Neon Dark Theme Controller
function initThemeController() {
  const btnThemeToggle = document.getElementById('btn-theme-toggle');
  const themeIcon = document.getElementById('theme-toggle-icon');
  const themeText = document.getElementById('theme-toggle-text');
  
  function applyTheme(theme) {
    const isBright = theme === 'bright';
    if (isBright) {
      document.body.classList.add('theme-bright');
      document.documentElement.classList.add('theme-bright');
      if (themeIcon) themeIcon.textContent = '🌙';
      if (themeText) themeText.textContent = 'Cyber Dark Mode';
      if (btnThemeToggle) btnThemeToggle.setAttribute('title', 'Switch to Cyber Neon Dark Mode');
    } else {
      document.body.classList.remove('theme-bright');
      document.documentElement.classList.remove('theme-bright');
      if (themeIcon) themeIcon.textContent = '☀️';
      if (themeText) themeText.textContent = 'High Visibility Mode';
      if (btnThemeToggle) btnThemeToggle.setAttribute('title', 'Switch to High-Visibility Bright Mode');
    }
    localStorage.setItem('qc_theme', theme);
  }

  // Load saved preference (or default to dark with bright toggle available)
  const savedTheme = localStorage.getItem('qc_theme') || 'dark';
  applyTheme(savedTheme);

  if (btnThemeToggle) {
    btnThemeToggle.addEventListener('click', () => {
      const currentTheme = document.body.classList.contains('theme-bright') ? 'bright' : 'dark';
      const newTheme = currentTheme === 'bright' ? 'dark' : 'bright';
      applyTheme(newTheme);
      showNotification(
        newTheme === 'bright' 
          ? '☀️ High-Visibility Bright Mode Activated' 
          : '🌙 Cyber Neon Dark Mode Activated', 
        'info'
      );
      printConsoleLog(`[THEME] Switched display profile to: ${newTheme.toUpperCase()}`, 'var(--neon-cyan)');
    });
  }
}

// DOM Setup
document.addEventListener('DOMContentLoaded', () => {
  // Only execute dashboard logic if the dashboard markup is on this page.
  // ("/" and "/index.html" also serve dashboard.html, so the URL alone is not a reliable test.)
  const isDashboardPage = !!document.getElementById('schema-selector');
  if (!isDashboardPage) return;

  // Initialize theme
  initThemeController();

  // Initialize view
  setupOrchestrationControls();
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
      renderQuickTableChips();
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

  // Live in-grid filter across visible rows
  const gridFilterInput = document.getElementById('grid-filter-input');
  if (gridFilterInput) {
    gridFilterInput.addEventListener('input', (e) => {
      const term = e.target.value.toLowerCase().trim();
      if (!term) {
        renderTableRows(currentTableColumns, currentTableData);
        const footerRows = document.getElementById('footer-row-count');
        if (footerRows) {
          const valSpan = footerRows.querySelector('.val');
          if (valSpan) valSpan.textContent = currentTableData.length;
        }
        return;
      }
      const filtered = currentTableData.filter(row => {
        return currentTableColumns.some(col => {
          const val = row[col];
          return val !== null && val !== undefined && String(val).toLowerCase().includes(term);
        });
      });
      renderTableRows(currentTableColumns, filtered);
      const footerRows = document.getElementById('footer-row-count');
      if (footerRows) {
        const valSpan = footerRows.querySelector('.val');
        if (valSpan) valSpan.textContent = `${filtered.length} (filtered from ${currentTableData.length})`;
      }
    });
  }

  // Export Table Data to CSV
  const btnExportCsv = document.getElementById('btn-export-csv');
  if (btnExportCsv) {
    btnExportCsv.addEventListener('click', () => {
      if (!currentTableData || currentTableData.length === 0) {
        showNotification('No table data to export.', 'info');
        return;
      }
      exportTableToCSV(currentTableColumns, currentTableData, `${activeSchema}_records.csv`);
      showNotification('Table rows exported as CSV!', 'success');
    });
  }

  // TRANSLATE BUTTON HANDLER (Executes Multi-Agent Orchestration via Flask API)
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

      printConsoleLog(`[ORCHESTRATOR] Connecting to database tables: "${activeSchema}"...`, 'var(--neon-cyan)');
      resetPipelineUI();

      sqlTerminal.innerHTML = `
        <div class="terminal-line loading">[0.00s] INITIALIZING MULTI-AGENT COMPILER...</div>
        <div class="terminal-line loading">[0.04s] PARADIGM: ${activeOrchestrationMode}</div>
        <div class="terminal-line loading">[0.08s] LINKING RELEVANT TABLES & COLUMNS...</div>
      `;

      fetch(`${API_URL}/api/orchestrate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          english: englishText,
          schema: activeSchema,
          mode: activeOrchestrationMode,
          constraints: { token_budget: 500, latency_budget_ms: 2500 }
        }),
        credentials: 'include'
      })
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            const sqlQuery = data.sql;
            const engineName = data.mode_meta ? data.mode_meta.name : 'Adaptive Multi-Agent';
            lastGeneratedSQL = sqlQuery;
            lastOrchestrationResult = data;

            // Trigger Visual Trajectory Animations & Confidence HUD Updates
            animatePipelineTrajectory(data);
            updateConfidenceHUD(data);

            const durationSec = ((data.metrics?.duration_ms || 350) / 1000).toFixed(2);
            const tokensCount = data.metrics?.total_tokens || 0;
            const exitStage = data.early_exit_stage || 'Complete';

            // Auto-render query records immediately in the center output grid
            const displayRows = (data.data && data.data.length > 0) ? data.data : (data.rows_preview && data.rows_preview.length > 0 ? data.rows_preview : null);
            const displayCols = (data.columns && data.columns.length > 0) ? data.columns : (displayRows ? Object.keys(displayRows[0]) : []);

            if (displayRows && displayCols.length > 0) {
              renderDbPreviewTable(displayCols, displayRows);
              printConsoleLog(`[DB] Connected to tables: retrieved ${displayRows.length} rows across ${displayCols.length} columns.`, 'var(--neon-green)');
              const previewCard = document.getElementById('db-preview-card');
              if (previewCard) previewCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            } else if (sqlQuery) {
              // Auto-execute live if not pre-fetched
              fetch(`${API_URL}/api/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sql: sqlQuery, schema: activeSchema }),
                credentials: 'include'
              })
                .then(r => r.json())
                .then(r => {
                  if (r.success && r.data && r.columns) {
                    renderDbPreviewTable(r.columns, r.data);
                    printConsoleLog(`[DB] Live query executed: returned ${r.rows_count} records.`, 'var(--neon-green)');
                    const previewCard = document.getElementById('db-preview-card');
                    if (previewCard) previewCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                  }
                })
                .catch(e => console.error('Live execution error:', e));
            }

            setTimeout(() => {
              sqlTerminal.innerHTML = `
                <div class="terminal-line cmd">adaptive_orchestrator --mode="${data.mode}" --exit="${exitStage}" --tokens=${tokensCount}</div>
                <div class="terminal-line sql-code-block">${highlightSQL(sqlQuery)}</div>
              `;
              sqlTerminal.scrollTop = 0;

              printConsoleLog(`[ORCHESTRATOR] ${engineName} completed in ${durationSec}s (${tokensCount} tokens used).`, 'var(--neon-green)');
              if (data.early_exit_taken) {
                printConsoleLog(`[FAST-PATH] Early-exit triggered: saved ${data.metrics.tokens_saved_pct}% tokens!`, 'var(--neon-cyan)');
              } else if (data.repaired) {
                printConsoleLog(`[REPAIR] Self-correction repaired execution defect successfully.`, '#ffd700');
              }
            }, (data.trajectory?.length || 3) * 10 + 5);

          } else {
            // A run that ends without a valid query has no `message`; show the real reason instead of "undefined".
            const reason = data.message || data.exec_error || (data.sql ? `generated SQL did not execute: ${data.sql}` : 'no SQL was produced');
            if (data.trajectory) animatePipelineTrajectory(data);
            showNotification(`Orchestration failed: ${reason}`, 'error');
            printConsoleLog(`[ERROR] Orchestration pipeline failed: ${reason}`, 'var(--neon-pink)');
          }
        })
        .catch(err => {
          showNotification('Orchestration server unavailable.', 'error');
          printConsoleLog(`[ERROR] Connection refused to orchestration API gateway.`, 'var(--neon-pink)');
          console.error(err);
        });
    });
  }

  // CLEAR INPUT BUTTON
  const btnClearInput = document.getElementById('btn-clear-input');
  if (btnClearInput && englishInput) {
    btnClearInput.addEventListener('click', () => {
      englishInput.value = '';
      englishInput.dispatchEvent(new Event('input'));
      englishInput.focus();
    });
  }

  // CLEAR GRID BUTTON
  const btnClearGrid = document.getElementById('btn-clear-grid');
  if (btnClearGrid) {
    btnClearGrid.addEventListener('click', () => {
      currentTableColumns = [];
      currentTableData = [];

      const activeTableBadge = document.getElementById('active-table-badge');
      if (activeTableBadge) {
        activeTableBadge.innerHTML = '';
      }
      const filterInput = document.getElementById('grid-filter-input');
      if (filterInput) filterInput.style.display = 'none';
      const btnExport = document.getElementById('btn-export-csv');
      if (btnExport) btnExport.style.display = 'none';
      const footerBar = document.getElementById('grid-footer-bar');
      if (footerBar) footerBar.style.display = 'none';

      const dbTablePreview = document.getElementById('db-table-preview');
      if (dbTablePreview) {
        dbTablePreview.innerHTML = `
          <div class="simulator-empty">
            <svg class="icon-svg" viewBox="0 0 24 24" width="36" height="36" fill="currentColor" style="opacity: 0.35;">
              <path d="M12 2C6.48 2 2 4.02 2 6.5v11c0 2.48 4.48 4.5 10 4.5s10-2.02 10-4.5v-11C22 4.02 17.52 2 12 2zm0 3c4.13 0 7.5 1.25 7.5 2.5S16.13 10 12 10s-7.5-1.25-7.5-2.5S7.87 5 12 5zm0 14c-4.13 0-7.5-1.25-7.5-2.5V14c1.61 1.2 4.39 2 7.5 2s5.89-.8 7.5-2v2.5c0 1.25-3.37 2.5-7.5 2.5zm0-4.5c-4.13 0-7.5-1.25-7.5-2.5V9.5c1.61 1.2 4.39 2 7.5 2s5.89-.8 7.5-2v2.5c0 1.25-3.37 2.5-7.5 2.5z"/>
            </svg>
            <span>CONNECTING TO DATABASE TABLES... ROWS &amp; COLUMNS WILL BE DISPLAYED HERE</span>
          </div>
        `;
      }
      showNotification('Table grid cleared.', 'success');
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

  // RUN SQL BUTTON (Executes query against MySQL backend database)
  const btnRunSql = document.getElementById('btn-run-sql');
  if (btnRunSql) {
    btnRunSql.addEventListener('click', () => {
      if (!lastGeneratedSQL) {
        showNotification('Compile SQL query first.', 'error');
        return;
      }

      printConsoleLog(`[SQL] Compiling generated query string...`, 'var(--text-muted)');
      showNotification('Compiling query in database...', 'info');

      fetch(`${API_URL}/api/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sql: lastGeneratedSQL, schema: activeSchema }),
        credentials: 'include'
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
      fetch(`${API_URL}/api/history/clear`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include'
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

      fetch(`${API_URL}/api/schema/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ table: tableName, columns: cols }),
        credentials: 'include'
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


// ==========================================================================
// OPTIONAL GEMINI API KEY (pasted by the user; kept only in this browser)
// ==========================================================================
const GEMINI_KEY_STORE = 'querycraft_gemini_key';
function getUserGeminiKey() {
  try { return localStorage.getItem(GEMINI_KEY_STORE) || ''; } catch (e) { return ''; }
}
function setUserGeminiKey(k) {
  try { if (k) localStorage.setItem(GEMINI_KEY_STORE, k); else localStorage.removeItem(GEMINI_KEY_STORE); } catch (e) { /* storage blocked: key lasts only for this page */ }
  window.__querycraftKey = k || '';
}
// Every call to this app's /api/ endpoints carries the user's key, if one is set.
(function attachKeyToApiCalls() {
  const nativeFetch = window.fetch.bind(window);
  window.fetch = function (url, opts) {
    const u = typeof url === 'string' ? url : (url && url.url) || '';
    const key = window.__querycraftKey !== undefined ? window.__querycraftKey : getUserGeminiKey();
    if (key && (u.startsWith(API_URL + '/api/') || u.startsWith('/api/'))) {
      opts = Object.assign({}, opts || {});
      const h = new Headers(opts.headers || {});
      h.set('X-Gemini-Key', key);
      opts.headers = h;
    }
    return nativeFetch(url, opts);
  };
})();

function showKeyStatus(text, cls) {
  const el = document.getElementById('api-key-status');
  if (!el) return;
  el.textContent = text;
  el.classList.remove('ok', 'bad');
  if (cls) el.classList.add(cls);
}
function checkGeminiKey() {
  showKeyStatus('checking...');
  return fetch(`${API_URL}/api/status/check-key`, { method: 'POST', credentials: 'include' })
    .then(res => res.json())
    .then(d => {
      const who = d.key_source === 'browser' ? 'your key' : d.key_source === 'server' ? 'server key' : 'no key';
      showKeyStatus(d.ok ? who + ' ✓' : who + ' ✗', d.ok ? 'ok' : 'bad');
      if (typeof printConsoleLog === 'function') {
        printConsoleLog('[KEY] ' + (d.ok ? 'Using ' + who + ': ' : 'Problem with ' + who + ': ') + d.message, d.ok ? 'var(--neon-cyan)' : 'var(--neon-pink)');
      }
      if (typeof checkEngineStatus === 'function') checkEngineStatus();
    })
    .catch(() => showKeyStatus('check failed', 'bad'));
}
document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('api-key-input');
  if (!input) return;
  window.__querycraftKey = getUserGeminiKey();
  const savedHint = k => 'your key is saved (••••' + k.slice(-4) + ')';
  if (window.__querycraftKey) input.placeholder = savedHint(window.__querycraftKey);
  const save = () => {
    const k = input.value.trim();
    if (!k) { input.focus(); return; }
    if (!/^[A-Za-z0-9._\-]{20,200}$/.test(k)) { showKeyStatus('not a valid key', 'bad'); return; }
    setUserGeminiKey(k);
    input.value = '';
    input.placeholder = savedHint(k);
    checkGeminiKey();
  };
  document.getElementById('btn-api-key-save').addEventListener('click', save);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') save(); });
  document.getElementById('btn-api-key-clear').addEventListener('click', () => {
    setUserGeminiKey('');
    input.value = '';
    input.placeholder = 'Gemini API key (optional)';
    checkGeminiKey();
  });
  checkGeminiKey();
});
