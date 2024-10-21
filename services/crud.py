from typing import List, Type

from sqlalchemy.orm import Session, Query

from services.models import Match, PlayerMatchStats, Player


def get_player(db: Session, player_id: int) -> Type[Player]:
    return db.query(Player).filter(Player.id == player_id).first()


def get_player_by_steamid(db: Session, steamid: str) -> Type[Player]:
    return db.query(Player).filter(Player.steamid == steamid).first()


def create_player(db: Session, player: Player) -> Player:
    db_player = Player(
        steamid=player.steamid,
        username=player.username,
        mmr=player.mmr,
        role=player.role,
        discord_id=player.discord_id,
        discord_name=player.discord_name
    )
    db.add(db_player)
    db.commit()
    db.refresh(db_player)
    return db_player


def update_player_discord_info(db: Session, player_id: int, discord_id: str, discord_name: str) -> Type[Player]:
    db_player = get_player(db, player_id)
    if db_player:
        db_player.username = discord_name
        db_player.discord_id = discord_id
        db_player.discord_name = discord_name
        db.commit()
        db.refresh(db_player)
    return db_player


def update_player_mmr(db: Session, player_id: int, mmr: float) -> Type[Player]:
    db_player = get_player(db, player_id)
    if db_player:
        db_player.mmr = mmr
        db.commit()
        db.refresh(db_player)
    return db_player


def get_players(db: Session, skip: int = 0, limit: int = 100) -> list[Type[Player]]:
    return db.query(Player).offset(skip).limit(limit).all()


def create_match(db: Session, match: Match) -> Match:
    """
    Create a new match.
    """
    db_match = Match(
        date_time=match.date_time,
        map_name=match.map_name,
        team1_name=match.team1_name,
        team2_name=match.team2_name,
        team1_score=match.team1_score,
        team2_score=match.team2_score,
        winner=match.winner
    )
    db.add(db_match)
    db.commit()
    db.refresh(db_match)
    return db_match


def create_player_match_stats(db: Session, stats: PlayerMatchStats) -> PlayerMatchStats:
    db.add(stats)
    db.commit()
    db.refresh(stats)
    return stats


def get_player_stats(db: Session, player_id: int) -> list[Type[PlayerMatchStats]]:
    return db.query(PlayerMatchStats).filter(PlayerMatchStats.player_id == player_id).all()


def get_match_stats(db: Session, match_id: int) -> list[Type[PlayerMatchStats]]:
    return db.query(PlayerMatchStats).filter(PlayerMatchStats.match_id == match_id).all()


def get_match(db: Session, match_id: int) -> Type[Match]:
    """
    Retrieve a match by ID.
    """
    return db.query(Match).filter(Match.id == match_id).first()


def get_all_matches(db: Session) -> list[Type[Match]]:
    """
    Retrieve all matches.
    """
    return db.query(Match).all()


def get_player_by_username(db: Session, username: str) -> Type[Player]:
    return db.query(Player).filter(Player.username == username).first()


def get_player_by_discord_id(db: Session, discord_id) -> Type[Player]:
    return db.query(Player).filter(Player.discord_id == discord_id).first()
