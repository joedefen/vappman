#!/usr/bin/env python3
import json
import os
from pathlib import Path

class PersistentState:
    def __init__(self, app, **defaults):
        # Setup the storage path
        self._config_dir = Path.home() / ".config" / app
        self._config_file = self._config_dir / "state_vars.json"
        
        # Store internal metadata
        self._defaults = defaults
        
        # Initialize the instance attributes with defaults first
        for key, value in defaults.items():
            setattr(self, key, value)
            
        # Attempt to load existing state
        self.load()

    def load(self):
        """Loads state from JSON, validating keys and types."""
        if not self._config_file.exists():
            self.save()
            return

        try:
            with open(self._config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Validation logic
            # 1. Check if keys match identically
            if set(data.keys()) != set(self._defaults.keys()):
                raise ValueError("Key sets do not match.")

            # 2. Check if types match the defaults
            for key, value in data.items():
                if type(value) != type(self._defaults[key]):
                    raise TypeError(f"Type mismatch for {key}.")

            # If valid, update the object attributes
            for key, value in data.items():
                setattr(self, key, value)

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            print(f"Invalid state file ({e}). Reverting to defaults.")
            self._reset_to_defaults()
            self.save()

    def _reset_to_defaults(self):
        """Internal helper to reset attributes to original defaults."""
        for key, value in self._defaults.items():
            setattr(self, key, value)

    def save(self):
        """Saves current attribute values to the JSON file."""
        # Ensure directory exists
        self._config_dir.mkdir(parents=True, exist_ok=True)

        # Extract current values of the keys defined in defaults
        current_state = {key: getattr(self, key) for key in self._defaults}

        with open(self._config_file, 'w', encoding='utf-8') as f:
            json.dump(current_state, f, indent=4)

    def save_if_changed(self, app_object):
        """
        Compare persistent state attributes with matching attributes in app_object.
        If any differ, update all changed attributes and save once.

        :param app_object: Object to compare attributes with (e.g., app.opts)
        :returns: True if changes were detected and saved, False otherwise
        """
        changed = False

        # Check all persistent state attributes
        for key in self._defaults:
            # Only compare if app_object has this attribute
            if hasattr(app_object, key):
                app_value = getattr(app_object, key)
                state_value = getattr(self, key)

                # If values differ, mark as changed and update
                if app_value != state_value:
                    setattr(self, key, app_value)
                    changed = True

        # Save only if something changed
        if changed:
            self.save()

        return changed
