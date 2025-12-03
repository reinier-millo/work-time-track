import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
import database
from plugins.jira_plugin import JiraPlugin
from plugins.gauzzy_plugin import GauzzyPlugin

# Page Config
st.set_page_config(
    page_title="Work Time Tracker",
    page_icon="⏱️",
    layout="wide"
)

# Initialize Database
database.init_db()

# Initialize Plugins
if 'plugins' not in st.session_state:
    st.session_state.plugins = [
        JiraPlugin(),
        GauzzyPlugin()
    ]

# Restore Active Session
if 'active_timer' not in st.session_state:
    active_session = database.get_active_session()
    st.session_state.active_timer = active_session # (log_id, start_time, prefix) or None

# Initialize Jira tasks on first load
jira_plugin = next((p for p in st.session_state.plugins if isinstance(p, JiraPlugin)), None)
if jira_plugin and jira_plugin.get_setting("enabled") == "True":
    if 'jira_issues' not in st.session_state:
        st.session_state.jira_issues = jira_plugin.get_assigned_issues()

# Initialize Gauzzy tasks on first load
gauzzy_plugin = next((p for p in st.session_state.plugins if isinstance(p, GauzzyPlugin)), None)
if gauzzy_plugin and gauzzy_plugin.get_setting("enabled") == "True":
    access_token = gauzzy_plugin.get_setting("access_token")
    if access_token and 'gauzzy_tasks' not in st.session_state:
        gauzzy_plugin.fetch_tasks()

# Sidebar - Settings
st.sidebar.title("Settings")

# General Settings
st.sidebar.subheader("General")
weekly_limit_hours = float(database.get_setting("weekly_limit_hours", "40.0"))
new_limit = st.sidebar.number_input("Weekly Limit (Hours)", min_value=0.0, value=weekly_limit_hours, step=0.5)
if new_limit != weekly_limit_hours:
    database.set_setting("weekly_limit_hours", str(new_limit))

st.sidebar.markdown("---")

# Plugin Settings
for plugin in st.session_state.plugins:
    plugin.render_settings()
    st.sidebar.markdown("---")

# Main Interface
st.title("⏱️ Work Time Tracker")

# Helper
def format_time(seconds):
    m, s = divmod(abs(int(seconds)), 60)
    h, m = divmod(m, 60)
    sign = "-" if seconds < 0 else ""
    return f"{sign}{h:02}:{m:02}:{s:02}"

# Tabs
tab_timer, tab_stats = st.tabs(["⏱️ Timer", "📊 Statistics"])

with tab_timer:
    # Dashboard Metrics
    col_m1, col_m2, col_m3 = st.columns(3)
    
    total_today = database.get_total_time_today()
    total_week = database.get_total_time_week()
    
    # Add current running time to totals if active
    if st.session_state.active_timer:
        _, start_time, _ = st.session_state.active_timer
        elapsed = (datetime.now() - start_time).total_seconds()
        total_today += elapsed
        total_week += elapsed

    remaining_week = (new_limit * 3600) - total_week
    
    col_m1.metric("Today", format_time(total_today))
    col_m2.metric("This Week", format_time(total_week))
    col_m3.metric("Remaining", format_time(remaining_week), delta_color="normal" if remaining_week > 0 else "inverse")

    # Limit Alert
    if remaining_week <= 0:
        st.error("⚠️ Weekly limit reached!")
        # Play sound if we just crossed the limit (simple check: if we are active and over limit)
        # To avoid constant playing, we might want to be smarter, but for now this meets requirements.
        if st.session_state.active_timer:
             # Just a beep sound
            st.audio("https://upload.wikimedia.org/wikipedia/commons/0/05/Beep-09.ogg", format="audio/ogg", start_time=0, loop=True, autoplay=True)

    st.markdown("---")

    # Jira Tasks List
    # Find Jira plugin instance
    jira_plugin = next((p for p in st.session_state.plugins if isinstance(p, JiraPlugin)), None)
    
    def start_timer_callback(prefix):
        if prefix:
            # Check if there is an active timer
            if st.session_state.active_timer:
                current_log_id, current_start_time, current_prefix = st.session_state.active_timer
                
                # If it's the same task, do nothing (or maybe stop it? User asked for Stop button in list)
                if current_prefix == prefix:
                    # We will handle stop in the list UI separately, but if start is called on active, maybe ignore?
                    # Actually, let's make this callback purely for STARTING. 
                    # If we want to stop, we should call a stop callback.
                    return 

                # Stop the current timer
                end_time = database.stop_timer(current_log_id)
                duration = (end_time - current_start_time).total_seconds()
                
                # Notify plugins
                for plugin in st.session_state.plugins:
                    plugin.stop_tracking(current_prefix, duration, start_time=current_start_time, end_time=end_time)
                
                st.session_state.active_timer = None
                st.toast(f"Stopped tracking '{current_prefix}'")

            # Start the new timer
            log_id, start_time = database.start_timer(prefix)
            st.session_state.active_timer = (log_id, start_time, prefix)
            
            # Notify plugins
            for plugin in st.session_state.plugins:
                plugin.start_tracking(prefix)
            
            st.rerun()

    def stop_timer_callback(prefix):
        if st.session_state.active_timer:
            log_id, start_time, active_prefix = st.session_state.active_timer
            if active_prefix == prefix:
                end_time = database.stop_timer(log_id)
                duration = (end_time - start_time).total_seconds()
                
                # Notify plugins
                for plugin in st.session_state.plugins:
                    plugin.stop_tracking(active_prefix, duration, start_time=start_time, end_time=end_time)
                
                st.session_state.active_timer = None
                st.success(f"Stopped tracking '{active_prefix}'. Duration: {duration:.2f}s")
                st.rerun()

    # Check weekly limit before rendering button
    weekly_limit_hours = float(database.get_setting("weekly_limit_hours", "40.0"))
    weekly_data = database.get_total_time_week()  # Returns seconds
    current_week_hours = weekly_data / 3600.0  # Convert seconds to hours
    weekly_limit_reached = current_week_hours >= weekly_limit_hours
    
    if jira_plugin:
        jira_plugin.render_assigned_issues(start_timer_callback, stop_timer_callback, weekly_limit_reached)

    col1, col2 = st.columns([3, 1])

    with col1:
        # If active, lock the input to the current prefix
        default_prefix = st.session_state.active_timer[2] if st.session_state.active_timer else ""
        prefix_input = st.text_input("Task Prefix / ID", value=default_prefix, placeholder="e.g., JIRA-123, Project-A", disabled=st.session_state.active_timer is not None)

    with col2:
        st.write("")
        st.write("")
        if st.session_state.active_timer is None:
            # Disable button if weekly limit reached
            if st.button("Start Timer", type="primary", width='stretch', disabled=weekly_limit_reached):
                if prefix_input:
                    can_start = True
                    # Jira Validation - check if issue exists (not just assigned)
                    if jira_plugin and jira_plugin.get_setting("enabled") == "True":
                        # Check if it looks like a Jira key (e.g., PROJ-123)
                        if "-" in prefix_input:
                            if not jira_plugin.issue_exists(prefix_input):
                                st.error(f"Jira issue {prefix_input} not found or you don't have access to it.")
                                can_start = False
                    
                    # Gauzzy Validation
                    gauzzy_plugin = next((p for p in st.session_state.plugins if isinstance(p, GauzzyPlugin)), None)
                    if can_start and gauzzy_plugin and gauzzy_plugin.get_setting("enabled") == "True":
                        is_valid, task_name = gauzzy_plugin.validate_prefix(prefix_input)
                        if not is_valid:
                            st.error(f"No Gauzzy task found matching prefix '{prefix_input}'")
                            can_start = False
                    
                    if can_start:
                        log_id, start_time = database.start_timer(prefix_input)
                        st.session_state.active_timer = (log_id, start_time, prefix_input)
                        
                        # Notify plugins
                        for plugin in st.session_state.plugins:
                            plugin.start_tracking(prefix_input)
                        
                        st.rerun()
                else:
                    st.error("Please enter a prefix.")
        else:
            if st.button("Stop Timer", type="secondary", width='stretch'):
                log_id, start_time, prefix = st.session_state.active_timer
                end_time = database.stop_timer(log_id)
                duration = (end_time - start_time).total_seconds()
                
                # Notify plugins
                for plugin in st.session_state.plugins:
                    plugin.stop_tracking(prefix, duration, start_time=start_time, end_time=end_time)
                
                st.session_state.active_timer = None
                st.success(f"Stopped tracking '{prefix}'. Duration: {duration:.2f}s")
                st.rerun()

    # Active Timer Display
    if st.session_state.active_timer:
        log_id, start_time, prefix = st.session_state.active_timer
        
        # Build info message
        info_message = f"Currently tracking: **{prefix}** (Started at {start_time.strftime('%H:%M:%S')})"
        
        # Add Gauzzy task title if available
        if 'gauzzy_task_title' in st.session_state:
            info_message += f"\n\nGauzzy Task: *{st.session_state.gauzzy_task_title}*"
        
        st.info(info_message)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        st.metric("Elapsed Time", format_time(elapsed))
        
        time.sleep(1)
        st.rerun()
    
    # Display Gauzzy stop message if available
    if 'gauzzy_last_stop_message' in st.session_state:
        msg = st.session_state.gauzzy_last_stop_message
        if msg.startswith('✅'):
            st.success(msg)
        else:
            st.error(msg)
        # Clear after showing once
        del st.session_state.gauzzy_last_stop_message

with tab_stats:
    st.header("Statistics")
    
    # Date range picker - default to current week (Monday to Sunday)
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(days=6)  # Sunday
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=week_start)
    with col2:
        end_date = st.date_input("End Date", value=week_end)
    
    if start_date and end_date:
        df_daily, df_all = database.get_stats_for_period(start_date, end_date)
        
        # Summary metrics
        if not df_daily.empty:
            total_seconds = df_daily['total_seconds'].sum()
            days_worked = len(df_daily)
            daily_avg = total_seconds / days_worked if days_worked > 0 else 0
            
            col_s1, col_s2 = st.columns(2)
            col_s1.metric("Total Time", format_time(total_seconds))
            col_s2.metric("Daily Average", format_time(daily_avg))
        
        # Daily activity graph
        st.subheader("📈 Daily Activity")
        # Create a complete date range
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        df_complete = pd.DataFrame({'day': date_range.strftime('%Y-%m-%d')})
        
        if not df_daily.empty:
            # Merge with actual data
            df_daily['hours'] = df_daily['total_seconds'] / 3600
            df_chart = df_complete.merge(df_daily[['day', 'hours']], on='day', how='left')
            df_chart['hours'] = df_chart['hours'].fillna(0)
            st.bar_chart(df_chart, x='day', y='hours')
        else:
            # Show all days with 0 hours
            df_complete['hours'] = 0
            st.bar_chart(df_complete, x='day', y='hours')
        
        
        st.markdown("---")
        # Task Totals section
        st.subheader("📊 Task Totals")
        if not df_all.empty:
            # Get Jira URL for links
            jira_url = jira_plugin.get_setting("url", "") if jira_plugin else ""
            
            # Group by prefix and sum durations
            df_totals = df_all.groupby('prefix').agg({
                'duration_seconds': ['sum', 'count']
            }).reset_index()
            df_totals.columns = ['prefix', 'total_seconds', 'entry_count']
            df_totals['total_hours'] = df_totals['total_seconds'] / 3600
            df_totals = df_totals.sort_values('total_seconds', ascending=False)
            
            # Build custom table with st.columns
            import re

            # Header row
            header_cols = st.columns([3, 1, 1])
            header_cols[0].markdown("**Task/Issue**")
            header_cols[1].markdown("**Total Hours**")
            header_cols[2].markdown("**Entries**")
            
            # Data rows
            for _, row in df_totals.iterrows():
                cols = st.columns([3, 1, 1])
                
                # Task/Issue column - conditionally render as link or text
                prefix = str(row['prefix'])
                if jira_url and re.match(r'^[A-Z][A-Z0-9]+-[0-9]+$', prefix):
                    # Jira issue - show as link
                    cols[0].markdown(f"[{prefix}]({jira_url}/browse/{prefix})")
                else:
                    # Non-Jira - show as plain text
                    cols[0].text(prefix)
                
                # Hours and count columns
                cols[1].text(f"{row['total_hours']:.2f}")
                cols[2].text(f"{int(row['entry_count'])}")
        else:
            st.info("No task data for selected period.")
        
        st.markdown("---")
        # All entries table
        st.subheader("📋 All Entries")
        if not df_all.empty:
            # Get Jira URL for links
            jira_url = jira_plugin.get_setting("url", "") if jira_plugin else ""
            
            import re
            
            # Header row
            header_cols = st.columns([2, 2, 2, 1])
            header_cols[0].markdown("**Task/Issue**")
            header_cols[1].markdown("**Start Time**")
            header_cols[2].markdown("**End Time**")
            header_cols[3].markdown("**Duration (s)**")
            
            # Data rows
            for _, row in df_all.iterrows():
                cols = st.columns([2, 2, 2, 1])
                
                # Task/Issue column - conditionally render as link or text
                prefix = str(row['prefix'])
                if jira_url and re.match(r'^[A-Z][A-Z0-9]+-[0-9]+$', prefix):
                    # Jira issue - show as link
                    cols[0].markdown(f"[{prefix}]({jira_url}/browse/{prefix})")
                else:
                    # Non-Jira - show as plain text
                    cols[0].text(prefix)
                
                # Time columns
                start_time = pd.to_datetime(row['start_time']).strftime('%d %b %Y, %I:%M %p')
                end_time = pd.to_datetime(row['end_time']).strftime('%d %b %Y, %I:%M %p')
                cols[1].text(start_time)
                cols[2].text(end_time)
                cols[3].text(f"{row['duration_seconds']:.2f}")
        else:
            st.info("No entries for selected period.")




