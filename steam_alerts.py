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

def fetch_top_100_steam_native():
    """
    Paginates through Steam's official storesearch API to build a 100-item buffer.
    This avoids reliance on third-party APIs and HTML scraping.
    """
    url = "https://store.steampowered.com/api/storesearch/"
    all_items = []
    
    print("Paginating through Steam API to fetch top 100 sellers...")
    # Loop from 0 to 90 in steps of 10
    for start_idx in range(0, 100, 10):
        params = {
            "term": "",
            "search_filter": "topsellers",
            "cc": "US",
            "l": "english",
            "start": start_idx,
            "count": 10
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            items = data.get("items", [])
            if not items:
                break # Stop if Steam stops returning items
                
            all_items.extend(items)
            time.sleep(0.5) # Brief pause to respect Steam's rate limits
        except requests.exceptions.RequestException as e:
            print(f"Error fetching batch at start={start_idx}: {e}")
            break
            
    return all_items

def filter_and_deduplicate(raw_items):
    """Cleans the raw buffer list and outputs exactly 30 valid games."""
    valid_items = []
    seen_ids = set()
    seen_names = set()
    
    all_excluded = HARDWARE_BLOCKLIST + GAME_BLOCKLIST

    for item in raw_items:
        appid = item.get("id") or item.get("appid")
        name = item.get("name", "")
        name_lower = name.lower()
        
        if not appid or not name:
            continue
            
        if appid in seen_ids or name_lower in seen_names:
            continue
            
        is_blocked = any(excluded in name_lower for excluded in all_excluded)
        if is_blocked:
            continue
            
        valid_items.append(item)
        seen_ids.add(appid)
        seen_names.add(name_lower)
        
        if len(valid_items) == 30:
            break
            
    return valid_items

def format_slack_payload(filtered_items):
    """Formats the filtered items safely, ensuring an empty string is never sent."""
    # Safeguard: Handle the case where no items were found to prevent a 400 Bad Request
    if not filtered_items:
        combined_games_text = "⚠️ *No valid top sellers found.* The Steam API might be down or returning empty results."
    else:
        game_lines = []
        for rank, item in enumerate(filtered_items, start=1):
            name = item.get("name")
            appid = item.get("id")
            
            # Since we are using storesearch, the price is provided natively
            price_cents = item.get("price", {}).get("final") or 0
            price = f"${price_cents / 100:.2f}" if price_cents else "Free / Unknown"
            
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
                    "text": f"Filtered Top Sellers for {datetime.now().strftime('%Y-%m-%d')}."
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
        print("Successfully sent report to Slack.")
    except requests.exceptions.RequestException as e:
        print(f"Error sending to Slack: {e}")

if __name__ == "__main__":
    raw_buffer = fetch_top_100_steam_native()
    
    clean_top_30 = filter_and_deduplicate(raw_buffer)
    print(f"Found {len(clean_top_30)} valid items after filtering.")
        
    slack_payload = format_slack_payload(clean_top_30)
    send_to_slack(slack_payload)
