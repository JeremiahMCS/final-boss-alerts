import os
import requests
import json
import time
from datetime import datetime

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

# Comprehensive Blocklists
HARDWARE_BLOCKLIST = [
    "steam deck", "steam frame", "steam machine", 
    "steam controller", "valve index", "steamvr"
]

GAME_BLOCKLIST = [
    "cs2", "counter-strike", "marvel rivals", 
    "last of us", "the last of us", "destiny 2", 
    "overwatch", "rust", "kingdom hearts"
]

def fetch_top_100_sellers():
    """
    Fetches the Top 100 Global Sellers from a reliable 3rd-party API 
    because Steam's 'storesearch' is hard-limited to 10 items.
    """
    url = "https://games-popularity.com/swagger/api/top-sellers"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Handle if the API returns a direct list or is wrapped in a dict
        if isinstance(data, list):
            return data
        return data.get("items") or data.get("data") or []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching top 100 sellers: {e}")
        return []

def get_steam_price(appid):
    """
    Fetches the official price from Steam's appdetails endpoint.
    Prices are returned in cents, and this endpoint bypasses age gates.
    """
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        
        app_data = data.get(str(appid), {})
        if not app_data.get("success"):
            return "Unknown"
            
        game_info = app_data.get("data", {})
        
        # Check if the game is listed as free
        if game_info.get("is_free"):
            return "Free / Unknown"
            
        price_overview = game_info.get("price_overview")
        if price_overview:
            # Convert cents to decimal format
            cents = price_overview.get("final", 0)
            return f"${cents / 100:.2f}"
            
        return "Unknown"
    except Exception:
        return "Unknown"

def filter_and_deduplicate(raw_items):
    """Cleans the raw 100-item list and outputs exactly 30 valid games."""
    valid_items = []
    seen_ids = set()
    seen_names = set()
    
    all_excluded = HARDWARE_BLOCKLIST + GAME_BLOCKLIST

    for item in raw_items:
        # Accommodate different potential JSON key names
        appid = item.get("steamId") or item.get("appid") or item.get("id")
        name = item.get("name", "")
        name_lower = name.lower()
        
        if not appid or not name:
            continue
            
        if appid in seen_ids or name_lower in seen_names:
            continue
            
        is_blocked = any(excluded in name_lower for excluded in all_excluded)
        if is_blocked:
            continue
            
        # Add to our valid list
        valid_items.append({"appid": appid, "name": name})
        seen_ids.add(appid)
        seen_names.add(name_lower)
        
        if len(valid_items) == 30:
            break
            
    return valid_items

def format_slack_payload(filtered_items):
    """Fetches pricing for the 30 items and formats them into a single Slack block."""
    game_lines = []
    
    print("Fetching live prices from Steam for 30 items...")
    for rank, item in enumerate(filtered_items, start=1):
        name = item["name"]
        appid = item["appid"]
        
        # Get the official price (with a tiny delay to be polite to Steam's servers)
        price = get_steam_price(appid)
        time.sleep(0.1) 
        
        store_url = f"https://store.steampowered.com/app/{appid}/"
        game_lines.append(f"{rank}. *{name}* — {price} | <{store_url}|Store Page>")
    
    combined_games_text = "\n".join(game_lines)
    
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
                    "text": f"Filtered Top 30 Sellers for {datetime.now().strftime('%Y-%m-%d')}."
                }
            ]
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": combined_games_text
            }
        }
    ]
        
    return {"blocks": blocks}

def send_to_slack(payload):
    """Pushes the payload to the provided Slack webhook."""
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
        print("Successfully sent full 30-item report to Slack.")
    except requests.exceptions.RequestException as e:
        print(f"Error sending to Slack: {e}")

if __name__ == "__main__":
    print("Fetching Top 100 Steam buffer...")
    raw_buffer = fetch_top_100_sellers()
    
    if raw_buffer:
        clean_top_30 = filter_and_deduplicate(raw_buffer)
        
        if len(clean_top_30) < 30:
            print(f"Warning: Only found {len(clean_top_30)} valid items after filtering.")
            
        slack_payload = format_slack_payload(clean_top_30)
        send_to_slack(slack_payload)
    else:
        print("Failed to retrieve items or API returned an empty list.")
