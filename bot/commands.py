import logging

import discord
from discord import TextStyle
from discord.ext import commands

from bot.modals import RegistrationModal
from services import crud
from services.dependencies import get_db
from services.models import Player
from services.team_balancer import balance_teams

logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

team_assignments = {}

@bot.command(name='mmr', help='Displays the MMR and stats for a player.')
async def mmr(ctx, *, username: str):
    """
    Fetch and display the MMR and stats for a player.
    """
    with get_db() as db:
        try:
            player = crud.get_player_by_username(db, username=username)
            if not player:
                await ctx.send(f"Player '{username}' not found.")
                return

            mmr = player.mmr
            role = player.role or 'N/A'
            await ctx.send(f"Player **{player.username}**:\nMMR: **{mmr}**\nRole: **{role}**")
        except Exception as e:
            await ctx.send(f"An error occurred while fetching MMR for '{username}'.")
            logger.error(f"Error in !mmr command: {e}")


@bot.command(name='stats', help='Shows detailed stats for a player.')
async def stats(ctx, user: discord.Member = None):
    """
    Fetch and display detailed stats for a player.
    If no user is provided, it will show stats for the command caller.
    """
    with get_db() as db:
        try:
            if user is None:
                user = ctx.author

            discord_id = str(user.id)
            player = crud.get_player_by_discord_id(db, discord_id=discord_id)
            if not player:
                await ctx.send(f"❌ Player '{user.display_name}' is not registered.")
                return

            # Fetch the player's stats
            player_id = player.id
            stats = crud.get_player_stats(db, player_id=player_id)
            matches_played = len(stats)

            total_kills = sum(match.kills_total for match in stats)
            total_deaths = sum(match.deaths_total for match in stats)
            total_assists = sum(match.assists_total for match in stats)
            kd_ratio = total_kills / total_deaths if total_deaths > 0 else total_kills

            stats_embed = discord.Embed(
                title=f"Stats for {player.username}",
                color=discord.Color.blue()
            )
            stats_embed.add_field(name="Matches Played", value=matches_played, inline=False)
            stats_embed.add_field(name="Total Kills", value=total_kills, inline=True)
            stats_embed.add_field(name="Total Deaths", value=total_deaths, inline=True)
            stats_embed.add_field(name="Total Assists", value=total_assists, inline=True)
            stats_embed.add_field(name="K/D Ratio", value=f"{kd_ratio:.2f}", inline=False)

            await ctx.send(embed=stats_embed)
        except Exception as e:
            await ctx.send(f"❌ An error occurred while fetching stats for '{user.display_name}'.")
            logger.error(f"Error in !stats command: {e}", exc_info=True)


@bot.tree.command(name='balance', description='Triggers team balancing and posts team assignments.')
async def balance(interaction: discord.Interaction):
    with get_db() as db:
        try:

            if interaction.user.voice.channel:
                voice_channel = interaction.user.voice.channel
            else:
                await interaction.response.send_message("You are not connected to a voice channel.")
                return
            voice_members = voice_channel.members

            # player_ids = [
            #     "170206898426085378",
            #     "490931120083435561",
            #     "91586668531814400",
            #     "474880896927924234",
            #     "174231477188296704",
            #     "359428429256589313",
            #     "126092325947441152",
            #     "245963484783837184",
            #     "149587719725514752",
            #     "380370600746680320",
            #     "416909299915161600",
            #     "414137584235708437",
            #     "273161188899160064",
            #     "185708633575784449",
            #     "731839710347132968",
            #     "692045889522499615",
            #     "450262973139910656",
            #     "349568977376378881",
            #     "277547882482106368",
            #
            # ]
            player_ids = []
            for member in voice_members:
                if member.id == "108220450194092032":
                    continue
                player = crud.get_player_by_discord_id(db, discord_id=str(member.id))
                if player:
                    player_ids.append(player.discord_id)
                else:
                    player_create = Player(
                        username=str(member.display_name),
                        discord_id=str(member.id),
                        discord_name=str(member.display_name),
                        mmr=1000
                    )
                    crud.create_player(db, player_create)
                    await interaction.response.send_message(f"Member '<@{member.id}>' is not registered, please use !register")
                    return

            team_a, team_b, mmr = balance_teams(player_ids, db)

            # Store the team assignments
            guild_id = interaction.guild.id
            team_assignments[guild_id] = {'team_a': team_a, 'team_b': team_b}


            team_a = [f"<@{player}>" for player in team_a]
            team_b = [f"<@{player}>" for player in team_b]

            team_a_str = '\n'.join([f"- {player}" for player in team_a])
            team_b_str = '\n'.join([f"- {player}" for player in team_b])
            mmr_diff = mmr

            teams_embed = discord.Embed(
                title="Teams",
                description=(
                    f"**Team 🅰 :**\n"
                    f" {team_a_str}\n"
                    f"**Team 🅱️ :**\n"
                    f"{team_b_str}\n"
                    f"**MMR difference:** {mmr_diff}\n"
                ),
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=teams_embed)
        except Exception as e:
            await interaction.response.send_message("An error occurred while balancing teams.")
            logger.error(f"Error in !balance command: {e}")


@bot.tree.command(name='register', description='Register yourself by linking your SteamID.')
async def register(interaction: discord.Interaction):
    """
    Register a user by presenting a modal to enter their SteamID64.
    """
    with get_db() as db:
        try:
            existing_player = crud.get_player_by_discord_id(db, discord_id=str(interaction.user.id))
            if existing_player:
                await interaction.response.send_message(
                    f"✅ You are already registered as **'{existing_player.username}'**. Use `/update` to change your SteamID.",
                    ephemeral=True
                )
                return
        except Exception as e:
            await interaction.response.send_message(
                "❌ An error occurred while checking your registration status. Please try again later.",
                ephemeral=True
            )
            logger.error(f"Error in /register command: {e}")
            return

        # Send the registration modal
        modal = RegistrationModal()
        await interaction.response.send_modal(modal)


@bot.event
async def on_command_error(ctx, error):
    """
    Global error handler.
    """
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Missing argument. Please check the command usage.")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("Unknown command. Use `!help` to see available commands.")
    else:
        await ctx.send("An error occurred while processing the command.")
        logger.error(f"Unhandled error: {error}")





# class UpdateModal(Modal):
#     discord.ui.View(
#
#     )
#     steamid_input = discord.ui.TextInput(
#         label="SteamID64",
#         placeholder="Enter your 17-digit SteamID64",
#         style=TextStyle.short,
#         max_length=17,
#         min_length=17,
#         required=True
#     )
#
#     async def callback(self, interaction: discord.Interaction):
#         confirmation = self.children[0].value.strip().upper()
#         user = interaction.user
#
#         if confirmation != "CONFIRM":
#             await interaction.response.send_message(
#                 "❌ Unregistration canceled. Please type `CONFIRM` exactly to proceed.",
#                 ephemeral=True
#             )
#             return


# @bot.tree.command(name='update', description='Unregister yourself from the system.')
# async def update(ctx):
#     """
#     Unregister a user by presenting a confirmation modal.
#     """
#     # Check if the user is registered
#     with get_db() as db:
#         try:
#             existing_player = crud.get_player_by_discord_id(db, discord_id=str(ctx.author.id))
#             if not existing_player:
#                 await ctx.send("❌ You are not registered.")
#                 return
#         except Exception as e:
#             await ctx.send("❌ An error occurred while checking your registration status. Please try again later.")
#             logger.error(f"Error in !unregister command: {e}")
#             return
#
#         # Send the unregister confirmation modal
#         modal = UpdateModal()
#         await ctx.send_modal(modal)
#


@bot.tree.command(name='start', description='Moves players into team voice channels.')
async def start(interaction: discord.Interaction):
    try:
        guild = interaction.guild
        guild_id = guild.id

        # Check if team assignments exist
        if guild_id not in team_assignments:
            await interaction.response.send_message("Teams have not been balanced yet. Use `/balance` first.")
            return

        teams = team_assignments[guild_id]
        team_a_ids = teams['team_a']
        team_b_ids = teams['team_b']

        # Get or create voice channels for Team A and Team B
        team_a_channel = discord.utils.get(guild.voice_channels, name="team-1")
        team_b_channel = discord.utils.get(guild.voice_channels, name="team-2")

        # Create channels if they don't exist
        if not team_a_channel:
            team_a_channel = await guild.create_voice_channel("team-1")
        if not team_b_channel:
            team_b_channel = await guild.create_voice_channel("team-2")

        # Move members to their respective channels
        for member_id in team_a_ids:
            member = guild.get_member(int(member_id))
            if member and member.voice:
                await member.move_to(team_a_channel)

        for member_id in team_b_ids:
            member = guild.get_member(int(member_id))
            if member and member.voice:
                await member.move_to(team_b_channel)

        await interaction.response.send_message("Players have been moved to their team voice channels.")
    except Exception as e:
        await interaction.response.send_message("An error occurred while moving players.")
        logger.error(f"Error in /start command: {e}")


@bot.event
async def on_ready():
    # guild = discord.Object(id=819717610509041665) # dev
    guild = discord.Object(id=1274066274619490345)
    await bot.tree.sync(guild=guild)
    print(f"Logged in as {bot.user}")