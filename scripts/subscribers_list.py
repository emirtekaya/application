import subprocess
import json
import os

# Replace with your actual server IP
server_ip = "213.133.199.244"

curl_command = [
    "curl",
    f"http://{server_ip}:2000/rpc/get-subscribers/extensive",
    "-u", "support:sabel2025!",
    "-H", "Content-Type: application/xml",
    "-H", "Accept: application/json"
]

try:
    result = subprocess.run(curl_command, capture_output=True, text=True, timeout=10)
    output = result.stdout

    # Load the JSON (handle double-decoding if needed)
    data = json.loads(output)
    if isinstance(data, str):
        data = json.loads(data)

    # Navigate to the subscribers list
    subscribers = data.get("subscribers-information", [])[0].get("subscriber", [])

    # Extract usernames
    usernames = []
    for sub in subscribers:
        user_name_list = sub.get("user-name", [])
        if user_name_list and isinstance(user_name_list[0], dict):
            username = user_name_list[0].get("data")
            if username:
                usernames.append(username)

    # Write usernames to a file (plain list, no formatting)
    with open("datas/usernames", "w") as file:
        file.write("\n".join(usernames))

except Exception as e:
    print("❌ Error:", e)

