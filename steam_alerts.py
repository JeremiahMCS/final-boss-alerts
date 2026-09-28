import os
import requests
import json
from datetime import datetime
from bs4 import BeautifulSoup

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

# Replace these with your actual GitHub username and repository name!
GITHUB_PAGES_URL = "https://YOUR_GITHUB_USERNAME.github.io/YOUR_REPO_NAME/"

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
    Fetches the main HTML search page acting as a normal browser.
    Parses the structured HTML payload using BeautifulSoup.
    """
    url = "https://store.steampowered.com/search/"
    params = {
        "filter": "topsellers",
        "cc": "US"
    }
    
    # This header masquerades our script as a standard Google Chrome browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    valid_items = []
    seen_names = set()
    all_excluded = HARDWARE_BLOCKLIST + GAME_BLOCKLIST
    
    try:
        print("Fetching Steam search page...")
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        
        # We no longer ask for .json(). We pass the raw HTML text directly to BeautifulSoup.
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('a', class_='search_result_row')
        
        for row in rows:
            title_elem = row.find('span', class_='title')
            if not title_elem:
                continue
                
            name = title_elem.get_text(strip=True)
            name_lower = name.lower()
            store_url = row.get('href', '').split('?')[0] 
            
            if name_lower in seen_names:
                continue
                
            is_blocked = any(excluded in name_lower for excluded in all_excluded)
            if is_blocked:
                continue
                
            price_elem = row.find('div', class_='discount_final_price')
            if price_elem:
                price = price_elem.get_text(strip=True)
            else:
                price_box = row.find('div', class_='search_price')
                price = price_box.get_text(strip=True) if price_box else "Free / Unknown"
            
            # Clean up empty price text if a game hasn't launched yet
            if not price.strip():
                price = "TBA"
                
            valid_items.append({
                "name": name,
                "price": price,
                "url": store_url
            })
            
            seen_names.add(name_lower)
            
            if len(valid_items) == 30:
                break
                
        return valid_items
    except Exception as e:
        print(f"Error fetching/parsing data: {e}")
        return []

def generate_html_page(items):
    """Generates a simple HTML file containing the full list of games."""
    date_str = datetime.now().strftime('%Y-%m-%d')
    
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
    
    for rank, item in enumerate(items, start=1):
        html_content += f"""
        <div class="game-item">
            <strong>{rank}. {item['name']}</strong> — {item['price']} <br>
            <a href="{item['url']}" target="_blank">View on Steam Store</a>
        </div>
        """
        
    html_content += """
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as file:
        file.write(html_content)
    print("Successfully generated index.html")

def format_and_send_slack(items):
    """Sends only the top 10 items to Slack and links to the HTML page."""
    if not items:
        return
        
    top_10_items = items[:10]
    remaining_count = len(items) - len(top_10_items)
    
    game_lines = []
    for rank, item in enumerate(top_10_items, start=1):
        game_lines.append(f"{rank}. *{item['name']}* — {item['price']} | <{item['url']}|Store Page>")
    
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
