import os
import requests
import json
from datetime import datetime

# Configuration
# The featuredcategories endpoint provides pure JSON data directly from the storefront.
STEAM_API_URL = "https://store.steampowered.com/api/featuredcategories?cc=US&l=english"
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

# Excluded terms (lowercase for case-insensitive matching)
EXCLUDED_TERMS = [
    "steam deck", "steam frame", "cs2", "marvel rivals", 
    "last of us 2", "destiny 2", "overwatch", "rust", "kingdom hearts"
]

def fetch_top_sellers():
    """Fetches the top sellers JSON from the Steam Storefront API."""
    try:
        response = requests.get(STEAM_API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        # Extract the items array from the top_sellers category
        return data.get("top_sellers", {}).get("items", [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from Steam: {e}")
        return []

def filter_items(items):
    """Filters out excluded terms from the items list."""
    filtered = []
    for item in items:
        name_lower = item.get("name", "").lower()
        # Skip if any excluded term is found in the item's name
        if not any(excluded in name_lower for excluded in EXCLUDED_TERMS):
            filtered.append(item)
    
    # Trim to a maximum of 30 items if the endpoint returns more
    return filtered[:30]

def format_slack_payload(filtered_items):
    """Formats the filtered items into a Slack Block Kit payload."""
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🏆 Daily Steam Top Sellers Alert",
                "emoji": True
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Filtered Top Sellers for {datetime.now().strftime('%Y-%m-%d')}."
                }
            ]
        },
        {"type": "divider"}
    ]

    for rank, item in enumerate(filtered_items, start=1):
        name = item.get("name")
        appid = item.get("id")
        # Price is returned in cents; convert to decimal
        price = f"${item.get('final_price', 0) / 100:.2f}"
        store_url = f"https://store.steampowered.com/app/{appid}/"
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{rank}. {name}*\nPrice: {price} | <{store_url}|Store Page>"
            },
            "accessory": {
                "type": "image",
                "image_url": item.get("header_image", ""),
                "alt_text": name
            }
        })
        
    return {"blocks": blocks}

def send_to_slack(payload):
    """Sends the formatted payload to the Slack Webhook."""
    if not SLACK_WEBHOOK_URL:
        print("Error: SLACK_WEBHOOK_URL environment variable is not set.")
        return
        
    try:
        response = requests.post(
            SLACK_WEBHOOK_URL, 
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        print("Successfully sent report to Slack.")
    except requests.exceptions.RequestException as e:
        print(f"Error sending to Slack: {e}")

if __name__ == "__main__":
    print("Fetching Steam data...")
    raw_items = fetch_top_sellers()
    
    if raw_items:
        filtered_list = filter_items(raw_items)
        slack_payload = format_slack_payload(filtered_list)
        send_to_slack(slack_payload)
    else:
        print("No items to process.")
