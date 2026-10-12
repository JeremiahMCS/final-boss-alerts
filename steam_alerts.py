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
    """Generates an ultra-fast, compact HTML page with Top 10 default view, tabs, and archive navigation."""
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
    
    # Dropdown options
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
        prev_btn = f'<a href="{prev_link}" class="nav-btn">◀ Prev Day</a>'
    else:
        prev_btn = '<span class="nav-btn disabled">◀ Prev Day</span>'
        
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
        is_free = 'free' in price.lower()
            
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
            
        price_badge = f'<span class="price-pill free">FREE</span>' if is_free else f'<span class="price-pill paid">{price}</span>'
        is_extended = ' extended-game' if rank > 10 else ''
        
        cards_html.append(f'''
        <div class="game-card{is_extended}" data-rank="{rank}" data-free="{'true' if is_free else 'false'}" data-title="{name}">
            <div class="card-left">
                <div class="{rank_class}">{rank_icon}#{rank}</div>
                <div class="game-info">
                    <h2 class="game-title">{name}</h2>
                    <span class="rank-label">Top Seller #{rank}</span>
                </div>
            </div>
            <div class="card-right">
                {price_badge}
                <a href="{url}" target="_blank" rel="noopener noreferrer" class="store-btn" title="View {name} on Steam">
                    Store ↗
                </a>
            </div>
        </div>
        ''')
        
    cards_markup = '\n'.join(cards_html)
    status_badge = '<span class="badge-live">● Latest</span>' if is_latest else '<span class="badge-archive">📁 Archive</span>'
    
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Steam Top Sellers - {formatted_date} | Final Boss Alerts</title>
    <meta name="description" content="Daily Steam Top Sellers list for {formatted_date} tracked by Final Boss Alerts.">
    <!-- Fast Preconnect & Async Font Loading to prevent render blocking -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="preload" href="https://fonts.googleapis.com/css2?family=Outfit:wght@600;700;800&display=swap" as="style" onload="this.onload=null;this.rel='stylesheet'">
    <noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Outfit:wght@600;700;800&display=swap"></noscript>
    <style>
        :root {{
            --bg-base: #090e17;
            --bg-surface: #10192a;
            --bg-card: #131e31;
            --bg-card-hover: #19273f;
            --border: rgba(56, 189, 248, 0.14);
            --border-hover: rgba(56, 189, 248, 0.4);
            --primary: #38bdf8;
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
            background: #090e17 radial-gradient(circle at 50% 0%, #16243c 0%, #090e17 60%);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            min-height: 100vh;
            padding-bottom: 50px;
            -webkit-font-smoothing: antialiased;
        }}

        .container {{
            max-width: 860px;
            margin: 0 auto;
            padding: 20px 16px;
        }}

        /* Header */
        header {{
            margin-bottom: 18px;
        }}

        .header-top {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }}

        .brand {{
            display: flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
        }}

        .brand-icon {{
            font-size: 24px;
            background: rgba(56, 189, 248, 0.15);
            border: 1px solid var(--border);
            border-radius: 10px;
            width: 42px;
            height: 42px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .brand-text h1 {{
            font-family: 'Outfit', -apple-system, sans-serif;
            font-size: 20px;
            font-weight: 800;
            letter-spacing: -0.3px;
            color: #ffffff;
        }}

        .brand-text p {{
            font-size: 12px;
            color: var(--text-dim);
            font-weight: 500;
        }}

        .badge-live, .badge-archive {{
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 16px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .badge-live {{
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}

        .badge-archive {{
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}

        /* Controls Panel */
        .controls-panel {{
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 14px 16px;
            margin-bottom: 18px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}

        .nav-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            flex-wrap: wrap;
        }}

        .nav-buttons {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .nav-btn {{
            background: #152238;
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            text-decoration: none;
            transition: background 0.15s, border-color 0.15s;
        }}

        .nav-btn:hover:not(.disabled) {{
            background: #1e3355;
            border-color: var(--primary);
            color: var(--primary);
        }}

        .nav-btn.disabled {{
            opacity: 0.35;
            cursor: not-allowed;
        }}

        .nav-btn.today-btn {{
            background: rgba(14, 165, 233, 0.2);
            border-color: rgba(56, 189, 248, 0.35);
            color: #7dd3fc;
        }}

        .date-dropdown {{
            background: #0d1524;
            color: var(--text-main);
            border: 1px solid var(--border);
            padding: 7px 12px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            outline: none;
            flex: 1;
            min-width: 200px;
            max-width: 320px;
        }}

        .date-dropdown:focus {{
            border-color: var(--primary);
        }}

        /* Tabs & Filter Bar */
        .filter-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            flex-wrap: wrap;
            padding-top: 10px;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
        }}

        .tabs-group {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .tab-btn {{
            background: #142034;
            border: 1px solid var(--border);
            color: var(--text-dim);
            padding: 5px 12px;
            border-radius: 7px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s;
        }}

        .tab-btn:hover {{
            color: #ffffff;
            background: #1b2b46;
        }}

        .tab-btn.active {{
            background: rgba(56, 189, 248, 0.2);
            border-color: var(--primary);
            color: #38bdf8;
        }}

        .search-box {{
            flex: 1;
            min-width: 200px;
            position: relative;
        }}

        .search-input {{
            width: 100%;
            background: #0d1524;
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 7px 12px 7px 32px;
            border-radius: 8px;
            font-size: 13px;
            outline: none;
        }}

        .search-input:focus {{
            border-color: var(--primary);
        }}

        .search-icon {{
            position: absolute;
            left: 10px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
            pointer-events: none;
        }}

        .list-summary {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 12px;
            color: var(--text-muted);
            margin-bottom: 10px;
            padding: 0 4px;
        }}

        /* Game Cards - Compact & Fast */
        .games-list {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}

        .game-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 10px 14px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            transition: background 0.15s, border-color 0.15s, transform 0.15s;
        }}

        .game-card:hover {{
            background: var(--bg-card-hover);
            border-color: var(--border-hover);
            transform: translateY(-1px);
        }}

        .game-card.extended-game {{
            display: none; /* Collapsed by default in Top 10 view */
        }}

        .card-left {{
            display: flex;
            align-items: center;
            gap: 12px;
            flex: 1;
            min-width: 0;
        }}

        .rank-badge {{
            width: 34px;
            height: 34px;
            border-radius: 8px;
            background: #17243a;
            border: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'Outfit', -apple-system, sans-serif;
            font-size: 13px;
            font-weight: 800;
            color: var(--text-dim);
            flex-shrink: 0;
        }}

        .rank-badge.rank-1 {{
            background: rgba(245, 158, 11, 0.25);
            border-color: var(--accent-gold);
            color: #fde047;
        }}

        .rank-badge.rank-2 {{
            background: rgba(203, 213, 225, 0.2);
            border-color: var(--accent-silver);
            color: #ffffff;
        }}

        .rank-badge.rank-3 {{
            background: rgba(234, 88, 12, 0.2);
            border-color: var(--accent-bronze);
            color: #fdba74;
        }}

        .game-info {{
            min-width: 0;
            flex: 1;
        }}

        .game-title {{
            font-size: 14px;
            font-weight: 700;
            color: #ffffff;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            line-height: 1.3;
        }}

        .rank-label {{
            font-size: 11px;
            color: var(--text-muted);
            font-weight: 500;
        }}

        .card-right {{
            display: flex;
            align-items: center;
            gap: 10px;
            flex-shrink: 0;
        }}

        .price-pill {{
            padding: 4px 9px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 700;
            white-space: nowrap;
        }}

        .price-pill.free {{
            background: var(--accent-green-bg);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}

        .price-pill.paid {{
            background: rgba(56, 189, 248, 0.1);
            color: #7dd3fc;
            border: 1px solid rgba(56, 189, 248, 0.2);
        }}

        .store-btn {{
            background: #0284c7;
            color: #ffffff;
            padding: 5px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            text-decoration: none;
            white-space: nowrap;
            transition: background 0.15s;
        }}

        .store-btn:hover {{
            background: #0369a1;
        }}

        /* Show More Button */
        .show-more-box {{
            margin-top: 12px;
            text-align: center;
        }}

        .show-more-btn {{
            background: #131e31;
            border: 1px solid var(--border);
            color: #7dd3fc;
            padding: 10px 20px;
            border-radius: 10px;
            font-size: 13px;
            font-weight: 700;
            cursor: pointer;
            width: 100%;
            transition: all 0.15s;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }}

        .show-more-btn:hover {{
            background: #182842;
            border-color: var(--primary);
        }}

        @media (max-width: 600px) {{
            .game-card {{
                padding: 10px 12px;
            }}
            .game-title {{
                white-space: normal;
                font-size: 13px;
            }}
            .card-right {{
                gap: 6px;
            }}
            .date-dropdown {{
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
                        <p>Daily Steam Top Sellers Tracker</p>
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
                <select id="date-select" class="date-dropdown" aria-label="Select archive date">
                    {dropdown_markup}
                </select>
            </div>

            <div class="filter-row">
                <div class="tabs-group">
                    <button class="tab-btn active" data-view="top10">🏆 Top 10</button>
                    <button class="tab-btn" data-view="all">📋 All 30</button>
                    <button class="tab-btn" data-view="free">🎮 Free Only</button>
                </div>
                <div class="search-box">
                    <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    <input type="text" id="search-input" class="search-input" placeholder="Search games..." autocomplete="off">
                </div>
            </div>
        </section>

        <div class="list-summary">
            <span>Filtered list for: <strong style="color: #f1f5f9;">{formatted_date}</strong></span>
            <span id="count-badge">Showing Top 10</span>
        </div>

        <main class="games-list" id="games-container">
            {cards_markup}
        </main>

        <div class="show-more-box" id="show-more-box">
            <button class="show-more-btn" id="show-more-btn">
                <span>▼ Show Remaining 20 Games (Ranks 11–30)</span>
            </button>
        </div>
    </div>

    <script>
        // Archive Dropdown navigation
        const dateSelect = document.getElementById('date-select');
        if (dateSelect) {{
            dateSelect.addEventListener('change', (e) => {{
                if (e.target.value) window.location.href = e.target.value;
            }});
        }}

        // Tabs & Filtering
        let currentView = 'top10';
        const tabBtns = document.querySelectorAll('.tab-btn');
        const gameCards = document.querySelectorAll('.game-card');
        const showMoreBox = document.getElementById('show-more-box');
        const showMoreBtn = document.getElementById('show-more-btn');
        const searchInput = document.getElementById('search-input');
        const countBadge = document.getElementById('count-badge');

        function updateDisplay() {{
            const query = searchInput ? searchInput.value.toLowerCase().trim() : '';
            let visible = 0;

            gameCards.forEach(card => {{
                const rank = parseInt(card.getAttribute('data-rank') || '0', 10);
                const isFree = card.getAttribute('data-free') === 'true';
                const title = (card.getAttribute('data-title') || '').toLowerCase();

                let matchesFilter = true;
                if (query) {{
                    matchesFilter = title.includes(query);
                }} else {{
                    if (currentView === 'top10') {{
                        matchesFilter = (rank <= 10);
                    }} else if (currentView === 'free') {{
                        matchesFilter = isFree;
                    }} else if (currentView === 'all') {{
                        matchesFilter = true;
                    }}
                }}

                if (matchesFilter) {{
                    card.style.display = 'flex';
                    visible++;
                }} else {{
                    card.style.display = 'none';
                }}
            }});

            if (showMoreBox) {{
                if (currentView === 'top10' && !query) {{
                    showMoreBox.style.display = 'block';
                }} else {{
                    showMoreBox.style.display = 'none';
                }}
            }}

            if (countBadge) {{
                if (query) {{
                    countBadge.textContent = visible + ' matching games';
                }} else if (currentView === 'top10') {{
                    countBadge.textContent = 'Showing Top 10 of 30';
                }} else if (currentView === 'free') {{
                    countBadge.textContent = visible + ' Free to Play games';
                }} else {{
                    countBadge.textContent = 'Showing all 30 games';
                }}
            }}
        }}

        tabBtns.forEach(btn => {{
            btn.addEventListener('click', () => {{
                tabBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentView = btn.getAttribute('data-view');
                if (searchInput) searchInput.value = '';
                updateDisplay();
            }});
        }});

        if (showMoreBtn) {{
            showMoreBtn.addEventListener('click', () => {{
                tabBtns.forEach(b => b.classList.remove('active'));
                const allBtn = document.querySelector('.tab-btn[data-view="all"]');
                if (allBtn) allBtn.classList.add('active');
                currentView = 'all';
                updateDisplay();
            }});
        }}

        if (searchInput) {{
            searchInput.addEventListener('input', () => {{
                updateDisplay();
            }});
        }}

        // URL parameter routing support (?date=YYYY-MM-DD)
        const urlParams = new URLSearchParams(window.location.search);
        const reqDate = urlParams.get('date');
        if (reqDate && reqDate !== '{date_str}') {{
            window.location.replace('{base_path}archive/' + reqDate + '.html');
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

