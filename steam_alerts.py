import os
import requests
import json
from datetime import datetime

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

# Replace these with your actual GitHub username and repository name!
GITHUB_PAGES_URL = "https://JeremiahMCS.github.io/final-boss-alerts/"

HARDWARE_BLOCKLIST = [
    "steam deck", "steam frame", "steam machine", 
    "steam controller", "valve index", "steamvr"
]

GAME_BLOCKLIST = [
    "cs2", "counter-strike", "marvel rivals", 
    "last of us", "the last of us", "destiny 2", 
    "overwatch", "rust", "kingdom hearts"
]

def fetch_and_filter_steam_data():
    """
    Fetches data using Steam's featuredcategories endpoint which reliably returns a larger initial chunk.
    Filters out hardware and blocked games.
    """
    url = "https://store.steampowered.com/api/featuredcategories?cc=US&l=english"
    valid_items = []
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        raw_items = data.get("top_sellers", {}).get("items", [])
        
        all_excluded = HARDWARE_BLOCKLIST + GAME_BLOCKLIST
        
        for item in raw_items:
            name = item.get("name", "")
            if not name:
                continue
                
            is_blocked = any(excluded in name.lower() for excluded in all_excluded)
            if not is_blocked:
                valid_items.append(item)
                
        return valid_items
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []

def generate_html_page(items):
    """Generates a simple HTML file containing the full list of games."""
    date_str = datetime.now().strftime('%Y-%m-%d')
    
    # Start building the HTML string
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Steam Top Sellers - {date_str}</title>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #1b2838; color: #c7d5e0; max-width: 800px; margin: 0 auto; padding: 20px; }}
            h1 {{ color: #ffffff; }}
            .game-item {{ background-color: #2a475e; margin-bottom: 10px; padding: 15px; border-radius: 5px; }}
            a {{ color: #66c0f4; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <h1>🏆 Daily Steam Top Sellers Alert</h1>
        <p>Filtered list for {date_str}</p>
    """
    
    # Add each game to the HTML
    for rank, item in enumerate(items, start=1):
        name = item.get("name")
        appid = item.get("id")
        price_cents = item.get("final_price", 0)
        price = f"${price_cents / 100:.2f}" if price_cents else "Free / Unknown"
        store_url = f"https://store.steampowered.com/app/{appid}/"
        
        html_content += f"""
        <div class="game-item">
            <strong>{rank}. {name}</strong> — {price} <br>
            <a href="{store_url}" target="_blank">View on Steam Store</a>
        </div>
        """
        
    html_content += """
    </body>
    </html>
    """
    
    # Save the HTML to a file
    with open("index.html", "w", encoding="utf-8") as file:
        file.write(html_content)
    print("Successfully generated index.html")

def format_and_send_slack(items):
    """Sends only the top 10 items to Slack and links to the HTML page."""
    if not items:
        return
        
    # Slicing the list to only format the first 10 items
    top_10_items = items[:10]
    remaining_count = len(items) - len(top_10_items)
    
    game_lines = []
    for rank, item in enumerate(top_10_items, start=1):
        name = item.get("name")
        appid = item.get("id")
        price_cents = item.get("final_price", 0)
        price = f"${price_cents / 100:.2f}" if price_cents else "Free"
        store_url = f"https://store.steampowered.com/app/{appid}/"
        
        game_lines.append(f"{rank}. *{name}* — {price} | <{store_url}|Store Page>")
    
    # Add the "...and X more" and link to the full list, just like the other bots
    if remaining_count > 0:
        game_lines.append(f"\n_...and {remaining_count} more_")
    
    game_lines.append(f"\n<{GITHUB_PAGES_URL}|Open Full Top Sellers List>")
    
    combined_games_text = "\n".join(game_lines)
    
    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🏆 Daily Steam Top Sellers", "emoji": True}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": combined_games_text}
            }
        ]
    }
    
    requests.post(
        SLACK_WEBHOOK_URL, 
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"}
    )
    print("Sent truncated list to Slack.")

if __name__ == "__main__":
    clean_items = fetch_and_filter_steam_data()
    print(f"Found {len(clean_items)} valid items.")
    
    if clean_items:
        generate_html_page(clean_items)
        format_and_send_slack(clean_items)
