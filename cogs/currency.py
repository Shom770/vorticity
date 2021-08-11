import discord
from discord.ext import commands
from discord.ext.commands import Context, BucketType
from pymongo import MongoClient
import pymongo
from bisect import insort
from config import mongodb_link


class Currency(commands.Cog):
    """Cog for currency system"""
    def __init__(self, bot):
        self.bot = bot
        self.db = MongoClient(mongodb_link)

    @commands.command()
    async def config(self, ctx: Context) -> None:
        """Configure the currency system in the server"""

    @commands.command(aliases=["balance", "bal", "wal"])
    @commands.cooldown(1, 10, BucketType.user)
    async def wallet(self, ctx: Context, member: discord.Member = None) -> None:
        """Command to fetch balance local to the server."""
        server_col = self.db[str(ctx.guild.id)]
        if member:
            name = member.display_name
            member = member.id
        else:
            member = ctx.author.id
            name = ctx.author.display_name

        if str(member) not in (collections := server_col.collection_names()):
            new_col = server_col[str(member)]
            ranks = [server_col[col].find_one()['balance'] for col in collections]
            insort(ranks, 250)
            try:
                rank = ranks.index(250) + 1
            except ValueError:
                rank = 1
            new_col.insert_one({'_id': len(collections) + 1,
                                'balance': 250,
                                'rank': rank})

        info = server_col[str(member)].find_one()
        wallet_embed = discord.Embed(title=f"{name}'s wallet", color=discord.Color.green())
        wallet_embed.add_field(name="Balance", value=f"{info['balance']} ⛂", inline=False)
        wallet_embed.add_field(name="Server Rank", value=info['rank'], inline=False)

        await ctx.send(embed=wallet_embed)


def setup(bot):
    bot.add_cog(Currency(bot))
