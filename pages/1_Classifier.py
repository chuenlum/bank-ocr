import streamlit as st
import pandas as pd
import database

st.set_page_config(page_title="Transaction Classifier", layout="wide")
st.title("Transaction Classifier")

# 1. Load Data & Settings
# Starting Balance
current_balance = database.get_starting_balance()
new_balance = st.number_input("Starting Balance", value=current_balance, step=100.0)
if new_balance != current_balance:
    database.set_starting_balance(new_balance)
    st.success("Starting balance updated!")
    st.rerun()

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

    # Add 'Select' column for deletion
    df['Select'] = False

    # Ensure project_name exists in df (if new column added to DB but not yet in loaded DF for some reason, though read_sql should handle it)
    if 'project_name' not in df.columns:
        df['project_name'] = ""

    # Use data_editor
    # We need to handle updates.
    # st.data_editor returns the edited dataframe.
    edited_df = st.data_editor(
        df,
        column_config={
            "Select": st.column_config.CheckboxColumn("Select", help="Select to delete"),
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "date": st.column_config.TextColumn("Date", required=True),
            "description": st.column_config.TextColumn("Description", disabled=True),
            "amount": st.column_config.NumberColumn("Amount", required=True),
            "source_file": st.column_config.TextColumn("Source File", disabled=True),
            "project_name": st.column_config.TextColumn("Project Name"),
            "category": st.column_config.SelectboxColumn(
                "Category",
                help="Select the category for this transaction",
                width="medium",
                options=categories,
                required=True,
            )
        },
        column_order=["id", "Select", "date", "description", "amount", "category", "project_name", "source_file"],
        hide_index=True,
        num_rows="fixed", # Don't allow adding/deleting rows here, only editing
        key="data_editor"
    )

    # Actions
    st.subheader("Actions")
    col_actions1, col_actions2, col_actions3 = st.columns([1, 1, 2])

    # 3. Save Changes
    with col_actions1:
        if st.button("Save Changes"):
            # Detect changes
            # We iterate and check for changes in category, date, project_name, amount

            updates = []
            for index, row in edited_df.iterrows():
                original_row = df.iloc[index]

                # Check for changes
                row_updates = {}
                if row['category'] != original_row['category']:
                    row_updates['category'] = row['category']
                if row['date'] != original_row['date']:
                    row_updates['date'] = row['date']
                if row['amount'] != original_row['amount']:
                    row_updates['amount'] = row['amount']
                if row['project_name'] != original_row['project_name']:
                    # Handle NaN/None vs empty string
                    p_new = row['project_name'] if pd.notna(row['project_name']) else ""
                    p_old = original_row['project_name'] if pd.notna(original_row['project_name']) else ""
                    if p_new != p_old:
                        row_updates['project_name'] = p_new

                if row_updates:
                    row_updates['id'] = row['id']
                    updates.append(row_updates)

            if updates:
                database.update_transactions_batch(updates)
                st.success(f"Updated {len(updates)} transactions.")
                st.rerun()
            else:
                st.info("No changes detected.")

    # 4. Delete Selected
    with col_actions2:
        if st.button("Delete Selected"):
            selected_rows = edited_df[edited_df['Select']]
            if not selected_rows.empty:
                ids_to_delete = selected_rows['id'].tolist()
                database.delete_transactions(ids_to_delete)
                st.success(f"Deleted {len(ids_to_delete)} transactions.")
                st.rerun()
            else:
                st.warning("No transactions selected for deletion.")

    # 5. Batch Update Year
    with col_actions3:
        with st.form("batch_year_form"):
            st.write("Batch Update Year")
            c1, c2 = st.columns([1, 1])
            target_year = c1.number_input("Target Year", min_value=2000, max_value=2100, value=2024, step=1)
            if c2.form_submit_button("Apply to Selected"):
                selected_rows = edited_df[edited_df['Select']]
                if not selected_rows.empty:
                    updates = []
                    for index, row in selected_rows.iterrows():
                        try:
                            # Parse date
                            # Assuming YYYY-MM-DD or similar standard format
                            current_date = pd.to_datetime(row['date'])
                            # Update year
                            new_date = current_date.replace(year=target_year)
                            # Format back to string (ISO format)
                            new_date_str = new_date.strftime('%Y-%m-%d')

                            updates.append({
                                'id': row['id'],
                                'date': new_date_str
                            })
                        except Exception as e:
                            st.error(f"Error parsing date for ID {row['id']}: {e}")

                    if updates:
                        database.update_transactions_batch(updates)
                        st.success(f"Updated year to {target_year} for {len(updates)} transactions.")
                        st.rerun()
                else:
                    st.warning("No transactions selected.")

    # 5. Export
    st.subheader("Export Categorized Data")

    # Summary stats
    if 'amount' in edited_df.columns:
        total_amount = edited_df['amount'].sum()
        final_balance = new_balance + total_amount

        col_metric1, col_metric2, col_metric3 = st.columns(3)
        col_metric1.metric("Starting Balance", f"{new_balance:.2f}")
        col_metric2.metric("Total Movement", f"{total_amount:.2f}")
        col_metric3.metric("Final Balance", f"{final_balance:.2f}")

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
