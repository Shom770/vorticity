import discord
from discord.ext import commands
from discord.ext.commands import Context, BucketType
from pymongo import MongoClient
import pymongo
import asyncio
from bisect import insort
from config import mongodb_link


class Currency(commands.Cog):
    """Cog for currency system"""

    def __init__(self, bot):
        self.bot = bot
        self.db = MongoClient(mongodb_link)

    def able_to_use_market(self, guild: Context.guild, member: discord.Member):
        """Helper function to check if the user can buy/sell on the market"""
        store_config = self.db[str(guild.id)]['info'].find_one()['store']
        user_col = self.db[str(guild.id)][str(member.id)].find_one()
        rank, role, bal = store_config['rank'], store_config['role'], store_config['balance']
        if role != 'None' and role:
            for guild_role in guild.roles:
                if guild_role.name == role:
                    role_bool = member.top_role >= guild_role
                    break
        else:
            role_bool = True

        if rank != 'None' and rank:
            rank_bool = int(user_col['rank']) >= int(rank)
        else:
            rank_bool = True

        if bal != 'None' and bal:
            bal_bool = int(user_col['balance']) >= int(bal)
        else:
            bal_bool = True

        return rank_bool and role_bool and bal_bool, \
               [(name, ele) for name, ele, ele_bool in zip(('rank', 'role', 'balance'),
                                                           [rank, role, bal],
                                                           [rank_bool, role_bool, bal_bool]) if not ele_bool]

    @commands.command(aliases=["mark", "store"])
    async def market(self, ctx: Context, *, sort_key: str = None):
        """Command to get the local server market."""
        server_col = self.db[str(ctx.guild.id)]
        emojis = ['⏮', '⏪', '⏩', '⏭']
        store_col = server_col['store']
        if len(store_col.find_one().keys()) <= 1:
            store_col.insert_one({'_id': 1, 'items': []})
        all_items = [(ele['name'], ele['description'], ele['cost']) for ele in store_col.find_one()['items']]
        market_embed = discord.Embed(title=f"Market for {ctx.guild.name}", color=discord.Color.green())
        market_embed.set_thumbnail(url=ctx.guild.icon_url)
        sort_keys = {'low cost': sorted(all_items, key=lambda x: x[-1]), 'high cost': sorted(all_items,
                                                                                             key=lambda x: x[-1],
                                                                                             reverse=True),
                     'a-z': sorted(all_items, key=lambda x: x[0]), None: all_items}
        all_items = sort_keys[sort_key]
        market_embeds = []
        ct_embed = 0
        for name, desc, cost in all_items:
            market_embed.add_field(name=f"**{name}** | ${cost}",
                                   value=desc, inline=False)
            if ct_embed >= 10:
                market_embeds.append(market_embed)
                market_embed = discord.Embed(title=f"Market for {ctx.guild.name}", color=discord.Color.green())
                market_embed.set_thumbnail(url=ctx.guild.icon_url)
                ct_embed = 0
            ct_embed += 1
        if ct_embed < 10:
            market_embeds.append(market_embed)
        msg = await ctx.send(embed=market_embeds[0])
        if len(market_embeds) > 1:
            for emoji in emojis:
                await msg.add_reaction(emoji=emoji)
            count = 0
            page = 0
            while count <= len(market_embeds):
                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=120.0,
                                           check=lambda reaction, user: ctx.author and str(reaction.emoji) in emojis)
                    if user.name + '#' + user.discriminator != 'Vorticity#5053':
                        page_cases = {'⏮': 0, '⏪': -1, '⏩': 1, '⏭': len(market_embeds) - 1}
                        if (page_num := page_cases[reaction.emoji]) in (0, len(market_embed) - 1):
                            page = page_num
                        else:
                            page += page_num
                        await msg.edit(embed=market_embeds[page])
                        count += 1
                except (asyncio.TimeoutError, IndexError):
                    break

    @commands.command(aliases=["market_sell", "on_market"])
    async def sell(self, ctx: Context, *, item: str):
        """Command to sell items."""
        server_col = self.db[str(ctx.guild.id)]
        able_to_buy, failed = self.able_to_use_market(ctx.guild, ctx.author)
        if not able_to_buy:
            user_col = server_col[str(ctx.author.id)].find_one()
            error_embed = discord.Embed(title="You failed one or more of the requirements to be able to use the market",
                                        color=discord.Color.red())
            for element_type, failed_element in failed:
                field = {'name': f"You failed the minimum {element_type} needed."}
                if element_type == 'rank':
                    field['value'] = f"Your rank in the server for this bot's economy is {user_col['rank']}, " \
                                     f"though the minimum rank needed is {failed_element}"
                elif element_type == 'role':
                    field['value'] = f"Your top role is {ctx.author.top_role}, " \
                                     f"though the minimum role needed is {failed_element}"
                elif element_type == 'balance':
                    field['value'] = f"Your balance is {user_col['balance']}, " \
                                     f"though the minimum balance needed is {failed_element}"
                error_embed.add_field(name=field['name'], value=field['value'], inline=False)
            await ctx.send(embed=error_embed)
            return

        item = item.split(',' if ', ' not in item else ', ')
        if item[-1] in ('true', 'false'):
            name, desc, cost, in_inventory = item
        else:
            name, desc, cost = item
            in_inventory = 'false'

        if len(name) >= 225:
            await ctx.send(embed=discord.Embed(title="The name you are trying to sell your item under is too long.",
                                               description="Keep the name under 225 characters",
                                               color=discord.Color.red()))
            return
        elif len(desc) >= 1023:
            await ctx.send(embed=discord.Embed(title="The description of your item is too long",
                                               description="Keep the description of your item under 1024 characters.",
                                               color=discord.Color.red()))
            return

        in_inventory = {'true': 1, 'false': 0}[in_inventory]
        if not server_col['store'].find_one():
            server_col['store'].insert_one({'_id': 1, 'items': []})
        user_col = server_col[str(ctx.author.id)]
        if in_inventory and name in [ele[0] for ele in user_col['inventory']]:
            items = server_col['store'].find_one()['items']
            items.append({'name': name, 'description': desc, 'cost': int(cost), 'owner': ctx.author.id})
        else:
            items = server_col['store'].find_one()['items']
            items.append({'name': name, 'description': desc, 'cost': int(cost), 'owner': None})
        server_col['store'].update_one(server_col['store'].find_one(),
                                       {'$set': {'_id': 1, 'items': items}})
        try:
            await self.bot.get_user(ctx.author.id).send(embed=discord.Embed(title='Success!',
                                                                            color=discord.Color.green()))
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(title=f'Success, {ctx.author.display_name}!',
                                               color=discord.Color.green()))

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
                                'rank': rank,
                                'inventory': ('The Copper Coin',
                                              'Owned by the first three users of this bot in their server.', 2500)
                                if len(collections) + 1 <= 3 else ()})

        info = server_col[str(member)].find_one()
        wallet_embed = discord.Embed(title=f"{name}'s wallet", color=discord.Color.green())
        wallet_embed.add_field(name="Balance", value=f"{info['balance']} {info_col.find_one()['currency_name']}",
                               inline=False)
        wallet_embed.add_field(name="Server Rank", value=info['rank'], inline=False)

        await ctx.send(embed=wallet_embed)


def setup(bot):
    bot.add_cog(Currency(bot))
