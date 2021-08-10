from discord.ext import commands
import discord
from discord.ext.commands.context import Context


class MainCommands(commands.Cog):
    """Cog for all the main commands."""
    def __init__(self, bot):
        self.bot = bot
        

def setup(bot):
    bot.add_cog(MainCommands(bot))
