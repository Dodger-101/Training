#!/usr/bin/env python3

import datetime
import json
import socket
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
SHELF_FILE = BASE_DIR / "shelves_config.json"
HIDDEN_CONFIG_KEYS = {"shekel_email", "shekel_password"}


def format_default(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def parse_value(raw_value, default):
    if isinstance(default, bool):
        normalized = raw_value.strip()
        if normalized == "1":
            return True
        if normalized == "2":
            return False
        raise ValueError("Please enter 1 for true or 2 for false.")

    if isinstance(default, int) and not isinstance(default, bool):
        return int(raw_value)

    if isinstance(default, float):
        return float(raw_value.replace(",", "."))

    if default is None or isinstance(default, (list, dict)):
        return json.loads(raw_value)

    return raw_value


def ask_value(name, default):
    while True:
        if isinstance(default, bool):
            default_choice = "1" if default else "2"
            prompt = (
                f"{name} (1 = true, 2 = false) "
                f"[{default_choice}]: "
            )
        else:
            prompt = f"{name} [{format_default(default)}]: "

        answer = input(prompt).strip()

        if not answer:
            return default

        try:
            return parse_value(answer, default)
        except (ValueError, json.JSONDecodeError) as error:
            print(f"Invalid input: {error}")


def edit_config_main():
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as file:
            config = json.load(file)
    except FileNotFoundError:
        print(f"Error: {CONFIG_FILE} was not found.")
        return 1
    except json.JSONDecodeError as error:
        print(f"Error: config.json contains invalid JSON: {error}")
        return 1

    if not isinstance(config, dict):
        print("Error: config.json must contain a JSON object.")
        return 1

    print("Edit config (press Enter to keep the value in brackets).\n")

    updated_config = config.copy()
    for name, current_value in config.items():
        if name not in HIDDEN_CONFIG_KEYS:
            updated_config[name] = ask_value(name, current_value)

    with CONFIG_FILE.open("w", encoding="utf-8") as file:
        json.dump(updated_config, file, ensure_ascii=False, indent=4)
        file.write("\n")

    print(f"\nConfig saved: {CONFIG_FILE}")
    return 0


SHEKEL_BASE_URL = "https://integration.shekelbrainweighmc.com/FlexiCore/rest"

AUTH_URL = f"{SHEKEL_BASE_URL}/authenticationNew/login"
DATA_URL = f"{SHEKEL_BASE_URL}/plugins/facade/listAllBays"

OUTPUT_FILE = SHELF_FILE

def remove_duplicate_ids(elements):
    """
    Keeps the first element for each ID.
    Additional elements with the same ID are removed.
    """
    seen_ids = set()
    unique_elements = []

    for element in elements:
        element_id = element.get("id")

        # Keep elements that do not have an ID
        if element_id is None:
            unique_elements.append(element)
            continue

        if element_id in seen_ids:
            print(f"Duplicate ID removed: {element_id}")
            continue

        seen_ids.add(element_id)
        unique_elements.append(element)

    return unique_elements


def get_shelves_main():
    with CONFIG_FILE.open("r", encoding="utf-8") as file:
        config = json.load(file)

    email = config.get("shekel_email")
    password = config.get("shekel_password")
    if not email or not password:
        raise ValueError("shekel_email and shekel_password are required")

    session = requests.Session()

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # --------------------------------------------------
    # 1. Log in
    # --------------------------------------------------
    auth_response = session.post(
        AUTH_URL,
        headers=headers,
        json={
            "email": email,
            "password": password
        },
        timeout=30
    )

    auth_response.raise_for_status()

    print("Login successful")

    # Token-based authentication, if available
    try:
        auth_data = auth_response.json()

        token = (
            auth_data.get("authenticationKey")
        )

        if token:
            session.headers.update({
                "authenticationKey": token
            })

    except ValueError:
        # Cookie-based authentication
        pass

    # --------------------------------------------------
    # 2. Retrieve all pages
    # --------------------------------------------------
    all_elements = []

    currentPage = 0
    last_response_json = None

    while True:
        print(f"Retrieving page {currentPage}...")

        response = session.post(
            DATA_URL,
            headers=headers,
            json={
                "bayIds": [],
                "currentPage": currentPage
            },
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        # Save the response for later use
        last_response_json = data

        # Add elements from "list"
        elements = data.get("list", [])

        all_elements.extend(elements)

        print(
            f"Page {currentPage}: "
            f"{len(elements)} elements | "
            f"Total collected: {len(all_elements)}"
        )

        # For example, endPage = 4
        end_page = data.get("endPage")

        if end_page is None:
            raise ValueError("API response does not contain 'endPage'")

        # currentPage 0,1,2,3 when endPage = 4
        currentPage += 1

        if currentPage >= end_page:
            break

    # --------------------------------------------------
    # 3. Remove duplicates
    # --------------------------------------------------
    print()
    print(f"Elements before cleanup: {len(all_elements)}")

    unique_elements = remove_duplicate_ids(all_elements)

    print(f"Elements after cleanup: {len(unique_elements)}")
    print(f"Duplicates removed: {len(all_elements) - len(unique_elements)}")

    # --------------------------------------------------
    # 4. Create the combined JSON document
    # --------------------------------------------------

    # Preserve metadata from the API response
    result = last_response_json.copy()

    # Insert the complete merged list
    result["list"] = unique_elements

    # Set totalRecords to the actual count after deduplication
    result["totalRecords"] = len(unique_elements)

    # The result now contains all retrieved records
    result["startPage"] = 0

    # --------------------------------------------------
    # 5. Save the JSON file
    # --------------------------------------------------
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=4
        )

    print()
    print(f"Done. JSON saved to: {OUTPUT_FILE}")



def load_config():
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as file:
            config = json.load(file)

        if not isinstance(config, dict):
            raise ValueError("config.json must contain a JSON object.")

        return config

    except FileNotFoundError:
        print("Error: 'config.json' not found! Using default values.")
    except (json.JSONDecodeError, ValueError) as error:
        print(f"Error: config.json is invalid: {error}")
        print("Using default values.")

    return {}


def ask_boolean(question, default=False):
    default_choice = "y" if default else "n"

    while True:
        answer = input(
            f"{question} (y = yes, n = no) [{default_choice}]: "
        ).strip().lower()

        if not answer:
            return default
        if answer == "y":
            return True
        if answer == "n":
            return False

        print("Invalid input. Please enter y or n.")


# --------------------------------------------------
# Load Shekel data from shelves_config.json
# --------------------------------------------------

def load_shelf_lookup():
    """
    Loads shelves_config.json and builds a lookup:

    Shelf ID -> shelf/bay information
    """

    try:
        with SHELF_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        shelf_lookup = {}

        for bay in data.get("list", []):
            bay_name = bay.get("name", "Unknown")
            bay_id = bay.get("id", "")
            shelves = bay.get("shelvesTopToBottom", [])

            for index, shelf in enumerate(shelves):

                shelf_id = shelf.get("id")

                if not shelf_id:
                    continue

                shelf_lookup[shelf_id] = {
                    "bay_name": bay_name,
                    "bay_id": bay_id,
                    "shelf_position": index + 1,
                    "shelf": shelf,
                    "shelvesTopToBottom": shelves
                }

        print(f"Shekel data loaded: {len(shelf_lookup)} shelves found.")

        return shelf_lookup

    except FileNotFoundError:
        print("WARNING: shelves_config.json was not found.")
        print("Shelf names therefore cannot be assigned.")
        return {}

    except json.JSONDecodeError:
        print("ERROR: shelves_config.json does not contain valid JSON.")
        return {}


# --------------------------------------------------
# Main program
# --------------------------------------------------

def run():

    print("--- Smart Shelf Monitor starting ---")

    # --------------------------------------------------
    # 1. Optionally edit the configuration
    # --------------------------------------------------

    if ask_boolean("Do you want to edit the config?"):
        if edit_config_main() != 0:
            print("The config could not be edited.")
            return

    # --------------------------------------------------
    # 2. Load config.json
    # --------------------------------------------------

    config = load_config()

    ip_address = config.get("nats_ip", "10.90.5.20")
    dump_log = config.get("dump_log", True)
    full_output = config.get("full_output", False)

    try:
        min_weight = float(config.get("min_weight_g", 0.0))
    except (TypeError, ValueError):
        print("Error: min_weight_g is invalid. Using default value 0.0.")
        min_weight = 0.0

    print(f"Config loaded: NATS IP={ip_address}, Filter={min_weight}g")

    # --------------------------------------------------
    # 3. Optionally retrieve a new shelf configuration
    # --------------------------------------------------

    if ask_boolean("Do you want to retrieve a new shelf config?"):
        try:
            get_shelves_main()
        except Exception as error:
            print(f"Shelf config could not be retrieved: {error}")
            return

    shelf_lookup = load_shelf_lookup()

    # --------------------------------------------------
    # 4. Connect to NATS
    # --------------------------------------------------

    print("\n--- Start ---")

    print(f"Connecting to NATS server at {ip_address}...")

    s = socket.socket()
    s.settimeout(30)
    try:
        s.connect((ip_address, 4222))
    except OSError as error:
        print(f"Error: Could not connect to {ip_address}. ({error})")
        s.close()
        return

    s.sendall(
        b'CONNECT {"verbose":false}\r\n'
        b'SUB > 1\r\n'
    )

    s.settimeout(None)

    print("Connected!")

    if dump_log:
        print("All NATS messages will be written to 'all_messages.log'.")
    else:
        print("Logfile dump is DISABLED.")

    print(f"Waiting for live events (from {min_weight}g)...\n")

    buffer = ""

    log_path = BASE_DIR / "all_messages.log"
    f = log_path.open("a", encoding="utf-8") if dump_log else None

    try:

        while True:

            data = s.recv(4096)

            if not data:
                break

            text = data.decode("utf-8", "ignore")

            buffer += text

            while "\n" in buffer:

                line, buffer = buffer.split("\n", 1)

                line = line.strip()

                if not line:
                    continue

                # ------------------------------------------
                # Log file
                # ------------------------------------------

                if dump_log and f:

                    f.write(line + "\n")
                    f.flush()

                # ------------------------------------------
                # Detect JSON messages
                # ------------------------------------------

                if line.startswith("{") and line.endswith("}"):

                    try:

                        msg = json.loads(line)

                        if "weight" in msg or "location" in msg:

                            # ----------------------------------
                            # Weight
                            # ----------------------------------

                            raw_weight = msg.get("weight", 0.0)

                            try:
                                weight = round(float(raw_weight), 2)

                            except (ValueError, TypeError):
                                weight = raw_weight

                            # Ignore small weight fluctuations
                            try:

                                if abs(float(weight)) < min_weight:
                                    continue

                            except (ValueError, TypeError):
                                pass

                            # ----------------------------------
                            # Timestamp
                            # ----------------------------------

                            ts_raw = msg.get(
                                "measurementTimestamp",
                                msg.get("measurement_timestamp", "")
                            )

                            readable_timestamp = ts_raw

                            if ts_raw:

                                try:

                                    ts_float = float(ts_raw)

                                    if ts_float > 1e11:
                                        ts_float = ts_float / 1000.0

                                    readable_timestamp = datetime.datetime.fromtimestamp(
                                        ts_float
                                    ).strftime(
                                        "%d.%m.%Y %H:%M:%S"
                                    )

                                except (ValueError, TypeError):
                                    pass

                            # ----------------------------------
                            # Position
                            # ----------------------------------

                            raw_location = msg.get("location", 0.0)

                            try:

                                location_cm = round(
                                    float(raw_location) * 100
                                )

                            except (ValueError, TypeError):

                                location_cm = raw_location

                            # ----------------------------------
                            # Shelf ID from NATS
                            # ----------------------------------

                            shelf_id = msg.get(
                                "shelfId",
                                msg.get("shelf_id", "")
                            )

                            shelf_ordinal = msg.get(
                                "shelfOrdinal",
                                msg.get("shelf_ordinal", "")
                            )

                            # ----------------------------------
                            # Match the shelf ID with Shekel data
                            # ----------------------------------

                            shelf_info = shelf_lookup.get(shelf_id)

                            # ----------------------------------
                            # Output
                            # ----------------------------------

                            print("-" * 40)

                            print(f"Timestamp: {readable_timestamp}")
                            print(f"Weight in g: {weight}")
                            print(f"Location in cm: {location_cm}")

                            print(f"Shelf-ID: {shelf_id}")

                            if shelf_info:

                                print(
                                    f"Shelf name: "
                                    f"{shelf_info['bay_name']}"
                                )

                                print(
                                    f"Shelf Position (Top to Bottom): "
                                    f"{shelf_info['shelf_position']}"
                                )

                            else:

                                print(
                                    "Shelf name: Shelf ID "
                                    "not found in shelves_config.json"
                                )

                            if full_output:

                                print(f"ShelfOrdinal: {shelf_ordinal}")

                                if shelf_info:

                                    print(
                                        f"Bay-ID: "
                                        f"{shelf_info['bay_id']}"
                                    )

                                    print(
                                        "Shelf enabled:",
                                        shelf_info["shelf"].get("enabled")
                                    )

                    except json.JSONDecodeError:
                        pass

    finally:

        if f:
            f.close()

        s.close()


if __name__ == "__main__":
    run()
