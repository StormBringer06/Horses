import streamlit as st
import pandas as pd
import plotly.express as px
import asyncio
import time
from datetime import datetime

# Import your custom modules (UK and foreign versions)
import upcomingRaceScrape
import upcomingOddsScraper
import upcomingRaceDataProcess
import upcomingRaceScrapeForeign
import upcomingOddsScraperForeign
import findBets2
import findBetsAllHorses

st.set_page_config(page_title="Betting Recommendations Analyzer", layout="wide")

# ---------------------------
# Define Functions
# ---------------------------
def scrapeHorseData(date, mode):
    if mode == "UK":
        asyncio.run(upcomingRaceScrape.main(date))
    else:
        asyncio.run(upcomingRaceScrapeForeign.main(date))

def scrapeOdds(is_today, mode):
    if mode == "UK":
        upcomingOddsScraper.main(is_today)
    else:
        upcomingOddsScraperForeign.main(is_today)

def processData():
    upcomingRaceDataProcess.main()

def findGoodBets(minEdge, maxEdge, minOdds, maxOdds, bankroll, min_prob):
    findBets2.main(minEdge=minEdge, maxEdge=maxEdge, minOdds=minOdds,
                    maxOdds=maxOdds, bankroll=bankroll, minProb=min_prob)

def getAllBets():
    findBetsAllHorses.main()

# ---------------------------
# Initialize the Session State Mode
# ---------------------------
if "mode" not in st.session_state:
    st.session_state.mode = "UK"

# ---------------------------
# Header Banner with Switch Mode Button (Top Right)
# ---------------------------
# Create two columns: the first (col_title) spans 9/10 of the width,
# and the second (col_button) spans 1/10, placing the button to the right.
col_title, col_button = st.columns([9, 1])

# Process the switch mode button first; if clicked, update session state.
if col_button.button("Switch Mode"):
    st.session_state.mode = "US" if st.session_state.mode == "UK" else "UK"

# Then render the header with the updated mode in the left column.
col_title.markdown(
    f"<h1 style='color:white;'>Betting Recommendations Analyzer ({st.session_state.mode} Mode)</h1>",
    unsafe_allow_html=True
)

# Use the current mode from session state.
race_mode = st.session_state.mode

# ---------------------------
# Define Dark Mode Colour Schemes (Red/Blue Tints)
# ---------------------------
if race_mode == "UK":
    # Dark blue theme for UK mode
    main_bg    = "#112B3C"  # deep navy for main background
    sidebar_bg = "#1A3E55"  # slightly lighter navy for sidebar
else:
    # Dark red theme for US mode
    main_bg    = "#3C0D12"  # dark maroon for main background
    sidebar_bg = "#4E272C"  # slightly lighter maroon for sidebar

# For a unified look, set header/banner background to match the main background.
header_bg = main_bg

# ---------------------------
# Inject Custom CSS for Colour Scheme and Transitions
# ---------------------------
st.markdown(f"""
<style>
  :root {{
    --interactive-light: #333333;
    --interactive-dark: white;
  }}

  /* Background and Container Styling */
  html body [data-testid="stAppViewContainer"] {{
      background-color: {main_bg} !important;
      transition: background-color 1s ease;
  }}
  html body [data-testid="stSidebar"] {{
      background-color: {sidebar_bg} !important;
      transition: background-color 1s ease;
  }}
  html body [data-testid="stHeader"] {{
      background-color: {header_bg} !important;
      transition: background-color 1s ease;
  }}

  /* Static Text Styling for Headings and Paragraphs */
  html body [data-testid="stAppViewContainer"] h1,
  html body [data-testid="stAppViewContainer"] h2,
  html body [data-testid="stAppViewContainer"] h3,
  html body [data-testid="stAppViewContainer"] h4,
  html body [data-testid="stAppViewContainer"] h5,
  html body [data-testid="stAppViewContainer"] p,
  html body [data-testid="stSidebar"] h1,
  html body [data-testid="stSidebar"] h2,
  html body [data-testid="stSidebar"] h3,
  html body [data-testid="stSidebar"] h4,
  html body [data-testid="stSidebar"] h5,
  html body [data-testid="stSidebar"] p {{
      color: white !important;
  }}

  /* File Uploader Default Styling */
  @media (prefers-color-scheme: light) {{
    html body [data-testid="stFileUploader"],
    html body [data-testid="stFileUploader"] * {{
      color: #333333 !important;
    }}
  }}
  @media (prefers-color-scheme: dark) {{
    html body [data-testid="stFileUploader"],
    html body [data-testid="stFileUploader"] * {{
      color: white !important;
    }}
  }}

  /* Specific Override for Buttons */
  @media (prefers-color-scheme: light) {{
    html body button[data-testid^="stBaseButton-"] div[data-testid="stMarkdownContainer"] p {{
      color: #333333 !important;
    }}
  }}
  @media (prefers-color-scheme: dark) {{
    html body button[data-testid^="stBaseButton-"] div[data-testid="stMarkdownContainer"] p {{
      color: white !important;
    }}
  }}

  /* Force Metric Values to Stay White */
  html body [data-testid="stMetricValue"] {{
      color: white !important;
  }}

  /* Expander Border Styling */
  html body [data-testid="stSidebar"] details {{
      border: 1px solid white !important;
      border-radius: 4px;
  }}

  /* Override for SVG Icons in File Uploader */
  @media (prefers-color-scheme: light) {{
    html body [data-testid="stSidebar"] [data-testid="stFileUploader"] svg {{
      fill: white !important;
    }}
  }}

  /* Override for Uploaded File Info Text */
  @media (prefers-color-scheme: light) {{
    html body [data-testid="stSidebar"] [data-testid="stFileUploaderFileName"],
    html body [data-testid="stSidebar"] .stFileUploaderFileData small {{
      color: white !important;
    }}
  }}

  /* Fade-in Animation for Main Content */
  .fade-in {{
      animation: fadeIn 1s ease;
  }}
  @keyframes fadeIn {{
      0% {{
          opacity: 0;
          transform: translateY(-20px);
      }}
      100% {{
          opacity: 1;
          transform: translateY(0);
      }}
  }}
@media (prefers-color-scheme: light) {{
    [data-testid="stSidebarCollapsedControl"] button svg {{
      fill: white !important;
    }}
  }}
  /* Close sidebar arrow */
  @media (prefers-color-scheme: light) {{
    [data-testid="stSidebarCollapseButton"] button svg {{
      fill: white !important;
    }}
  }}
</style>
""", unsafe_allow_html=True)

# ---------------------------
# Main Content Area (with Fade-In)
# ---------------------------
st.markdown("<div class='fade-in'>", unsafe_allow_html=True)

# Sidebar items:
selected_date = st.sidebar.date_input(
    "Select Date",
    value=datetime.today(),
    format="DD-MM-YYYY"
)
formatted_date = selected_date.strftime("%d-%m-%Y")

time_period = st.sidebar.radio("Select Time Period", options=["Today", "Tomorrow"], index=0)
is_today = (time_period == "Today")

bankroll = st.sidebar.number_input(
    "Bankroll",
    min_value=0.0,
    max_value=1000000.0,
    value=100.0,
    step=0.01,
    format="%.2f"
)

with st.sidebar.expander("Collection Settings"):
    odds_prerange = st.slider(
        "Decimal Odds Range",
        min_value=0.0,
        max_value=100.0,
        value=(1.0, 100.0),
        step=0.5
    )
    edge_prerange = st.slider(
        "Edge Percentage Range",
        min_value=0.0,
        max_value=2.0,
        value=(0.0, 1.0),
        step=0.05
    )
    min_prob = st.slider(
        "Minimum Win Probability",
        min_value=0.0,
        max_value=1.0,
        value=0.15,
        step=0.05
    )

with st.sidebar.expander("Data Collection"):
    if st.button("Scrape Horse Data"):
        try:
            scrapeHorseData(formatted_date, race_mode)
            st.success(f"Horse data scraped for {formatted_date} in {race_mode} mode!")
        except Exception as e:
            st.error(f"Error scraping horse data: {str(e)}")
    if st.button("Scrape Odds"):
        try:
            scrapeOdds(is_today, race_mode)
            st.success(f"Odds scraped for {time_period} in {race_mode} mode!")
        except Exception as e:
            st.error(f"Error scraping odds: {str(e)}")
    if st.button("Process Data"):
        try:
            processData()
            st.success("Data processed successfully!")
        except Exception as e:
            st.error(f"Error processing data: {str(e)}")
    if st.button("Find Bets"):
        try:
            findGoodBets(*edge_prerange, *odds_prerange, bankroll, min_prob)
            st.success("Bets Found!")
        except Exception as e:
            st.error(f"Error finding bets: {str(e)}")
    if st.button("Get All Bets"):
        try:
            getAllBets()
            st.success("Bets Found!")
        except Exception as e:
            st.error(f"Error finding bets: {str(e)}")

# ---------------------------
# File Uploader (Still in the Sidebar)
# ---------------------------
st.sidebar.download_button(
    label="Download Bets CSV",
    data=open("today_bets.csv", "rb"),
    file_name="today_bets.csv",
    mime="text/csv",
    help="This is the bets csv file. You can upload it in the next step."
)

uploaded_file = st.sidebar.file_uploader(
    "Upload recommendations CSV", 
    type=["csv"],
    help="Requires columns: race_id, horse_id, decimal_odds, edge_pct, recommended_stake, model_prob_win"
)

# ---------------------------
# Main Window: Show prompt if no file is uploaded; otherwise display results.
# ---------------------------
if uploaded_file is None:
    st.markdown(f"<div style='background-color: {sidebar_bg}; padding: 12px; border-radius: 4px; color: white; margin-top: 20px;'>Upload Value Bets File.</div>", unsafe_allow_html=True)
else:
    try:
        df = pd.read_csv(uploaded_file)
        required_columns = {'race_id', 'horse_id', 'decimal_odds', 'edge_pct', 'recommended_stake', 'model_prob_win'}
        missing = required_columns - set(df.columns)
        if missing:
            st.error(f"Missing required columns: {', '.join(missing)}")
        else:
            # Clean and convert data
            df['decimal_odds'] = pd.to_numeric(df['decimal_odds'], errors='coerce')
            df['edge_pct'] = df['edge_pct'].astype(str).str.replace('%', '').astype(float)
            df = df.dropna(subset=['decimal_odds', 'edge_pct'])
            if df.empty:
                st.error("No valid data after cleaning. Check your numeric columns.")
            else:
                min_odds, max_odds = float(df['decimal_odds'].min()), float(df['decimal_odds'].max())
                if min_odds == max_odds:
                    min_odds = max(1.0, min_odds - 1)
                    max_odds += 1
                min_edge, max_edge = float(df['edge_pct'].min()), float(df['edge_pct'].max())
                if min_edge == max_edge:
                    min_edge = max(0.0, min_edge - 1)
                    max_edge += 1
                min_prob_val, max_prob_val = float(df['model_prob_win'].min()), float(df['model_prob_win'].max())
                
                # Move Filter Settings into a sidebar expander.
                with st.sidebar.expander("Filter Settings"):
                    odds_range_filter = st.slider("Filter: Decimal Odds Range", min_value=min_odds, max_value=max_odds,
                                                  value=(min_odds, max_odds), step=0.1)
                    edge_range_filter = st.slider("Filter: Edge Percentage Range", min_value=min_edge, max_value=max_edge,
                                                  value=(min_edge, max_edge), step=0.1)
                    prob_range_filter = st.slider("Filter: Win Probability Range", min_value=min_prob_val, max_value=max_prob_val,
                                                  value=(min_prob_val, max_prob_val), step=0.01)
                
                # Apply the filters
                filtered_df = df[
                    (df['decimal_odds'].between(*odds_range_filter)) &
                    (df['edge_pct'].between(*edge_range_filter)) &
                    (df['model_prob_win'].between(*prob_range_filter))
                ]
                if filtered_df.empty:
                    st.warning("No bets match current filters.")
                else:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Recommended Bets", len(filtered_df))
                    with col2:
                        total_stake = filtered_df['recommended_stake'].sum()
                        st.metric("Total Stake", f"${total_stake:,.2f}")
                    with col3:
                        avg_edge = filtered_df['edge_pct'].mean()
                        st.metric("Average Edge", f"{avg_edge:.1f}%")
                    
                    st.subheader("Recommended Bets")
                    st.dataframe(filtered_df, height=600, use_container_width=True)
                    
                    st.subheader("Data Distribution")
                    col1, col2 = st.columns(2)
                    with col1:
                        fig_hist = px.histogram(filtered_df, x='decimal_odds', title="Odds Distribution", nbins=20)
                        st.plotly_chart(fig_hist, use_container_width=True)
                    with col2:
                        fig_scatter = px.scatter(filtered_df, x='edge_pct', y='decimal_odds', size='recommended_stake',
                                                 title="Edge vs Odds Relationship", labels={'edge_pct': 'Edge (%)', 'decimal_odds': 'Odds'})
                        st.plotly_chart(fig_scatter, use_container_width=True)
                    
                    st.download_button(
                        "Download Filtered Data",
                        data=filtered_df.to_csv(index=False),
                        file_name="today_bets.csv",
                        mime="text/csv"
                    )
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")

st.markdown("</div>", unsafe_allow_html=True)
