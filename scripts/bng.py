
import argparse
import requests
from requests.auth import HTTPBasicAuth
from tabulate import tabulate
import sys
import getpass

# 🔧 Updated arguments
parser = argparse.ArgumentParser(description='PPP Session Analyzer (BNG)')
parser.add_argument('--server-ip', required=True, help='BNG server IP address (e.g., 213.133.199.244)')
parser.add_argument('--file', required=True, help='Path to the text file containing usernames (one per line)')
args = parser.parse_args()

# Authentification dynamique
auth_user = input("👤 BNG login username: ")
auth_pass = getpass.getpass("🔐 Password: ")

base_url = f"http://{args.server_ip}:2000"
auth = HTTPBasicAuth(auth_user, auth_pass)
headers = {
    "Content-Type": "application/xml",
    "Accept": "application/json"
}

# 🔧 Read usernames from file
try:
    with open(args.file, 'r') as f:
        username_list = [line.strip().lower() for line in f if line.strip()]
except Exception as e:
    print(f"❌ Could not read file {args.file}: {e}")
    sys.exit(1)

# Récupération des abonnés
try:
    response = requests.get(f"{base_url}/rpc/get-subscribers/extensive", headers=headers, auth=auth, timeout=60)
    response.raise_for_status()
    subs = response.json()
except requests.exceptions.RequestException as e:
    print(f"🚨 API Error: {str(e)}")
    sys.exit(1)

try:
    subscribers = subs["subscribers-information"][0]["subscriber"]
except (KeyError, IndexError, TypeError):
    print("❌ Unexpected API response structure")
    sys.exit(1)

# 🔧 Loop over usernames from file
for target_username in username_list:
    ppps = []
    for s in subscribers:
        try:
            user = s.get("user-name", [{}])[0].get("data", "").lower()
            iface = s.get("interface", [{}])[0].get("data", "")
            access = s.get("access-type", [{}])[0].get("data", "")

            if target_username != user or not (iface.startswith("pp0.") and access == "PPPoE"):
                continue

            ppps.append((iface, s))
        except Exception as e:
            print(f"⚠️ Error processing entry: {str(e)}")
            continue

    if not ppps:
        print(f"❌ No active PPPoE sessions found for username: {target_username}")
        continue

    for pp_if, subscriber in ppps:
        username = subscriber.get("user-name", [{}])[0].get("data", "N/A")

        print("\n" + "=" * 90)
        print(f"🧾 Information of the subscriber: {username}")
        print("=" * 90)

        session_info = [
            ["Session State", subscriber.get("state", [{}])[0].get("data", "N/A")],
            ["Session ID", subscriber.get("session-id", [{}])[0].get("data", "N/A")],
            ["Radius Accounting ID", subscriber.get("radius-accounting-id", [{}])[0].get("data", "N/A")],
            ["Type", subscriber.get("access-type", [{}])[0].get("data", "N/A")],
            ["Service Name", subscriber.get("routing-instance", [{}])[0].get("data", "N/A")],
            ["Remote MAC", subscriber.get("mac-address", [{}])[0].get("data", "N/A")],
            ["Session AC Name", subscriber.get("nas-ip-address", [{}])[0].get("data", "N/A")],
            ["Session Uptime", subscriber.get("login-time", [{}])[0].get("data", "N/A")],
            ["Dynamic Profile", subscriber.get("dynamic-profile", [{}])[0].get("data", "N/A")],
            ["Underlying Interfaces", pp_if],
        ]
        print("\n📶 PPPoE Session Info")
        print(tabulate(session_info, headers=["Field", "Value"], tablefmt="fancy_grid"))

        try:
            resp = requests.get(f"{base_url}/rpc/get-ppp-interface-information/interface-name={pp_if}/extensive", headers=headers, auth=auth)
            data = resp.json()
            sessions = data.get("ppp-interface-information", [])[0].get("ppp-session", [])
        except:
            print("⚠️ Could not fetch detailed PPP information.")
            continue

        for s in sessions:
            def safe(section, key):
                return section.get(key, [{}])[0].get("data", "N/A")

            for section in s.get("ppp-session-protocol-information", []):
                if section.get("ppp-protocol", [{}])[0].get("data") != "IPCP":
                    continue
                opts = section.get("ppp-negotiated-options", [{}])[0]
                ipcp = opts.get("ipcp-address", [{}])[0]
                ipcp_info = [
                    ["State", safe(section, "ppp-state")],
                    ["Last Started", safe(section, "ppp-last-started")],
                    ["Last Completed", safe(section, "ppp-last-completed")],
                    ["Local Address", ipcp.get("local-address", [{}])[0].get("data", "N/A")],
                    ["Remote Address", ipcp.get("remote-address", [{}])[0].get("data", "N/A")],
                    ["Primary DNS", opts.get("ipcp-primary-dns", [{}])[0].get("data", "N/A")],
                    ["Secondary DNS", opts.get("ipcp-secondary-dns", [{}])[0].get("data", "N/A")]
                ]
                print("\n🧩 IPCP Information")
                print(tabulate(ipcp_info, headers=["IPCP", "Value"], tablefmt="fancy_grid"))

            for section in s.get("ppp-auth-protocol-information", []):
                auth_info = [
                    ["Protocol", safe(section, "ppp-auth-proto")],
                    ["State", safe(section, "ppp-state")],
                    ["Last Started", safe(section, "ppp-last-started")],
                    ["Last Completed", safe(section, "ppp-last-completed")]
                ]
                print("\n🔐 CHAP/PAP Authentication")
                print(tabulate(auth_info, headers=["Auth Info", "Value"], tablefmt="fancy_grid"))

            for section in s.get("ppp-session-protocol-information", []):
                if section.get("ppp-protocol", [{}])[0].get("data") != "LCP":
                    continue
                opts = section.get("ppp-negotiated-options", [{}])[0]
                lcp_info = [
                    ["State", safe(section, "ppp-state")],
                    ["Last Started", safe(section, "ppp-last-started")],
                    ["Last Completed", safe(section, "ppp-last-completed")],
                    ["Authentication Protocol", opts.get("authentication-protocol", [{}])[0].get("data", "N/A")],
                    ["Magic Number", opts.get("magic-number", [{}])[0].get("data", "N/A")],
                    ["Advertised MRU", opts.get("advertised-mru", [{}])[0].get("data", "N/A")],
                    ["Local MRU", opts.get("local-mru", [{}])[0].get("data", "N/A")],
                    ["Peer MRU", opts.get("peer-mru", [{}])[0].get("data", "N/A")],
                ]
                print("\n🔄 LCP Information")
                print(tabulate(lcp_info, headers=["LCP", "Value"], tablefmt="fancy_grid"))

