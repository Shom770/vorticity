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

    @commands.command(aliases=['configure'])
    @commands.has_permissions(administrator=True)
    async def config(self, ctx: Context, *, params: str = '') -> None:
        """Configure the currency system in the server"""
        if not params:
            help_embed = discord.Embed(title=f"Configure {ctx.guild.name}'s currency system",
                                       description="An embed of all the settings you can configure for this "
                                                   "currency system.", color=discord.Color.orange())
            help_embed.set_thumbnail(url=ctx.guild.icon_url)
            help_embed.add_field(name="**Add a name to the currency**",
                                 value='``' + self.bot.command_prefix + "config name=[name you want]``")
            help_embed.add_field(name="**Set permissions for who can use this server's market**",
                                 value='``' + self.bot.command_prefix + "config store=(role=[minimum role needed] - "
                                                                        "rank=[minimum server rank by balance needed] -"
                                                                        " balance=[minimum balance needed])``")
            await ctx.send(embed=help_embed)
        else:
            info_col = self.db[str(ctx.guild.id)]['info']
            config_info = info_col.find_one()
            if len(info_col.find_one().keys()) <= 1:
                info_col.insert_one({'currency_name': 'dollars', 'store': {'role': None, 'rank': None, 'balance': 250}})
            currency_name, store = config_info['currency_name'], config_info['store']
            params = dict([[ele for ele in param.partition('=') if ele != '=']
                          for param in params.split(',' if ', ' not in params else ', ')])
            currency_name = params.get('name', currency_name)
            store = params.get('store', store)
            if '=' in store:
                store = store.replace('(', '').replace(')', '').split('-' if ' - ' not in store else ' - ')
                store = dict([element.split('=') for element in store])
                for key in ('role', 'rank', 'balance'):
                    if key not in store.keys():
                        store[key] = None
            info_col.update_one(info_col.find_one(), {'$set': {'currency_name': currency_name,
                                                               'store': store}})
            await ctx.send(embed=discord.Embed(title="Success!", color=discord.Color.green()))

    @commands.command(aliases=["balance", "bal", "wal"])
    @commands.cooldown(1, 10, BucketType.user)
    async def wallet(self, ctx: Context, member: discord.Member = None) -> None:
        """Command to fetch balance local to the server."""
        server_col = self.db[str(ctx.guild.id)]
        info_col = server_col['info']
        if len(info_col.find_one().keys()) <= 1:
            info_col.insert_one({'currency_name': 'dollars', 'store': {'role': None, 'rank': None, 'balance': 250}})
        if member:
            name = member.display_name
            member = member.id
        else:
            member = ctx.author.id
            name = ctx.author.display_name

        if str(member) not in (collections := server_col.collection_names()):
            new_col = server_col[str(member)]
            ranks = [server_col[col].find_one()['balance'] for col in collections if col != 'info']
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
        wallet_embed.add_field(name="Balance", value=f"{info['balance']} {info_col.find_one()['currency_name']}",
                               inline=False)
        wallet_embed.add_field(name="Server Rank", value=info['rank'], inline=False)

        await ctx.send(embed=wallet_embed)


def setup(bot):
    bot.add_cog(Currency(bot))
