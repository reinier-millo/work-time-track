from abc import ABC, abstractmethod
import database

class TimeTrackerPlugin(ABC):
    @property
    @abstractmethod
    def name(self):
        pass

    def get_setting(self, key, default=None):
        """Get a plugin-specific setting."""
        full_key = f"{self.name}.{key}"
        return database.get_setting(full_key, default)

    def set_setting(self, key, value):
        """Set a plugin-specific setting."""
        full_key = f"{self.name}.{key}"
        database.set_setting(full_key, value)

    @abstractmethod
    def start_tracking(self, prefix):
        """Called when a timer is started."""
        pass

    @abstractmethod
    def stop_tracking(self, prefix, duration, start_time=None, end_time=None):
        """
        Called when a timer is stopped.
        :param prefix: The task prefix/ID.
        :param duration: The duration in seconds.
        :param start_time: The datetime when the timer started (optional but recommended).
        :param end_time: The datetime when the timer ended (optional but recommended).
        """
        pass

    @abstractmethod
    def render_settings(self):
        """Render plugin settings in the Streamlit sidebar."""
        pass
