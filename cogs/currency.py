import discord
from discord.ext import commands
from discord.ext.commands import Context, BucketType
from pymongo import MongoClient
import pymongo
from config import mongodb_link

class Currency(commands.Cog):
    """Cog for currency system"""
    def __init__(self, bot):
        self.bot = bot
        self.db = MongoClient(mongodb_link)['Data']


def setup(bot):
    bot.add_cog(Currency(bot))
