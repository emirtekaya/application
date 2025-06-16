import argparse
import json
import urllib.parse
import requests
import sys
import time
import threading
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s - %(message)s',
    datefmt='%H:%M:%S'
)

ACS_BASE_URL = "http://13.69.26.119:7557/devices"

PARAMS = [
"Device.PPP.Interface.2.IPCP.LocalIPAddress",
"InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANPPPConnection.1.ExternalIPAddress"
]

FIELD_MAP = {
    "mac": [
        "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANPPPConnection.1.MACAddress",
        "Device.Ethernet.Interface.1.MACAddress"
    ],
    "ip": [
        "Device.PPP.Interface.2.IPCP.LocalIPAddress",
        "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANPPPConnection.1.ExternalIPAddress"
    ],
    "ppp": [
        "VirtualParameters.PPPoEUsername"
    ]
}


def spinner(message, event):
    spinstr = "|/-\\"
    idx = 0
    while not event.is_set():
        sys.stdout.write(f"\r{message} {spinstr[idx % len(spinstr)]}")
        sys.stdout.flush()
        idx += 1
        time.sleep(0.2)
    sys.stdout.write("\r")


def get_device_id(fields, value):
    """
    fields: list of potential parameter paths
    value: value to match
    """
    for field in fields:
        query = urllib.parse.quote(json.dumps({field: value}))
        url = f"{ACS_BASE_URL}/?query={query}"
        logging.info(f"Trying field: {field} with value: {value}")

        try:
            response = requests.get(url)
            response.raise_for_status()
            device_list = response.json()
            if device_list:
                logging.info(f"✅ Match found using field: {field}")
                return device_list[0]["_id"]
        except requests.RequestException as e:
            logging.warning(f"Request error on field {field}: {e}")
        except json.JSONDecodeError:
            logging.warning("JSON decode error")

    logging.warning(f"❌ No matching device found for value: {value}")
    return None


def send_refresh_task(device_id):
    encoded_id = urllib.parse.quote(device_id)
    post_url = f"{ACS_BASE_URL}/{encoded_id}/tasks?connection_request"
    payload = {"name": "refreshObject", "objectName": ""}
    logging.info(f"Sending refreshObject task to device: {device_id}")

    try:
        response = requests.post(post_url, json=payload)
        if response.status_code == 200:
            logging.info("refreshObject task sent successfully.")
        else:
            logging.error(f"Failed to send task. Status: {response.status_code} - {response.text}")
            response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"HTTP error while sending refresh task: {e}")
        raise


def retrieve_parameters(device_id):
    projection = urllib.parse.quote(",".join(PARAMS))
    query_id = urllib.parse.quote(json.dumps({"_id": device_id}))
    full_url = f"{ACS_BASE_URL}?query={query_id}&projection={projection}"
    logging.info("Retrieving parameter values from ACS.")

    try:
        response = requests.get(full_url)
        response.raise_for_status()
        data = response.json()

        if not data:
            logging.warning("No data returned for device.")
            return

        print("📥 Parameter values retrieved:")
        for param in PARAMS:
            path = param.split(".")
            val = data[0]
            for p in path:
                val = val.get(p, {})
            print(f"➡️  {param} = {val.get('_value', '❌ no value')}")
    except requests.RequestException as e:
        logging.error(f"HTTP error while retrieving parameters: {e}")
        raise
    except json.JSONDecodeError:
        logging.error("Failed to decode JSON response for parameters.")
        raise
    except Exception as e:
        logging.error(f"Unexpected error while retrieving parameters: {e}")
        raise


def process_value(search_type, value):
    fields = FIELD_MAP[search_type]

    event = threading.Event()
    thread = threading.Thread(target=spinner, args=(f"🔍 Searching device ID for '{value}'", event))
    thread.start()

    try:
        device_id = get_device_id(fields, value)
        event.set()
        thread.join()

        if not device_id:
            print(f"❌ Device not found for {search_type}: {value}")
            return

        print(f"\n✅ Found device ID for {value}: {device_id}")
    except Exception as e:
        event.set()
        thread.join()
        print(f"❌ Error occurred searching device for {value}: {e}")
        return

    event.clear()
    thread = threading.Thread(target=spinner, args=(f"⚙️  Sending refreshObject task for '{value}'", event))
    thread.start()

    try:
        send_refresh_task(device_id)
        event.set()
        thread.join()
    except Exception as e:
        event.set()
        thread.join()
        print(f"❌ Error occurred sending refresh task for {value}: {e}")
        return

    try:
        retrieve_parameters(device_id)
    except Exception as e:
        print(f"❌ Error occurred retrieving parameters for {value}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Process device info from a file or single input")
    parser.add_argument("search_type", choices=["mac", "ip", "ppp"], help="Type of search")
    parser.add_argument("--input-file", help="Fichier contenant les valeurs, une par ligne")
    parser.add_argument("--single-value", help="Valeur unique à chercher (alternative à --input-file)")

    args = parser.parse_args()

    if args.input_file:
        try:
            with open(args.input_file, "r") as f:
                values = [line.strip() for line in f if line.strip()]
        except Exception as e:
            logging.error(f"Failed to read input file: {e}")
            sys.exit(1)
    elif args.single_value:
        values = [args.single_value]
    else:
        logging.error("Il faut fournir --input-file ou --single-value")
        sys.exit(1)

    for val in values:
        print(f"\n=== Processing {args.search_type}: {val} ===")
        process_value(args.search_type, val)


if __name__ == "__main__":
    main()
