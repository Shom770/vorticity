import discord
from discord.ext import commands
from discord.ext.commands import Context


class Currency(commands.Cog):
    """Cog for currency system"""
    def __init__(self, bot):
        self.bot = bot


def setup(bot):
    bot.add_cog(Currency(bot))
