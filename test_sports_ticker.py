"""
Sports Ticker - PC Test Script
Tests the ESPN API calls and game parsing logic from the CircuitPython sports ticker
without needing any hardware. Run with: python test_sports_ticker.py
"""

import requests
from datetime import datetime, timedelta

# --- CONFIG (mirrors the CircuitPython code) ---
timezone_info = [-5, "EST"]  # Change to your timezone

sport_names = ["football", "baseball", "hockey", "basketball",
               "football", "basketball", "hockey"]
sport_leagues = ["nfl", "mlb", "nhl", "nba",
                 "cfb", "cbb", "chk"]

espn_league_slugs = {
    "nfl": "nfl", "mlb": "mlb", "nhl": "nhl", "nba": "nba",
    "cfb": "college-football",
    "cbb": "mens-college-basketball",
    "chk": "mens-college-hockey",
}

league_display_names = {
    "nfl": "NFL", "mlb": "MLB", "nhl": "NHL", "nba": "NBA",
    "cfb": "NCAAF", "cbb": "NCAAB", "chk": "NCAAH",
}

# ---- FILTER SETTINGS ----
# Filter by league: e.g. ["nhl"] or ["nhl", "nba"] or [] for all leagues
filter_leagues = []

# Filter by team abbreviation: e.g. ["BOS", "TOR", "NYR"] or [] for all teams
# Uses ESPN abbreviations (run with no filters first to see them all)
filter_teams = []

SPORT_URLS = [
    f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{espn_league_slugs[league]}/scoreboard"
    for sport, league in zip(sport_names, sport_leagues)
]

# --- DATE CONVERSION (same logic as the original) ---
def convert_date_format(date_str, tz_info):
    try:
        dt = datetime.strptime(date_str[:16], "%Y-%m-%dT%H:%M")
        dt_adjusted = dt + timedelta(hours=tz_info[0])

        hour = dt_adjusted.hour
        am_pm = "AM" if hour < 12 else "PM"
        hour_12 = hour if hour <= 12 else hour - 12
        if hour_12 == 0:
            hour_12 = 12

        return f"{dt_adjusted.month}/{dt_adjusted.day} {hour_12}:{dt_adjusted.minute:02d}{am_pm}"
    except Exception as e:
        print(f"Date conversion error: {e}")
        return "TBD"

# --- GAME PARSING (same logic as the original) ---
def parse_game(event, league_idx):
    try:
        competition = event["competitions"][0]
        competitors = competition["competitors"]

        if len(competitors) != 2:
            return None

        home_team = competitors[0]["team"]["abbreviation"]
        away_team = competitors[1]["team"]["abbreviation"]
        home_score = competitors[0].get("score", "0")
        away_score = competitors[1].get("score", "0")

        status_type = event["status"]["type"]
        status_name = status_type.get("name", "STATUS_SCHEDULED")
        status_detail = status_type.get("shortDetail", "")
        game_date = event.get("date", "")

        if status_name == "STATUS_FINAL":
            display_status = "FINAL"
        elif status_name == "STATUS_IN_PROGRESS":
            display_status = status_detail
        elif status_name == "STATUS_SCHEDULED":
            display_status = convert_date_format(game_date, timezone_info)
        elif status_name == "STATUS_POSTPONED":
            display_status = "POSTPONED"
        elif status_name == "STATUS_CANCELED":
            display_status = "CANCELED"
        else:
            display_status = status_detail if status_detail else "SCHEDULED"

        return {
            "league": league_display_names.get(sport_leagues[league_idx], sport_leagues[league_idx].upper()),
            "league_idx": league_idx,
            "home_team": home_team,
            "away_team": away_team,
            "home_score": str(home_score),
            "away_score": str(away_score),
            "status": display_status,
            "is_final": status_name == "STATUS_FINAL",
            "is_live": status_name == "STATUS_IN_PROGRESS",
            "is_scheduled": status_name == "STATUS_SCHEDULED",
        }
    except Exception as e:
        print(f"Parse error: {e}")
        return None

# --- FETCH ALL GAMES ---
def fetch_all_games():
    all_games = []

    for league_idx, url in enumerate(SPORT_URLS):
        league = sport_leagues[league_idx]

        # Skip leagues not in filter (if filter is set)
        if filter_leagues and league not in filter_leagues:
            print(f"Skipping {league.upper()} (filtered out)")
            continue

        print(f"Fetching {league.upper()} games...")

        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            events = data.get("events", [])
            print(f"  Found {len(events)} {league.upper()} events")

            for event in events:
                game = parse_game(event, league_idx)
                if game:
                    # Apply team filter
                    if filter_teams and game["home_team"] not in filter_teams and game["away_team"] not in filter_teams:
                        continue
                    all_games.append(game)

        except requests.RequestException as e:
            print(f"  Error fetching {league.upper()}: {e}")
            continue

    return all_games

# --- SIMULATE DISPLAY ---
def display_game(game, index, total):
    width = 50
    print("=" * width)
    print(f"  Game {index + 1}/{total}  |  {game['league']}")
    print("-" * width)

    # Status indicator
    if game["is_live"]:
        indicator = "🔴 LIVE"
    elif game["is_final"]:
        indicator = "✅ FINAL"
    else:
        indicator = f"🕐 {game['status']}"

    # Score or VS
    if game["is_scheduled"]:
        score_line = "VS"
    else:
        score_line = f"{game['home_score']} - {game['away_score']}"

    print(f"  {game['home_team']:>10}   {score_line:^10}   {game['away_team']:<10}")
    print(f"  {'(HOME)':>10}   {' ':^10}   {'(AWAY)':<10}")
    print(f"  {indicator:^{width}}")
    print("=" * width)

# --- MAIN ---
if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  SPORTS TICKER - PC TEST")
    print(f"  Timezone: UTC{timezone_info[0]:+d} ({timezone_info[1]})")
    if filter_leagues:
        print(f"  Leagues: {', '.join(l.upper() for l in filter_leagues)}")
    if filter_teams:
        print(f"  Teams: {', '.join(filter_teams)}")
    if not filter_leagues and not filter_teams:
        print("  Filters: None (showing all games)")
    print("=" * 50 + "\n")

    games = fetch_all_games()

    if not games:
        print("No games found. Check your filters or try again later.\n")

    if games:
        print(f"\n{'=' * 50}")
        print(f"  TOTAL GAMES FOUND: {len(games)}")
        print(f"{'=' * 50}\n")

        # Summarize by league
        leagues_found = {}
        for g in games:
            leagues_found[g["league"]] = leagues_found.get(g["league"], 0) + 1
        for league, count in leagues_found.items():
            live = sum(1 for g in games if g["league"] == league and g["is_live"])
            final = sum(1 for g in games if g["league"] == league and g["is_final"])
            sched = sum(1 for g in games if g["league"] == league and g["is_scheduled"])
            print(f"  {league}: {count} games ({live} live, {final} final, {sched} scheduled)")

        print()

        # Display each game
        for i, game in enumerate(games):
            display_game(game, i, len(games))
            print()

    # Check for missing logos that would be needed
    if games:
        print("\n" + "=" * 50)
        print("  LOGO FILES NEEDED")
        print("=" * 50)
        teams_by_league = {}
        for g in games:
            key = g["league"]
            if key not in teams_by_league:
                teams_by_league[key] = set()
            teams_by_league[key].add(g["home_team"])
            teams_by_league[key].add(g["away_team"])

        folder_map = {"NFL": "team0_logos", "MLB": "team1_logos", "NHL": "team2_logos", "NBA": "team3_logos"}
        for league, teams in sorted(teams_by_league.items()):
            folder = folder_map.get(league, "unknown")
            print(f"\n  /{folder}/")
            for team in sorted(teams):
                print(f"    {team}.bmp")

    print("\nTest complete! If you saw games above, the API + parsing logic works correctly.")

    # Show what refresh rate the board would use
    if games:
        is_live = any(g["is_live"] for g in games)
        print(f"\n  Smart refresh: {'30s (live games detected)' if is_live else '5min (no live games)'}")
        print("  The board will automatically switch to 30s refresh when games go live,")
        print("  and back to 5min when all games are final or scheduled.")

    print("\nThe code is ready for your hardware.\n")
