import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime

from demoparser2 import DemoParser

from database.database import SessionLocal
from services.mmr_algorithm import recalculate_all_mmr
from services.models import PlayerMatchStats, Player, Match


def parse_demo_file(demo_file_path, discord_mapping, db: SessionLocal):
    """
    Parse the demo file to extract match and player statistics and save them to the database.
    """
    try:
        # Check if the demo has already been processed
        demo_file_name = os.path.basename(demo_file_path)
        existing_match = db.query(Match).filter(Match.team_results == demo_file_name).first()
        if existing_match:
            logging.info(f"Demo {demo_file_name} has already been processed. Skipping.")
            return

        parser = DemoParser(demo_file_path)
        logging.info(f"Initialized DemoParser for {demo_file_path}.")

        # Parse player info to get team mapping
        player_info_df = parser.parse_player_info()
        logging.info("Parsed player info.")

        header_info = parser.parse_header()
        map_name = header_info.get('map_name', 'unknown')

        # Map team numbers to team names
        team_map = {2: 'TERRORIST', 3: 'COUNTER_TERRORIST', 0: 'SPECTATOR'}

        # Parse 'round_end' events to accumulate team scores
        round_end_events = parser.parse_event("round_end")
        if round_end_events.empty:
            logging.error("No round_end events found.")
            return

        # Winner team map
        winner_team_map = {'T': 'TERRORIST', 'CT': 'COUNTER_TERRORIST'}

        # Initialize team scores
        team_scores = {'TERRORIST': 0, 'COUNTER_TERRORIST': 0}

        # Iterate over round_end events
        for _, event in round_end_events.iterrows():
            winner_team_code = event.get('winner')
            winner_team_name = winner_team_map.get(winner_team_code)
            if winner_team_name:
                team_scores[winner_team_name] += 1

        # Determine match result
        t_rounds = team_scores.get('TERRORIST', 0)
        ct_rounds = team_scores.get('COUNTER_TERRORIST', 0)

        if t_rounds > ct_rounds:
            winner = 'TERRORIST'
        elif ct_rounds > t_rounds:
            winner = 'COUNTER_TERRORIST'
        else:
            winner = 'draw'

        # Get the maximum tick
        max_tick = round_end_events["tick"].max()

        # Fields to extract
        wanted_fields = [
            "player_name",
            "user_id",
            "team_num",
            "kills_total",
            "deaths_total",
            "assists_total",
            "mvps",
            "score",
            "headshot_kills_total",
            "ace_rounds_total",
            "4k_rounds_total",
            "3k_rounds_total",
            "utility_damage_total",
            "enemies_flashed_total",
            "alive_time_total",
            "damage_total",
        ]

        # Parse the desired ticks
        df = parser.parse_ticks(wanted_fields, ticks=[max_tick])
        logging.info("Parsed ticks for desired fields.")

        # Replace NaN with zeros
        df.fillna(0, inplace=True)

        # Map team numbers to team names
        df['team_name'] = df['team_num'].map(team_map)
        df = df[df['team_name'] != 'SPECTATOR']  # remove spectators

        # Extract date from filename
        demo_date = extract_date_from_filename(demo_file_path)
        if not demo_date:
            demo_date = datetime.utcnow()  # Use current time if extraction fails

        # Create Match instance
        match = Match(
            date_time=demo_date,
            map_name=map_name,
            team1_name='TERRORIST',
            team2_name='COUNTER_TERRORIST',
            team1_score=t_rounds,
            team2_score=ct_rounds,
            winner=winner,
            team_results=demo_file_name  # Store the demo file name to track processing
        )

        db.add(match)
        db.commit()  # Commit to get match.id

        # get additional custom mappings
        account_mapping = discord_mapping.get("accounts")
        role_mapping = discord_mapping.get("roles")
        core_members = discord_mapping.get("core")

        # Process players and stats
        for _, player_data in df.iterrows():
            steamid = player_data['steamid']
            player_name = player_data['player_name']
            team_name = player_data['team_name']
            discord_id = account_mapping.get(str(steamid))
            role = role_mapping.get(str(steamid))
            core = True if str(steamid) in core_members else False
            # Check if player exists
            player = db.query(Player).filter_by(steamid=steamid).first()
            if not player:
                # Create new player
                player = Player(
                    steamid=steamid,
                    username=player_name,
                    discord_id=discord_id,
                    role=role,
                    core_member=core,
                )
                db.add(player)
                db.commit()  # Commit to get player.id

            # Create PlayerMatchStats
            player_stats = PlayerMatchStats(
                match_id=match.id,
                player_id=player.id,
                team=team_name,
                kills_total=int(player_data.get('kills_total', 0)),
                deaths_total=int(player_data.get('deaths_total', 0)),
                assists_total=int(player_data.get('assists_total', 0)),
                damage_total=int(player_data.get('damage_total', 0)),
                alive_time_total=int(player_data.get('alive_time_total', 0)),
                headshot_kills_total=int(player_data.get('headshot_kills_total', 0)),
                utility_damage_total=int(player_data.get('utility_damage_total', 0)),
                enemies_flashed_total=int(player_data.get('enemies_flashed_total', 0)),
                ace_rounds_total=int(player_data.get('ace_rounds_total', 0)),
                four_k_rounds_total=int(player_data.get('4k_rounds_total', 0)),
                three_k_rounds_total=int(player_data.get('3k_rounds_total', 0)),
                score=int(player_data.get('score', 0)),
                mvps=int(player_data.get('mvps', 0)),
                rounds_won=team_scores.get(team_name, 0),
                rounds_lost=(t_rounds + ct_rounds) - team_scores.get(team_name, 0),
            )

            db.add(player_stats)

        db.commit()
        logging.info(f"Successfully processed and saved data for demo: {demo_file_name}")

    except Exception as e:
        logging.error(f"Failed to parse demo file {demo_file_path}: {e}")
        db.rollback()


def extract_date_from_filename(filename):
    """
    Extracts the date and time from the demo file name.

    Args:
        filename (str): The name of the demo file.

    Returns:
        datetime.datetime: The extracted date and time as a datetime object,
                           or None if parsing fails.
    """
    # Define a regex pattern to match the date and time at the start of the filename
    base_filename = os.path.basename(filename)
    pattern = r'^(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})(?:_\d+)?'
    match = re.match(pattern, base_filename)
    if match:
        date_part = match.group(1)  # e.g., '2024-09-26'
        time_part = match.group(2)  # e.g., '19-17-28'
        # Replace '-' in time with ':' to match the standard time format
        time_part = time_part.replace('-', ':')
        datetime_str = f"{date_part} {time_part}"
        try:
            date_time = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
            logging.debug(f"Extracted datetime: {date_time}")
            return date_time
        except ValueError as e:
            logging.error(f"Failed to parse date and time from filename '{filename}': {e}")
    else:
        logging.warning(f"Filename '{filename}' does not match expected pattern for date extraction.")
    return None


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Parse CS2 .dem files to extract player statistics.'
    )
    parser.add_argument('-i', '--input', required=True, help='Input .dem file path or directory')
    parser.add_argument('-o', '--output', required=True, help='Output JSON file path')
    return parser.parse_args()


def setup_logging():

    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
    )


def main(input_path, db: SessionLocal):
    """Main function to execute the script."""
    setup_logging()

    if not os.path.exists(input_path):
        logging.error(f"Input path {input_path} does not exist.")
        sys.exit(1)

    try:
        logging.info(f"Parsing demo files in: {input_path}")

        if os.path.isdir(input_path):
            demo_files = [os.path.join(input_path, f) for f in os.listdir(input_path) if f.endswith('.dem')]
        else:
            demo_files = [input_path]

        with open("mapping.json", "r") as discord_mapping_file:
            discord_mapping = json.load(discord_mapping_file)
            for demo_file in demo_files:
                logging.info(f"Processing {demo_file}")
                parse_demo_file(demo_file, discord_mapping, db)

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        sys.exit(1)



if __name__ == '__main__':
    db = SessionLocal()
    main("C:/Users/Dimas/MatchZy", db)
    recalculate_all_mmr(db)
