"""
Get Team Logos - Downloads team logos from ESPN for the Sports Ticker

Downloads logos for NFL, MLB, NHL, NBA, NCAAF, NCAAB, and NCAAH teams,
converts them to 32x32 .bmp files named by ESPN abbreviation, and organizes
them into the correct folders for use with both the LED hardware and the emulator.

Install requirements:
    pip install requests Pillow

Run:
    python get_team_logos.py

To re-download all logos (replace existing):
    python get_team_logos.py --force

Output:
    sport_logos/
      team0_logos/   (NFL)
      team1_logos/   (MLB)
      team2_logos/   (NHL)
      team3_logos/   (NBA)
      team4_logos/   (CFB)
      team5_logos/   (CBB)
      team6_logos/   (CHK)
"""

import os
import sys
import requests
from PIL import Image, ImageEnhance
from io import BytesIO

# Logo size for LED matrix (32x32 is standard for this project)
LOGO_SIZE = 32

# Number of palette colors for indexed BMP
# 256 gives best quality. CircuitPython's displayio.OnDiskBitmap handles up to 256.
# Pro leagues with simple logos look fine at 64+. College logos with detailed
# mascots and gradients need more colors to avoid looking blurry/blocky.
PALETTE_COLORS_PRO = 128    # NFL, MLB, NHL, NBA
PALETTE_COLORS_COLLEGE = 256  # CFB, CBB, CHK — need more colors for detailed crests

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

# College leagues that need higher color depth
COLLEGE_LEAGUES = {"cfb", "cbb", "chk"}


def get_best_logo_url(logos):
    """Pick the best logo URL from ESPN's logo list.

    ESPN often provides multiple logo variants. We prefer:
    1. A 'default' logo with dimensions >= 100px (good source for downscaling)
    2. The first logo in the list as fallback

    For college teams, ESPN sometimes only has small (48x48 or 64x64) logos.
    We try to get the largest available.
    """
    if not logos:
        return ""

    best_url = logos[0].get("href", "")
    best_size = 0

    for logo in logos:
        href = logo.get("href", "")
        w = logo.get("width", 0)
        h = logo.get("height", 0)
        size = max(w, h)

        # Prefer larger source images for better downscaling quality
        if size > best_size:
            best_size = size
            best_url = href

    # ESPN logo URLs often have a size parameter — try to request a larger version
    # e.g., ...&w=48&h=48 can be changed to &w=200&h=200
    if best_url and ("&w=" in best_url or "?w=" in best_url):
        # Replace width/height params to request a larger image
        import re
        best_url = re.sub(r'([?&])w=\d+', r'\1w=200', best_url)
        best_url = re.sub(r'([?&])h=\d+', r'\1h=200', best_url)

    return best_url


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
            logo_url = get_best_logo_url(logos)
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


def download_and_convert_logo(team, output_dir, league, force=False):
    """Download a team logo and save it as a 32x32 indexed-color BMP."""
    abbr = team["abbreviation"]
    output_path = os.path.join(output_dir, f"{abbr}.bmp")

    # Skip if already downloaded (unless --force)
    if os.path.exists(output_path) and not force:
        print(f"    {abbr} - already exists, skipping")
        return True

    try:
        resp = requests.get(team["logo_url"], timeout=15)
        resp.raise_for_status()

        # Open image and convert
        img = Image.open(BytesIO(resp.content))

        # Convert to RGBA first to handle transparency
        img = img.convert("RGBA")

        # If source image is very small (common for college teams), use NEAREST
        # for the initial upscale to avoid excessive blur, then use LANCZOS
        # for the final resize. Otherwise just use LANCZOS directly.
        src_w, src_h = img.size
        if max(src_w, src_h) < LOGO_SIZE:
            # Source is smaller than target — scale up with NEAREST first
            # to preserve hard edges, then let quantization handle it
            img = img.resize((LOGO_SIZE, LOGO_SIZE), Image.NEAREST)
        elif max(src_w, src_h) <= LOGO_SIZE * 2:
            # Source is close to target size — use LANCZOS but it may blur
            img = img.resize((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)
        else:
            # Source is larger — LANCZOS downscale gives best quality
            img = img.resize((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)

        # Composite onto black background (LED matrix background)
        background = Image.new("RGB", (LOGO_SIZE, LOGO_SIZE), (0, 0, 0))
        background.paste(img, mask=img.split()[3])

        # Slight sharpening to counteract resize blur — helps on LED matrix
        enhancer = ImageEnhance.Sharpness(background)
        background = enhancer.enhance(1.3)

        # Convert to palette mode (P) to match what CircuitPython expects
        # College logos need more colors due to detailed mascots/crests
        num_colors = PALETTE_COLORS_COLLEGE if league in COLLEGE_LEAGUES else PALETTE_COLORS_PRO
        bmp_img = background.quantize(colors=num_colors, method=Image.Quantize.MEDIANCUT)

        # Save as BMP
        bmp_img.save(output_path, format="BMP")

        size_kb = os.path.getsize(output_path) / 1024
        print(f"    {abbr} - downloaded ({team['name']}) [{size_kb:.1f}KB, {num_colors} colors]")
        return True

    except Exception as e:
        print(f"    {abbr} - FAILED: {e}")
        return False


def main():
    force = "--force" in sys.argv

    print("=" * 50)
    print("  SPORTS TICKER - LOGO DOWNLOADER")
    print("=" * 50)
    print(f"\nLogo size: {LOGO_SIZE}x{LOGO_SIZE}")
    print(f"Pro league colors: {PALETTE_COLORS_PRO}")
    print(f"College colors: {PALETTE_COLORS_COLLEGE}")
    print(f"Output: {OUTPUT_BASE}/")
    if force:
        print("Mode: FORCE RE-DOWNLOAD (replacing existing logos)")
    print()

    total_downloaded = 0
    total_failed = 0

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
            result = download_and_convert_logo(team, output_dir, league, force=force)
            if result:
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
            total_size = sum(
                os.path.getsize(os.path.join(path, f))
                for f in os.listdir(path) if f.endswith(".bmp")
            )
            print(f"    {path}/ - {count} logos ({total_size / 1024:.0f}KB)")

    print(f"\nTo use with the emulator:")
    print(f"  Copy the '{OUTPUT_BASE}/' folder into your emulator_ticker/ directory")
    print(f"\nTo use with the hardware:")
    print(f"  Copy each team*_logos/ folder to the root of your CIRCUITPY drive")


if __name__ == "__main__":
    main()
