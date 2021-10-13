from discord.ext import commands
from discord.ui import Select, View
from discord.ext.tasks import loop
from discord.ext.commands import BucketType
from discord.ext.commands.context import Context
from discord import Color, Embed, Guild, Interaction, Member, Message, SelectOption
from discord.utils import get
import arrow
from pymongo import MongoClient
import pymongo
import ssl
from itertools import zip_longest
from config import mongodb_link
from aiohttp import ClientSession
from datetime import datetime
from tzwhere import tzwhere


class VoiceRegulate(commands.Cog):
    """Cog for letting the user choose how long they want to stay in voice chat."""

    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.db = MongoClient(mongodb_link, ssl_cert_reqs=ssl.CERT_NONE)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.downtime_check.is_running():
            self.downtime_check.start()

    @loop(minutes=1)
    async def downtime_check(self):
        for server in self.db.list_database_names():
            if server.isnumeric():
                server_guild: Guild = self.bot.get_guild(int(server))
                for user in self.db[server].list_collections():
                    user = self.db[server][user["name"]]
                    user_dict = user.find_one()
                    if information := user_dict.get("downtime"):
                        timezone = information["timezone"]
                        cur_time = arrow.now(timezone)
                        user_obj: Member = await server_guild.fetch_member(information["id"])
                        start_time = cur_time.replace(
                            hour=information["start_time"]["hour"],
                            minute=information["start_time"]["minute"]
                        )
                        try:
                            end_time = cur_time.replace(
                                day=cur_time.day + information["end_time"]["offset"],
                                hour=information["end_time"]["hour"],
                                minute=information["end_time"]["minute"]
                            )
                        except ValueError:
                            end_time = cur_time.replace(
                                year=cur_time.year + 1 if cur_time.month + 1 > 12 else cur_time.year,
                                month=1 if cur_time.month + 1 > 12 else cur_time.month + 1,
                                day=1,
                                hour=information["end_time"]["hour"],
                                minute=information["end_time"]["minute"]
                            )

                        if start_time <= cur_time <= end_time and not get(user_obj.roles, name="Voice Locked"):
                            await user_obj.add_roles(get(server_guild.roles, name="Voice Locked"))
                        elif cur_time >= end_time and get(user_obj.roles, name="Voice Locked"):
                            await user_obj.remove_roles(get(server_guild.roles, name="Voice Locked"))

    @commands.group(name="voice")
    async def voice(self, ctx: commands.Context) -> None:
        """No-op for a discord command group."""
        pass

    @voice.command(aliases=["dt"])
    async def downtime(self, ctx: commands.Context, *, time: str) -> None:
        """Allowing a user to specify what time they should be barred from the voice channel."""
        voice_role = get(ctx.guild.roles, name="Voice Locked")
        if not voice_role:
            voice_role = await ctx.guild.create_role(name="Voice Locked")
            voice_role.edit(position=ctx.me.top_role.position - 1)
            for channel in ctx.guild.voice_channels:
                await channel.set_permissions(voice_role, connect=False)

        start_time, end_time = time.split(' to ')

        end_time, timezone = end_time.split(',' if ', ' not in end_time else ', ')

        # Get the timezone from the city name
        async with ClientSession(trust_env=True) as session:
            async with session.get(
                    f"https://nominatim.openstreetmap.org/search.php?q={timezone}&format=json",
                    ssl=False
            ) as resp:
                resp = await resp.json()
                if not resp:
                    await ctx.send(embed=Embed(
                        title=f"'{timezone}' is not a valid city!",
                        description="Check if you made a typo or something else.",
                        color=Color.red()))
                    return
                else:
                    coords = (float(resp[0]["lat"]), float(resp[0]["lon"]))

        timezone_name = tzwhere.tzwhere(forceTZ=True)
        timezone = timezone_name.tzNameAt(*coords)

        if int(start_time[:start_time.find(':')]) < 10:
            start_time = '0' + start_time
        if int(end_time[:end_time.find(':')]) < 10:
            end_time = '0' + end_time

        start_time_p = datetime.strptime(start_time, "%I:%M %p")
        end_time_p = datetime.strptime(end_time, "%I:%M %p")
        start_time = {"hour": start_time_p.hour,
                      "minute": start_time_p.minute,
                      "offset": 0}
        end_time = {"hour": end_time_p.hour,
                    "minute": end_time_p.minute,
                    "offset": 1 if start_time["hour"] > end_time_p.hour else 0}

        server_col = self.db[str(ctx.guild.id)]
        user_col = server_col[str(ctx.author.id)]
        if not user_col.find_one():
            user_col.insert_one({})

        user_dict = user_col.find_one()
        user_dict.update(
            {"downtime": {"id": ctx.author.id, "start_time": start_time, "end_time": end_time, "timezone": timezone}}
        )

        user_col.replace_one(user_col.find_one(), user_dict)
        success_embed = Embed(title="Success!", description="The downtime has been set!", color=Color.green())
        await ctx.send(embed=success_embed)


def setup(bot):
    bot.add_cog(VoiceRegulate(bot))
