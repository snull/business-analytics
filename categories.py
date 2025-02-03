import requests
import streamlit as st


@st.cache_data(ttl=6000)
def fetch_category_data(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return {}


category_url = "https://search.raah.ir/v6/bundle-list/full/"


@st.cache_data()
def fetch_categories():
    data = fetch_category_data(category_url)
    results = data.get("results", [])
    if not results:
        st.warning("No categories found.")
        return None

    else:
        categories = {}
        slugs = {}

        for result in results:
            title = result.get("title", "No Title")
            sub_categories = result.get("categories", [])

            sub_category_names = [
                f"{sub_category.get('name', 'No Name')}"
                for sub_category in sub_categories
            ]
            sub_category_slugs = [
                f"{sub_category.get('slug', 'No slug')}"
                for sub_category in sub_categories
            ]
            categories[title] = sub_category_names
            slugs[title] = dict(zip(sub_category_names, sub_category_slugs))
        return categories, slugs


def select_category():
    categories, slugs = fetch_categories()
    col1, col2 = st.columns(2)
    with col1:
        selected_category = st.selectbox("Choose a category:", list(categories.keys()))
        # st.write(f"You selected category: {selected_category}")
    with col2:
        if selected_category:
            selected_sub_category = st.selectbox(
                "Choose a subcategory:", categories[selected_category]
            )
            selected_slug = slugs[selected_category].get(selected_sub_category, "No slug")
            # st.write(f"You selected subcategory: {selected_sub_category}")
            # st.write(f"Slug for selected subcategory: {selected_slug}")

            selected = {"category": selected_category, "sub_category": selected_sub_category, "slug": selected_slug}
            return selected
