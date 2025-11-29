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

    # List and Delete
    categories = database.get_categories()
    if categories:
        st.write("Existing Categories:")
        for cat in categories:
            col1, col2 = st.columns([4, 1])
            col1.write(cat)
            if cat != "Uncategorized": # Prevent deleting default
                if col2.button("Delete", key=f"del_cat_{cat}"):
                    database.delete_category(cat)
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
        category = col2.selectbox("Category", options=categories)

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
