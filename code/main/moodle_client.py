# moodle_client.py
# Handles all communication with the Moodle website API.
# Used by export.py to fetch course data.

import hashlib
import time
from datetime import datetime

import requests


class MoodleClient:
    # Groups all tools needed to talk to Moodle's REST API.

    def __init__(self, base_url, token, salt):
        # Store the login details and build the API URL.
        self.token = token
        self.salt = salt
        self.api_url = base_url.rstrip("/") + "/webservice/rest/server.php"

    def anonymize_student_id(self, real_student_id):
        # Turn a real student ID into a private anonymous code.
        # The code is always the same for the same student, so data can be linked
        # across files without ever revealing who the student is.
        if real_student_id is None:
            return None

        combined = self.salt + str(real_student_id)
        hashed = hashlib.sha256(combined.encode()).hexdigest()
        return "u_" + hashed[:12]

    def unix_timestamp_to_date(self, unix_timestamp):
        # Convert a number like 1717255123 to a readable date like "2024-06-02 10:32:03".
        if not unix_timestamp or int(unix_timestamp) == 0:
            return None

        dt = datetime.fromtimestamp(int(unix_timestamp))
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def duration_in_seconds(self, start_unix, finish_unix):
        # Calculate how many seconds passed between a start time and a finish time.
        try:
            return int(finish_unix) - int(start_unix)
        except Exception:
            return None

    def parse_cmid_list(self, env_value):
        # Convert a comma-separated string like "123, 456" into a list of integers [123, 456].
        if not env_value:
            return []

        cmid_list = []
        for item in env_value.split(","):
            stripped = item.strip()
            if stripped.isdigit():
                cmid_list.append(int(stripped))

        return cmid_list

    def call_api(self, function_name, **parameters):
        # Send one request to Moodle and return the response as Python data.
        # If the network fails, retries up to 3 times with a 3-second pause between tries.

        # Build the data packet we send to Moodle
        payload = {
            "wstoken": self.token,
            "wsfunction": function_name,
            "moodlewsrestformat": "json",
        }

        # Moodle needs list values in the format key[0], key[1], key[2] etc.
        for key, value in parameters.items():
            if isinstance(value, list):
                for index, item in enumerate(value):
                    payload[f"{key}[{index}]"] = item
            else:
                payload[key] = value

        # Try up to 3 times before giving up
        for attempt in range(1, 4):
            try:
                response = requests.post(self.api_url, data=payload, timeout=60)
                response.raise_for_status()
                data = response.json()

                # Moodle sometimes sends an error message inside the JSON response
                if isinstance(data, dict) and data.get("exception"):
                    raise RuntimeError(f"Moodle error: {data.get('message')}")

                return data

            except Exception as error:
                if attempt == 3:
                    raise
                print(f"  Request failed (attempt {attempt}): {error}. Retrying in 3 seconds...")
                time.sleep(3)

    def get_all_course_modules(self, course_id):
        # Fetch every quiz, assignment, forum, and other activity in the course.
        # Returns a dictionary: {cmid: {"modname": "quiz", "instance": 42, "name": "Quiz 1"}}
        modules = {}

        sections = self.call_api("core_course_get_contents", courseid=course_id)

        for section in sections:
            for module in section.get("modules", []):
                cmid = module.get("id")
                if cmid:
                    modules[int(cmid)] = {
                        "modname": module.get("modname"),
                        "instance": module.get("instance"),
                        "name": module.get("name"),
                    }

        return modules

    def get_enrolled_student_ids(self, course_id):
        # Get a list of all student IDs enrolled in the course.
        users_data = self.call_api("core_enrol_get_enrolled_users", courseid=course_id)

        student_ids = []
        for user in users_data:
            student_ids.append(int(user["id"]))

        return student_ids
