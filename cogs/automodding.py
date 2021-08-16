from discord.ext import commands
import discord
from discord.ext.commands import BucketType
from discord.ext.commands.context import Context


class Automodding(commands.Cog):
    """Cog for moderating system"""

    def __init__(self, bot):
        self.bot = bot

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
    @commands.cooldown(1, 30, BucketType.user)
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
                kick_embed.description = reason
            await ctx.send(embed=ban_embed)


def setup(bot):
    bot.add_cog(Automodding(bot))
