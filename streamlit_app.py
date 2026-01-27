import streamlit as st
import requests
from datetime import datetime
import time
import os

# --- Streamlit UI --- 
st.set_page_config(layout="wide", page_title="TDnet Announcement Analyzer")

st.title("TDnet Announcement Analyzer")
st.markdown("--- ")

# --- Sidebar: Search Parameters ---
st.sidebar.header("Search Settings")
start_date = st.sidebar.date_input("Start Date", datetime.now())
end_date = st.sidebar.date_input("End Date", datetime.now())
search_scope = st.sidebar.radio("Search Scope", ("Watchlist", "All"), index=0)

st.sidebar.markdown("---")
st.sidebar.header("AI Settings")
ai_provider = st.sidebar.selectbox("Model Provider", ["OpenAI (GPT-5 Mini)", "Google (Gemini 2.0 Flash)"], index=0)

# --- Stock Code Management ---
STOCK_CODES_FILE = "stock_codes.txt"

def load_stock_codes():
    if not os.path.exists(STOCK_CODES_FILE):
        return []
    with open(STOCK_CODES_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def save_stock_codes(codes):
    with open(STOCK_CODES_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(codes))

BACKEND_URL = "http://127.0.0.1:5000"

# Initialize session state
if 'search_results' not in st.session_state:
    st.session_state['search_results'] = []
if 'downloaded_files' not in st.session_state:
    st.session_state['downloaded_files'] = {} # Map url -> text_path
if 'analysis_results' not in st.session_state:
    st.session_state['analysis_results'] = {} # Map url -> analysis text
if 'analysis_times' not in st.session_state:
    st.session_state['analysis_times'] = {} # Map url -> time string
if 'monitoring' not in st.session_state:
    st.session_state['monitoring'] = True
if 'seen_urls' not in st.session_state:
    st.session_state['seen_urls'] = set()
if 'last_poll_time' not in st.session_state:
    st.session_state['last_poll_time'] = 0
if 'new_announcements_indices' not in st.session_state:
    st.session_state['new_announcements_indices'] = set()
if 'managed_stock_codes' not in st.session_state:
    st.session_state['managed_stock_codes'] = load_stock_codes()

# --- Sidebar: Stock Management UI ---
st.sidebar.markdown("---")
st.sidebar.header("Stock Code Management")

# Add Code
new_code_input = st.sidebar.text_input("Add Stock Code (comma separated)", key="new_code_input")
if st.sidebar.button("Add"):
    if new_code_input:
        new_codes = [c.strip() for c in new_code_input.split(',') if c.strip()]
        added_count = 0
        for code in new_codes:
            if code not in st.session_state['managed_stock_codes']:
                st.session_state['managed_stock_codes'].append(code)
                added_count += 1
        if added_count > 0:
            save_stock_codes(st.session_state['managed_stock_codes'])
            st.success(f"Added {added_count} codes.")
            time.sleep(0.5)
            st.rerun()

# List & Delete
if st.session_state['managed_stock_codes']:
    st.sidebar.subheader("Watchlist")
    selected_to_delete = st.sidebar.multiselect(
        "Select to Delete", 
        options=st.session_state['managed_stock_codes']
    )
    if st.sidebar.button("Delete Selected"):
        if selected_to_delete:
            for c in selected_to_delete:
                if c in st.session_state['managed_stock_codes']:
                    st.session_state['managed_stock_codes'].remove(c)
            save_stock_codes(st.session_state['managed_stock_codes'])
            st.rerun()
    
    with st.sidebar.expander("View Full List"):
        st.write(st.session_state['managed_stock_codes'])
else:
    st.sidebar.info("List is empty. Searching ALL data.")

# --- Helper Function: Perform Search ---
def perform_search(silent=False, use_today=False):
    """Executes the search against the backend."""
    # Use managed codes
    if search_scope == "All":
        current_codes_str = ""
    else:
        current_codes_str = ",".join(st.session_state['managed_stock_codes'])
    try:
        if use_today:
            current_date_str = datetime.now().strftime("%Y-%m-%d")
            payload = {
                "start_date": current_date_str,
                "end_date": current_date_str,
                "codes": current_codes_str
            }
        else:
            payload = {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "codes": current_codes_str
            }
        response = requests.post(f"{BACKEND_URL}/api/search", json=payload)
        response.raise_for_status()
        data = response.json()
        
        if data['status'] == 'success':
            announcements = data['announcements']
            
            # Identify new items for monitoring
            new_indices = set()
            if st.session_state['monitoring']:
                for idx, ann in enumerate(announcements):
                    if ann['url'] not in st.session_state['seen_urls']:
                        new_indices.add(idx)
                        st.session_state['seen_urls'].add(ann['url'])
                
                if new_indices:
                    st.toast(f"Found {len(new_indices)} new announcements!", icon="🔔")
                elif not silent:
                    st.toast("No new announcements found.", icon="zzz")
            else:
                # For manual search, just mark everything as seen so future monitoring doesn't flag them all
                for ann in announcements:
                    st.session_state['seen_urls'].add(ann['url'])

            st.session_state['search_results'] = announcements
            st.session_state['new_announcements_indices'] = new_indices
            
            if not silent:
                st.success(f"Found {len(announcements)} announcements.")
        else:
            st.error(f"Search failed: {data.get('message')}")
            
    except Exception as e:
        st.error(f"Connection error: {e}")

# --- Sidebar: Monitoring Controls ---
st.sidebar.markdown("---")
st.sidebar.header("Real-time Monitoring")
col_m1, col_m2 = st.sidebar.columns(2)

if col_m1.button("Start"):
    st.session_state['monitoring'] = True
    st.session_state['last_poll_time'] = 0 # Force immediate poll
    st.rerun()

if col_m2.button("Stop"):
    st.session_state['monitoring'] = False
    st.rerun()

if st.session_state['monitoring']:
    st.sidebar.success("Monitoring Active 🟢")
    st.sidebar.caption("Polling every 5 minutes...")

# --- Step 1: Search ---
if st.sidebar.button("Search TDnet"):
    st.session_state['monitoring'] = False # Stop monitoring if manual search is triggered
    if end_date < start_date:
        st.error("End date must be after start date.")
    elif (end_date - start_date).days > 30:
        st.error("Date range cannot exceed 5 days.")
    else:
        with st.spinner("Searching TDnet..."):
            perform_search()

# --- Display Results ---
if st.session_state['search_results']:
    st.subheader("Search Results")
    
    for i, ann in enumerate(st.session_state['search_results']):
        with st.container():
            col1, col2 = st.columns([3, 1])
            
            with col1:
                # Highlight new items
                new_badge = "🆕 " if i in st.session_state['new_announcements_indices'] else ""
                if new_badge:
                    st.markdown(f":red[{new_badge} **NEW ANNOUNCEMENT**]")
                
                st.markdown(f"**{ann.get('time', '--:--')} | {ann['stock_code']} {ann['company']}**")
                st.write(f"{new_badge}[{ann['title']}]({ann['url']}) ({ann['type']})")
            
            with col2:
                # Unique key for buttons
                btn_key = f"btn_{i}"
                
                # Check if already downloaded
                is_downloaded = ann.get('is_downloaded', False) or (ann['url'] in st.session_state['downloaded_files'])
                
                if not is_downloaded:
                    if st.button("Download & Parse", key=btn_key):
                        with st.spinner("Downloading..."):
                            resp = requests.post(f"{BACKEND_URL}/api/download", json=ann)
                            if resp.status_code == 200 and resp.json()['status'] == 'success':
                                st.session_state['downloaded_files'][ann['url']] = resp.json()['text_path']
                                st.rerun()
                            else:
                                st.error("Download failed")
                else:
                    st.success("Downloaded")
                    
                    # Check if analysis exists in DB (passed via search results) or session
                    has_analysis = ann.get('analysis') is not None or ann['url'] in st.session_state['analysis_results']
                    analyze_btn_label = "Re-analyze 🔄" if has_analysis else "AI Analyze 🤖"
                    
                    if st.button(analyze_btn_label, key=f"analyze_{i}"):
                        provider_code = "gemini" if "Gemini" in ai_provider else "openai"
                        with st.spinner(f"Analyzing with {ai_provider}..."):
                            # Get path from session or DB
                            text_path = st.session_state['downloaded_files'].get(ann['url']) or ann.get('local_path')
                            
                            payload = {
                                "url": ann['url'],
                                "text_path": text_path,
                                "stock_code": ann['stock_code'],
                                "title": ann['title'],
                                "force": True if has_analysis else False, # Force refresh if clicking Re-analyze
                                "provider": provider_code
                            }
                            try:
                                resp = requests.post(f"{BACKEND_URL}/api/analyze", json=payload)
                                data = resp.json()
                                if resp.status_code == 200 and data['status'] == 'success':
                                    st.session_state['analysis_results'][ann['url']] = data['analysis']
                                    st.session_state['analysis_times'][ann['url']] = data.get('analysis_time')
                                    # Update local ann object to reflect immediate change
                                    ann['analysis'] = data['analysis']
                                    ann['analysis_time'] = data.get('analysis_time')
                                else:
                                    reason = data.get('reason', 'Unknown error')
                                    st.error(f"Analysis failed: {reason}")
                            except Exception as e:
                                st.error(f"Connection error: {e}")

            # Show Analysis if available
            # Priority: Session State > DB Data
            display_analysis = st.session_state['analysis_results'].get(ann['url']) or ann.get('analysis')
            display_time = st.session_state['analysis_times'].get(ann['url']) or ann.get('analysis_time')
            
            if display_analysis:
                with st.expander("AI Analysis Result", expanded=True):
                    if display_time:
                        st.caption(f"Analysis Time: {display_time}")
                    st.markdown(display_analysis)
            
            st.markdown("---")

# --- Monitoring Loop ---
if st.session_state['monitoring']:
    current_dt = datetime.now()
    
    # Check operating hours (08:00 - 22:00)
    if 8 <= current_dt.hour < 22:
        current_time = time.time()
        poll_interval = 300 # 5 minutes
        
        # Check if it's time to poll
        if current_time - st.session_state['last_poll_time'] >= poll_interval:
            st.session_state['last_poll_time'] = current_time
            perform_search(silent=True, use_today=True)
            st.rerun()
        else:
            # Show countdown
            remaining = int(poll_interval - (current_time - st.session_state['last_poll_time']))
            st.sidebar.info(f"Next update in {remaining}s")
            time.sleep(1) # Small sleep to prevent high CPU usage, but keep UI responsive enough
            st.rerun()
    else:
        # Sleep mode
        st.sidebar.warning("System Sleeping (08:00 - 22:00)")
        time.sleep(10) # Sleep to reduce load during off-hours
        st.rerun()
