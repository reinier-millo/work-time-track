import streamlit as st
from .base import TimeTrackerPlugin
from jira import JIRA
from datetime import datetime

class JiraPlugin(TimeTrackerPlugin):
    @property
    def name(self):
        return "Jira"

    def get_client(self):
        url = self.get_setting("url")
        username = self.get_setting("username")
        api_token = self.get_setting("api_token")
        
        if not (url and username and api_token):
            return None
            
        try:
            return JIRA(server=url, basic_auth=(username, api_token))
        except Exception as e:
            st.error(f"Jira Connection Error: {e}")
            return None

    def is_assigned_to_me(self, issue_key):
        client = self.get_client()
        if not client: return False
        
        try:
            issue = client.issue(issue_key)
            # Check if assigned to current user (using accountId or name depending on Jira version/setup)
            # For simplicity, we'll check if the current user matches the assignee
            myself = client.myself()
            if issue.fields.assignee and issue.fields.assignee.accountId == myself['accountId']:
                return True
            return False
        except Exception:
            return False
    
    def issue_exists(self, issue_key):
        """Check if a Jira issue exists (regardless of assignment)"""
        client = self.get_client()
        if not client: return False
        
        try:
            issue = client.issue(issue_key)
            return True
        except Exception:
            return False

    def get_assigned_issues(self):
        client = self.get_client()
        if not client: return []
        
        try:
            # JQL to find issues assigned to current user that are not done
            return client.search_issues('assignee = currentUser() AND statusCategory != Done')
        except Exception as e:
            st.error(f"Error fetching issues: {e}")
            return []

    def log_work(self, issue_key, duration_seconds, started_at):
        client = self.get_client()
        if not client: return
        
        try:
            # Round up to the nearest minute
            import math
            minutes = math.ceil(duration_seconds / 60)
            # Ensure at least 1 minute if there was any duration, though ceil handles 0 -> 0
            if duration_seconds > 0 and minutes == 0: minutes = 1 # Should be covered by ceil(0.1) = 1
            
            rounded_seconds = minutes * 60
            
            # started_at should be a datetime object.
            # Jira requires timezone aware datetime to correctly interpret the time.
            # If started_at is naive, we assume it's local time and add the local timezone info.
            if started_at.tzinfo is None:
                started_at = started_at.astimezone()

            client.add_worklog(issue=issue_key, timeSpentSeconds=int(rounded_seconds), started=started_at)
            st.toast(f"Jira: Logged {minutes}m on {issue_key} (rounded up from {duration_seconds:.0f}s)")
        except Exception as e:
            st.error(f"Failed to log work to Jira: {e}")

    def render_settings(self):
        st.sidebar.subheader("Jira Settings")
        
        # Load current values
        enabled = self.get_setting("enabled", "False") == "True"
        url = self.get_setting("url", "https://your-domain.atlassian.net")
        username = self.get_setting("username", "")
        api_token = self.get_setting("api_token", "")

            # Render inputs
        new_enabled = st.sidebar.checkbox("Enable Jira Integration", value=enabled)
        if new_enabled:
            new_url = st.sidebar.text_input("Jira URL", value=url)
            new_username = st.sidebar.text_input("Jira Username", value=username)
            new_api_token = st.sidebar.text_input("Jira API Token", value=api_token, type="password")
                
            # Save if changed
            if new_url != url: self.set_setting("url", new_url)
            if new_username != username: self.set_setting("username", new_username)
            if new_api_token != api_token: self.set_setting("api_token", new_api_token)
        
        if new_enabled != enabled:
            self.set_setting("enabled", str(new_enabled))

    def render_assigned_issues(self, start_callback, stop_callback, disable_start_button):
        if self.get_setting("enabled") != "True":
            return

        with st.expander("My Jira Tasks", expanded=True):
            if st.button("Refresh Jira Tasks"):
                st.session_state.jira_issues = self.get_assigned_issues()
            
            issues = st.session_state.get("jira_issues", [])
            if not issues:
                st.info("No issues loaded or found.")
            else:
                # Check active timer
                active_prefix = None
                if st.session_state.get('active_timer'):
                    active_prefix = st.session_state.active_timer[2]

                for issue in issues:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**{issue.key}**: {issue.fields.summary}")
                    with col2:
                        if active_prefix == issue.key:
                            if st.button("Stop", key=f"stop_{issue.key}", type="primary"):
                                stop_callback(issue.key)
                        else:
                            if st.button("Start", key=f"start_{issue.key}", disabled=disable_start_button):
                                start_callback(issue.key)

    def start_tracking(self, prefix):
        if self.get_setting("enabled") == "True":
            # Validation happens in main.py before calling this, or we can double check here
            # But main.py needs to know if it should block, so validation logic is exposed via is_assigned_to_me
            st.toast(f"Jira: Started tracking for issue {prefix}")

    def stop_tracking(self, prefix, duration, start_time=None, end_time=None):
        if self.get_setting("enabled") == "True":
            # Check if prefix looks like a Jira issue key (e.g., PROJ-123)
            import re
            if not re.match(r'^[A-Z][A-Z0-9]+-[0-9]+$', prefix):
                # Not a Jira key format, skip
                return

            # Log work to Jira
            # Use explicit start_time if provided, otherwise fallback to calculation
            if not start_time:
                from datetime import timedelta
                start_time = datetime.now() - timedelta(seconds=duration)
            
            self.log_work(prefix, duration, start_time)
