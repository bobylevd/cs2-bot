from sqlalchemy.orm import Session
from services import models, crud


def calculate_mmr_change(player_stat: models.PlayerMatchStats, db: Session) -> int:
    """
    Calculate the MMR change for a single player based on match performance using the HLTV 2.0 rating formula.
    """
    player = crud.get_player(db, player_id=player_stat.player_id)
    if not player:
        return 0

    # Get match details
    match = crud.get_match(db, match_id=player_stat.match_id)
    if not match:
        return 0

    # Determine team result
    player_team = player_stat.team.lower()  # 'terrorist' or 'counter_terrorist'
    match_winner = match.winner.lower()  # 'terrorist', 'counter_terrorist', or 'draw'

    if match_winner == 'draw':
        team_result = 'draw'
    elif player_team == match_winner:
        team_result = 'win'
    else:
        team_result = 'loss'

    # Calculate total rounds played
    total_rounds = match.team1_score + match.team2_score
    if total_rounds == 0:
        return 0  # Avoid division by zero

    # Calculate KPR, DPR, APR
    KPR = player_stat.kills_total / total_rounds
    DPR = player_stat.deaths_total / total_rounds
    APR = player_stat.assists_total / total_rounds

    # Calculate ADR
    ADR = player_stat.damage_total / total_rounds

    # Estimate KAST
    rounds_survived = total_rounds - player_stat.deaths_total
    KAST = ((player_stat.kills_total + player_stat.assists_total + rounds_survived) / total_rounds) * 100

    # Calculate Impact
    Impact = 2.13 * KPR + 0.42 * APR - 0.41

    # Calculate Rating 2.0
    Rating = (
        0.0073 * KAST +
        0.3591 * KPR -
        0.5329 * DPR +
        0.2372 * Impact +
        0.0032 * ADR +
        0.1587
    )

    # Adjust MMR based on Rating
    mmr_change = (Rating - 1.0) * 20  # Scale the rating difference

    # Apply team result modifier
    if team_result == 'win':
        mmr_change += 5
    elif team_result == 'loss':
        mmr_change -= 5
    # Draw results in no additional change

    # Ensure MMR change is within reasonable bounds
    mmr_change = max(-50, min(mmr_change, 50))

    mmr_change = int(round(mmr_change))
    return mmr_change


def recalculate_all_mmr(db: Session) -> None:
    """
    Recalculate MMR for all players based on all matches.
    """
    # Reset all player MMRs to base value
    players = crud.get_players(db)
    for player in players:
        player.mmr = 1000  # Base MMR
    db.commit()

    # Get all matches
    matches = crud.get_all_matches(db)
    for match in matches:
        match_stats = crud.get_match_stats(db, match_id=match.id)
        for player_stat in match_stats:
            mmr_change = calculate_mmr_change(player_stat, db)
            player = crud.get_player(db, player_id=player_stat.player_id)
            if player:
                player.mmr += mmr_change
    db.commit()
