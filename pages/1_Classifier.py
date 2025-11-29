import streamlit as st
import pandas as pd
import database

st.set_page_config(page_title="Transaction Classifier", layout="wide")
st.title("Transaction Classifier")

# 1. Load Data
# Filter option
filter_option = st.radio("Show:", ["Uncategorized", "All Transactions"], horizontal=True)

if filter_option == "Uncategorized":
    df = database.get_uncategorized()
else:
    df = database.get_all_transactions()

if df.empty:
    st.info("No transactions found in the database.")
else:
    # 2. Categorization UI
    st.subheader("Categorize Transactions")

    # Auto-Categorize Button
    col1, col2 = st.columns([1, 4])
    if col1.button("✨ Auto-Categorize"):
        count = database.apply_auto_categorization()
        if count > 0:
            st.success(f"Auto-categorized {count} transactions based on rules and history!")
            st.rerun()
        else:
            st.info("No new auto-categorizations found.")

    # Define categories from DB
    categories = database.get_categories()

    # Use data_editor
    # We need to handle updates.
    # st.data_editor returns the edited dataframe.
    edited_df = st.data_editor(
        df,
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "date": st.column_config.TextColumn("Date", disabled=True),
            "description": st.column_config.TextColumn("Description", disabled=True),
            "amount": st.column_config.NumberColumn("Amount", disabled=True),
            "source_file": st.column_config.TextColumn("Source File", disabled=True),
            "category": st.column_config.SelectboxColumn(
                "Category",
                help="Select the category for this transaction",
                width="medium",
                options=categories,
                required=True,
            )
        },
        hide_index=True,
        num_rows="fixed", # Don't allow adding/deleting rows here, only editing
        key="data_editor"
    )

    # 3. Save Changes
    if st.button("Save Changes"):
        # Detect changes
        # We can compare edited_df with df
        # Or just update all (simpler for now, but less efficient if large)
        # Better: iterate and update where category changed

        updates = []
        for index, row in edited_df.iterrows():
            original_row = df.iloc[index]
            if row['category'] != original_row['category']:
                updates.append((row['id'], row['category']))

        if updates:
            database.update_categories_batch(updates)
            st.success(f"Updated {len(updates)} transactions.")
            st.rerun()
        else:
            st.info("No changes detected.")

    # 4. Export
    st.subheader("Export Categorized Data")

    # Summary stats
    if 'amount' in edited_df.columns:
        st.metric("Total Balance", f"{edited_df['amount'].sum():.2f}")

        # Group by Category
        st.write("Summary by Category:")
        st.dataframe(edited_df.groupby('category')['amount'].sum())

    csv = edited_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Categorized CSV",
        data=csv,
        file_name="categorized_transactions.csv",
        mime="text/csv",
    )
