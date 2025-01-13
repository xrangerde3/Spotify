import http.client
import json
import random
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)

RAPIDAPI_KEY = "b7fb9487d5msh98c311a62c8d538p17d143jsn3392672cb30d"
CONSTANT_ISRC = "CA5KR1821202"

# GLOBAL STORAGE
tracked_songs = []
stats = {
    "total_urls": 0,
    "total_streams": 0,
    "unique_artists": 0
}

# A utility function to get today's date in YYYY-MM-DD
def today_str():
    return datetime.now().strftime("%Y-%m-%d")

def get_stream_count(track_id):
    """
    Example of getting the stream count from RapidAPI.
    If the key isn't provided, we generate a random number.
    """
    if not RAPIDAPI_KEY or RAPIDAPI_KEY == "YOUR_RAPIDAPI_KEY_HERE":
        return random.randint(5000, 20000)
    try:
        conn = http.client.HTTPSConnection("spotify-track-streams-playback-count1.p.rapidapi.com")
        headers = {
            'x-rapidapi-key': RAPIDAPI_KEY,
            'x-rapidapi-host': "spotify-track-streams-playback-count1.p.rapidapi.com"
        }
        endpoint = f"/tracks/spotify_track_streams?spotify_track_id={track_id}&isrc={CONSTANT_ISRC}"
        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        data = res.read()
        conn.close()

        parsed = json.loads(data.decode("utf-8"))
        if parsed.get("result") == "success":
            return parsed.get("streams", "N/A")
        else:
            return "N/A"
    except Exception as e:
        print("Error calling RapidAPI:", e)
        return "N/A"

def month_name(m):
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return names[m-1]

def generate_fake_chart_data(release_year, current_year, current_stream_count):
    """
    This was your existing 'fake' historical data generator for the detail page.
    We'll keep it mostly as-is for the detail page's chart.
    """
    import random
    chart_labels = []
    chart_values = []
    cumulative_streams = 0

    if release_year <= 2023:
        for y in range(release_year, min(2024, current_year + 1)):
            if y > 2023:
                break
            year_label = str(y)
            chart_labels.append(year_label)
            increment = random.randint(
                max(100, current_stream_count // 10),
                max(500, current_stream_count // 5)
            )
            cumulative_streams += increment
            if cumulative_streams > current_stream_count:
                cumulative_streams = current_stream_count
            chart_values.append(cumulative_streams)
            if cumulative_streams >= current_stream_count:
                break

    if current_year >= 2024:
        start_year = max(2024, release_year)
        for y in range(start_year, current_year + 1):
            for month in range(1, 13):
                if y > current_year:
                    break
                month_label = f"{month_name(month)} {y}"
                chart_labels.append(month_label)
                increment = random.randint(
                    max(50, current_stream_count // 20),
                    max(300, current_stream_count // 10)
                )
                cumulative_streams += increment
                if cumulative_streams > current_stream_count:
                    cumulative_streams = current_stream_count
                chart_values.append(cumulative_streams)
                if cumulative_streams >= current_stream_count:
                    break
            if cumulative_streams >= current_stream_count:
                break

    return chart_labels, chart_values

def get_spotify_track_data(track_url_or_id):
    """
    Fetches basic track data by scraping the Spotify page via Selenium,
    plus the actual stream count from the API.
    """
    track_id = track_url_or_id
    if "open.spotify.com/track/" in track_url_or_id:
        track_id = track_url_or_id.split("/track/")[1].split("?")[0]

    service = ChromeService(executable_path="C:/Users/Nnoop/Downloads/chromedriver.exe")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    driver = webdriver.Chrome(service=service, options=options)
    driver.get(f"https://open.spotify.com/track/{track_id}")

    track_data = {
        "track_id": track_id,
        "artist": "Unknown Artist",
        "title": "Unknown Track",
        "stream_count": "N/A",
        "release_year": "2023",
        "duration": "3:45",
        "image_url": ""
    }

    wait = WebDriverWait(driver, 10)
    try:
        wait.until(EC.title_contains("Spotify"))
        full_title = driver.title
        parts = full_title.replace(" | Spotify", "").split(" - ")
        if len(parts) >= 2:
            track_data["title"] = parts[0].strip()
            track_data["artist"] = parts[1].strip()
        try:
            og_meta = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'meta[property="og:image"]'))
            )
            track_data["image_url"] = og_meta.get_attribute("content")
        except:
            pass
    except Exception as e:
        print("Error scraping track data with Selenium:", e)
    finally:
        driver.quit()

    track_data["stream_count"] = get_stream_count(track_id)
    return track_data

def update_daily_differences():
    """
    This function checks if >=24 hours have passed for each tracked song.
    If so, it fetches the new stream_count, calculates difference,
    and appends a new entry to that song's history.
    """
    now = datetime.now()
    for song in tracked_songs:
        last_checked = song.get("last_checked")
        if not last_checked:
            # If never checked before, set it to now
            song["last_checked"] = now
            continue

        diff_hours = (now - last_checked).total_seconds() / 3600.0
        if diff_hours >= 24.0:
            # Time to update the stream count
            old_stream_count = song["stream_count"]
            new_stream_count = 0
            try:
                new_stream_count = int(get_stream_count(song["track_id"]))
            except:
                new_stream_count = old_stream_count  # fallback

            difference = new_stream_count - old_stream_count

            # Update the song's global stream count
            song["stream_count"] = new_stream_count
            song["difference"] = f"+{difference}" if difference >= 0 else f"{difference}"

            # Update the history
            if "history" not in song:
                song["history"] = []
            song["history"].append({
                "date": today_str(),
                "stream_count": new_stream_count,
                "difference": difference
            })
            # Update last_checked
            song["last_checked"] = now


@app.route("/", methods=["GET", "POST"])
def index():
    global tracked_songs, stats

    # 1) Attempt to update daily differences for each track if >=24h
    update_daily_differences()

    if request.method == "POST":
        track_url_or_id = request.form.get("track_url")
        track_data = get_spotify_track_data(track_url_or_id)

        try:
            sc = int(track_data["stream_count"])
        except:
            sc = 0

        # Initialize a new track with 'history' containing today's record
        new_song = {
            "artist": track_data["artist"],
            "title": track_data["title"],
            "track_id": track_data["track_id"],
            "date": today_str(),  # store the date the user added
            "stream_count": sc,
            "difference": "+0",
            "status": "resume",
            "image_url": track_data["image_url"],
            "last_checked": datetime.now(),  # store current time
            "history": [
                {
                    "date": today_str(),
                    "stream_count": sc,
                    "difference": 0
                }
            ]
        }

        tracked_songs.append(new_song)

    # Recalculate top-level stats
    stats["total_urls"] = len(tracked_songs)
    stats["total_streams"] = sum(song["stream_count"] for song in tracked_songs)
    unique_artists = set(song["artist"] for song in tracked_songs)
    stats["unique_artists"] = len(unique_artists)

    return render_template("index.html", track_data=None, stats=stats, tracks=tracked_songs)


@app.route("/detail/<track_id>")
def detail_by_id(track_id):
    found_song = None
    for s in tracked_songs:
        if s["track_id"] == track_id:
            found_song = s
            break

    if not found_song:
        return redirect(url_for("index"))

    track_data = {
        "track_id": found_song["track_id"],
        "artist": found_song["artist"],
        "title": found_song["title"],
        "stream_count": found_song["stream_count"],
        "release_year": "2023",
        "duration": "3:45",
        "image_url": found_song["image_url"]
    }

    try:
        release_year = int(track_data.get("release_year", 2022))
    except:
        release_year = 2022

    current_year = 2025
    try:
        current_streams = int(track_data.get("stream_count", 0))
    except:
        current_streams = 0

    chart_labels, chart_values = generate_fake_chart_data(
        release_year,
        current_year,
        current_streams
    )

    return render_template(
        "detail.html",
        track_data=track_data,
        chart_labels=chart_labels,
        chart_values=chart_values
    )


@app.route("/pause/<track_id>")
def pause(track_id):
    global tracked_songs
    for song in tracked_songs:
        if song["track_id"] == track_id:
            song["status"] = "pause"
    return redirect(url_for("index"))


@app.route("/resume/<track_id>")
def resume(track_id):
    global tracked_songs
    for song in tracked_songs:
        if song["track_id"] == track_id:
            song["status"] = "resume"
    return redirect(url_for("index"))


@app.route("/delete/<track_id>")
def delete(track_id):
    global tracked_songs
    tracked_songs = [s for s in tracked_songs if s["track_id"] != track_id]
    return redirect(url_for("index"))

########################
# NEW: CHART DATA ROUTE
########################
@app.route("/chart_data")
def chart_data():
    """
    Returns JSON for the 'difference streams' chart on the homepage.
    Query params:
      - song_id = track_id of a specific song. If omitted, sum across all.
      - days = an integer (7,14,31...). If omitted, return all known data.
    Example:
      /chart_data?song_id=XYZ&days=7
    """
    song_id = request.args.get("song_id", None)
    days = request.args.get("days", None, type=int)

    # We'll build a dictionary: { date_str: sum_of_differences }
    # If song_id is given, we only sum that track's differences.
    date_diff_map = {}

    now = datetime.now()
    cutoff_date = None
    if days:
        cutoff_date = (now - timedelta(days=days)).date()

    for song in tracked_songs:
        # If a song_id is specified, skip if track_id doesn't match
        if song_id and song["track_id"] != song_id:
            continue

        for rec in song.get("history", []):
            d_str = rec["date"]
            # Convert to date object
            try:
                d_obj = datetime.strptime(d_str, "%Y-%m-%d").date()
            except:
                # If, for some reason, the date isn't parseable
                continue

            if cutoff_date and d_obj < cutoff_date:
                continue

            diff_val = rec["difference"]
            # difference can be negative or positive, so sum them up
            date_diff_map[d_str] = date_diff_map.get(d_str, 0) + diff_val

    # Now sort the dates
    sorted_dates = sorted(date_diff_map.keys())
    labels = sorted_dates
    values = [date_diff_map[d] for d in labels]

    return jsonify({
        "labels": labels,
        "values": values
    })


if __name__ == "__main__":
    app.run(debug=True)
