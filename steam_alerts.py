import os
import requests
import json
from datetime import datetime

# Configuration
# Using the storesearch endpoint allows us to pass a 'count' parameter to fetch a larger buffer of 100 items.
STEAM_API_URL = "https://store.steampowered.com/api/storesearch/?term=&search_filter=topsellers&cc=US&l=english&start=0&count=100"
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

# Comprehensive Blocklists (lowercase for case-insensitive matching)
HARDWARE_BLOCKLIST = [
    "steam deck", "steam frame", "steam machine", 
    "steam controller", "valve index", "steamvr"
]

GAME_BLOCKLIST = [
    "cs2", "counter-strike", "marvel rivals", 
    "last of us", "the last of us", "destiny 2", 
    "overwatch", "rust", "kingdom hearts"
]

def fetch_top_sellers_buffer():
    """Fetches a buffer of 100 top sellers from the Steam Store API."""
    try:
        response = requests.get(STEAM_API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Depending on the exact endpoint, the items might be under 'items' or 'top_sellers'
        # The storesearch endpoint typically puts them directly in an 'items' array
        return data.get("items", [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from Steam: {e}")
        return []

def filter_and_deduplicate(raw_items):
    """
    Cleans the raw list by deduplicating and excluding blocklisted terms,
    then guarantees an output of exactly 30 items.
    """
    valid_items = []
    seen_ids = set()
    seen_names = set()
    
    # Combine blocklists for iteration
    all_excluded = HARDWARE_BLOCKLIST + GAME_BLOCKLIST

    for item in raw_items:
        name = item.get("name", "")
        name_lower = name.lower()
        appid = item.get("id") or item.get("appid")
        
        # 1. Deduplication: Skip if we've already seen this App ID or exact Title
        if appid in seen_ids or name_lower in seen_names:
            continue
            
        # 2. Blocklist Check: Skip if the name contains any excluded substring
        is_blocked = False
        for excluded_term in all_excluded:
            if excluded_term in name_lower:
                is_blocked = True
                break
                
        if is_blocked:
            continue
            
        # 3. Validation: If it passes both checks, add it to our valid list and mark as seen
        valid_items.append(item)
        seen_ids.add(appid)
        seen_names.add(name_lower)
        
        # 4. Strict Limit: Stop processing once we have exactly 30 clean items
        if len(valid_items) == 30:
            break
            
    return valid_items

def format_slack_payload(filtered_items):
    """
    Formats the top 30 valid items into a single, compact Slack Block Kit payload
    to avoid hitting Slack's 50-block maximum limit.
    """
    # 1. Initialize a list to hold the formatted text strings for each game
    game_lines = []
    
    # 2. Iterate through the filtered list and build each line
    for rank, item in enumerate(filtered_items, start=1):
        name = item.get("name")
        appid = item.get("id") or item.get("appid")
        
        # Check multiple common Steam JSON price keys
        price_cents = item.get("price", {}).get("final") or item.get("final_price") or 0
        price = f"${price_cents / 100:.2f}" if price_cents else "Free / Unknown"
        
        store_url = f"https://store.steampowered.com/app/{appid}/"
        
        # Append the specific compact markdown format requested
        game_lines.append(f"{rank}. *{name}* — {price} | <{store_url}|Store Page>")
    
    # 3. Join all the individual game strings together using a newline character (\n)
    # This creates one large continuous text block containing all 30 games.
    combined_games_text = "\n".join(game_lines)
    
    # 4. Construct the final Block Kit payload using only 4 blocks
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
        print("Successfully sent 30-item report to Slack.")
    except requests.exceptions.RequestException as e:
        print(f"Error sending to Slack: {e}")

if __name__ == "__main__":
    print("Fetching Steam data buffer (100 items)...")
    raw_buffer = fetch_top_sellers_buffer()
    
    if raw_buffer:
        clean_top_30 = filter_and_deduplicate(raw_buffer)
        
        if len(clean_top_30) < 30:
            print(f"Warning: Only found {len(clean_top_30)} valid items after filtering.")
            
        slack_payload = format_slack_payload(clean_top_30)
        send_to_slack(slack_payload)
    else:
        print("Failed to retrieve items or API returned an empty list.")
