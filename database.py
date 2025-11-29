import sqlite3
import pandas as pd
import os

DB_NAME = "transactions.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    """
    Initialize the database with the transactions, categories, and rules tables.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Transactions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            description TEXT,
            amount REAL,
            category TEXT DEFAULT 'Uncategorized',
            source_file TEXT,
            project_name TEXT,
            UNIQUE(date, description, amount, source_file)
        )
    ''')

    # Migration: Add project_name if it doesn't exist
    cursor.execute("PRAGMA table_info(transactions)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'project_name' not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN project_name TEXT")

    # Categories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    ''')

    # Rules table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE,
            category_name TEXT
        )
    ''')

    # Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    # Seed default categories if empty
    cursor.execute("SELECT count(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        defaults = [
            "Uncategorized", "Revenue", "COGS", "OpEx", "Marketing",
            "Salaries", "Rent", "Software", "Meals", "Travel",
            "Personal", "Transfer", "Utilities", "Insurance", "Taxes"
        ]
        cursor.executemany("INSERT INTO categories (name) VALUES (?)", [(c,) for c in defaults])

    conn.commit()
    conn.close()

def save_transactions(df, filename):
    """
    Save a dataframe of transactions to the database.
    Avoids duplicates based on the UNIQUE constraint.
    """
    if df.empty:
        return 0

    conn = get_connection()
    cursor = conn.cursor()

    saved_count = 0
    records_to_insert = []

    for _, row in df.iterrows():
        date = row.get('date', '')
        desc = row.get('description', '')
        source = row.get('source_file', filename)

        # Calculate amount
        withdrawal = pd.to_numeric(row.get('withdrawal', 0), errors='coerce')
        if pd.isna(withdrawal): withdrawal = 0

        deposit = pd.to_numeric(row.get('deposit', 0), errors='coerce')
        if pd.isna(deposit): deposit = 0

        amount = deposit - withdrawal

        # Category default
        category = 'Uncategorized'
        project_name = None # Default project name

        records_to_insert.append((date, desc, amount, category, source, project_name))

    # Use INSERT OR IGNORE to handle duplicates
    cursor.executemany('''
        INSERT OR IGNORE INTO transactions (date, description, amount, category, source_file, project_name)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', records_to_insert)

    saved_count = cursor.rowcount

    conn.commit()
    conn.close()

    return saved_count

def get_all_transactions():
    """
    Return all transactions as a DataFrame.
    """
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM transactions", conn)
    conn.close()
    return df

def get_uncategorized():
    """
    Return uncategorized transactions as a DataFrame.
    """
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM transactions WHERE category = 'Uncategorized'", conn)
    conn.close()
    return df

def update_transaction(id, field, value):
    """
    Update a specific field for a transaction.
    """
    conn = get_connection()
    cursor = conn.cursor()
    query = f"UPDATE transactions SET {field} = ? WHERE id = ?"
    cursor.execute(query, (value, id))
    conn.commit()
    conn.close()

def update_transactions_batch(updates):
    """
    Update multiple transactions at once.
    updates: list of dictionaries with 'id' and fields to update.
    Example: [{'id': 1, 'category': 'Meals'}, {'id': 2, 'project_name': 'Project A'}]
    """
    conn = get_connection()
    cursor = conn.cursor()

    for update in updates:
        id = update.pop('id')
        set_clause = ", ".join([f"{k} = ?" for k in update.keys()])
        values = list(update.values())
        values.append(id)

        cursor.execute(f"UPDATE transactions SET {set_clause} WHERE id = ?", values)

    conn.commit()
    conn.close()

def delete_transactions(ids):
    """
    Delete transactions by ID list.
    """
    if not ids:
        return
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ', '.join(['?'] * len(ids))
    cursor.execute(f"DELETE FROM transactions WHERE id IN ({placeholders})", ids)
    conn.commit()
    conn.close()

# --- Settings Management ---

def get_starting_balance():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'starting_balance'")
    row = cursor.fetchone()
    conn.close()
    if row:
        return float(row[0])
    return 0.0

def set_starting_balance(amount):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('starting_balance', ?)", (str(amount),))
    conn.commit()
    conn.close()

# --- Category Management ---

def get_categories():
    """
    Return categories as a list of names.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM categories ORDER BY name")
    categories = [row[0] for row in cursor.fetchall()]
    conn.close()
    return categories

def get_categories_df():
    """
    Return categories as a DataFrame with id and name.
    """
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM categories ORDER BY name", conn)
    conn.close()
    return df

def add_category(name):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def update_category_name(id, new_name):
    """
    Update a category name and propagate the change to transactions and rules.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Get old name
        cursor.execute("SELECT name FROM categories WHERE id = ?", (id,))
        row = cursor.fetchone()
        if not row:
            return False
        old_name = row[0]

        # Update category name
        cursor.execute("UPDATE categories SET name = ? WHERE id = ?", (new_name, id))

        # Propagate to transactions
        cursor.execute("UPDATE transactions SET category = ? WHERE category = ?", (new_name, old_name))

        # Propagate to rules
        cursor.execute("UPDATE rules SET category_name = ? WHERE category_name = ?", (new_name, old_name))

        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Likely new name already exists
        return False
    finally:
        conn.close()

def delete_category(name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM categories WHERE name = ?", (name,))
    conn.commit()
    conn.close()

# --- Rule Management ---

def get_rules():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM rules ORDER BY keyword", conn)
    conn.close()
    return df

def add_rule(keyword, category_name):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO rules (keyword, category_name) VALUES (?, ?)", (keyword, category_name))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def delete_rule(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM rules WHERE id = ?", (id,))
    conn.commit()
    conn.close()

# --- Auto-Categorization Logic ---

def predict_category(description):
    """
    Predict category based on:
    1. Exact keyword match in rules.
    2. Historical match (most frequent category for this exact description).
    """
    conn = get_connection()
    cursor = conn.cursor()
    description = description.strip()

    # 1. Check Rules
    # We need to check if any keyword is IN the description.
    # Since SQL LIKE is usually 'keyword LIKE description', we do it in python for flexibility or reverse LIKE.
    # For simple keyword matching:
    cursor.execute("SELECT keyword, category_name FROM rules")
    rules = cursor.fetchall()

    for keyword, category in rules:
        if keyword.lower() in description.lower():
            conn.close()
            return category, "Rule: " + keyword

    # 2. Check History
    # Find most used category for this description
    cursor.execute('''
        SELECT category, COUNT(*) as cnt
        FROM transactions
        WHERE description = ? AND category != 'Uncategorized'
        GROUP BY category
        ORDER BY cnt DESC
        LIMIT 1
    ''', (description,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return row[0], "History"

    return None, None

def apply_auto_categorization():
    """
    Iterate over all 'Uncategorized' transactions and try to predict category.
    Returns count of updated rows.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Get uncategorized
    cursor.execute("SELECT id, description FROM transactions WHERE category = 'Uncategorized'")
    rows = cursor.fetchall()

    updated_count = 0
    updates = []

    for id, desc in rows:
        category, source = predict_category(desc)
        if category:
            updates.append((category, id))
            updated_count += 1

    if updates:
        cursor.executemany("UPDATE transactions SET category = ? WHERE id = ?", updates)
        conn.commit()

    conn.close()
    return updated_count
