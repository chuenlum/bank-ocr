import streamlit as st
import pandas as pd
import database

st.set_page_config(page_title="Manage Categories", layout="wide")
st.title("Manage Categories & Rules")

# Initialize DB to ensure tables exist (in case this page is hit first)
database.init_db()

tab1, tab2 = st.tabs(["Categories", "Rules"])

with tab1:
    st.header("Categories")

    # Add new category
    with st.form("add_category_form", clear_on_submit=True):
        new_cat = st.text_input("New Category Name")
        submitted = st.form_submit_button("Add Category")
        if submitted and new_cat:
            if database.add_category(new_cat):
                st.success(f"Added category: {new_cat}")
                st.rerun()
            else:
                st.error("Category already exists.")

    # List and Edit Categories
    st.subheader("Existing Categories")
    st.write("You can rename categories here. Changes will update all existing transactions.")

    categories_df = database.get_categories_df()

    if not categories_df.empty:
        edited_categories = st.data_editor(
            categories_df,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "name": st.column_config.TextColumn("Category Name", required=True),
            },
            hide_index=True,
            num_rows="fixed",
            key="categories_editor"
        )

        # Save Changes
        if st.button("Save Category Changes"):
            updates = []
            for index, row in edited_df.iterrows() if 'edited_df' in locals() else edited_categories.iterrows():
                original_row = categories_df.iloc[index]
                if row['name'] != original_row['name']:
                    updates.append((row['id'], row['name']))

            success_count = 0
            for id, new_name in updates:
                if database.update_category_name(id, new_name):
                    success_count += 1
                else:
                    st.error(f"Failed to update category ID {id} to '{new_name}'. Name might already exist.")

            if success_count > 0:
                st.success(f"Updated {success_count} categories.")
                st.rerun()
            elif not updates:
                st.info("No changes detected.")

        # Delete Section (Separate to avoid accidental deletes in editor)
        st.divider()
        st.subheader("Delete Category")
        cat_to_delete = st.selectbox("Select Category to Delete", options=categories_df['name'].tolist())
        if st.button("Delete Category"):
            if cat_to_delete == "Uncategorized":
                st.error("Cannot delete 'Uncategorized'.")
            else:
                database.delete_category(cat_to_delete)
                st.success(f"Deleted category: {cat_to_delete}")
                st.rerun()

    else:
        st.info("No categories found.")

with tab2:
    st.header("Auto-Categorization Rules")
    st.write("Define keywords that automatically map to a category.")

    # Add new rule
    with st.form("add_rule_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        keyword = col1.text_input("Keyword (e.g., 'Uber')")
        category = col2.selectbox("Category", options=database.get_categories())

        submitted = st.form_submit_button("Add Rule")
        if submitted and keyword and category:
            if database.add_rule(keyword, category):
                st.success(f"Added rule: '{keyword}' -> {category}")
                st.rerun()
            else:
                st.error("Rule for this keyword already exists.")

    # List Rules
    rules_df = database.get_rules()
    if not rules_df.empty:
        st.dataframe(rules_df, use_container_width=True)

        # Delete Rule
        rule_to_delete = st.selectbox("Select Rule ID to Delete", options=rules_df['id'].tolist())
        if st.button("Delete Rule"):
            database.delete_rule(rule_to_delete)
            st.success("Rule deleted.")
            st.rerun()
    else:
        st.info("No rules defined.")
