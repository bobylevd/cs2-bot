import itertools
import logging
import random

from services import crud, models
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def balance_teams(player_ids: List[int], db: Session) -> Tuple[List[int], List[int], int]:
    """
    Balance teams based on player MMR and constraints.
    """
    logger.info(f"Balancing teams for players: {player_ids}")

    # Retrieve player data
    players = []
    for pid in player_ids:
        player = crud.get_player_by_discord_id(db, discord_id=pid)
        if not player:
            raise ValueError(f"Player with id {pid} not found")
        players.append(player)

    core_members = [player for player in players if player.core_member]
    non_core_members = [player for player in players if not player.core_member]
    total_players = len(core_members) + len(non_core_members)
    if total_players < 10:
        raise ValueError("At least 10 players are required to form two teams of five.")

    if len(core_members) >= 10:
        selected_players = random.sample(core_members, 10)

    else:
        # Include all core members
        selected_players = core_members.copy()
        # Need to fill up remaining slots with non-core members
        remaining_slots = 10 - len(core_members)
        if len(non_core_members) < remaining_slots:
            raise ValueError(
                f"Not enough non-core members to fill the teams. Need {remaining_slots}, "
                f"but have {len(non_core_members)}"
            )
        # Randomly select non-core members to fill up
        selected_players.extend(random.sample(non_core_members, remaining_slots))

    random.shuffle(selected_players)

    # Define team size
    team_size = 5

    # Initialize variables to track the best team combination
    min_mmr_diff = float('inf')
    best_team_a = []
    best_team_b = []

    constraints = {
        'roles': {
            'sniper': 1
        },
        'conflicts': [
        ]
    }

    # Generate all possible combinations for team A
    player_indices = list(range(len(selected_players)))
    player_roles = [player.role for player in selected_players]

    sniper_count = sum(1 for role in player_roles if role == 'sniper')

    combinations = list(itertools.combinations(player_indices, team_size))

    # Iterate through all possible team combinations
    for combo in combinations:
        team_a_indices = set(combo)
        team_b_indices = set(player_indices) - team_a_indices

        team_a = [selected_players[i] for i in team_a_indices]
        team_b = [selected_players[i] for i in team_b_indices]

        if sniper_count >= 2:
            if not snipers_balanced(team_a, team_b):
                continue

        # Check role constraints
        # if not roles_balanced(team_a, team_b, constraints['roles']):
        #     continue
        #
        # # Check conflicts
        # if not conflicts_respected(team_a, team_b, constraints['conflicts']):
        #     continue

        # Calculate total MMR for each team
        mmr_team_a = sum(player.mmr for player in team_a)
        mmr_team_b = sum(player.mmr for player in team_b)

        # Calculate the absolute difference in MMR between the two teams
        mmr_diff = abs(mmr_team_a - mmr_team_b)

        # Update the best team combination if a better one is found
        if mmr_diff < min_mmr_diff:
            min_mmr_diff = mmr_diff
            best_team_a = team_a
            best_team_b = team_b

            # Early exit if perfect balance is found
            if mmr_diff == 0:
                break

    if not best_team_a or not best_team_b:
        raise ValueError("Unable to balance teams with the given constraints")

    # Prepare the output data
    team_a_output = [
        player.discord_id for player in best_team_a
    ]
    team_b_output = [
        player.discord_id for player in best_team_b
    ]

    logger.info(f"Teams balanced with MMR difference of {min_mmr_diff}")

    return team_a_output, team_b_output, min_mmr_diff


def roles_balanced(
    team_a: List[models.Player],
    team_b: List[models.Player],
    role_constraints: Dict[str, int]
) -> bool:
    """
    Check if roles are balanced according to the specified constraints.
    """
    for role, count in role_constraints.items():
        team_a_role_count = sum(1 for player in team_a if player.role == role)
        team_b_role_count = sum(1 for player in team_b if player.role == role)
        if team_a_role_count != count or team_b_role_count != count:
            logger.debug(
                f"Role constraint not met for role '{role}': "
                f"Team A has {team_a_role_count}, Team B has {team_b_role_count}, "
                f"expected {count} per team."
            )
            return False
    return True


def conflicts_respected(
    team_a: List[models.Player],
    team_b: List[models.Player],
    conflicts: List[Tuple[int, int]]
) -> bool:
    """
    Check if player conflicts are respected, ensuring conflicting players are not on the same team.
    """
    team_a_ids = {player.id for player in team_a}
    team_b_ids = {player.id for player in team_b}

    for conflict in conflicts:
        p1, p2 = conflict
        if {p1, p2}.issubset(team_a_ids):
            logger.debug(f"Conflict detected in Team A between players {p1} and {p2}")
            return False
        if {p1, p2}.issubset(team_b_ids):
            logger.debug(f"Conflict detected in Team B between players {p1} and {p2}")
            return False
    return True


def snipers_balanced(team_a: List[models.Player], team_b: List[models.Player]) -> bool:
    """
    Ensure that snipers are distributed between teams when there are at least two snipers.
    """
    snipers_in_team_a = sum(1 for player in team_a if player.role == 'sniper')
    snipers_in_team_b = sum(1 for player in team_b if player.role == 'sniper')

    # If there are at least two snipers, ensure at least one in each team
    if snipers_in_team_a >= 1 and snipers_in_team_b >= 1:
        return True
    return False
