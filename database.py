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
            UNIQUE(date, description, amount, source_file)
        )
    ''')

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

    # Prepare data for insertion
    # Ensure columns exist and are in order
    # Expected columns in df: date, description, withdrawal, deposit, balance (maybe), source_file
    # We need to normalize this to match the DB schema: date, description, amount, category, source_file

    # Note: The OCR output might have 'withdrawal' and 'deposit'.
    # We should normalize it BEFORE saving if we want to store 'amount'.
    # However, the user's prompt for Page 2 said "If Withdrawal/Deposit columns exist, merge them...".
    # This implies the DB might store them raw, OR we normalize before saving.
    # The prompt for database.py said: "Columns: id, date, description, amount, category, source_file".
    # So we MUST normalize to 'amount' before saving.

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

        records_to_insert.append((date, desc, amount, category, source))

    # Use INSERT OR IGNORE to handle duplicates
    cursor.executemany('''
        INSERT OR IGNORE INTO transactions (date, description, amount, category, source_file)
        VALUES (?, ?, ?, ?, ?)
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

def update_category(id, new_category):
    """
    Update the category for a specific transaction ID.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE transactions SET category = ? WHERE id = ?", (new_category, id))

    conn.commit()
    conn.close()

def update_categories_batch(updates):
    """
    Update multiple categories at once.
    updates: list of tuples (id, new_category)
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executemany("UPDATE transactions SET category = ? WHERE id = ?", [(cat, id) for id, cat in updates])

    conn.commit()
    conn.close()

# --- Category Management ---

def get_categories():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM categories ORDER BY name")
    categories = [row[0] for row in cursor.fetchall()]
    conn.close()
    return categories

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
