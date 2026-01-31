import os
import re
import shutil
import subprocess
import time
from types import SimpleNamespace

# --- 1. The Background Execution Engine ---

class CommandRunner:
    def __init__(self, arg_vector, final_destination):
        self.arg_vector = arg_vector
        self.final_destination = final_destination
        self.temp_file = final_destination + ".tmp"
        self.process = None
        self._file_handle = None

    def start(self):
        self._file_handle = open(self.temp_file, 'w', encoding='utf-8')
        self.process = subprocess.Popen(
            self.arg_vector,
            stdout=self._file_handle,
            stderr=subprocess.STDOUT,
            text=True
        )

    def is_running(self):
        if self.process is None:
            return False
        status = self.process.poll()
        if status is not None:
            self._finalize_file()
            return False
        return True

    def _finalize_file(self):
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None
        if os.path.exists(self.temp_file):
            os.replace(self.temp_file, self.final_destination)

    def get_return_code(self):
        return self.process.poll() if self.process else None


# --- 2. The Text Parser ---

class VAppConfigParser:
    def __init__(self, filepath):
        self.filepath = filepath

    def parse(self):
        apps = {}  # key: appname, value: list of namespaces
        apps_by_key = {}  # key: (appname, db), value: one namespace
        databases = set(['am'])
        if not os.path.exists(self.filepath):
            return apps, apps_by_key, databases

        # Read file with multiple fallback strategies for encoding
        lines = []
        try:
            with open(self.filepath, 'rb') as f:
                raw_data = f.read()

            # Try multiple encoding strategies
            try:
                content = raw_data.decode('utf-8', errors='replace')
            except Exception:
                try:
                    content = raw_data.decode('latin-1', errors='replace')
                except Exception:
                    content = str(raw_data, errors='replace')

            lines = content.splitlines()
        except Exception as e:
            print(f"[VappmanListCache] Error reading file {self.filepath}: {e}")
            return apps, apps_by_key, databases

        current_appname = None
        current_text = []

        def finalize_entry():
            if not current_appname:
                return

            try:
                # Join all lines and collapse whitespace
                raw_text = " ".join(" ".join(current_text).split())

                db = "am"
                synopsis = raw_text

                # Remove "To install" instructions
                if "To install" in raw_text:
                    parts = re.split(r'\.\s*To install\b.*', raw_text, flags=re.IGNORECASE | re.DOTALL)
                    synopsis = parts[0].strip()
                    if synopsis and not synopsis.endswith('.'):
                        synopsis += '.'

                    # Extract DB flag if present
                    db_match = re.search(r'--(\w+)\s+flag', raw_text)
                    if db_match:
                        db = db_match.group(1)
                        databases.add(db)

                entry = SimpleNamespace(appname=current_appname, synopsis=synopsis, db=db)

                # Add to list-based dict
                if current_appname not in apps:
                    apps[current_appname] = []
                apps[current_appname].append(entry)

                # Add to tuple-key dict
                apps_by_key[(current_appname, db)] = entry
            except Exception as e:
                # Skip malformed entries silently, but continue parsing
                print(f"[VappmanListCache] Warning: Failed to parse entry for {current_appname!r}: {e}")

        try:
            for line in lines:
                try:
                    stripped = line.strip()
                    if not stripped:
                        # Empty line ends the current entry
                        finalize_entry()
                        current_appname = None
                        current_text = []
                        continue

                    # Check if line starts with diamond
                    if stripped.startswith('◆'):
                        # Finalize previous entry
                        finalize_entry()

                        # Parse new entry
                        rest = stripped[1:].strip()  # Remove diamond
                        if ':' in rest:
                            parts = rest.split(':', 1)
                            appname = parts[0].strip()

                            # Skip headers
                            if any(x in appname for x in ["INSTALLED", "AVAILABLE", "LIST OF"]):
                                current_appname = None
                                current_text = []
                                continue

                            current_appname = appname
                            current_text = [parts[1].strip()] if len(parts) > 1 else []
                    else:
                        # Continuation line - append to current entry
                        if current_appname:
                            current_text.append(stripped)
                except Exception as e:
                    # Skip malformed lines but continue parsing
                    print(f"[VappmanListCache] Warning: Failed to parse line: {e}")
                    continue

            # Don't forget the last entry
            finalize_entry()
        except Exception as e:
            print(f"[VappmanListCache] Error during parsing: {e}")

        return apps, apps_by_key, databases


# --- 3. The Manager ---

class AppCacheManager:
    def __init__(self, cache_duration=3600):
        self.config_dir = os.path.expanduser("~/.config/vappman")
        self.list_file = os.path.join(self.config_dir, "list-all.txt")
        self.cache_duration = cache_duration
        self.binary = self._find_binary()
        self.dbs = set(['am'])
        self.apps = {}  # key: appname, value: list of namespaces
        self.apps_by_key = {}  # key: (appname, db), value: one namespace
        self.runner = None

    def _find_binary(self):
        for cmd in ["am", "appman"]:
            if shutil.which(cmd): return cmd
        raise RuntimeError("Neither 'am' nor 'appman' found in PATH.")

    def _parse_now(self):
        parser = VAppConfigParser(self.list_file)
        apps, apps_by_key, databases = parser.parse()
        if len(apps_by_key) > 1000: # actually expecting over 5000
            self.apps, self.apps_by_key, self.dbs = apps, apps_by_key, databases

    def refresh_background(self):
        if self.runner and self.runner.is_running(): return
        os.makedirs(self.config_dir, exist_ok=True)
        self.runner = CommandRunner([self.binary, "list", "--all"], self.list_file)
        self.runner.start()

    def get_apps(self):
        if not os.path.exists(self.list_file):
            # print("[Cache] No file found. Fetching initial list...")
            self.refresh_background()
            print('Fetching initial app list [IF STUCK, press ENTER several times]...')
            while self.runner.is_running(): time.sleep(0.1)
            print('... got initial app list ... continuing up ...')
            self._parse_now()
        else:
            self._parse_now()
            age = time.time() - os.path.getmtime(self.list_file)
            if age > self.cache_duration:
                # print(f"[Cache] File is {int(age)}s old. Refreshing in background...")
                self.refresh_background()
        return self.apps

    def check_for_updates(self):
        if self.runner and not self.runner.is_running():
            # print("[Cache] Background update finished. Reloading dict.")
            self._parse_now()
            self.runner = None
            return True
        return False


# --- 4. Main Test Block ---

if __name__ == "__main__":
    # Initialize with a very short cache duration (5 seconds) for testing
    manager = AppCacheManager(cache_duration=5)
    
    # 1. Initial Load
    apps = manager.get_apps()

    # Count duplicates
    dup_count = sum(1 for entries in apps.values() if len(entries) > 1)
    total_entries = sum(len(entries) for entries in apps.values())

    print(f"Initial Load:")
    print(f"  - {len(apps)} unique app names")
    print(f"  - {total_entries} total entries")
    print(f"  - {dup_count} app names with duplicates")
    print(f"  - {len(manager.apps_by_key)} entries in apps_by_key dict")

    # 2. Pick an app to display (show first entry for each)
    print("\n=== FIRST 50 APPS ===")
    for idx, (appname, entries) in enumerate(apps.items()):
        first = entries[0]
        dup_marker = f" [{len(entries)} versions]" if len(entries) > 1 else ""
        print(f"{appname!r}{dup_marker}: DB={first.db!r}, Synopsis={first.synopsis!r}\n")
        if idx >= 50:
            break

    # Show some examples of duplicates
    print("\n=== SAMPLE DUPLICATES ===")
    shown = 0
    for appname, entries in apps.items():
        if len(entries) > 1 and shown < 10:
            print(f"\n{appname!r} has {len(entries)} versions:")
            for entry in entries:
                print(f"  - db={entry.db!r}: {entry.synopsis[:60]}...")
            shown += 1

    # 3. Simulate a work loop and poll for the background update
    print("\nEntering loop. If the cache was stale, an update is running...")
    try:
        for i in range(10):
            if manager.check_for_updates():
                print(f"!!! DICTIONARY UPDATED. New count: {len(manager.apps)}")
                apps = manager.apps
            
            print(f"Doing other work... {i+1}/10")
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    print("Test complete.")
