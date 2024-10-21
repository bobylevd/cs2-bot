import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship

from database.database import Base


class Player(Base):
    __tablename__ = 'players'

    id = Column(Integer, primary_key=True, index=True)
    steamid = Column(String, unique=True, index=True)
    username = Column(String)
    mmr = Column(Integer, default=1000)
    role = Column(String)
    discord_id = Column(String, unique=True, index=True)
    discord_name = Column(String)
    core_member = Column(Boolean, default=False)
    matches = relationship('PlayerMatchStats', back_populates='player')


class Match(Base):
    __tablename__ = 'matches'

    id = Column(Integer, primary_key=True, index=True)
    date_time = Column(DateTime, default=datetime.datetime.utcnow)
    map_name = Column(String)
    team1_name = Column(String)
    team2_name = Column(String)
    team1_score = Column(Integer)
    team2_score = Column(Integer)
    winner = Column(String)
    team_results = Column(String, unique=True)
    players = relationship('PlayerMatchStats', back_populates='match')


class PlayerMatchStats(Base):
    __tablename__ = 'player_match_stats'

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey('matches.id'))
    player_id = Column(Integer, ForeignKey('players.id'))
    team = Column(String)
    kills_total = Column(Integer)
    damage_total = Column(Integer)
    deaths_total = Column(Integer)
    assists_total = Column(Integer)
    alive_time_total = Column(Integer)
    headshot_kills_total = Column(Integer)
    utility_damage_total = Column(Integer)
    enemies_flashed_total = Column(Integer)
    ace_rounds_total = Column(Integer)
    four_k_rounds_total = Column(Integer)
    three_k_rounds_total = Column(Integer)
    score = Column(Integer)
    mvps = Column(Integer)
    rounds_won = Column(Integer)
    rounds_lost = Column(Integer)
    player = relationship('Player', back_populates='matches')
    match = relationship('Match', back_populates='players')
