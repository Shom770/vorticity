import discord
from discord.ext import commands
from discord.ext.commands import Context, BucketType
from pymongo import MongoClient
import pymongo
import asyncio
from bisect import insort
from config import mongodb_link
from random import randint
from typing import Union


class Currency(commands.Cog):
    """Cog for currency system"""

    def __init__(self, bot):
        self.bot = bot
        self.db = MongoClient(mongodb_link)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Used for creating the profile as soon as the user joins"""
        server_col = self.db[str(member.guild.id)]
        new_col = server_col[str(member.id)]
        collections = server_col.collection_names()
        ranks = [server_col[col].find_one()['balance'] for col in collections if col not in ('info', 'store')]
        insort(ranks, 250)
        try:
            rank = ranks.index(250) + 1
        except ValueError:
            rank = 1
        new_col.insert_one({'_id': len(collections) + 1,
                            'balance': 250,
                            'rank': rank,
                            'inventory': [('The Copper Coin',
                                           'Owned by the first three users of this bot in their server.', 2500)]
                            if len(collections) + 1 <= 3 else [("Beginner's Treasure",
                                                                "A starting item.", 100)]})

    def able_to_use_market(self, guild: Context.guild, member: discord.Member) -> Union[discord.Embed, bool]:
        """Helper function to check if the user can buy/sell on the market"""
        server_col = self.db[str(guild.id)]
        store_config = server_col['info'].find_one()['store']
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

        failed = [(name, ele) for name, ele, ele_bool in zip(('rank', 'role', 'balance'),
                                                             [rank, role, bal],
                                                             [rank_bool, role_bool, bal_bool]) if not ele_bool]

        if failed:
            user_col = server_col[str(member.id)].find_one()
            error_embed = discord.Embed(title="You failed one or more of the requirements to be able to use the market",
                                        color=discord.Color.red())
            for element_type, failed_element in failed:
                field = {'name': f"You failed the minimum {element_type} needed."}
                if element_type == 'rank':
                    field['value'] = f"Your rank in the server for this bot's economy is {user_col['rank']}, " \
                                     f"though the minimum rank needed is {failed_element}"
                elif element_type == 'role':
                    field['value'] = f"Your top role is {member.top_role.name}, " \
                                     f"though the minimum role needed is {failed_element}"
                elif element_type == 'balance':
                    field['value'] = f"Your balance is {user_col['balance']}, " \
                                     f"though the minimum balance needed is {failed_element}"
                error_embed.add_field(name=field['name'], value=field['value'], inline=False)
            return error_embed
        else:
            return True

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
                                                             check=lambda reaction, user: ctx.author and str(
                                                                 reaction.emoji) in emojis)
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
    @commands.cooldown(1, 30, BucketType.user)
    async def sell(self, ctx: Context, *, item: str) -> None:
        """Command to sell items."""
        server_col = self.db[str(ctx.guild.id)]
        able_to_sell = self.able_to_use_market(ctx.guild, ctx.author)
        if not isinstance(able_to_sell, bool):
            await ctx.send(embed=able_to_sell)
            return

        item = item.split(',' if ', ' not in item else ', ')
        name, desc, cost = item

        if len(name) >= 225:
            await ctx.send(embed=discord.Empribed(title="The name you are trying to sell your item under is too long.",
                                                  description="Keep the name under 225 characters",
                                                  color=discord.Color.red()))
            return
        elif len(desc) >= 1023:
            await ctx.send(embed=discord.Embed(title="The description of your item is too long",
                                               description="Keep the description of your item under 1024 characters.",
                                               color=discord.Color.red()))
            return

        if name in [ele[0] for ele in server_col[str(ctx.author.id)].find_one()['inventory']]:
            in_inventory = True
        else:
            in_inventory = False

        if not server_col['store'].find_one():
            server_col['store'].insert_one({'_id': 1, 'items': []})
        user_col = server_col[str(ctx.author.id)]

        if in_inventory and name in [ele[0] for ele in user_col.find_one()['inventory']]:
            items = server_col['store'].find_one()['items']
            items.append({'name': name, 'description': desc, 'cost': int(cost), 'owner': ctx.author.id,
                          'transfer': True})
        else:
            items = server_col['store'].find_one()['items']
            items.append({'name': name, 'description': desc, 'cost': int(cost), 'owner': ctx.author.id,
                          'transfer': False})
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
                                 value='``' + self.bot.command_prefix + "config name=[name you want]``",
                                 inline=False)
            help_embed.add_field(name="**Set permissions for who can use this server's market**",
                                 value='``' + self.bot.command_prefix + "config store=(role=[minimum role needed] - "
                                                                        "rank=[minimum server rank by balance needed] -"
                                                                        " balance=[minimum balance needed])``",
                                 inline=False)
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

    @commands.command(aliases=['purchase'])
    @commands.cooldown(1, 30, BucketType.user)
    async def buy(self, ctx: Context, *, item_name: str) -> None:
        """Command to buy items/services on the market"""
        able_to_buy = self.able_to_use_market(ctx.guild, ctx.author)
        if not isinstance(able_to_buy, bool):
            await ctx.send(embed=able_to_buy)
            return

        server_col = self.db[str(ctx.guild.id)]
        market = server_col['store']
        item_to_purchase = sorted(market.find_one()['items'], key=lambda x: x['name'] == item_name)[-1]
        if int(ctx.author.id) == int(item_to_purchase['owner']):
            await ctx.send(embed=discord.Embed(title="You cannot buy an item you own!", color=discord.Color.red()))
            return
        update_market = sorted(market.find_one()['items'], key=lambda x: x['name'] == item_name)[:-1]
        owner_col = server_col[str(item_to_purchase['owner'])].find_one()
        print(owner_col)
        consumer_col = server_col[str(ctx.author.id)].find_one()
        if int(consumer_col['balance']) < item_to_purchase['cost']:
            await ctx.send(embed=discord.Embed(title="You don't have enough money to buy this item",
                                               color=discord.Color.dark_red()))
            return
        owner_col['balance'] += item_to_purchase['cost']
        consumer_col['balance'] -= item_to_purchase['cost']
        if item_to_purchase['transfer']:
            owner_col['inventory'] = sorted(owner_col['inventory'], key=lambda x: x[0] == item_name)[:-1]
        consumer_col['inventory'].append((item_to_purchase['name'],
                                          item_to_purchase['description'],
                                          item_to_purchase['cost']))
        collections = server_col.collection_names()
        (owner_id := server_col[str(item_to_purchase['owner'])]).update_one(owner_id.find_one(),
                                                                            {'$set': owner_col})
        (author_id := server_col[str(ctx.author.id)]).update_one(author_id.find_one(),
                                                                 {'$set': consumer_col})
        new_ranks = [server_col[col].find_one()['balance'] for col in collections if col not in ('info', 'store')]
        owner_col['rank'], consumer_col['rank'] = new_ranks.index(owner_col['balance']), \
                                                  new_ranks.index(consumer_col['balance'])
        success_owner_embed = discord.Embed(title=f"Congratulations! {ctx.author.display_name} has bought your item!",
                                            description=f"This user bought the following item: {item_name}",
                                            color=discord.Color.green())
        success_consumer_embed = discord.Embed(title=f"Success, {ctx.author.display_name}!",
                                               description=f"You have successfully bought the item: {item_name}",
                                               color=discord.Color.green())
        try:
            await self.bot.get_user(item_to_purchase['owner']).send(embed=success_owner_embed)
        except discord.Forbidden:
            print("forbidden")

        try:
            await self.bot.get_user(ctx.author.id).send(embed=success_consumer_embed)
        except discord.Forbidden:
            print("forbidden")

        market.update_one(market.find_one(), {'$set': {'_id': 1, 'items': update_market}})
        owner_id.update_one(owner_id.find_one(), {'$set': owner_col})
        author_id.update_one(author_id.find_one(), {'$set': consumer_col})

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
            ranks = [server_col[col].find_one()['balance'] for col in collections if col not in ('info', 'store')]
            insort(ranks, 250)
            try:
                rank = ranks.index(250) + 1
            except ValueError:
                rank = 1
            new_col.insert_one({'_id': len(collections) + 1,
                                'balance': 250,
                                'rank': rank,
                                'inventory': [('The Copper Coin',
                                               'Owned by the first three users of this bot in their server.', 2500)]
                                if len(collections) + 1 <= 3 else []})

        info = server_col[str(member)].find_one()
        wallet_embed = discord.Embed(title=f"{name}'s wallet", color=discord.Color.green())
        wallet_embed.add_field(name="Balance", value=f"{info['balance']} {info_col.find_one()['currency_name']}",
                               inline=False)
        wallet_embed.add_field(name="Server Rank", value=info['rank'], inline=False)

        await ctx.send(embed=wallet_embed)

    @commands.command(aliases=["gamble", "gam", "bet"])
    @commands.cooldown(1, 15, BucketType.user)
    async def roll_the_dice(self, ctx: Context, money: str) -> None:
        if money == 'all':
            money = self.db[str(ctx.guild.id)][str(ctx.author.id)].find_one()['balance']
        else:
            money = int(money.replace(',', ''))
        """One way to earn money by betting."""
        server_col = self.db[str(ctx.guild.id)]
        user_col = server_col[str(ctx.author.id)]
        user_dict = user_col.find_one()
        if money > user_dict['balance']:
            await ctx.send(embed=discord.Embed(title="You don't have enough money.",
                                               color=discord.Color.red()))
            return
        bot_value, user_value = randint(1, 101), randint(1, 101)
        if user_value > bot_value:
            multiplier = (user_value * 2 - bot_value) / 100
            money = int(money * multiplier)
            res_embed = discord.Embed(title="You won!", color=discord.Color.green())
            res_embed.set_footer(text=f"Multiplier: {multiplier}")
            user_dict['balance'] += money
        else:
            res_embed = discord.Embed(title="You lost.", color=discord.Color.red())
            user_dict['balance'] -= money

        user_col.update_one(user_col.find_one(), {'$set': user_dict})
        collections = server_col.collection_names()
        new_ranks = [server_col[col].find_one()['balance'] for col in collections if col not in ('info', 'store')]
        rank = new_ranks.index(user_dict['balance']) + 1
        user_dict['rank'] = rank
        user_col.update_one(user_col.find_one(), {'$set': user_dict})

        res_embed.add_field(name=f"{ctx.author.display_name} rolled a",
                            value=str(user_value), inline=False)
        res_embed.add_field(name=f"{self.bot.user.name} rolled a",
                            value=str(bot_value), inline=False)
        await ctx.send(embed=res_embed)

    @commands.command(aliases=["give", "don"])
    @commands.cooldown(1, 30, BucketType.user)
    async def donate(self, ctx: Context, member: discord.Member, money: str, *, message: str = '') -> None:
        """Give money to another member"""
        server_col = self.db[str(ctx.guild.id)]
        user_col = server_col[str(ctx.author.id)]
        member_to_give_col = server_col[str(member.id)]
        if money == 'all':
            money = self.db[str(ctx.guild.id)][str(ctx.author.id)].find_one()['balance']
        else:
            money = int(money.replace(',', ''))
            if money > user_col.find_one()['balance']:
                await ctx.send(embed=discord.Embed(title=f"You don't have enough money to donate {money} "
                                                         f"{server_col['info'].find_one()['currency_name']}."),
                               color=discord.Color.red())
                return
            elif money < 0:
                await ctx.send(embed=discord.Embed(title=f"You can't donate negative money.",
                                                   description="Nice try.",
                                                   color=discord.Color.red()))
                return
            user_dict = user_col.find_one()
            member_to_give_dict = member_to_give_col.find_one()
            user_dict['balance'] -= money
            member_to_give_dict['balance'] += money
            user_col.update_one(user_col.find_one(), {'$set': user_dict})
            member_to_give_col.update_one(member_to_give_col.find_one(),
                                          {'$set': member_to_give_dict})
            collections = server_col.collection_names()
            new_ranks = [server_col[col].find_one()['balance'] for col in collections if col not in ('info', 'store')]
            user_dict['rank'] = new_ranks.index(user_dict['balance']) + 1
            member_to_give_dict['rank'] = new_ranks.index(member_to_give_dict['balance']) + 1
            user_col.update_one(user_col.find_one(), {'$set': user_dict})
            member_to_give_col.update_one(member_to_give_col.find_one(),
                                          {'$set': member_to_give_dict})
            try:
                await self.bot.get_user(member.id).send(embed=discord.Embed(
                    title=f"{ctx.author.display_name} has donated ${money} to you.",
                    description=f"They left a message: {message}",
                    color=discord.Color.green()))
            except discord.Forbidden:
                pass
            await ctx.send(embed=discord.Embed(
                title=f"Success!", description=f"You have donated {money} "
                                               f"{server_col['info'].find_one()['currency_name']} to "
                                               f"@{member.display_name}#{member.discriminator}",
                color=discord.Color.green()
            ))


def setup(bot):
    bot.add_cog(Currency(bot))
