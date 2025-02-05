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
    st.write("- CE Final Year Project")
    st.caption("Project Title:")
    st.write("- Design And Implementation Of A Business Geographic Recommendation System")
    st.caption("Prepared By:")
    st.write("- Shayan Golmohammadi")
    st.caption("Supervised By:")
    st.write("- Dr Somaye Sayari")
    st.divider()
    st.subheader("Help")
    st.write("- There are already locations available from these subcategories: <br>:grey[بیمارستان, تعمیرگاه خودرو, رستوران, سوپرمارکت]", unsafe_allow_html=True)
    st.write("- If you want to run analysis on other subcategories, you should first scrape data in :grey-background[🔍Scrape data] section.")
    st.write("- if you want to use the :grey-background[💼Business Suggestion] section, you should first generate heat maps :grey[(with 100% percnetile)] for the desired district in the :grey-background[🔥Generate heat maps] section.")
    st.caption("- (There are already some heat maps generated for district 1 and 2.)")

pages = {
    "Home": [
        st.Page(home, title="Home", icon='🏠'),
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
