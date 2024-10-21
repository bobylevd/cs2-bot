import logging

import discord
from discord import TextStyle

from services import crud
from services.dependencies import get_db
from services.models import Player

logger = logging.getLogger(__name__)


class RegistrationModal(discord.ui.Modal, title="Register Your SteamID"):
    steamid_input = discord.ui.TextInput(
        label="SteamID64",
        placeholder="Enter your 17-digit SteamID64",
        style=TextStyle.short,
        max_length=17,
        min_length=17,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        steamid = self.steamid_input.value.strip()
        user = interaction.user

        with get_db() as db:
            try:
                # Validate SteamID format
                if not steamid.isdigit() or len(steamid) != 17:
                    await interaction.response.send_message(
                        "❌ Invalid SteamID format. Please enter a valid **17-digit SteamID64**.",
                        ephemeral=True
                    )
                    return

                # Check if the SteamID is already linked to another Discord account
                existing_player = crud.get_player_by_steamid(db, steamid=steamid)
                if existing_player:
                    if existing_player.discord_id and existing_player.discord_id != str(user.id):
                        await interaction.response.send_message(
                            "❌ This SteamID is already linked to another Discord account.",
                            ephemeral=True
                        )
                        return
                    else:
                        # Update Discord information if SteamID exists but is not linked
                        updated_player = crud.update_player_discord_info(
                            db,
                            player_id=existing_player.id,
                            discord_id=str(user.id),
                            discord_name=user.display_name
                        )
                        await interaction.response.send_message(
                            f"✅ Successfully linked your Discord account to existing player **'{updated_player.username}'**.",
                            ephemeral=True
                        )
                        logger.info(f"Linked Discord ID {user.id} to existing player '{updated_player.username}'.")
                        return

                # Create a new player entry
                player_data = Player(
                    steamid=steamid,
                    username=user.display_name,
                    mmr=1000,
                    role=None,
                    discord_id=str(user.id),
                    discord_name=user.display_name
                )
                new_player = crud.create_player(db=db, player=player_data)

                # Send a confirmation message
                confirmation_embed = discord.Embed(
                    title="Registration Successful",
                    description=(
                        f"✅ **Username:** {new_player.username}\n"
                        f"✅ **SteamID:** {new_player.steamid}\n"
                        f"✅ **MMR:** {new_player.mmr}\n"
                    ),
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=confirmation_embed, ephemeral=True)
                logger.info(f"Registered new player '{new_player.username}' with SteamID {steamid} and Discord ID {user.id}.")

            except Exception as e:
                await interaction.response.send_message(
                    "❌ An error occurred during registration. Please try again later.",
                    ephemeral=True
                )
                logger.error(f"Error in RegistrationModal on_submit: {e}")