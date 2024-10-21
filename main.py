import os

from bot.commands import bot
import logging

from database.database import SessionLocal, Base, engine
from services.mmr_algorithm import recalculate_all_mmr

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


TOKEN = os.getenv('DISCORD_BOT_TOKEN')


if __name__ == '__main__':
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    recalculate_all_mmr(db)
    if not TOKEN:
        logger.error("Discord bot token not found. Please set the DISCORD_BOT_TOKEN environment variable.")
    else:
        bot.run(TOKEN)
