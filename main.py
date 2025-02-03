import streamlit as st

import districts
import location_suggestion
import scrape
import heatmaps
import business_suggestion
from test import test


# st.sidebar.title("Navigation")
def home():
    st.title('📊 AnalytX')
    st.subheader('Optimize your venture: ')
    st.write('Find what to run, where to thrive, and how to succeed. 🚀')
    st.divider()


pages = {
    "Home": [
        st.Page(home, title="Home"),
    ],
    "Districts": [
        st.Page(districts.extract_tehran_districts, title="Extract districts", icon='🗺️️'),
        st.Page(districts.add_district, title="Add district", icon='➕'),
        st.Page(districts.add_banned_district, title="Add banned district", icon='✖️'),
    ],
    "Locations": [
        st.Page(scrape.scrape_data, title="Scrape data", icon='🔍'),
    ],
    "Heat Maps": [
        st.Page(business_suggestion.generate_heatmaps, title="Generate heat maps", icon='🔥'),
    ],
    "Location suggestion": [
        st.Page(location_suggestion.location_suggestion, title="Location suggestion", icon='📍'),
    ],
    "Business suggestion": [
        st.Page(business_suggestion.display_suggestions, title="Business suggestion", icon='💼'),
    ]
}
pg = st.navigation(pages)
pg.run()

# app_mode = st.sidebar.selectbox(
#     placeholder="Mode",
#     label="Choose an app mode",
#     options=["Extract districts", "Add district", "Add banned district", "Scrape data", "Generate heat maps", "Location suggestion", "Business suggestion", "test"]
# )
#
# if app_mode == "Scrape data":
#     scrape_data()
# elif app_mode == "Extract districts":
#     extract_tehran_districts()
# elif app_mode == "Add district":
#     add_district()
# elif app_mode == "Add banned district":
#     add_banned_district()
# elif app_mode == 'Generate heat maps':
#     generate_heatmaps()
# elif app_mode == 'Location suggestion':
#     location_suggestion()
# elif app_mode == 'Business suggestion':
#     display_suggestions()
# elif app_mode == 'test':
#     test()

