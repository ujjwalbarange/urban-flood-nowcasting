#!/usr/bin/env python3
"""
Template for the MOSDAC Data Download API. Fill in YOUR OWN MOSDAC credentials below
(the user of this script stated they already have a MOSDAC account).
Do NOT commit real credentials to version control.
Follow MOSDAC's own user manual: https://www.mosdac.gov.in/user-manual-mosdac-data-download-api
"""
import json

config = {
    "user_credentials": {
        "username": "FILL_IN_YOUR_MOSDAC_USERNAME",
        "password": "FILL_IN_YOUR_MOSDAC_PASSWORD",
    },
    "search_parameters": {
        # Fill in the EXACT product name after browsing:
        # https://mosdac.gov.in -> Data Access -> Order Data / API based Access / Open Data
        "product": "FILL_IN_PRODUCT_NAME (e.g. GSMaP-ISRO Rain, MT-SAPHIR rainfall)",
        "start_date": "2015-01-01",
        "end_date": "2025-12-31",
        "bbox": [72.75, 18.85, 72.98, 19.30],
    },
}
with open("mosdac_config.json", "w") as f:
    json.dump(config, f, indent=2)

print("Wrote mosdac_config.json - fill in credentials and product name,")
print("then run MOSDAC's official download client per their user manual:")
print("https://www.mosdac.gov.in/user-manual-mosdac-data-download-api")
