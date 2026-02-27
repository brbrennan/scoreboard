"""
Get Team Logos - Downloads team logos from ESPN for the Sports Ticker

Downloads logos for NFL, MLB, NHL, and NBA teams, converts them to 32x32 .bmp
files named by ESPN abbreviation, and organizes them into the correct folders
for use with both the LED hardware and the emulator.

Install requirements:
    pip install requests Pillow

Run:
    python get_team_logos.py

Output:
    sport_logos/
      team0_logos/   (NFL)
      team1_logos/   (MLB)
      team2_logos/   (NHL)
      team3_logos/   (NBA)
"""

import os
import requests
from PIL import Image
from io import BytesIO

# Logo size for LED matrix (32x32 is standard for this project)
LOGO_SIZE = 32

# Output folder structure (matches code.py)
OUTPUT_BASE = "sport_logos"
FOLDERS = {
    "nfl": "team0_logos",
    "mlb": "team1_logos",
    "nhl": "team2_logos",
    "nba": "team3_logos",
    "cfb": "team4_logos",
    "cbb": "team5_logos",
    "chk": "team6_logos",
}

SPORTS = {
    "nfl": "football",
    "mlb": "baseball",
    "nhl": "hockey",
    "nba": "basketball",
    "cfb": "football",
    "cbb": "basketball",
    "chk": "hockey",
}

# ESPN API uses different league slugs
ESPN_SLUGS = {
    "nfl": "nfl",
    "mlb": "mlb",
    "nhl": "nhl",
    "nba": "nba",
    "cfb": "college-football",
    "cbb": "mens-college-basketball",
    "chk": "mens-college-hockey",
}


def get_teams(sport, league):
    """Fetch the team list from ESPN's API."""
    espn_slug = ESPN_SLUGS.get(league, league)
    url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{espn_slug}/teams?limit=500"
    print(f"  Fetching {league.upper()} team list...")
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        teams_raw = data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
        teams = []
        for entry in teams_raw:
            team = entry.get("team", {})
            abbr = team.get("abbreviation", "")
            name = team.get("displayName", "")
            logos = team.get("logos", [])
            logo_url = logos[0].get("href", "") if logos else ""
            if abbr and logo_url:
                teams.append({
                    "abbreviation": abbr,
                    "name": name,
                    "logo_url": logo_url,
                })
        return teams
    except Exception as e:
        print(f"  Error fetching {league.upper()} teams: {e}")
        return []


def download_and_convert_logo(team, output_dir):
    """Download a team logo and save it as a 32x32 indexed-color BMP."""
    abbr = team["abbreviation"]
    output_path = os.path.join(output_dir, f"{abbr}.bmp")

    # Skip if already downloaded
    if os.path.exists(output_path):
        print(f"    {abbr} - already exists, skipping")
        return True

    try:
        resp = requests.get(team["logo_url"], timeout=15)
        resp.raise_for_status()

        # Open image and convert
        img = Image.open(BytesIO(resp.content))

        # Convert to RGBA first to handle transparency
        img = img.convert("RGBA")

        # Resize to target size
        img = img.resize((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)

        # Composite onto black background (LED matrix background)
        background = Image.new("RGB", (LOGO_SIZE, LOGO_SIZE), (0, 0, 0))
        background.paste(img, mask=img.split()[3])

        # Convert to palette mode (P) to match what CircuitPython expects
        # Use adaptive palette with limited colors for small BMP size
        bmp_img = background.quantize(colors=16, method=Image.Quantize.MEDIANCUT)

        # Save as BMP
        bmp_img.save(output_path, format="BMP")

        print(f"    {abbr} - downloaded ({team['name']})")
        return True

    except Exception as e:
        print(f"    {abbr} - FAILED: {e}")
        return False


def main():
    print("=" * 50)
    print("  SPORTS TICKER - LOGO DOWNLOADER")
    print("=" * 50)
    print(f"\nLogo size: {LOGO_SIZE}x{LOGO_SIZE}")
    print(f"Output: {OUTPUT_BASE}/\n")

    total_downloaded = 0
    total_failed = 0
    total_skipped = 0

    for league, sport in SPORTS.items():
        folder = FOLDERS[league]
        output_dir = os.path.join(OUTPUT_BASE, folder)
        os.makedirs(output_dir, exist_ok=True)

        print(f"\n{'=' * 40}")
        print(f"  {league.upper()} -> {folder}/")
        print(f"{'=' * 40}")

        teams = get_teams(sport, league)
        if not teams:
            print(f"  No teams found for {league.upper()}")
            continue

        print(f"  Found {len(teams)} teams\n")

        for team in teams:
            result = download_and_convert_logo(team, output_dir)
            if result:
                if os.path.exists(os.path.join(output_dir, f"{team['abbreviation']}.bmp")):
                    total_downloaded += 1
            else:
                total_failed += 1

    # Summary
    print(f"\n{'=' * 50}")
    print(f"  DONE")
    print(f"{'=' * 50}")
    print(f"  Downloaded: {total_downloaded}")
    print(f"  Failed: {total_failed}")
    print(f"\n  Logo folders:")
    for league, folder in FOLDERS.items():
        path = os.path.join(OUTPUT_BASE, folder)
        if os.path.exists(path):
            count = len([f for f in os.listdir(path) if f.endswith(".bmp")])
            print(f"    {path}/ - {count} logos")

    print(f"\nTo use with the emulator:")
    print(f"  Copy the '{OUTPUT_BASE}/' folder into your emulator_ticker/ directory")
    print(f"\nTo use with the hardware:")
    print(f"  Copy each team*_logos/ folder to the root of your CIRCUITPY drive")


if __name__ == "__main__":
    main()
