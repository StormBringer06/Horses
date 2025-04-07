import aiohttp
import asyncio
from bs4 import BeautifulSoup
import json
from aiohttp import ClientTimeout
import os
from colorama import Fore, Back, Style, init

init()

# Configuration
USE_PROXIES = False
REQUEST_DELAY = 0.3
RETRY_DELAY = 0.3
BATCH_SIZE = 10
CONCURRENT_REQUESTS = 10

# Load proxies
if USE_PROXIES:
    with open("validProxyList.json", "r") as f:
        PROXY_LIST = json.load(f)
else:
    PROXY_LIST = []



async def fetch_page(session, url, semaphore, retries=5):
    for attempt in range(retries):
        try:
            proxy = PROXY_LIST[attempt % len(PROXY_LIST)] if USE_PROXIES and PROXY_LIST else None
            async with semaphore:
                async with session.get(url, proxy=proxy, timeout=ClientTimeout(total=10)) as response:
                    response.raise_for_status()
                    return await response.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            print(f"Attempt {attempt + 1} failed for {url}: {e}")
            if attempt == retries - 1:
                print(f"Failed to fetch {url} after {retries} attempts.")
                print(Back.RED + "FAIL FAIL FAIL FAIL" + Style.RESET_ALL)
                return None
            await asyncio.sleep(RETRY_DELAY * (2 ** attempt))
    return None

async def extract_links(session, soup, base_url, semaphore):
    initial_links = []
    final_links = []
    
    # Collect initial links
    for location in soup.find_all("div", {"class": "sdc-site-concertina-block__inner"}):
        title_span = location.find("span", {"class": "sdc-site-concertina-block__title"})
        if not title_span:
            continue
        title_text = title_span.text.strip()
        if not any(x in title_text for x in ["(USA)", "(BRZ)", "(FR)", "(SAF)", "(ARG)"]):
            print("Skipping UK race:", title_text)
            continue
        for link in location.find_all('a', {'class': 'sdc-site-racing-meetings__event-link'}):
            initial_links.append(base_url + link['href'])

    # Process intermediate pages
    async def process_intermediate_link(link):
        content = await fetch_page(session, link, semaphore)
        if not content:
            return None
            
        intermediate_soup = BeautifulSoup(content, 'html.parser')
        message_div = intermediate_soup.find('div', class_='sdc-site-message--horseracing')
        
        if message_div:
            racecard_link = message_div.find('a', class_='sdc-site-message__link', 
                                            string=lambda text: 'Racecard' in text)
            if racecard_link:
                return base_url + racecard_link['href']
        print(f"Racecard not found in intermediate page: {link}")
        return None

    tasks = [process_intermediate_link(link) for link in initial_links]
    results = await asyncio.gather(*tasks)
    final_links = [link for link in results if link is not None]
    
    return final_links

async def get_racecard_or(session, racecard_url, base_url, semaphore):
    or_data = {}
    page_content = await fetch_page(session, base_url + racecard_url, semaphore)
    if not page_content:
        return or_data

    soup = BeautifulSoup(page_content, 'html.parser')
    for card in soup.find_all('div', {'class': 'sdc-site-racing-card__item'}):
        name_tag = card.find('h4', {'class': 'sdc-site-racing-card__name'})
        if name_tag:
            horse_name = name_tag.text.strip()
            or_tag = card.find('li', {'data-label': 'OR'})
            or_data[horse_name] = or_tag.find('strong').text.strip() if or_tag else 'N/A'
    return or_data

async def get_jockey_win_percentage(session, jockey_url, base_url, semaphore):
    try:
        content = await fetch_page(session, base_url + jockey_url, semaphore)
        if not content:
            return 'N/A'
            
        soup = BeautifulSoup(content, 'html.parser')
        table = soup.find('table', class_='sdc-site-scrolling-table__table')
        if not table:
            return 'N/A'

        for row in table.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) >= 6 and 'Season (Jump)' in cells[0].get_text():
                return cells[5].get_text(strip=True)
        return 'N/A'
    except Exception as e:
        print(f"Error getting jockey stats: {str(e)}")
        return 'N/A'

async def extract_data_from_race_page(session, url, base_url, all_horse_data, jockey_cache, semaphore):
    await asyncio.sleep(REQUEST_DELAY)
    results = []
    
    page_content = await fetch_page(session, url, semaphore)
    if not page_content:
        return results

    soup = BeautifulSoup(page_content, 'html.parser')
    race_name_tag = soup.find("h3", {"class": "sdc-site-racing-header__description"})
    race_name = race_name_tag.text.strip() if race_name_tag else "Unknown Race"
    
    # Track length extraction
    track_length = "N/A"
    for item in soup.find_all('li', {'class': 'sdc-site-racing-header__details-item'}):
        if "Distance:" in item.text:
            track_length = item.find('strong').next_sibling.strip()
            break

    # Racecard OR data
    racecard_link = soup.find('a', {'class': 'sdc-site-racing-status__link'})
    or_data = {}
    if racecard_link:
        or_data = await get_racecard_or(session, racecard_link['href'], base_url, semaphore)

    race_title = soup.find("h2", {"class": "sdc-site-racing-header__name"}).text.strip()
    race_time = race_title.split(" ", 1)[0]
    race_location = race_title.split(" ", 1)[1]

    # Process horses
    for card in soup.find_all('div', {'class': 'sdc-site-racing-card__item'}):
        race_position = card.find('span', {'class': 'sdc-site-racing-card__position'})
        race_position = race_position.text.strip() if race_position else ''
        
        race_number = card.find('div', {'class': 'sdc-site-racing-card__number'})
        race_number = race_number.text.strip() if race_number else ''
        
        horse_name_tag = card.find('h4', {'class': 'sdc-site-racing-card__name'})
        horse_name = horse_name_tag.text.strip() if horse_name_tag else ''
        
        last_run_days = card.find('span', {'class': 'sdc-site-racing-card__last-run'})
        last_run_days = last_run_days.text.strip() if last_run_days else ''
        
        betting_odds = card.find('span', {'class': 'sdc-site-racing-card__betting-odds'})
        betting_odds = betting_odds.text.strip() if betting_odds else ''
        
        horse_form = card.find('li', {'data-label': 'Form'})
        horse_form = horse_form.find('strong').text.strip() if horse_form else ''
        
        horse_age = card.find('li', {'data-label': 'Age'})
        horse_age = horse_age.find('strong').text.strip() if horse_age else ''
        
        horse_weight = card.find('li', {'data-label': 'Wgt'})
        horse_weight = horse_weight.find('strong').text.strip() if horse_weight else ''
        
        trainer = card.find('a', {'href': lambda x: x and '/racing/form-profiles/trainer/' in x})
        trainer = trainer.text.strip() if trainer else ''
        
        jockey_tag = card.find('a', {'href': lambda x: x and '/racing/form-profiles/jockey/' in x})
        jockey = jockey_tag.text.strip() if jockey_tag else 'N/A'
        jockey_url = jockey_tag['href'] if jockey_tag else None
        
        # Jockey win percentage with caching
        jockey_win_percent = 'N/A'
        if jockey_url:
            if jockey_url in jockey_cache:
                jockey_win_percent = jockey_cache[jockey_url]
            else:
                jockey_win_percent = await get_jockey_win_percentage(session, jockey_url, base_url, semaphore)
                jockey_cache[jockey_url] = jockey_win_percent

        race_summary = card.find('p', {'class': 'sdc-site-racing-card__summary'})
        race_summary = race_summary.text.strip() if race_summary else ''

        # Horse win percentage handling
        h_win_per = 'N/A'
        horse_link_tag = horse_name_tag.find("a") if horse_name_tag else None
        if horse_link_tag:
            horse_name = horse_link_tag.text.strip()
            horse_link = base_url + horse_link_tag["href"]
            
            # Use cached data if available
            if horse_name in all_horse_data:
                h_win_per = all_horse_data[horse_name].get("hWinPer", "N/A")
                print(Fore.YELLOW + f"Using cached win% for {horse_name}" + Style.RESET_ALL)
            else:
                # Fetch new data if not in cache
                horse_content = await fetch_page(session, horse_link, semaphore)
                if horse_content:
                    horse_soup = BeautifulSoup(horse_content, 'html.parser')
                    table = horse_soup.find('table', class_='sdc-site-scrolling-table__table')
                    if table:
                        tds = table.find_all('td')
                        h_win_per = tds[5].text.strip() if len(tds) > 5 else 'N/A'
                        all_horse_data[horse_name] = {"hWinPer": h_win_per}
                        print(Fore.GREEN + f"Fetched new win% for {horse_name}" + Style.RESET_ALL)

        results.append({
            'Position': race_position,
            'Number': race_number,
            'Horse Name': horse_name,
            'Last Run Days': last_run_days,
            'Betting Odds': betting_odds,
            'Form': horse_form,
            'Age': horse_age,
            'Weight': horse_weight,
            'Trainer': trainer,
            'Jockey': jockey,
            'JockeyWinPercent': jockey_win_percent,
            'Summary': race_summary,
            "raceName": race_name,
            "trackLength": track_length,
            "OfficialRating": or_data.get(horse_name, 'N/A'),
            "hWinPer": h_win_per,
            "time": race_time,
            "location": race_location
        })

    return results

# File handling functions
def save_to_json(data, filename):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def load_json(filename):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def load_jockey_cache(filename="jockey_cache.json"):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

async def main(date="21-03-2025", main_url='https://www.skysports.com/racing/results/21-03-2025'):
    base_url = 'https://www.skysports.com'
    main_url = f"https://www.skysports.com/racing/results/{date}"
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
    
    async with aiohttp.ClientSession() as session:
        all_results = []
        all_horse_data = load_json("testHorseData.json")
        race_ids = load_json("testRaceIDs.json")
        jockey_cache = load_jockey_cache()

        page_content = await fetch_page(session, main_url, semaphore)
        if not page_content:
            print("Failed to fetch main page")
            return

        soup = BeautifulSoup(page_content, 'html.parser')
        race_links = await extract_links(session, soup, base_url, semaphore)

        for i in range(0, len(race_links), BATCH_SIZE):
            batch_links = race_links[i:i + BATCH_SIZE]
            print(Back.GREEN + f"Processing batch {i//BATCH_SIZE + 1}/{(len(race_links)-1)//BATCH_SIZE + 1}" + Style.RESET_ALL)

            tasks = [extract_data_from_race_page(session, link, base_url, all_horse_data, jockey_cache, semaphore) 
                    for link in batch_links]
            batch_results = await asyncio.gather(*tasks)

            for race_results in batch_results:
                if race_results:
                    all_results.extend(race_results)
                    if race_results:
                        race_ids.append(race_results[0]["raceName"])

            # Save progress after each batch
            save_to_json(all_results, 'upcomingRace_results.json')
            save_to_json(all_horse_data, "testHorseData.json")
            save_to_json(race_ids, "testRaceIDs.json")
            save_to_json(jockey_cache, "jockey_cache.json")

        print(Back.BLUE + "\nAll data scraped successfully!" + Style.RESET_ALL)

if __name__ == '__main__':
    asyncio.run(main())