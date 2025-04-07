import json
import re
import time
import gc
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

def process_race_page(page, race_url, wait_timeout=30):
    print(f"[DEBUG] Loading race URL: {race_url}")
    page_data = {}
    try:
        # Increase timeout to 30 seconds and wait until DOM is ready.
        page.goto(race_url, timeout=wait_timeout * 1000, wait_until="domcontentloaded")
    except Exception as e:
        print(f"[ERROR] page.goto() failed for {race_url}: {e}")
        return {}
    try:
        # Wait for the header element (adjust selector as needed)
        page.wait_for_selector("._n47wzcNaN", timeout=wait_timeout * 1000)
        header_text = page.inner_text("._n47wzcNaN").strip()
        print(f"[DEBUG] Found header: {header_text}")
    except Exception as e:
        print(f"[ERROR] Error retrieving header on {race_url}: {e}")
        return {}

    # Extract race time and location from the header using regular expressions.
    match = re.match(r"(\d{2}\.\d{2})\s(.+?)(\s-|$)", header_text)
    if match:
        race_time = match.group(1)
        race_location = match.group(2).strip()
        page_data['race_time'] = race_time
        page_data['race_location'] = race_location
        print(f"[DEBUG] Race time: {race_time}; Location: {race_location}")
        horses = {}
        horse_containers = page.query_selector_all("div._e296pg")
        print(f"[DEBUG] Found {len(horse_containers)} horse container(s)")
        for container in horse_containers:
            try:
                horse_elem = container.query_selector("button._1pjekjq7 div._1ksksp3")
                if not horse_elem:
                    continue
                horse_name = horse_elem.inner_text().strip()
                odds_elem = container.query_selector("div._18w1m8i span._l437sv > span")
                odds = odds_elem.inner_text().strip() if odds_elem else "N/A"
                horses[horse_name] = odds
                print(f"[DEBUG] Horse: {horse_name} | Odds: {odds}")
            except Exception as e:
                print(f"[ERROR] Error extracting horse data on {race_url}: {e}")
        page_data['horses'] = horses
    else:
        print(f"[ERROR] Couldn't parse header on {race_url}: {header_text}")
    
    return page_data


def get_race_data_for_url(page, race_url, max_retries=2):
    attempt = 0
    data = None
    while attempt < max_retries and not data:
        print(f"[DEBUG] Attempt {attempt + 1} for URL: {race_url}")
        data = process_race_page(page, race_url)
        if not data:
            attempt += 1
            print(f"[WARN] Retry {attempt} for {race_url}")
            time.sleep(2)
            page.context.clear_cookies()  # Clear cookies between attempts.
    if not data:
        print(f"[WARN] Skipping {race_url} after {max_retries} attempts.")
    return data

def merge_results(final_data, new_data):
    for location, times in new_data.items():
        if location not in final_data:
            final_data[location] = times
        else:
            final_data[location].update(times)
    return final_data

def main(today=True):
    print("[INFO] Starting race URL scraping with Playwright...")
    base_url = "https://m.skybet.com/horse-racing/meetings"
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-webgl",
                "--disable-cache",
                "--disk-cache-size=0",
            ]
        )
        # Set a custom user-agent to mimic a real browser.
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
        
        # Block images, stylesheets, and fonts to conserve memory.
        # def block_resource(route, request):
        #     if request.resource_type in ["image", "stylesheet", "font"]:
        #         route.abort()
        #     else:
        #         route.continue_()
        # context.route("**/*", block_resource)

        # Create a page
        main_page = context.new_page()
        try:
            # Wait for DOMContentLoaded instead of full load, and increase timeout to 30000ms
            main_page.goto(base_url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(3)  # Give additional time for JS to render, if needed.
        except Exception as e:
            print(f"[ERROR] Failed to load main page: {e}")
            browser.close()
            return

        # Use BeautifulSoup to parse the page content and extract race URLs.
        page_content = main_page.content()
        soup = BeautifulSoup(page_content, "html.parser")
        race_urls = []
        uk_section = None
        for accordion in soup.find_all("li", class_="accordion--generic js-toggle"):
            title_el = accordion.find("span", class_="split__title")
            if title_el and "UK & Irish Racing" in title_el.text.strip():
                if today:
                    uk_section = accordion
                    break
                else:
                    today=True
        if uk_section:
            for race_div in uk_section.find_all("div", class_="cell--link race-grid-col"):
                if "settled-meeting" in race_div.get("class", []):
                    continue
                link = race_div.find("a", class_="cell--link__link")
                if link and link.get("href"):
                    full_url = f"https://m.skybet.com{link.get('href')}"
                    race_urls.append(full_url)
            print(f"[INFO] Found {len(race_urls)} upcoming races.")
        else:
            print("[WARN] UK & Irish Racing section not found.")

        if not race_urls:
            print("[WARN] No race URLs to process; exiting.")
            browser.close()
            return

        # Process race URLs in batches (to reduce per-page overhead)
        batch_size = 10
        final_results = {}
        total_urls = len(race_urls)
        for i in range(0, total_urls, batch_size):
            batch_urls = race_urls[i : i + batch_size]
            print(f"[INFO] Processing batch {i // batch_size + 1} (URLs {i+1} to {i + len(batch_urls)})")
            page = context.new_page()
            batch_results = {}
            for race_url in batch_urls:
                result = get_race_data_for_url(page, race_url)
                if result:
                    race_location = result.get("race_location", "Unknown")
                    race_time = result.get("race_time", "Unknown")
                    horses = result.get("horses", {})
                    if race_location not in batch_results:
                        batch_results[race_location] = {}
                    batch_results[race_location][race_time] = horses
                # Clear cookies after each race URL.
                page.context.clear_cookies()
            batch_file = f"partial_upcomingOddsData_{i // batch_size + 1}.json"
            with open(batch_file, "w") as outfile:
                json.dump(batch_results, outfile, indent=4)
            print(f"[INFO] Flushed batch {i // batch_size + 1} results to {batch_file}.")
            final_results = merge_results(final_results, batch_results)
            page.close()
            del batch_results
            gc.collect()
        
        final_file = "upcomingOddsData.json"
        with open(final_file, "w") as outfile:
            json.dump(final_results, outfile, indent=4)
        print(f"[INFO] Saved final results to {final_file}.")
        print("[INFO] Scraping complete!")
        browser.close()

if __name__ == "__main__":
    main()
