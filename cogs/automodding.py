from discord.ext import commands
import discord
from discord.ext.tasks import loop
from discord.ext.commands import BucketType
from discord.ext.commands.context import Context
from discord import Message
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
    async def on_message(self, message: Message):
        server_col = self.db[str(message.guild.id)]['jobs'].find_one()
        if any([(key in message.content) for key in server_col.keys()]):
            await message.reply(embed=discord.Embed(title=f"Shhhh! The person you tagged is in a productivity "
                                                          f"session right now.",
                                                    color=discord.Color.orange()))

        await self.bot.process_commands(message)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.iterate_through_jobs.is_running():
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
    async def iterate_through_jobs(self) -> None:
        for server in self.db.database_names():
            if len(server) >= 18:
                jobs_col = self.db[server]['jobs']
                jobs_dict = jobs_col.find_one()
                for key, value in jobs_col.find_one().items():
                    if key != '_id':
                        if len(key) != 18:
                            if isinstance(value, dict):
                                value = list(value.values())[0]
                            if isinstance(value, int):
                                time = datetime.fromisoformat(key)
                                server_guild = self.bot.get_guild(int(server))
                                if datetime.now() > time:
                                    banned_users = await server_guild.bans()
                                    banned_users = [i.user for i in banned_users]
                                    if value in (id_lst := [x.id for x in banned_users]):
                                        banned_user = banned_users[id_lst.index(value)]
                                        await server_guild.unban(banned_user)
                                    else:
                                        muted_role = get(server_guild.roles, name="Muted")
                                        user = server_guild.get_member(value)
                                        await user.remove_roles(muted_role)
                                        try:
                                            await user.send(embed=discord.Embed(title="You have been unmuted.",
                                                                                color=discord.Color.green()))
                                        except discord.Forbidden:
                                            pass
                                    del jobs_dict[key]
                        elif len(key) == 18:
                            key = int(key)
                            server_guild = self.bot.get_guild(int(server))
                            time = datetime.fromisoformat(value['time'])
                            command_raised = datetime.fromisoformat(value['command_raised'])
                            member = server_guild.get_member(key)
                            if 625 <= (datetime.now() - command_raised).total_seconds() <= 629.99:
                                if member.status != discord.Status.idle:
                                    del jobs_dict[str(key)]
                                    try:
                                        await member.send(embed=discord.Embed(title="You didn't keep up your "
                                                                                    "productive time period!",
                                                                              color=discord.Color.red()))
                                    except discord.Forbidden:
                                        pass
                            elif time <= datetime.now():
                                user_col = self.db[server][key]
                                user_dict = user_col.find_one()
                                if not get(user_dict, 'productivity', None):
                                    user_dict['productivity'] = 0
                                user_dict['productivity'] += ((time - command_raised).total_seconds() // 60) % 60
                                try:
                                    await member.send(embed=discord.Embed(title="You remained productive for the "
                                                                                "time period you specified!",
                                                                          color=discord.Color.green()))
                                except discord.Forbidden:
                                    pass
                                del jobs_dict[str(key)]
                                user_col.replace_one(user_col.find_one(), user_dict)
                                
                            elif (datetime.now() - command_raised).total_seconds() <= 600 and \
                                    member.status == discord.Status.idle:
                                del jobs_dict[str(key)]
                                try:
                                    await member.send(embed=discord.Embed(title="Nice try!",
                                                                          description="Changing your status to Idle "
                                                                                      "manually doesn't work as the bot"
                                                                                      " can detect it.",
                                                                          color=discord.Color.red()))
                                except discord.Forbidden:
                                    pass

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
                await member.ban(reason=reason)
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

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def tempban(self, ctx: Context, member: discord.Member = None, *, time: str) -> None:
        """Unban a member"""
        server_col = self.db[str(ctx.guild.id)]
        if not member:
            await ctx.send(embed=discord.Embed(title="You forgot to provide someone to ban!",
                                               color=discord.Color.red()))
            return
        try:
            await member.ban(reason=None)
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(title="I don't have permissions to ban!",
                                               description="Go to my permissions, and allow Administrator"
                                                           " permissions.", color=discord.Color.red()))
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
            await ctx.send(embed=discord.Embed(title=f"{member.display_name} has been tempbanned.",
                                               color=discord.Color.green()))

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx: Context, member: int = None) -> None:
        """Unban a member"""
        if not member:
            await ctx.send(embed=discord.Embed(title="You forgot to provide someone to unban!",
                                               color=discord.Color.red()))
            return
        bans = await ctx.guild.bans()
        banned_users = [person.user for person in bans]
        if member in (banned_ids := [banned.id for banned in banned_users]):
            member = banned_users[banned_ids.index(member)]
            await ctx.guild.unban(member)
            await ctx.send(embed=discord.Embed(title=f"{member.display_name} has been unbanned!",
                                               color=discord.Color.green()))
        else:
            await ctx.send(embed=discord.Embed(title=f"This user is not banned!",
                                               color=discord.Color.red()))

    @commands.command(aliases=["prod"])
    async def productivity(self, ctx: Context, time: str = "0y, 0mo, 0d, 0h, 20m, 0s"):
        """Command to go 'productive', which checks if user is idle"""
        time = self.calculate_time(time)
        if (time - datetime.now()).total_seconds() <= 600:
            await ctx.send(embed=discord.Embed(title="You must give a time to go productive that is "
                                                     "higher than 10 minutes.",
                                               color=discord.Color.red()))
            return
        elif ctx.author.status in (discord.Status.idle, discord.Status.offline):
            await ctx.send(embed=discord.Embed(title="You need to change your status to something other than Idle"
                                                     " or Invisible to be able to run the productivity command.",
                                               color=discord.Color.red()))
            return
        server_col = self.db[str(ctx.guild.id)]
        jobs_col = server_col['jobs']
        if not jobs_col.find_one():
            jobs_col.insert_one({})
        jobs_dict = jobs_col.find_one()
        jobs_dict[str(ctx.author.id)] = {'time': time.isoformat(), 'command_raised': datetime.now().isoformat()}
        jobs_col.update_one(jobs_col.find_one(), {"$set": jobs_dict})
        success_embed = discord.Embed(title=f"Your time starts now, {ctx.author.display_name}!",
                                      description="Keep your Discord application open but "
                                                  "head to another application.",
                                      color=discord.Color.green())
        formatted_time = time - datetime.now()
        total_seconds = formatted_time.total_seconds()
        formatted_time = {'hours': total_seconds // 3600,
                          'minutes': int((total_seconds // 60) % 60), 'seconds': int(total_seconds % 60)}
        formatted_time = [f"{val} {key}" for key, val in formatted_time.items() if val != 0]
        formatted_time[-1] = 'and ' + formatted_time[-1]
        success_embed.add_field(name=f"Try to stay productive for {', '.join(formatted_time)}",
                                value="Ways to be productive!\n\t-Read a book\n\t-Take a walk outside"
                                      "\n\t-Socialize with others\n\t-Finish work that is due\n\t-etc.",
                                inline=False)
        await ctx.send(embed=success_embed)


def setup(bot):
    bot.add_cog(Automodding(bot))
