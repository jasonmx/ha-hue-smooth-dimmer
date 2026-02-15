import csv
import os
from datetime import UTC, datetime

import requests

URL = "https://analytics.home-assistant.io/custom_integrations.json"
DOMAIN = "hue_dimmer"
CSV_PATH = ".analytics/installs.csv"


def main():
    response = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    data = response.json()

    if DOMAIN not in data:
        print("Domain not found in analytics.")
        return

    total_installs = data[DOMAIN]["total"]
    today = datetime.now(UTC).date().isoformat()

    os.makedirs(".analytics", exist_ok=True)

    rows = []
    last_value = None

    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if rows:
                last_value = int(rows[-1]["total_installs"])

    # Only log if value changed
    if last_value == total_installs:
        print("No change in installs. Skipping log.")
        return

    rows.append({"date": today, "total_installs": total_installs})

    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "total_installs"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Logged new install count: {total_installs}")


if __name__ == "__main__":
    main()
