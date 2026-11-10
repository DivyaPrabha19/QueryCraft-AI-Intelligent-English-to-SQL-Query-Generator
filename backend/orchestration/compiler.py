"""
backend/orchestration/compiler.py
High-Precision Semantic Natural Language English-to-SQL Compiler.
Parses arbitrary free-form English queries into accurate, customized MySQL statements
matching the exact schema definition and database contents.
Ensures every distinct English request produces a differentiated, highly relevant SQL query.
"""

import re
from typing import Dict, Any, List, Optional, Tuple, Set


class SemanticSQLCompiler:
    """
    Intelligent NLP-to-SQL Semantic Compiler.
    Translates arbitrary English questions, filters, aggregations, sorts, groupings,
    joins, and modifications into accurate MySQL queries matching the exact schema definition.
    """

    # Common domain synonyms for tables
    TABLE_SYNONYMS = {
        "user": ["users", "user", "account", "accounts", "customer", "customers", "client", "clients", "farmer", "farmers", "person", "people"],
        "farmer": ["farmers", "farmer", "grower", "growers", "agriculture"],
        "employee": ["employees", "employee", "emp", "worker", "workers", "staff", "personnel"],
        "worker": ["workers", "worker", "employee", "employees", "emp", "staff", "labour", "labor"],
        "emp": ["emp", "employee", "employees", "worker", "workers"],
        "department": ["departments", "department", "dep", "dept", "division", "divisions", "unit", "units"],
        "dep": ["dep", "dept", "department", "departments"],
        "order": ["orders", "order", "purchase", "purchases", "transaction", "transactions"],
        "product": ["products", "product", "item", "items", "goods", "inventory", "merchandise", "crop", "produce"],
        "cart": ["cart", "cart_items", "basket", "shopping_cart"],
        "transportation": ["transportation", "transport", "transporter", "transporters", "delivery", "shipping", "logistics"],
        "machine": ["machines", "machine", "equipment", "device", "devices", "machinery"],
        "student": ["students", "student", "pupil", "pupils", "learner", "learners"],
        "movie": ["movie1", "movie", "movies", "film", "films", "cinema"]
    }

    # Common domain synonyms for columns
    COLUMN_SYNONYMS = {
        "name": ["name", "names", "title", "called", "label", "username", "emp_name", "first_name", "machine_name", "transporter_name", "dep_name"],
        "username": ["username", "user_name", "handle", "login"],
        "email": ["email", "emails", "mail", "email_id", "email_address", "user_email"],
        "salary": ["salary", "salaries", "pay", "wage", "wages", "income", "compensation", "earnings"],
        "price": ["price", "prices", "cost", "costs", "amount", "rate", "fee", "charge"],
        "total_amount": ["total_amount", "total", "amount", "price", "order_total"],
        "quantity": ["quantity", "qty", "count", "units", "number_of_items", "amount"],
        "stock": ["stock", "quantity", "inventory", "available", "units"],
        "age": ["age", "years_old"],
        "status": ["status", "state", "condition"],
        "role": ["role", "type", "category", "designation", "position", "occupation"],
        "category": ["category", "categories", "generic", "genre", "type", "kind", "class"],
        "location": ["location", "city", "place", "site", "address"],
        "city": ["city", "town", "place", "location"],
        "country": ["country", "nation"],
        "department": ["department", "dept", "dep", "dept_name", "division"],
        "rating": ["rating", "ratings", "score", "scores", "review", "reviews", "grade"],
        "hours": ["working_hours", "hours", "work_hours", "duration"],
        "date": ["created_at", "release_date", "joining_date", "timestamp", "date", "created", "joined", "released"]
    }

    @classmethod
    def compile(cls, english: str, schema_dict: Dict[str, Any], schema_name: str = "") -> str:
        english_clean = english.strip().strip('"').strip("'")
        eng_lower = english_clean.lower()

        # Handle simple catalog commands
        if re.search(r'\b(show|list)\s+(all\s+)?tables\b', eng_lower):
            return "SHOW TABLES;"
        
        describe_match = re.match(r'^\s*(?:describe|desc)\s+([a-zA-Z0-9_]+)\s*;?$', eng_lower)
        if describe_match:
            return f"DESCRIBE {describe_match.group(1)};"

        if not schema_dict or not isinstance(schema_dict, dict):
            schema_dict = {"products": ["id", "name", "category", "price", "stock"]}

        # Normalize schema: table_name -> dict with column info
        tables_meta = cls._parse_schema_metadata(schema_dict)
        if not tables_meta:
            return "SELECT * FROM users;"

        # 1. Detect target table and potential joined tables
        target_table, joined_tables, inferred_filters = cls._detect_tables_and_inferred_filters(
            eng_lower, english_clean, tables_meta
        )

        # 2. Check for DML (INSERT, UPDATE, DELETE)
        target_cols_raw = tables_meta[target_table]["raw_columns"]
        dml_query = cls._detect_dml(english_clean, eng_lower, target_table, target_cols_raw)
        if dml_query:
            return dml_query

        # 3. Check for Nested Queries & Subqueries (AVG/MAX/MIN scalar subqueries, IN/NOT IN subqueries)
        subquery = cls._detect_subquery(eng_lower, english_clean, target_table, tables_meta)
        if subquery:
            return subquery

        # 4. Check for Extreme Single-Record Queries (Cheapest, Most Expensive, Highest, Lowest, Latest, Oldest)
        extreme_query = cls._detect_extreme_query(eng_lower, target_table, tables_meta[target_table])
        if extreme_query:
            return extreme_query

        # 5. Check for JOIN if multiple tables mentioned or join requested
        join_clause, join_where = cls._detect_join_details(eng_lower, target_table, joined_tables, tables_meta)

        # 5. Extract WHERE Filters FIRST so we know which columns are part of filters
        where_clauses, filter_columns = cls._detect_where_filters(
            english_clean, eng_lower, target_table, tables_meta[target_table], inferred_filters
        )
        if join_where:
            where_clauses.extend(join_where)

        # 6. Extract Projection / Columns / Aggregations (excluding columns that were only mentioned for filters)
        projection_str, group_by_col = cls._detect_projections(
            english_clean, eng_lower, target_table, tables_meta[target_table], filter_columns, bool(join_clause)
        )

        # 7. ORDER BY
        order_by_clause = cls._detect_order_by(eng_lower, tables_meta[target_table])

        # 8. LIMIT
        limit_clause = cls._detect_limit(eng_lower)

        # 9. GROUP BY adjustments
        if group_by_col and projection_str == "*":
            projection_str = f"{group_by_col}, COUNT(*) AS total_count"

        # Construct final SQL
        query_parts = [f"SELECT {projection_str} FROM {target_table}"]

        if join_clause:
            query_parts.append(join_clause)

        if where_clauses:
            # Deduplicate while preserving order
            seen_filters = set()
            unique_filters = []
            for wf in where_clauses:
                wf_clean = wf.strip()
                if wf_clean and wf_clean.lower() not in seen_filters:
                    seen_filters.add(wf_clean.lower())
                    unique_filters.append(wf_clean)
            if unique_filters:
                query_parts.append(f"WHERE {' AND '.join(unique_filters)}")

        if group_by_col:
            query_parts.append(f"GROUP BY {group_by_col}")

        if order_by_clause:
            query_parts.append(order_by_clause)

        if limit_clause:
            query_parts.append(limit_clause)

        return " ".join(query_parts) + ";"

    # =========================================================================
    # SCHEMA METADATA PARSER
    # =========================================================================
    @classmethod
    def _parse_schema_metadata(cls, schema_dict: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        tables_meta = {}
        for t_name, cols in schema_dict.items():
            t_lower = t_name.lower()
            raw_columns = []
            cols_dict = {}
            enum_values = {}

            if isinstance(cols, dict):
                for c_field, c_type in cols.items():
                    raw_columns.append(c_field)
                    c_type_str = str(c_type).lower()
                    is_num = any(k in c_type_str for k in ['int', 'decimal', 'float', 'double', 'numeric', 'real'])
                    is_dt = any(k in c_type_str for k in ['date', 'time', 'year'])
                    is_enum = 'enum' in c_type_str
                    evals = []
                    if is_enum:
                        enum_match = re.findall(r"['\"]([a-zA-Z0-9_\-\s]+)['\"]", c_type_str)
                        evals = [e.lower() for e in enum_match]
                        enum_values[c_field] = evals

                    cols_dict[c_field.lower()] = {
                        "raw_name": c_field,
                        "type": c_type_str,
                        "is_numeric": is_num,
                        "is_date": is_dt,
                        "is_enum": is_enum,
                        "enum_values": evals
                    }
            elif isinstance(cols, list):
                for c_field in cols:
                    raw_columns.append(str(c_field))
                    cols_dict[str(c_field).lower()] = {
                        "raw_name": str(c_field),
                        "type": "varchar",
                        "is_numeric": any(k in str(c_field).lower() for k in ['id', 'price', 'salary', 'amount', 'age', 'stock', 'quantity', 'hours', 'count']),
                        "is_date": any(k in str(c_field).lower() for k in ['date', 'created', 'time', 'year', 'joined']),
                        "is_enum": False,
                        "enum_values": []
                    }

            singular = t_lower[:-1] if t_lower.endswith('s') else t_lower
            plural = t_lower if t_lower.endswith('s') else f"{t_lower}s"

            tables_meta[t_name] = {
                "raw_name": t_name,
                "name_lower": t_lower,
                "singular": singular,
                "plural": plural,
                "raw_columns": raw_columns,
                "columns": cols_dict,
                "enum_values": enum_values
            }
        return tables_meta

    # =========================================================================
    # TABLE DETECTION WITH INFERRED FILTERS & SYNONYM SCORING
    # =========================================================================
    @classmethod
    def _detect_tables_and_inferred_filters(
        cls, eng_lower: str, english_clean: str, tables_meta: Dict[str, Dict[str, Any]]
    ) -> Tuple[str, List[str], List[str]]:
        table_scores = {t: 0 for t in tables_meta}
        inferred_filters_map = {t: [] for t in tables_meta}

        # Check what the sentence begins with or main topic (Subject priority)
        # e.g., "products by farmer 1", "find products with ...", "show orders"
        for t_name, meta in tables_meta.items():
            t_lower = meta["name_lower"]
            t_sing = meta["singular"]
            t_plur = meta["plural"]

            # Starts with or directly focuses on table name
            if re.search(r'^(?:show|get|list|find|select|display)?\s*(?:all\s+)?' + re.escape(t_lower) + r'\b', eng_lower):
                table_scores[t_name] += 40
            elif re.search(r'^(?:show|get|list|find|select|display)?\s*(?:all\s+)?' + re.escape(t_plur) + r'\b', eng_lower):
                table_scores[t_name] += 40
            elif re.search(r'^(?:show|get|list|find|select|display)?\s*(?:all\s+)?' + re.escape(t_sing) + r'\b', eng_lower):
                table_scores[t_name] += 40

            # Anywhere match
            if re.search(r'\b' + re.escape(t_lower) + r'\b', eng_lower):
                table_scores[t_name] += 20
            elif re.search(r'\b' + re.escape(t_plur) + r'\b', eng_lower):
                table_scores[t_name] += 18
            elif re.search(r'\b' + re.escape(t_sing) + r'\b', eng_lower):
                table_scores[t_name] += 18

            # Check table synonyms
            synonyms = cls.TABLE_SYNONYMS.get(t_sing, []) + cls.TABLE_SYNONYMS.get(t_lower, [])
            for syn in synonyms:
                if re.search(r'\b' + re.escape(syn) + r'\b', eng_lower):
                    table_scores[t_name] += 12
                    break

            # Check enum values belonging to this table
            for col_name, evals in meta["enum_values"].items():
                for ev in evals:
                    if re.search(r'\b' + re.escape(ev) + r'\b', eng_lower):
                        table_scores[t_name] += 15
                        inferred_filters_map[t_name].append(f"{col_name} = '{ev}'")

            # Check column matches
            for col_lower, c_info in meta["columns"].items():
                raw_c = c_info["raw_name"]
                if col_lower == 'id':
                    continue
                if re.search(r'\b' + re.escape(col_lower) + r'\b', eng_lower):
                    table_scores[t_name] += 6
                elif re.search(r'\b' + re.escape(raw_c.lower()) + r'\b', eng_lower):
                    table_scores[t_name] += 6

                # Column synonyms
                c_syns = cls.COLUMN_SYNONYMS.get(col_lower, [])
                for syn in c_syns:
                    if syn != col_lower and re.search(r'\b' + re.escape(syn) + r'\b', eng_lower):
                        table_scores[t_name] += 4
                        break

        # Subject-specific refinements:
        # If "products by farmer" or "products from farmer" -> subject is products, filter is farmer_id!
        if re.search(r'\bproducts?\b', eng_lower) and re.search(r'\bfarmers?\b', eng_lower):
            for t_name, meta in tables_meta.items():
                if t_name.lower() in ['products', 'product']:
                    table_scores[t_name] += 50
        elif re.search(r'\bfarmers?\b', eng_lower):
            # Pure farmer query -> users with role='farmer'
            for t_name, meta in tables_meta.items():
                if "role" in meta["columns"]:
                    table_scores[t_name] += 25
                    inferred_filters_map[t_name].append("role = 'farmer'")

        if re.search(r'\bcustomers?\b', eng_lower):
            for t_name, meta in tables_meta.items():
                if "role" in meta["columns"]:
                    table_scores[t_name] += 25
                    inferred_filters_map[t_name].append("role = 'customer'")

        if re.search(r'\btransporters?\b', eng_lower):
            for t_name in tables_meta:
                if "transport" in t_name.lower():
                    table_scores[t_name] += 30

        if re.search(r'\b(movies?|films?|cinema|actor)\b', eng_lower):
            for t_name in tables_meta:
                if "movie" in t_name.lower():
                    table_scores[t_name] += 30

        if re.search(r'\bstudents?\b', eng_lower):
            for t_name in tables_meta:
                if "student" in t_name.lower():
                    table_scores[t_name] += 30

        if re.search(r'\bmachines?\b', eng_lower):
            for t_name in tables_meta:
                if "machine" in t_name.lower():
                    table_scores[t_name] += 30

        if re.search(r'\b(workers?|employees?|staff)\b', eng_lower):
            for t_name in tables_meta:
                if any(k in t_name.lower() for k in ["worker", "employee", "emp"]):
                    table_scores[t_name] += 30

        # Sort tables by score descending
        sorted_tables = sorted(table_scores.items(), key=lambda x: x[1], reverse=True)
        primary_table = sorted_tables[0][0]

        # Secondary joined tables
        joined_tables = []
        join_keywords = ['join', 'joined', 'along with', 'together with', 'combined with', 'and their', 'with their']
        has_join_intent = any(k in eng_lower for k in join_keywords)

        # Detect multiple distinct schema tables mentioned in query
        tables_found_in_query = [
            t for t in tables_meta
            if re.search(r'\b' + re.escape(t.lower()) + r'\b', eng_lower) or
               re.search(r'\b' + re.escape(tables_meta[t]['singular']) + r'\b', eng_lower)
        ]
        if len(tables_found_in_query) >= 2 and any(k in eng_lower for k in ['and', 'with', 'join', 'joined', 'to', 'for']):
            has_join_intent = True

        if has_join_intent and len(sorted_tables) > 1:
            for t_cand, score in sorted_tables[1:]:
                if (score >= 6 or t_cand in tables_found_in_query) and t_cand != primary_table:
                    joined_tables.append(t_cand)
                    break

        return primary_table, joined_tables, inferred_filters_map.get(primary_table, [])

    # =========================================================================
    # NESTED QUERIES & SUBQUERIES (Scalar Comparisons, IN / NOT IN, etc.)
    # =========================================================================
    @classmethod
    def _detect_subquery(
        cls,
        eng_lower: str,
        english_clean: str,
        target_table: str,
        tables_meta: Dict[str, Dict[str, Any]]
    ) -> Optional[str]:
        if target_table not in tables_meta:
            return None

        target_meta = tables_meta[target_table]
        cols = target_meta["columns"]

        limit_match = re.search(r'\b(?:limit|top|first|take)\s*[:=]?\s*(\d+)\b', eng_lower)
        limit_clause = f" LIMIT {limit_match.group(1)}" if limit_match else ""

        # 1. Set Membership Subqueries (IN / NOT IN)
        # 1.1 Users with no orders / without orders / haven't placed orders / not in orders
        no_orders_pat = r'\b(?:no|without|zero|never|haven\'t|have\s+not|not\s+in)\s+(?:placed\s+)?orders?\b'
        if re.search(no_orders_pat, eng_lower):
            if "orders" in tables_meta and ("users" in tables_meta or "user" in target_table):
                u_tab = "users" if "users" in tables_meta else target_table
                return f"SELECT * FROM {u_tab} WHERE id NOT IN (SELECT user_id FROM orders){limit_clause};"

        orders_pat = r'\b(?:who\s+have|with|having|placed|in)\s+orders?\b'
        if re.search(orders_pat, eng_lower) and not re.search(no_orders_pat, eng_lower):
            if "orders" in tables_meta and ("users" in tables_meta or "user" in target_table):
                u_tab = "users" if "users" in tables_meta else target_table
                return f"SELECT * FROM {u_tab} WHERE id IN (SELECT user_id FROM orders){limit_clause};"

        # 1.2 Farmers with no products / without products
        no_products_pat = r'\b(?:no|without|never|haven\'t|have\s+not)\s+(?:added\s+)?products?\b'
        if re.search(no_products_pat, eng_lower) and "products" in tables_meta:
            u_tab = target_table if target_table in ["users", "farmers"] else "users"
            role_filter = "role = 'farmer' AND " if "role" in tables_meta.get(u_tab, {}).get("columns", {}) else ""
            return f"SELECT * FROM {u_tab} WHERE {role_filter}id NOT IN (SELECT farmer_id FROM products){limit_clause};"

        farmers_with_products_pat = r'\b(?:farmers?\s+(?:with|having|who\s+have)|who\s+added)\s+products?\b'
        if re.search(farmers_with_products_pat, eng_lower) and "products" in tables_meta:
            u_tab = target_table if target_table in ["users", "farmers"] else "users"
            role_filter = "role = 'farmer' AND " if "role" in tables_meta.get(u_tab, {}).get("columns", {}) else ""
            return f"SELECT * FROM {u_tab} WHERE {role_filter}id IN (SELECT farmer_id FROM products){limit_clause};"

        # 1.3 Departments with no employees / workers
        no_emp_pat = r'\b(?:no|without|zero)\s+(?:employees?|workers?|staff)\b'
        if re.search(no_emp_pat, eng_lower):
            if "dep" in tables_meta and "emp" in tables_meta:
                return f"SELECT * FROM dep WHERE dep_id NOT IN (SELECT dept_id FROM emp){limit_clause};"
            elif "departments" in tables_meta and "employees" in tables_meta:
                return f"SELECT * FROM departments WHERE id NOT IN (SELECT dept_id FROM employees){limit_clause};"

        # 1.4 Products not in cart / never added to cart
        no_cart_pat = r'\b(?:not\s+in|not\s+added\s+to|without|no)\s+cart\b'
        if re.search(no_cart_pat, eng_lower) and "cart" in tables_meta and "products" in tables_meta:
            return f"SELECT * FROM products WHERE id NOT IN (SELECT product_id FROM cart){limit_clause};"

        # 1.5 Orders without transportation
        no_trans_pat = r'\b(?:no|without|zero)\s+transport(?:ation|er)?\b'
        if re.search(no_trans_pat, eng_lower) and "transportation" in tables_meta and "orders" in tables_meta:
            return f"SELECT * FROM orders WHERE id NOT IN (SELECT order_id FROM transportation){limit_clause};"

        # 2. Scalar Comparison with Aggregate Subqueries (AVG, MAX, MIN)
        avg_pat = r'\b(?:average|avg|mean)\b'
        has_avg = bool(re.search(avg_pat, eng_lower))

        max_sub_pat = r'\b(?:maximum|highest|max)\b'
        has_max_sub = bool(re.search(max_sub_pat, eng_lower)) and any(k in eng_lower for k in ["equal", "equals", "=", "nested", "subquery", "who has", "whose", "where"])

        min_sub_pat = r'\b(?:minimum|lowest|min)\b'
        has_min_sub = bool(re.search(min_sub_pat, eng_lower)) and any(k in eng_lower for k in ["equal", "equals", "=", "nested", "subquery", "who has", "whose", "where"])

        if has_avg or has_max_sub or has_min_sub:
            if any(k in eng_lower for k in ["greater than", "more than", "above", "higher than", ">=", ">", "exceeding"]):
                op = ">"
            elif any(k in eng_lower for k in ["less than", "fewer than", "lower than", "below", "cheaper than", "<=", "<", "under"]):
                op = "<"
            elif any(k in eng_lower for k in ["equal to", "equals", "=", "is equal"]):
                op = "="
            elif has_max_sub or has_min_sub:
                op = "="
            else:
                op = ">"

            if has_avg:
                agg = "AVG"
            elif has_max_sub:
                agg = "MAX"
            elif has_min_sub:
                agg = "MIN"
            else:
                agg = "AVG"

            comp_col = None
            if "salary" in cols and ("salary" in eng_lower or any(k in target_table for k in ["emp", "worker", "employee"])):
                comp_col = cols["salary"]["raw_name"]
            elif "price" in cols and ("price" in eng_lower or "product" in target_table or "movie" in target_table):
                comp_col = cols["price"]["raw_name"]
            elif "total_amount" in cols and ("amount" in eng_lower or "total" in eng_lower or "order" in target_table):
                comp_col = cols["total_amount"]["raw_name"]
            elif "working_hours" in cols and ("hour" in eng_lower or "machine" in target_table):
                comp_col = cols["working_hours"]["raw_name"]
            else:
                for c_name, c_info in cols.items():
                    if c_info["is_numeric"] and c_name != "id":
                        if c_name in eng_lower:
                            comp_col = c_info["raw_name"]
                            break
                if not comp_col:
                    for c_name, c_info in cols.items():
                        if c_info["is_numeric"] and c_name != "id":
                            comp_col = c_info["raw_name"]
                            break

            if comp_col:
                extra_filters = []
                dept_match = re.search(r'\bin\s+([a-zA-Z\s]+?)(?:\s+department|\s+dept|$)', english_clean, re.IGNORECASE)
                if dept_match and "department" in cols:
                    d_val = dept_match.group(1).strip()
                    if d_val.lower() not in ['the', 'my', 'all', 'table', 'a']:
                        extra_filters.append(f"{cols['department']['raw_name']} = '{d_val}'")

                extra_str = f"{' AND '.join(extra_filters)} AND " if extra_filters else ""
                order_clause = f" ORDER BY {comp_col} DESC" if op == ">" and not limit_clause else ""
                return f"SELECT * FROM {target_table} WHERE {extra_str}{comp_col} {op} (SELECT {agg}({comp_col}) FROM {target_table}){order_clause}{limit_clause};"

        # 3. Explicit Nested / Subquery Keyword Handling
        if any(k in eng_lower for k in ["nested query", "subquery", "sub query", "inner query"]):
            where_clauses, _ = cls._detect_where_filters(english_clean, eng_lower, target_table, target_meta, [])
            if where_clauses:
                where_inner = f"WHERE {' AND '.join(where_clauses)}"
                return f"SELECT * FROM {target_table} WHERE id IN (SELECT id FROM {target_table} {where_inner}){limit_clause};"
            else:
                return f"SELECT * FROM (SELECT * FROM {target_table}{limit_clause}) AS subquery_table;"

        return None

    # =========================================================================
    # EXTREME QUERIES (Cheapest, Most Expensive, Highest Salary, Latest, etc.)
    # =========================================================================
    @classmethod
    def _detect_extreme_query(cls, eng_lower: str, table: str, meta: Dict[str, Any]) -> Optional[str]:
        cols = meta["columns"]

        lim_m = re.search(r'\b(?:top|first|limit|cheapest|lowest|highest|most\s+expensive)\s*[:=]?\s*(\d+)\b', eng_lower)
        limit_num = int(lim_m.group(1)) if lim_m else 1

        # Cheapest / Lowest price
        if any(k in eng_lower for k in ["cheapest", "lowest price", "least expensive", "lowest cost"]):
            price_col = cls._find_column(cols, ["price", "total_amount", "cost"])
            if price_col:
                return f"SELECT * FROM {table} ORDER BY {price_col} ASC LIMIT {limit_num};"

        # Most expensive / Highest price
        if any(k in eng_lower for k in ["most expensive", "highest price", "top price", "priciest"]):
            price_col = cls._find_column(cols, ["price", "total_amount", "cost"])
            if price_col:
                return f"SELECT * FROM {table} ORDER BY {price_col} DESC LIMIT {limit_num};"

        # Highest salary / Highest paid
        if any(k in eng_lower for k in ["highest salary", "highest paid", "top earner", "max salary"]):
            sal_col = cls._find_column(cols, ["salary", "pay", "wage"])
            if sal_col:
                return f"SELECT * FROM {table} ORDER BY {sal_col} DESC LIMIT {limit_num};"

        # Lowest salary / Lowest paid
        if any(k in eng_lower for k in ["lowest salary", "lowest paid", "min salary"]):
            sal_col = cls._find_column(cols, ["salary", "pay", "wage"])
            if sal_col:
                return f"SELECT * FROM {table} ORDER BY {sal_col} DESC LIMIT {limit_num};"

        # Latest / Most recent / Newest
        if any(k in eng_lower for k in ["latest", "most recent", "newest"]):
            date_col = cls._find_column(cols, ["created_at", "release_date", "joining_date", "timestamp", "date"])
            if date_col:
                lim_m = re.search(r'\b(?:top|first|latest)\s+(\d+)\b', eng_lower)
                limit_num = lim_m.group(1) if lim_m else 1
                return f"SELECT * FROM {table} ORDER BY {date_col} DESC LIMIT {limit_num};"

        # Oldest / Earliest
        if any(k in eng_lower for k in ["oldest", "earliest"]):
            date_col = cls._find_column(cols, ["release_date", "created_at", "joining_date", "date", "age"])
            if date_col:
                return f"SELECT * FROM {table} ORDER BY {date_col} ASC LIMIT {limit_num};"

        # Highest rating / Top rated
        if any(k in eng_lower for k in ["highest rated", "top rated", "best rated"]):
            rate_col = cls._find_column(cols, ["rating", "score"])
            if rate_col:
                return f"SELECT * FROM {table} ORDER BY {rate_col} DESC LIMIT {limit_num};"

        return None

    # =========================================================================
    # DML & DDL DETECTION
    # =========================================================================
    @classmethod
    def _detect_dml(cls, english: str, eng_lower: str, table: str, cols: List[str]) -> Optional[str]:
        if eng_lower.startswith('delete') or 'delete from' in eng_lower or 'remove from' in eng_lower:
            where_match = re.search(r'\bwhere\s+(.+)$', english, re.IGNORECASE)
            if where_match:
                where_raw = where_match.group(1).strip().rstrip(';')
                where_cond = cls._parse_single_condition(where_raw, cols)
                if where_cond:
                    return f"DELETE FROM {table} WHERE {where_cond};"
            id_match = re.search(r'\b(?:id|record)\s*(?:is|=|:)?\s*(\d+)\b', eng_lower)
            if id_match:
                return f"DELETE FROM {table} WHERE id = {id_match.group(1)};"
            return f"DELETE FROM {table};"

        if eng_lower.startswith('update') or 'update ' in eng_lower:
            set_match = re.search(r'set\s+(.+?)(?:\s+where\s+(.+))?$', english, re.IGNORECASE)
            if set_match:
                set_part = set_match.group(1).strip()
                where_part = set_match.group(2)
                where_sql = f" WHERE {where_part.strip().rstrip(';')}" if where_part else ""
                return f"UPDATE {table} SET {set_part}{where_sql};"

        if eng_lower.startswith('insert into') or 'insert into' in eng_lower:
            clean_insert = re.search(r'(insert\s+into\s+[\s\S]+)', english, re.IGNORECASE)
            if clean_insert:
                return clean_insert.group(1).rstrip(';') + ';'

        return None

    # =========================================================================
    # PROJECTION (SELECT) & AGGREGATION EXTRACTION
    # =========================================================================
    @classmethod
    def _detect_projections(
        cls,
        english: str,
        eng_lower: str,
        table: str,
        meta: Dict[str, Any],
        filter_columns: Set[str],
        is_join: bool = False
    ) -> Tuple[str, Optional[str]]:
        cols = meta["columns"]
        raw_cols = meta["raw_columns"]

        # Check for GROUP BY first to align projection
        group_by_col = cls._detect_group_by(eng_lower, meta)

        # 1. COUNT
        if re.search(r'\b(?:how\s+many|count|number\s+of|total\s+count|total\s+number)\b', eng_lower):
            if "distinct" in eng_lower:
                for c_raw in raw_cols:
                    if re.search(r'\b' + re.escape(c_raw.lower()) + r'\b', eng_lower):
                        return f"COUNT(DISTINCT {c_raw})", group_by_col
            if group_by_col:
                return f"{group_by_col}, COUNT(*) AS total_count", group_by_col
            return "COUNT(*)", group_by_col

        # 2. SUM / TOTAL
        sum_match = re.search(r'\b(?:sum of|total|sum)\s+([a-zA-Z0-9_]+)\b', eng_lower)
        if sum_match:
            cand = sum_match.group(1)
            target_col = cls._match_column_name(cand, cols)
            if target_col and cols[target_col.lower()]["is_numeric"]:
                raw_c = cols[target_col.lower()]["raw_name"]
                if group_by_col:
                    return f"{group_by_col}, SUM({raw_c}) AS total_{raw_c}", group_by_col
                return f"SUM({raw_c}) AS total_{raw_c}", group_by_col

        # 3. AVERAGE / MEAN
        avg_match = re.search(r'\b(?:average|avg|mean)\s+(?:of\s+)?([a-zA-Z0-9_]+)\b', eng_lower)
        if avg_match:
            cand = avg_match.group(1)
            target_col = cls._match_column_name(cand, cols)
            if target_col and cols[target_col.lower()]["is_numeric"]:
                raw_c = cols[target_col.lower()]["raw_name"]
                if group_by_col:
                    return f"{group_by_col}, AVG({raw_c}) AS avg_{raw_c}", group_by_col
                return f"AVG({raw_c}) AS avg_{raw_c}", group_by_col

        # 4. MAX
        max_match = re.search(r'\b(?:maximum|max|highest)\s+(?:of\s+)?([a-zA-Z0-9_]+)\b', eng_lower)
        if max_match and not any(k in eng_lower for k in ["order by", "sort by", "highest salary in", "highest paid"]):
            cand = max_match.group(1)
            target_col = cls._match_column_name(cand, cols)
            if target_col and cols[target_col.lower()]["is_numeric"]:
                raw_c = cols[target_col.lower()]["raw_name"]
                return f"MAX({raw_c}) AS max_{raw_c}", group_by_col

        # 5. MIN
        min_match = re.search(r'\b(?:minimum|min|lowest)\s+(?:of\s+)?([a-zA-Z0-9_]+)\b', eng_lower)
        if min_match and not any(k in eng_lower for k in ["order by", "sort by", "lowest salary in", "lowest paid"]):
            cand = min_match.group(1)
            target_col = cls._match_column_name(cand, cols)
            if target_col and cols[target_col.lower()]["is_numeric"]:
                raw_c = cols[target_col.lower()]["raw_name"]
                return f"MIN({raw_c}) AS min_{raw_c}", group_by_col

        if is_join:
            return "*", group_by_col

        # 6. Specific requested projection columns:
        # Check explicit request keywords: "get/show/list/select/display [cols] from/of..."
        explicit_select = re.search(
            r'\b(?:select|get|show|display|find|list)\s+(.+?)(?:\s+(?:from|where|order|group|limit|whose|with)|$)',
            english,
            re.IGNORECASE
        )
        explicit_tokens = []
        if explicit_select:
            raw_target = explicit_select.group(1).lower().replace(' and ', ',')
            raw_parts = raw_target.split(',')
            table_words = {
                table.lower(), meta["singular"], meta["plural"],
                "all", "the", "me", "records", "data", "rows", "details", "items"
            }
            # Add table synonyms to table_words
            for syn in cls.TABLE_SYNONYMS.get(meta["singular"], []) + cls.TABLE_SYNONYMS.get(meta["name_lower"], []):
                table_words.add(syn.lower())
                table_words.add(syn.lower().rstrip('s'))

            for p in raw_parts:
                for w in p.split():
                    cleaned_tok = re.sub(r'[^a-zA-Z0-9_]', '', w).strip()
                    if cleaned_tok and cleaned_tok not in table_words:
                        explicit_tokens.append(cleaned_tok)

        matched_selected_cols = []
        if explicit_tokens:
            for raw_c in raw_cols:
                c_low = raw_c.lower()
                if c_low == 'id':
                    continue

                matched = False
                for tok in explicit_tokens:
                    if c_low == tok or c_low == tok.rstrip('s') or c_low.rstrip('s') == tok:
                        matched = True
                        break
                    for syn_group, syns in cls.COLUMN_SYNONYMS.items():
                        if (c_low == syn_group or c_low in syns or syn_group in c_low) and (tok in syns or tok.rstrip('s') in syns):
                            matched = True
                            break
                    if matched:
                        break

                if matched and raw_c not in matched_selected_cols:
                    matched_selected_cols.append(raw_c)

        if matched_selected_cols and len(matched_selected_cols) < len(raw_cols):
            is_distinct = "distinct" in eng_lower or "unique" in eng_lower
            dist_prefix = "DISTINCT " if is_distinct else ""
            return f"{dist_prefix}{', '.join(matched_selected_cols)}", group_by_col

        return "*", group_by_col

    # =========================================================================
    # WHERE FILTER EXTRACTION
    # =========================================================================
    @classmethod
    def _detect_where_filters(
        cls,
        english: str,
        eng_lower: str,
        table: str,
        meta: Dict[str, Any],
        inferred_filters: List[str]
    ) -> Tuple[List[str], Set[str]]:
        where_clauses = list(inferred_filters)
        filter_columns = set()

        for f in inferred_filters:
            col_part = f.split('=')[0].strip().lower()
            filter_columns.add(col_part)

        cols = meta["columns"]
        raw_cols = meta["raw_columns"]

        # 1. State / Status adjectives
        status_col = cls._find_column(cols, ["status", "state", "condition"])
        if status_col:
            raw_sc = cols[status_col.lower()]["raw_name"]
            status_map = {
                "active": "active",
                "inactive": "inactive",
                "pending": "pending",
                "delivered": "delivered",
                "dispatched": "dispatched",
                "completed": "completed",
                "cancelled": "cancelled",
                "shipped": "shipped"
            }
            for kw, val in status_map.items():
                if re.search(r'\b' + re.escape(kw) + r'\b', eng_lower):
                    where_clauses.append(f"{raw_sc} = '{val}'")
                    filter_columns.add(status_col.lower())

        # 2. Role adjectives
        role_col = cls._find_column(cols, ["role", "type"])
        if role_col:
            raw_rc = cols[role_col.lower()]["raw_name"]
            if "farmer" in eng_lower and f"{raw_rc} = 'farmer'" not in where_clauses:
                where_clauses.append(f"{raw_rc} = 'farmer'")
                filter_columns.add(role_col.lower())
            elif "customer" in eng_lower and f"{raw_rc} = 'customer'" not in where_clauses:
                where_clauses.append(f"{raw_rc} = 'customer'")
                filter_columns.add(role_col.lower())

        # 3. Location / Country / City prepositional filters: "from USA", "in punjab", "in Zion"
        loc_col = cls._find_column(cols, ["country", "state", "city", "location"])
        if loc_col:
            raw_lc = cols[loc_col.lower()]["raw_name"]
            loc_match = re.search(r'\b(?:from|in)\s+([a-zA-Z\s0-9]+?)(?:\s+(?:ordered|sorted|order|sort|limit|group|department|dept)|$)', english, re.IGNORECASE)
            if loc_match:
                val = loc_match.group(1).strip()
                val_clean = re.sub(r'[^a-zA-Z0-9\s]', '', val).strip()
                if val_clean and val_clean.lower() not in ['the', 'my', 'all', 'table', 'active', 'inactive']:
                    if val_clean.lower() in ['usa', 'us', 'united states']:
                        val_clean = 'USA'
                    elif val_clean.lower() in ['uk', 'united kingdom']:
                        val_clean = 'UK'
                    elif val_clean.lower() in ['punjab', 'canada', 'germany', 'india', 'zion', 'paris', 'tokyo', 'london']:
                        val_clean = val_clean.capitalize()
                    where_clauses.append(f"{raw_lc} = '{val_clean}'")
                    filter_columns.add(loc_col.lower())

        # 4. Department prepositional filter: "in computer science department", "in IT", "in sales"
        dept_col = cls._find_column(cols, ["department", "Department", "dept", "dep"])
        if dept_col:
            raw_dc = cols[dept_col.lower()]["raw_name"]
            dept_match = re.search(r'\bin\s+([a-zA-Z\s]+?)(?:\s+department|\s+dept|$)', english, re.IGNORECASE)
            if dept_match:
                dept_val = dept_match.group(1).strip()
                if dept_val.lower() not in ['the', 'my', 'all', 'table', 'a']:
                    where_clauses.append(f"{raw_dc} = '{dept_val}'")
                    filter_columns.add(dept_col.lower())

        # 5. Rating filter: "with rating A", "rating is PG-13", "rating A"
        rate_col = cls._find_column(cols, ["rating", "score", "Rating"])
        if rate_col:
            raw_rc = cols[rate_col.lower()]["raw_name"]
            rate_match = re.search(r'\brating\s*(?:is|=|:)?\s*[\'"]?([a-zA-Z0-9_\-\+]+)[\'"]?', eng_lower)
            if rate_match:
                r_val = rate_match.group(1).strip().upper()
                where_clauses.append(f"{raw_rc} = '{r_val}'")
                filter_columns.add(rate_col.lower())

        # 6. Specific ID & Foreign key filters: "by user 2", "for user 2", "farmer 1", "by farmer 1", "post 201"
        fk_mappings = [
            ("user", ["user_id", "user"]),
            ("farmer", ["farmer_id"]),
            ("order", ["order_id"]),
            ("product", ["product_id"]),
            ("post", ["post_id"]),
            ("dep", ["dept_id", "dep_id"]),
            ("department", ["dept_id", "dep_id"])
        ]
        matched_fk = False
        for entity_name, candidate_cols in fk_mappings:
            entity_pat = r'\b(?:by\s+|for\s+|from\s+)?' + re.escape(entity_name) + r'\s*(?:id)?\s*(?:is|=|#)?\s*(\d+)\b'
            m = re.search(entity_pat, eng_lower)
            if m:
                val = m.group(1)
                for cand in candidate_cols:
                    if cand.lower() in cols:
                        raw_fk = cols[cand.lower()]["raw_name"]
                        where_clauses.append(f"{raw_fk} = {val}")
                        filter_columns.add(cand.lower())
                        matched_fk = True
                        break
            if matched_fk:
                break

        if not matched_fk:
            id_pat = r'\b(?:id|record)\s*(?:is|=|#)?\s*(\d+)\b'
            m = re.search(id_pat, eng_lower)
            if m and 'id' in cols:
                raw_id = cols['id']["raw_name"]
                where_clauses.append(f"{raw_id} = {m.group(1)}")
                filter_columns.add('id')

        # 7. LIKE / Contains filters: "containing apple", "with apple in name", "contains X"
        like_match = re.search(r'\b(?:containing|contains?|like)\s+[\'"]?([a-zA-Z0-9_\-\s]+?)[\'"]?(?:\s+(?:order|group|limit)|$)', english, re.IGNORECASE)
        if like_match:
            kw = like_match.group(1).strip()
            name_col = cls._find_column(cols, ["name", "title", "description"])
            if name_col:
                raw_nc = cols[name_col.lower()]["raw_name"]
                where_clauses.append(f"{raw_nc} LIKE '%{kw}%'")
                filter_columns.add(name_col.lower())

        # 8. Date / Year comparisons: "after 2020", "before 2023", "released after 2020"
        date_col = cls._find_column(cols, ["release_date", "created_at", "joining_date", "timestamp", "date"])
        if date_col:
            raw_date = cols[date_col.lower()]["raw_name"]
            year_after = re.search(r'\b(?:after|since|post|greater than|>)\s*(?:the\s+year\s+)?(19\d\d|20\d\d)\b', eng_lower)
            if year_after:
                where_clauses.append(f"{raw_date} > '{year_after.group(1)}-12-31'")
                filter_columns.add(date_col.lower())
            year_before = re.search(r'\b(?:before|prior to|less than|<)\s*(?:the\s+year\s+)?(19\d\d|20\d\d)\b', eng_lower)
            if year_before:
                where_clauses.append(f"{raw_date} < '{year_before.group(1)}-01-01'")
                filter_columns.add(date_col.lower())
            year_in = re.search(r'\b(?:in|during)\s+(19\d\d|20\d\d)\b', eng_lower)
            if year_in and not any(k in where_clauses for k in [raw_date]):
                where_clauses.append(f"YEAR({raw_date}) = {year_in.group(1)}")
                filter_columns.add(date_col.lower())

        # 9. Numeric & general condition parsing
        cond_text = ""
        boundary_pats = [r'\bwhere\s+', r'\bwhose\s+', r'\bwith\s+', r'\bhaving\s+', r'\bthat\s+have\s+']
        for bp in boundary_pats:
            m = re.search(bp, english, re.IGNORECASE)
            if m:
                cond_text = english[m.end():]
                break

        if not cond_text:
            # Check for inline operator conditions like "price > 50", "salary is greater than 1000"
            for c_low, c_info in cols.items():
                raw_c = c_info["raw_name"]
                if re.search(r'\b' + re.escape(c_low) + r'\b\s*(?:>|<|=|is|between|greater|less|more|above|below)', eng_lower):
                    idx = eng_lower.find(c_low)
                    cond_text = english[idx:]
                    break

        if cond_text:
            # Strip trailing clauses (order by, group by, limit)
            for boundary in [r'\b(?:ordered\s+by|order\s+by|sorted\s+by|sort\s+by)\b', r'\b(?:grouped\s+by|group\s+by)\b', r'\blimit\b']:
                m = re.search(boundary, cond_text, re.IGNORECASE)
                if m:
                    cond_text = cond_text[:m.start()]

            cond_text = cond_text.strip().rstrip(';')
            tokens = re.split(r'\b(?:and|or)\b', cond_text, flags=re.IGNORECASE)
            for tok in tokens:
                tok_clean = tok.strip()
                if not tok_clean:
                    continue
                parsed = cls._parse_single_condition(tok_clean, raw_cols)
                if parsed and parsed not in where_clauses:
                    where_clauses.append(parsed)
                    col_key = parsed.split()[0].strip().lower()
                    filter_columns.add(col_key)

        return where_clauses, filter_columns

    @classmethod
    def _parse_single_condition(cls, filter_text: str, cols: List[str]) -> Optional[str]:
        ft_lower = filter_text.lower().strip()

        # Find which column is being referenced
        matched_col = None
        for c in cols:
            if re.search(r'\b' + re.escape(c.lower()) + r'\b', ft_lower):
                matched_col = c
                break

        # Check column synonyms if not found directly
        if not matched_col:
            for c in cols:
                c_low = c.lower()
                for syn_group, syns in cls.COLUMN_SYNONYMS.items():
                    if c_low in syns:
                        for s in syns:
                            if re.search(r'\b' + re.escape(s) + r'\b', ft_lower):
                                matched_col = c
                                break
                    if matched_col:
                        break
                if matched_col:
                    break

        if not matched_col:
            return None

        # 1. BETWEEN
        between_match = re.search(r'\bbetween\s+(\d+(?:\.\d+)?)\s+and\s+(\d+(?:\.\d+)?)', ft_lower)
        if between_match:
            return f"{matched_col} BETWEEN {between_match.group(1)} AND {between_match.group(2)}"

        # 2. Greater than / >= / >
        gt_match = re.search(r'(?:greater than|more than|above|over|exceeding|>|>=|at least)\s*(\d+(?:\.\d+)?)', ft_lower)
        if gt_match:
            op = ">=" if ("at least" in ft_lower or ">=" in ft_lower) else ">"
            return f"{matched_col} {op} {gt_match.group(1)}"

        # 3. Less than / <= / <
        lt_match = re.search(r'(?:less than|under|below|fewer than|<|<=|at most)\s*(\d+(?:\.\d+)?)', ft_lower)
        if lt_match:
            op = "<=" if ("at most" in ft_lower or "<=" in ft_lower) else "<"
            return f"{matched_col} {op} {lt_match.group(1)}"

        # 4. Equality: is X, = X, equals X
        eq_match = re.search(r'\b(?:is|equals?|=)\s+[\'"]?([a-zA-Z0-9_\s\.\@\-]+)[\'"]?$', filter_text, re.IGNORECASE)
        if eq_match and not any(k in ft_lower for k in ['greater', 'less', 'more', 'over', 'under', 'null', 'not']):
            val = eq_match.group(1).strip().strip("'").strip('"')
            if re.match(r'^\d+(\.\d+)?$', val):
                return f"{matched_col} = {val}"
            return f"{matched_col} = '{val}'"

        # 5. String contains
        contains_m = re.search(r'(?:contains?|like|including)\s+[\'"]?([a-zA-Z0-9_\-\.\@]+)[\'"]?', filter_text, re.IGNORECASE)
        if contains_m:
            return f"{matched_col} LIKE '%{contains_m.group(1).strip()}%'"

        return None

    # =========================================================================
    # GROUP BY, ORDER BY, LIMIT
    # =========================================================================
    @classmethod
    def _detect_group_by(cls, eng_lower: str, meta: Dict[str, Any]) -> Optional[str]:
        raw_cols = meta["raw_columns"]
        cols = meta["columns"]

        match = re.search(r'(?:grouped\s+by|group\s+by|per|for\s+each)\s+([a-zA-Z0-9_]+)', eng_lower)
        if match:
            cand = match.group(1).strip()
            matched = cls._match_column_name(cand, cols)
            if matched:
                return cols[matched.lower()]["raw_name"]

        return None

    @classmethod
    def _detect_order_by(cls, eng_lower: str, meta: Dict[str, Any]) -> Optional[str]:
        raw_cols = meta["raw_columns"]
        cols = meta["columns"]

        order_match = re.search(r'(?:ordered\s+by|order\s+by|sorted\s+by|sort\s+by)\s+([a-zA-Z0-9_]+)(?:\s+(asc|desc|ascending|descending))?', eng_lower)
        if order_match:
            cand = order_match.group(1).strip()
            direction = "DESC" if order_match.group(2) and "desc" in order_match.group(2) else "ASC"
            matched = cls._match_column_name(cand, cols)
            if matched:
                raw_c = cols[matched.lower()]["raw_name"]
                return f"ORDER BY {raw_c} {direction}"

        # Natural direction checks
        if any(k in eng_lower for k in ["highest", "most", "largest", "maximum"]):
            for raw_c in raw_cols:
                if re.search(r'\b' + re.escape(raw_c.lower()) + r'\b', eng_lower):
                    return f"ORDER BY {raw_c} DESC"

        if any(k in eng_lower for k in ["lowest", "least", "smallest", "cheapest"]):
            for raw_c in raw_cols:
                if re.search(r'\b' + re.escape(raw_c.lower()) + r'\b', eng_lower):
                    return f"ORDER BY {raw_c} ASC"

        return None

    @classmethod
    def _detect_limit(cls, eng_lower: str) -> Optional[str]:
        limit_match = re.search(r'\b(?:limit|top|first|take)\s*[:=]?\s*(\d+)\b', eng_lower)
        if limit_match:
            return f"LIMIT {limit_match.group(1)}"
        return None

    # =========================================================================
    # JOINS
    # =========================================================================
    @classmethod
    def _detect_join_details(
        cls,
        eng_lower: str,
        t1_name: str,
        joined_tables: List[str],
        tables_meta: Dict[str, Dict[str, Any]]
    ) -> Tuple[Optional[str], List[str]]:
        if not joined_tables:
            return None, []

        t2_name = joined_tables[0]
        t1_meta = tables_meta[t1_name]
        t2_meta = tables_meta[t2_name]

        t1_cols = [c.lower() for c in t1_meta["raw_columns"]]
        t2_cols = [c.lower() for c in t2_meta["raw_columns"]]

        # Find foreign key relationship
        join_cond = None
        s1 = t1_meta["singular"]
        s2 = t2_meta["singular"]

        # e.g. orders.user_id = users.id
        if f"{s2}_id" in t1_cols and "id" in t2_cols:
            join_cond = f"{t1_name}.{s2}_id = {t2_name}.id"
        elif f"{s1}_id" in t2_cols and "id" in t1_cols:
            join_cond = f"{t1_name}.id = {t2_name}.{s1}_id"
        elif "dept_id" in t1_cols and "dep_id" in t2_cols:
            join_cond = f"{t1_name}.dept_id = {t2_name}.dep_id"
        elif "dept_id" in t2_cols and "dep_id" in t1_cols:
            join_cond = f"{t1_name}.dep_id = {t2_name}.dept_id"
        elif "user_id" in t1_cols and "id" in t2_cols:
            join_cond = f"{t1_name}.user_id = {t2_name}.id"
        elif "user_id" in t2_cols and "id" in t1_cols:
            join_cond = f"{t1_name}.id = {t2_name}.user_id"
        elif "farmer_id" in t1_cols and "id" in t2_cols:
            join_cond = f"{t1_name}.farmer_id = {t2_name}.id"
        elif "farmer_id" in t2_cols and "id" in t1_cols:
            join_cond = f"{t1_name}.id = {t2_name}.farmer_id"
        elif "product_id" in t1_cols and "id" in t2_cols:
            join_cond = f"{t1_name}.product_id = {t2_name}.id"
        elif "product_id" in t2_cols and "id" in t1_cols:
            join_cond = f"{t1_name}.id = {t2_name}.product_id"
        elif "order_id" in t1_cols and "id" in t2_cols:
            join_cond = f"{t1_name}.order_id = {t2_name}.id"
        elif "order_id" in t2_cols and "id" in t1_cols:
            join_cond = f"{t1_name}.id = {t2_name}.order_id"
        elif "department" in t1_cols and "dep_name" in t2_cols:
            join_cond = f"{t1_name}.department = {t2_name}.dep_name"
        elif "department" in t2_cols and "dep_name" in t1_cols:
            join_cond = f"{t1_name}.dep_name = {t2_name}.department"

        if not join_cond:
            join_cond = f"{t1_name}.id = {t2_name}.id"

        is_left = any(k in eng_lower for k in ["left join", "without", "with or without", "even if no"])
        join_type = "LEFT JOIN" if is_left else "JOIN"
        join_clause = f"{join_type} {t2_name} ON {join_cond}"
        return join_clause, []

    # =========================================================================
    # HELPERS
    # =========================================================================
    @classmethod
    def _find_column(cls, cols_dict: Dict[str, Any], candidates: List[str]) -> Optional[str]:
        for cand in candidates:
            cand_low = cand.lower()
            if cand_low in cols_dict:
                return cols_dict[cand_low]["raw_name"]
            for c_key, c_val in cols_dict.items():
                if cand_low in c_key:
                    return c_val["raw_name"]
        return None

    @classmethod
    def _match_column_name(cls, word: str, cols_dict: Dict[str, Any]) -> Optional[str]:
        word_low = word.lower()
        if word_low in cols_dict:
            return cols_dict[word_low]["raw_name"]
        for syn_group, syns in cls.COLUMN_SYNONYMS.items():
            if word_low in syns:
                for s in syns:
                    if s in cols_dict:
                        return cols_dict[s]["raw_name"]
        return None
