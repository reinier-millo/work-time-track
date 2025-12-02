import streamlit as st
from .base import TimeTrackerPlugin
import requests
from datetime import datetime

class GauzzyPlugin(TimeTrackerPlugin):
    @property
    def name(self):
        return "Gauzzy"

    def authenticate(self, url, username, password):
        """Authenticate with Gauzzy and store credentials"""
        try:
            # Prepare request details
            login_url = f"{url}/api/auth/login"
            headers = {
                "accept": "application/json, text/plain, */*",
                "content-type": "application/json",
                "language": "en"
            }
            payload = {"email": username, "password": password}

            response = requests.post(
                login_url,
                json=payload,
                headers=headers,
                timeout=10
            )

            response.raise_for_status()
            data = response.json()

            # Store authentication data
            self.set_setting("access_token", data.get("token", ""))
            self.set_setting("refresh_token", data.get("refresh_token", ""))
            
            # Store user info
            user = data.get("user", {})
            self.set_setting("user_id", user.get("id", ""))
            self.set_setting("tenant_id", user.get("tenantId", ""))
            self.set_setting("user_name", user.get("name", ""))
            self.set_setting("user_email", user.get("email", ""))
            self.set_setting("user_image", user.get("imageUrl", ""))
            
            # Store timezone if available, otherwise use a default
            timezone = user.get("timeZone", "America/New_York")  # Default fallback
            self.set_setting("timezone", timezone)
            
            # Store employee info
            employee = user.get("employee", {})
            self.set_setting("employee_id", employee.get("id", ""))
            self.set_setting("organization_id", employee.get("organizationId", ""))
            
            # Fetch tasks after authentication
            self.fetch_tasks()
            
            return True, "Authentication successful"
        except requests.exceptions.RequestException as e:
            error_msg = f"**Request Error Details:**"
            error_msg += f"\n- Error Type: `{type(e).__name__}`"
            error_msg += f"\n- Error Message: `{str(e)}`"
            if hasattr(e, 'response') and e.response is not None:
                error_msg += f"\n- Status Code: `{e.response.status_code}`"
                error_msg += f"\n- Response Text: `{e.response.text}`"
            st.error(error_msg)
            return False, f"Authentication failed: {str(e)}"

    def fetch_tasks(self):
        """Fetch active tasks for the employee"""
        try:
            url = self.get_setting("url")
            employee_id = self.get_setting("employee_id")
            project_id = self.get_setting("project_id")
            organization_id = self.get_setting("organization_id")
            tenant_id = self.get_setting("tenant_id")

            if not all([url, employee_id, project_id, organization_id, tenant_id]):
                st.error(f"Gauzzy: Missing required settings for fetching tasks")
                return []
            
            params = {
                "where[projectId]": project_id,
                "where[organizationId]": organization_id,
                "where[tenantId]": tenant_id
            }

            response = requests.get(
                f"{url}/api/tasks/active/employee/{employee_id}",
                params=params,
                headers=self.get_headers(),
                timeout=10
            )

            response.raise_for_status()
            tasks = response.json()
            
            # Store tasks in session state (not in database as they change frequently)
            st.session_state.gauzzy_tasks = {task['id']: task for task in tasks}
            
            st.toast(f"Gauzzy: Fetched {len(tasks)} tasks successfully", icon="✅")
            return tasks
        except Exception as e:
            st.error(f"Gauzzy: Failed to fetch tasks - {str(e)}\n- Error details: {type(e).__name__}: {str(e)}", icon="❌")
            return []

    def find_task_by_prefix(self, prefix):
        """Find a task whose title starts with the given prefix"""
        import streamlit as st
        tasks = st.session_state.get('gauzzy_tasks', {})
                
        for task_id, task in tasks.items():
            title = task.get('title', '')
            if title.startswith(prefix):
                return task

        return None

    def get_headers(self):
        """Get headers for API requests"""
        access_token = self.get_setting("access_token")
        tenant_id = self.get_setting("tenant_id")
        organization_id = self.get_setting("organization_id")
        
        return {
            "accept": "application/json, text/plain, */*",
            "authorization": f"Bearer {access_token}",
            "content-type": "application/json",
            "language": "en",
            "tenant-id": tenant_id,
            "organization-id": organization_id
        }

    def render_settings(self):
        st.sidebar.subheader("Gauzzy Settings")
        
        # Load current values
        enabled = self.get_setting("enabled", "False") == "True"
        url = self.get_setting("url", "")
        username = self.get_setting("username", "")
        password = self.get_setting("password", "")
        project_id = self.get_setting("project_id", "")
        
        # Check if authenticated
        access_token = self.get_setting("access_token")
        is_authenticated = bool(access_token)
        
        # Render inputs
        new_enabled = st.sidebar.checkbox("Enable Gauzzy Integration", value=enabled)
            
        if new_enabled:
            new_url = st.sidebar.text_input("Gauzzy URL", value=url)
            new_username = st.sidebar.text_input("Email", value=username)
            new_password = st.sidebar.text_input("Password", value=password, type="password")
            new_project_id = st.sidebar.text_input("Project ID", value=project_id)
                
            # Check if settings changed
            settings_changed = (
                new_url != url or 
                new_username != username or 
                new_password != password
            )
            
            # Save settings if changed
            if new_url != url: self.set_setting("url", new_url)
            if new_username != username: self.set_setting("username", new_username)
            if new_password != password: self.set_setting("password", new_password)
            if new_project_id != project_id: self.set_setting("project_id", new_project_id)
            
            # Re-authenticate if settings changed or not authenticated
            if settings_changed or not is_authenticated:
                if new_url and new_username and new_password:
                    if st.sidebar.button("Login to Gauzzy"):
                        success, message = self.authenticate(new_url, new_username, new_password)
                        if success:
                            st.sidebar.success(message)
                            st.rerun()
                        else:
                            st.sidebar.error(message)
            
            # Display user info if authenticated
            if is_authenticated:
                st.sidebar.success("✓ Authenticated")
                user_name = self.get_setting("user_name")
                user_email = self.get_setting("user_email")
                user_image = self.get_setting("user_image")
                
                if user_image:
                    st.sidebar.image(user_image, width="stretch", caption=f"**{user_name}**")
                else:
                    st.sidebar.markdown(f"**{user_name}**")

            
        if new_enabled != enabled:
            self.set_setting("enabled", str(new_enabled))

    def start_tracking(self, prefix):
        if self.get_setting("enabled") == "True":
            # Find matching task
            task = self.find_task_by_prefix(prefix)
            if task:
                task_title = task.get('title', '')
                task_id = task['id']
                st.session_state.gauzzy_task_id = task_id
                st.session_state.gauzzy_task_title = task_title
                
                # Start timer in Gauzzy
                try:
                    url = self.get_setting("url")
                    organization_id = self.get_setting("organization_id")
                    tenant_id = self.get_setting("tenant_id")
                    project_id = self.get_setting("project_id")
                    
                    # Get current time in ISO format
                    from datetime import timezone
                    started_at = datetime.now(timezone.utc).isoformat()
                    
                    payload = {
                        "isBillable": True,
                        "organizationId": organization_id,
                        "tenantId": tenant_id,
                        "projectId": project_id,
                        "taskId": task_id,
                        "organizationContactId": None,
                        "organizationTeamId": None,
                        "description": None,
                        "logType": "TRACKED",
                        "source": "BROWSER",
                        "startedAt": started_at,
                        "stoppedAt": None,
                        "timeZone": self.get_setting("timezone", "America/New_York")
                    }
                    
                    response = requests.post(
                        f"{url}/api/timesheet/timer/start",
                        json=payload,
                        headers=self.get_headers(),
                        timeout=10
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    # Store timer ID for stopping later
                    st.session_state.gauzzy_timer_id = data.get('id')
                    st.session_state.gauzzy_timer_started_at = started_at
                    
                except Exception as e:
                    st.warning(f"Gauzzy: Failed to start timer - {str(e)}")
            else:
                # Clear any previous task info
                if 'gauzzy_task_title' in st.session_state:
                    del st.session_state.gauzzy_task_title
                st.warning(f"Gauzzy: No task found matching prefix '{prefix}'")

    def validate_prefix(self, prefix):
        """Check if prefix matches any task. Returns (is_valid, task_name)"""
        if self.get_setting("enabled") != "True":
            return True, None  # Not enabled, so don't validate
        
        # First attempt: check existing tasks
        task = self.find_task_by_prefix(prefix)
        if task:
            return True, task.get('title', '')
        
        # Second attempt: refetch tasks and check again (silently)
        self.fetch_tasks()
        task = self.find_task_by_prefix(prefix)
        if task:
            return True, task.get('title', '')
        
        return False, None

    def stop_tracking(self, prefix, duration, start_time=None, end_time=None):
        if self.get_setting("enabled") == "True":
            # Check if we have a Gauzzy timer running
            timer_id = st.session_state.get('gauzzy_timer_id')
                        
            if not timer_id:
                st.warning("Gauzzy: No timer ID found to stop")
                return  # No timer to stop
            
            try:
                url = self.get_setting("url")
                organization_id = self.get_setting("organization_id")
                tenant_id = self.get_setting("tenant_id")
                project_id = self.get_setting("project_id")
                task_id = st.session_state.get('gauzzy_task_id')
                started_at = st.session_state.get('gauzzy_timer_started_at')
                
                # Get stopped time in ISO format
                from datetime import timezone
                if end_time:
                    # Convert to UTC properly
                    if end_time.tzinfo is None:
                        # If naive, assume it's local time and convert to UTC
                        end_time = end_time.astimezone(timezone.utc)
                    else:
                        # Already has timezone, convert to UTC
                        end_time = end_time.astimezone(timezone.utc)
                    stopped_at = end_time.isoformat()
                else:
                    stopped_at = datetime.now(timezone.utc).isoformat()
                
                payload = {
                    "isBillable": True,
                    "organizationId": organization_id,
                    "tenantId": tenant_id,
                    "projectId": project_id,
                    "taskId": task_id,
                    "organizationContactId": None,
                    "organizationTeamId": None,
                    "description": None,
                    "logType": "TRACKED",
                    "source": "BROWSER",
                    "startedAt": started_at,
                    "stoppedAt": stopped_at,
                    "id": timer_id,
                    "tags": [],
                    "timeZone": self.get_setting("timezone", "America/New_York")
                }
                
                response = requests.post(
                    f"{url}/api/timesheet/timer/stop",
                    json=payload,
                    headers=self.get_headers(),
                    timeout=10
                )
                
                # Store response in session state to persist across rerun
                st.session_state.gauzzy_last_stop_status = response.status_code
                st.session_state.gauzzy_last_stop_response = response.text
                
                response.raise_for_status()
                
                # Clear session state
                if 'gauzzy_timer_id' in st.session_state:
                    del st.session_state.gauzzy_timer_id
                if 'gauzzy_timer_started_at' in st.session_state:
                    del st.session_state.gauzzy_timer_started_at
                if 'gauzzy_task_id' in st.session_state:
                    del st.session_state.gauzzy_task_id
                if 'gauzzy_task_title' in st.session_state:
                    del st.session_state.gauzzy_task_title
                
                st.session_state.gauzzy_last_stop_message = f"✅ Time logged successfully (Status: {response.status_code})"
                
            except Exception as e:
                # Store error in session state to persist across rerun
                error_msg = f"❌ Failed to stop timer: {str(e)}"
                if hasattr(e, 'response') and e.response is not None:
                    error_msg += f"\nStatus: {e.response.status_code}\nResponse: {e.response.text}"
                st.session_state.gauzzy_last_stop_message = error_msg
