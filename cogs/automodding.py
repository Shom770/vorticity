from discord.ext import commands
import discord
from discord.ext.tasks import loop
from discord.ext.commands import BucketType
from discord.ext.commands.context import Context
from discord.utils import get
from datetime import datetime, timedelta
from pymongo import MongoClient
import pymongo
from itertools import zip_longest
from config import mongodb_link


class Automodding(commands.Cog):
    """Cog for moderating system"""

    def __init__(self, bot):
        self.bot = bot
        self.db = MongoClient(mongodb_link)

    @commands.Cog.listener()
    async def on_ready(self):
        self.iterate_through_jobs.start()

    @staticmethod
    def calculate_time(time: str = "0y, 0mo, 0d, 0h, 0m, 0s") -> datetime:
        """Calculate seconds from time string"""
        time = time.split(',' if ', ' not in time else ', ')
        mapping = ["y", "mo", "d", "h", "m", "s"]
        idx = 0
        for map, item in zip_longest(mapping, time):
            if item is None or map not in item:
                time.insert(idx, 0)
            else:
                time[idx] = int(time[idx]
                                .replace('y', '')
                                .replace('mo', '')
                                .replace('d', '')
                                .replace('h', '')
                                .replace('m', '')
                                .replace('s', ''))
            idx += 1

        return datetime.now() + timedelta(days=(365 * time[0] + 30 * time[1] + time[2]),
                                          hours=time[3], minutes=time[4], seconds=time[5])

    @loop(seconds=5)
    async def iterate_through_jobs(self):
        for server in self.db.database_names():
            if len(server) >= 18:
                jobs_col = self.db[server]['jobs']
                jobs_dict = jobs_col.find_one()
                for key, value in jobs_col.find_one().items():
                    if key != '_id':
                        if isinstance(value, dict):
                            value = list(value.values())[0]
                        if isinstance(value, int):
                            time = datetime.fromisoformat(key)
                            if datetime.now() > time:
                                server_guild = self.bot.get_guild(int(server))
                                muted_role = get(server_guild.roles, name="Muted")
                                user = server_guild.get_member(value)
                                await user.remove_roles(muted_role)
                                try:
                                    await user.send(embed=discord.Embed(title="You have been unmuted.",
                                                                        color=discord.Color.green()))
                                except discord.Forbidden:
                                    pass
                                del jobs_dict[key]
                jobs_col.replace_one(jobs_col.find_one(), jobs_dict)
        
    @commands.command()
    @commands.has_permissions(kick_members=True)
    @commands.cooldown(1, 30, BucketType.user)
    async def kick(self, ctx: Context, member: discord.Member = None, *,
                   reason: str = "No reason specified") -> None:
        """Kick a member"""
        if not member:
            await ctx.send(embed=discord.Embed(title="You forgot to specify a user to kick!",
                                               color=discord.Color.red()))
        else:
            try:
                await member.kick(reason=reason)
            except discord.Forbidden:
                await ctx.send(embed=discord.Embed(title="I don't have permissions to kick!",
                                                   description="Go to my permissions, and allow Administrator"
                                                               " permissions.", color=discord.Color.red()))
                return
            kick_embed = discord.Embed(title=f"{member.display_name} has been kicked.", color=discord.Color.green())
            if reason:
                kick_embed.description = reason
            await ctx.send(embed=kick_embed)

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: Context, member: discord.Member = None, *,
                  reason: str = "No reason specified") -> None:
        """Ban a member"""
        if not member:
            await ctx.send(embed=discord.Embed(title="You forgot to specify a user to ban!",
                                               color=discord.Color.red()))
        else:
            try:
                await member.ban(reason=ban)
            except discord.Forbidden:
                await ctx.send(embed=discord.Embed(title="I don't have permissions to ban!",
                                                   description="Go to my permissions, and allow Administrator"
                                                               " permissions.", color=discord.Color.red()))
                return
            ban_embed = discord.Embed(title=f"{member.display_name} has been banned.", color=discord.Color.green())
            if reason:
                ban_embed.description = reason
            await ctx.send(embed=ban_embed)

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def softban(self, ctx: Context, member: discord.Member = None, *,
                      reason: str = "No reason specified.") -> None:
        """Ban and unban a member instantly"""
        if not member:
            await ctx.send(embed=discord.Embed(title="You forgot to specify a user to softban!",
                                               color=discord.Color.red()))
            return
        try:
            await member.ban(reason=reason)
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(title="I don't have permissions to ban!",
                                               description="Go to my permissions, and allow Administrator"
                                                           " permissions.", color=discord.Color.red()))
            return
        await member.unban(reason=reason)
        softban_embed = discord.Embed(title=f"{member.display_name} has been softbanned.", color=discord.Color.green())
        if reason:
            softban_embed.description = reason
        await ctx.send(embed=softban_embed)
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def mute(self, ctx: Context, member: discord.Member = None, *, time: str = "") -> None:
        """Mute a member"""
        server_col = self.db[str(ctx.guild.id)]
        if not member:
            await ctx.send(embed=discord.Embed(title="You didn't specify a member to mute.",
                                               color=discord.Color.red()))
            return
        elif member.id == ctx.author.id:
            await ctx.send(embed=discord.Embed(title="You can't mute yourself!",
                                               color=discord.Color.red()))
            return

        try:
            muted_role = get(ctx.guild.roles, name="Muted")
            if not muted_role:
                await ctx.send(embed=discord.Embed(title="There is no muted role for me to work with!",
                                                   color=discord.Color.red()))
                return
            await member.add_roles(muted_role)
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(title="I'm not high enough in the role hierarchy to mute this person!",
                                               color=discord.Color.red()))
            return
        if time:
            jobs_col = server_col['jobs']
            if not jobs_col.find_one():
                jobs_col.insert_one({})
            jobs_dict = jobs_col.find_one()
            time = self.calculate_time(time)
            jobs_dict[time.isoformat()] = member.id
            jobs_col.update_one(jobs_col.find_one(),
                                {"$set": jobs_dict})
            await member.send(embed=discord.Embed(title=f"You have been muted until "
                                                        f"{time.month}-{time.day}-{time.year}, "
                                                        f"{time.hour}:{time.minute}:{time.second}",
                                                  color=discord.Color.red()))
            await ctx.send(embed=discord.Embed(title=f"{member.display_name} has been muted.",
                                               color=discord.Color.green()))


def setup(bot):
    bot.add_cog(Automodding(bot))
