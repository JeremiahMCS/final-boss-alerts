import os
import requests
import json
import time
import html
import glob
from datetime import datetime
from bs4 import BeautifulSoup

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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
    Fetches the main HTML search page acting as a normal browser.
    Parses the structured HTML payload using BeautifulSoup.
    """
    url = "https://store.steampowered.com/search/"
    params = {
        "filter": "topsellers",
        "cc": "US"
    }
    
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

def generate_page_html(date_str, items, all_dates, is_root=False):
    """Generates a complete, premium HTML page for a specific date with archive navigation."""
    base_path = '' if is_root else '../'
    
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        formatted_date = dt.strftime('%A, %B %d, %Y')
    except Exception:
        formatted_date = date_str
    
    idx = all_dates.index(date_str) if date_str in all_dates else -1
    prev_date = all_dates[idx + 1] if 0 <= idx < len(all_dates) - 1 else None
    next_date = all_dates[idx - 1] if idx > 0 else None
    latest_date = all_dates[0] if all_dates else date_str
    is_latest = (date_str == latest_date)
    
    options_html = []
    for d in all_dates:
        try:
            d_dt = datetime.strptime(d, '%Y-%m-%d')
            d_label = d_dt.strftime('%b %d, %Y (%a)')
        except Exception:
            d_label = d
            
        if d == latest_date:
            d_label += ' — Latest'
        
        if not is_root:
            target_url = '../index.html' if d == latest_date else f'{d}.html'
        else:
            target_url = 'index.html' if d == latest_date else f'archive/{d}.html'
                
        selected = 'selected' if d == date_str else ''
        options_html.append(f'<option value="{target_url}" {selected}>{d_label}</option>')
    
    dropdown_markup = '\n'.join(options_html)
    today_link = f'{base_path}index.html'
    
    if prev_date:
        prev_link = f'{prev_date}.html' if not is_root else f'archive/{prev_date}.html'
        prev_btn = f'<a href="{prev_link}" class="nav-btn">◀ Previous Day</a>'
    else:
        prev_btn = '<span class="nav-btn disabled">◀ Previous Day</span>'
        
    if next_date:
        next_link = (f'../index.html' if next_date == latest_date else f'{next_date}.html') if not is_root else (f'index.html' if next_date == latest_date else f'archive/{next_date}.html')
        next_btn = f'<a href="{next_link}" class="nav-btn">Next Day ▶</a>'
    else:
        next_btn = '<span class="nav-btn disabled">Next Day ▶</span>'
        
    cards_html = []
    for item in items:
        rank = item.get('rank', 0)
        name = html.escape(item.get('name', 'Unknown'))
        price = html.escape(item.get('price', 'Unknown'))
        url = html.escape(item.get('url', '#'))
        
        rank_class = 'rank-badge'
        rank_icon = ''
        if rank == 1:
            rank_class += ' rank-1'
            rank_icon = '👑 '
        elif rank == 2:
            rank_class += ' rank-2'
            rank_icon = '🥈 '
        elif rank == 3:
            rank_class += ' rank-3'
            rank_icon = '🥉 '
            
        is_free = 'free' in price.lower()
        price_badge = f'<span class="price-pill free">FREE TO PLAY</span>' if is_free else f'<span class="price-pill paid">{price}</span>'
        
        cards_html.append(f'''
        <div class="game-card" data-title="{name}">
            <div class="card-left">
                <div class="{rank_class}">{rank_icon}#{rank}</div>
                <div class="game-info">
                    <h2 class="game-title">{name}</h2>
                    <span class="rank-label">Steam Top Seller Rank #{rank}</span>
                </div>
            </div>
            <div class="card-right">
                {price_badge}
                <a href="{url}" target="_blank" rel="noopener noreferrer" class="store-btn">
                    View on Steam
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                </a>
            </div>
        </div>
        ''')
        
    cards_markup = '\n'.join(cards_html)
    status_badge = '<span class="badge-live">● Latest Sync</span>' if is_latest else '<span class="badge-archive">📁 Archive View</span>'
    
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Steam Top Sellers - {formatted_date} | Final Boss Alerts</title>
    <meta name="description" content="Daily Steam Top Sellers list for {formatted_date} tracked by Final Boss Alerts.">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
    <meta http-equiv="Pragma" content="no-cache" />
    <meta http-equiv="Expires" content="0" />
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #070b12;
            --bg-surface: rgba(15, 23, 42, 0.75);
            --bg-card: rgba(22, 33, 56, 0.65);
            --bg-card-hover: rgba(30, 48, 80, 0.85);
            --border: rgba(56, 189, 248, 0.16);
            --border-hover: rgba(56, 189, 248, 0.45);
            --primary: #38bdf8;
            --primary-glow: rgba(56, 189, 248, 0.25);
            --text-main: #f8fafc;
            --text-dim: #94a3b8;
            --text-muted: #64748b;
            --accent-green: #10b981;
            --accent-green-bg: rgba(16, 185, 129, 0.15);
            --accent-gold: #f59e0b;
            --accent-silver: #cbd5e1;
            --accent-bronze: #ea580c;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg-base);
            background-image: 
                radial-gradient(at 0% 0%, rgba(14, 165, 233, 0.12) 0px, transparent 50%),
                radial-gradient(at 100% 0%, rgba(99, 102, 241, 0.12) 0px, transparent 50%),
                radial-gradient(at 50% 100%, rgba(15, 23, 42, 0.8) 0px, transparent 50%);
            background-attachment: fixed;
            color: var(--text-main);
            font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
            min-height: 100vh;
            padding-bottom: 60px;
        }}

        .container {{
            max-width: 960px;
            margin: 0 auto;
            padding: 24px 20px;
        }}

        /* Header */
        header {{
            margin-bottom: 24px;
        }}

        .header-top {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 12px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }}

        .brand {{
            display: flex;
            align-items: center;
            gap: 14px;
            text-decoration: none;
        }}

        .brand-icon {{
            font-size: 32px;
            background: linear-gradient(135deg, rgba(56, 189, 248, 0.2), rgba(99, 102, 241, 0.2));
            border: 1px solid var(--border);
            border-radius: 14px;
            width: 52px;
            height: 52px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        }}

        .brand-text h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 24px;
            font-weight: 800;
            letter-spacing: -0.5px;
            background: linear-gradient(120deg, #ffffff 40%, var(--primary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .brand-text p {{
            font-size: 13px;
            color: var(--text-dim);
            font-weight: 500;
        }}

        .header-badges {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .badge-live {{
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
            font-size: 12px;
            font-weight: 700;
            padding: 6px 12px;
            border-radius: 20px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .badge-archive {{
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.3);
            font-size: 12px;
            font-weight: 700;
            padding: 6px 12px;
            border-radius: 20px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        /* Control Panel */
        .controls-panel {{
            background: var(--bg-surface);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 18px;
            margin-bottom: 24px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
        }}

        .nav-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            flex-wrap: wrap;
        }}

        .nav-buttons {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .nav-btn {{
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 8px 14px;
            border-radius: 10px;
            font-size: 13px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}

        .nav-btn:hover:not(.disabled) {{
            background: rgba(56, 189, 248, 0.2);
            border-color: var(--primary);
            color: var(--primary);
            transform: translateY(-1px);
        }}

        .nav-btn.disabled {{
            opacity: 0.4;
            cursor: not-allowed;
        }}

        .nav-btn.today-btn {{
            background: linear-gradient(135deg, rgba(14, 165, 233, 0.25), rgba(99, 102, 241, 0.25));
            border-color: rgba(56, 189, 248, 0.4);
            color: #7dd3fc;
        }}

        .selector-box {{
            display: flex;
            align-items: center;
            gap: 8px;
            flex: 1;
            min-width: 250px;
            max-width: 380px;
        }}

        .date-dropdown {{
            width: 100%;
            background: #0f172a;
            color: var(--text-main);
            border: 1px solid var(--border);
            padding: 9px 14px;
            border-radius: 10px;
            font-family: inherit;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            outline: none;
        }}

        .date-dropdown:hover, .date-dropdown:focus {{
            border-color: var(--primary);
            box-shadow: 0 0 0 3px var(--primary-glow);
        }}

        .filter-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 14px;
            flex-wrap: wrap;
            padding-top: 12px;
            border-top: 1px solid rgba(255, 255, 255, 0.06);
        }}

        .search-box {{
            flex: 1;
            min-width: 240px;
            position: relative;
        }}

        .search-input {{
            width: 100%;
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 10px 14px 10px 38px;
            border-radius: 10px;
            font-size: 14px;
            outline: none;
            transition: all 0.2s ease;
        }}

        .search-input:focus {{
            border-color: var(--primary);
            box-shadow: 0 0 0 3px var(--primary-glow);
        }}

        .search-icon {{
            position: absolute;
            left: 12px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
            pointer-events: none;
        }}

        .current-summary {{
            font-size: 13px;
            font-weight: 600;
            color: var(--text-dim);
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .count-badge {{
            background: rgba(56, 189, 248, 0.1);
            color: var(--primary);
            padding: 4px 10px;
            border-radius: 12px;
            border: 1px solid rgba(56, 189, 248, 0.2);
            font-size: 12px;
        }}

        /* Game Cards */
        .games-list {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}

        .game-card {{
            background: var(--bg-card);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 14px 18px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        }}

        .game-card:hover {{
            background: var(--bg-card-hover);
            border-color: var(--border-hover);
            transform: translateY(-2px);
            box-shadow: 0 8px 24px -4px rgba(0, 0, 0, 0.4), 0 0 15px -2px var(--primary-glow);
        }}

        .card-left {{
            display: flex;
            align-items: center;
            gap: 16px;
            flex: 1;
            min-width: 0;
        }}

        .rank-badge {{
            width: 44px;
            height: 44px;
            border-radius: 12px;
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'Outfit', sans-serif;
            font-size: 14px;
            font-weight: 800;
            color: var(--text-dim);
            flex-shrink: 0;
        }}

        .rank-badge.rank-1 {{
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.3), rgba(217, 119, 6, 0.3));
            border-color: var(--accent-gold);
            color: #fef08a;
            box-shadow: 0 0 15px rgba(245, 158, 11, 0.3);
        }}

        .rank-badge.rank-2 {{
            background: linear-gradient(135deg, rgba(203, 213, 225, 0.25), rgba(148, 163, 184, 0.25));
            border-color: var(--accent-silver);
            color: #ffffff;
            box-shadow: 0 0 12px rgba(203, 213, 225, 0.2);
        }}

        .rank-badge.rank-3 {{
            background: linear-gradient(135deg, rgba(234, 88, 12, 0.25), rgba(180, 83, 9, 0.25));
            border-color: var(--accent-bronze);
            color: #fdba74;
            box-shadow: 0 0 12px rgba(234, 88, 12, 0.2);
        }}

        .game-info {{
            min-width: 0;
            flex: 1;
        }}

        .game-title {{
            font-family: 'Outfit', sans-serif;
            font-size: 16px;
            font-weight: 700;
            color: #ffffff;
            line-height: 1.3;
            margin-bottom: 3px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .rank-label {{
            font-size: 12px;
            color: var(--text-muted);
            font-weight: 500;
        }}

        .card-right {{
            display: flex;
            align-items: center;
            gap: 14px;
            flex-shrink: 0;
        }}

        .price-pill {{
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.3px;
            white-space: nowrap;
        }}

        .price-pill.free {{
            background: var(--accent-green-bg);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.35);
        }}

        .price-pill.paid {{
            background: rgba(56, 189, 248, 0.12);
            color: #7dd3fc;
            border: 1px solid rgba(56, 189, 248, 0.25);
        }}

        .store-btn {{
            background: linear-gradient(135deg, #0284c7, #2563eb);
            color: #ffffff;
            padding: 8px 16px;
            border-radius: 9px;
            font-size: 13px;
            font-weight: 600;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s ease;
            box-shadow: 0 4px 12px rgba(2, 132, 199, 0.25);
            white-space: nowrap;
        }}

        .store-btn:hover {{
            background: linear-gradient(135deg, #0369a1, #1d4ed8);
            transform: translateY(-1px);
            box-shadow: 0 6px 16px rgba(2, 132, 199, 0.4);
        }}

        /* Responsive */
        @media (max-width: 640px) {{
            .game-card {{
                flex-direction: column;
                align-items: stretch;
                gap: 12px;
            }}
            .card-right {{
                justify-content: space-between;
            }}
            .game-title {{
                white-space: normal;
            }}
            .selector-box {{
                max-width: 100%;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-top">
                <a href="{today_link}" class="brand">
                    <div class="brand-icon">🏆</div>
                    <div class="brand-text">
                        <h1>FINAL BOSS ALERTS</h1>
                        <p>Daily Steam Top Sellers Intelligence & Archives</p>
                    </div>
                </a>
                <div class="header-badges">
                    {status_badge}
                </div>
            </div>
        </header>

        <section class="controls-panel">
            <div class="nav-row">
                <div class="nav-buttons">
                    {prev_btn}
                    {next_btn}
                    <a href="{today_link}" class="nav-btn today-btn">⚡ Today</a>
                </div>
                <div class="selector-box">
                    <select id="date-select" class="date-dropdown" aria-label="Select archive date">
                        {dropdown_markup}
                    </select>
                </div>
            </div>

            <div class="filter-row">
                <div class="search-box">
                    <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    <input type="text" id="search-input" class="search-input" placeholder="Filter games by title..." autocomplete="off">
                </div>
                <div class="current-summary">
                    <span>Filtered for: <strong>{formatted_date}</strong></span>
                    <span id="visible-count" class="count-badge">{len(items)} Games</span>
                </div>
            </div>
        </section>

        <main class="games-list" id="games-container">
            {cards_markup}
        </main>
    </div>

    <script>
        // Archive Dropdown navigation
        const dateSelect = document.getElementById('date-select');
        if (dateSelect) {{
            dateSelect.addEventListener('change', (e) => {{
                if (e.target.value) {{
                    window.location.href = e.target.value;
                }}
            }});
        }}

        // Realtime Search Filter
        const searchInput = document.getElementById('search-input');
        const gameCards = document.querySelectorAll('.game-card');
        const countDisplay = document.getElementById('visible-count');

        if (searchInput) {{
            searchInput.addEventListener('input', (e) => {{
                const query = e.target.value.toLowerCase().trim();
                let count = 0;
                gameCards.forEach(card => {{
                    const title = (card.getAttribute('data-title') || '').toLowerCase();
                    if (title.includes(query)) {{
                        card.style.display = '';
                        count++;
                    }} else {{
                        card.style.display = 'none';
                    }}
                }});
                if (countDisplay) {{
                    countDisplay.textContent = count + ' of ' + gameCards.length + ' Games';
                }}
            }});
        }}

        // URL parameter routing support (?date=YYYY-MM-DD)
        const urlParams = new URLSearchParams(window.location.search);
        const reqDate = urlParams.get('date');
        if (reqDate && reqDate !== '{date_str}') {{
            const target = '{base_path}archive/' + reqDate + '.html';
            window.location.replace(target);
        }}

        // Keyboard navigation ([ for Prev, ] for Next)
        window.addEventListener('keydown', (e) => {{
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
            if (e.key === '[' && '{prev_date}') {{
                window.location.href = '{base_path}archive/{prev_date}.html';
            }} else if (e.key === ']' && '{next_date}') {{
                window.location.href = ('{next_date}' === '{latest_date}' ? '{base_path}index.html' : '{base_path}archive/{next_date}.html');
            }}
        }});
    </script>
</body>
</html>
'''
    return html_content

def save_and_generate_archives(items, date_str=None):
    """
    Saves daily data to JSON, updates the manifest, and generates
    both the standalone archive page and index.html with historical navigation.
    """
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')
        
    os.makedirs('data', exist_ok=True)
    os.makedirs('archive', exist_ok=True)
    
    # Ensure rank is populated in items
    for rank, item in enumerate(items, start=1):
        if 'rank' not in item:
            item['rank'] = rank
            
    # Save daily JSON
    daily_file = os.path.join('data', f'{date_str}.json')
    with open(daily_file, 'w', encoding='utf-8') as f:
        json.dump({'date': date_str, 'count': len(items), 'items': items}, f, indent=2)
    print(f"Saved daily JSON to {daily_file}")
    
    # Collect all available dates
    data_files = glob.glob(os.path.join('data', '*.json'))
    all_dates = []
    for fpath in data_files:
        base = os.path.basename(fpath)
        if base == 'manifest.json':
            continue
        date_name = os.path.splitext(base)[0]
        all_dates.append(date_name)
        
    if date_str not in all_dates:
        all_dates.append(date_str)
        
    all_dates = sorted(list(set(all_dates)), reverse=True)
    
    # Save manifest.json
    manifest_path = os.path.join('data', 'manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump({'dates': all_dates, 'latest': all_dates[0] if all_dates else None}, f, indent=2)
    print(f"Updated {manifest_path} with {len(all_dates)} dates.")
    
    # Regenerate all archive HTML files to ensure date dropdowns and next/prev are accurate
    for d in all_dates:
        d_json_path = os.path.join('data', f'{d}.json')
        if not os.path.exists(d_json_path):
            continue
        try:
            with open(d_json_path, 'r', encoding='utf-8') as df:
                d_data = json.load(df)
            d_items = d_data.get('items', [])
            html_out = generate_page_html(d, d_items, all_dates, is_root=False)
            archive_file = os.path.join('archive', f'{d}.html')
            with open(archive_file, 'w', encoding='utf-8') as af:
                af.write(html_out)
        except Exception as e:
            print(f"Error generating archive for {d}: {e}")
            
    # Generate index.html for latest date
    latest_date = all_dates[0]
    latest_json_path = os.path.join('data', f'{latest_date}.json')
    with open(latest_json_path, 'r', encoding='utf-8') as df:
        latest_data = json.load(df)
    index_html = generate_page_html(latest_date, latest_data.get('items', []), all_dates, is_root=True)
    with open('index.html', 'w', encoding='utf-8') as inf:
        inf.write(index_html)
    print("Successfully generated index.html and all archive pages.")

def format_and_send_slack(items, date_str=None):
    """Sends the top 10 items to Slack/Discord with a direct permanent link to that day's archive."""
    if not items:
        return
        
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')
        
    top_10_items = items[:10]
    remaining_count = len(items) - len(top_10_items)
    
    game_lines = []
    for rank, item in enumerate(top_10_items, start=1):
        game_lines.append(f"{rank}. *{item['name']}* — {item['price']} | <{item['url']}|Store Page>")
    
    if remaining_count > 0:
        game_lines.append(f"\n_...and {remaining_count} more_")
    
    # Permanent date-specific archive link with cache-busting timestamp
    timestamp = int(time.time())
    archive_url = f"{GITHUB_PAGES_URL}archive/{date_str}.html?v={timestamp}"
    
    game_lines.append(f"\n<{archive_url}|Open Full Top Sellers List>")
    
    combined_games_text = "\n".join(game_lines)
    
    if not SLACK_WEBHOOK_URL:
        print("[Notice] SLACK_WEBHOOK_URL is not set. Skipping Slack dispatch (dry-run mode).")
        print("--- Slack Payload Preview ---")
        print(combined_games_text)
        print("-----------------------------")
        return

    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🏆 Daily Steam Top Sellers ({date_str})", "emoji": True}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": combined_games_text}
            }
        ]
    }
    
    try:
        response = requests.post(
            SLACK_WEBHOOK_URL, 
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        response.raise_for_status()
        print("Sent truncated list to Slack.")
    except Exception as e:
        print(f"Error sending to Slack: {e}")

if __name__ == "__main__":
    clean_items = fetch_and_filter_steam_data()
    print(f"Found {len(clean_items)} valid items.")
    
    if clean_items:
        date_str = datetime.now().strftime('%Y-%m-%d')
        save_and_generate_archives(clean_items, date_str)
        format_and_send_slack(clean_items, date_str)

