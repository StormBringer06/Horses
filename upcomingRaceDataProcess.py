import json
import math
import re
from collections import defaultdict

def main():
    def convert_weight(weight_str):
        """Convert 'stones-pounds' or pounds-only format to total pounds"""
        try:
            if '-' in weight_str:
                stones, pounds = map(int, weight_str.split('-'))
                return stones * 14 + pounds
            else:
                return int(weight_str)
        except:
            return 0

    def convert_odds(odds_str):
        """Convert fractional odds to log of fractional odds (matches sample)"""
        try:
            odds_str = odds_str.strip().lower()
            if odds_str == 'evens':
                return math.log(1.0)  # 1/1 becomes log(1) = 0.0 (matches sample)
            if '/' in odds_str:
                numerator, denominator = map(int, odds_str.split('/'))
            else:  # Handle whole numbers like "5" (5/1)
                numerator = int(odds_str)
                denominator = 1
            return math.log(numerator / denominator)
        except:
            return math.log(1e-6)
        
    def get_odds(location, time, horse):
        try:
            splitTime = time.split(":")
            time = f"{splitTime[0]}.{splitTime[1]}"
            odds = oddsData[location.split()[0]][time][horse.split("(")[0].strip()]
            if '/' in odds:
                numerator, denominator = map(int, odds.split('/'))
            else:  # Handle whole numbers like "5" (5/1)
                numerator = int(odds)
                denominator = 1
            return math.log(numerator / denominator)
        except:
            return math.log(1e-6)

    def convert_percentage(percent_str):
        """Convert percentage string to float, handling decimals"""
        try:
            return float(percent_str.strip('%'))
        except:
            return 0.0

    def convert_distance(distance_str):
        """Convert race distance to total yards with improved parsing"""
        try:
            parts = re.findall(r'(\d+)(m|f|y)', distance_str)
            yards = 0
            for value, unit in parts:
                if unit == 'm':
                    yards += int(value) * 1760
                elif unit == 'f':
                    yards += int(value) * 220
                elif unit == 'y':
                    yards += int(value)
            return yards
        except:
            return 0
        
    def convert_form(form):
        try:
            if form == "":
                return 10
            total = 0
            i = 0
            for x in form:
                if not x in ["-", "/"]:
                    if x in ["0", "P", "F", "S", "U", "R"]:
                        total += 10
                        i+=1
                    elif x in ["B", "V", "D", "m", "h", "C"]:
                        continue
                    else:
                        total += int(x)
                        i+=1
            if i != 0:
                return total/i
            return 10
        except:
            print(form)


    def process_races(input_data, horse_data):
        processed = []
        # Initialize with the first entry's raceName and race metadata.
        current_race = input_data[0].get("raceName", "").strip()
        # Capture the location and time for the first race.
        last_location = input_data[0].get("location", "").strip()
        last_time = input_data[0].get("time", "").strip()
        race_id = 0
        race_entries = []
            
        for entry in input_data:
            # Skip entries missing a proper horse number
            if entry["Number"].split("(")[0] == "":
                continue

            horse_name = entry["Horse Name"].strip()
            hwinper = convert_percentage(horse_data.get(horse_name, {}).get("hWinPer", "0%"))
            
            clean_race_name = entry.get("raceName", "").strip()
            if not clean_race_name:
                continue  # Skip entries without raceName
            
            # If we encounter a new race, process the completed race entries.
            if clean_race_name != current_race:
                process_race_entries(
                    race_entries,
                    f"{last_location} {last_time} - {current_race}",
                    processed
                )
                # Update to the new race details.
                current_race = clean_race_name
                last_location = entry.get("location", "").strip()
                last_time = entry.get("time", "").strip()
                race_id += 1  # Increment after processing the previous race
                race_entries = []
                
            race_entries.append({
                "horse_id": entry["Horse Name"].strip(),
                "data": {
                    "Hwinper": hwinper,
                    "wt.carried": convert_weight(entry["Weight"]),
                    "Jwinper": convert_percentage(entry["JockeyWinPercent"]),
                    "age": int(entry["Age"]),
                    "logOdds": get_odds(entry["location"], entry["time"], entry["Horse Name"]),
                    "odds": entry["Betting Odds"],
                    "trackLength": convert_distance(entry["trackLength"]),
                    "rating": int(entry["OfficialRating"]) if entry["OfficialRating"].isdigit() else 0,
                    "form": convert_form(entry["Form"])
                }
            })
            
        # Process the final race using the last gathered location/time.
        if race_entries:
            process_race_entries(
                race_entries,
                f"{last_location} {last_time} - {current_race}",
                processed
            )
            
        return processed


    def process_race_entries(race_entries, race_id, processed):
        for entry in race_entries:
            wdproduct = entry["data"]["trackLength"] * entry["data"]["wt.carried"]
            processed.append({
                "race_id": race_id,
                "horse_id": entry["horse_id"],
                "Hwinper": entry["data"]["Hwinper"],
                "wt.carried": entry["data"]["wt.carried"],
                "rating": entry["data"]["rating"],
                "Jwinper": entry["data"]["Jwinper"],
                "age": entry["data"]["age"],
                "logOdds": entry["data"]["logOdds"],
                "wdproduct": wdproduct,
                "odds": entry["data"]["odds"],
                "form": entry["data"]["form"]
            })

    # Load and process data as before
    with open("upcomingRace_results.json", "r") as f:
        input_data = json.load(f)

    with open("testHorseData.json", "r") as f:
        horse_data = json.load(f)

    with open("upcomingOddsData.json", "r") as f:
        oddsData = json.load(f)


    output_data = process_races(input_data, horse_data)

    with open("upcomingRaceData.json", "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"Successfully processed {len(output_data)} entries across {output_data[-1]['race_id'] if output_data else 0} races")

if __name__ == "__main__":
    main()