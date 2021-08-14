from discord.ext import commands
import discord
from discord.ext.commands.context import Context


class MainCommands(commands.Cog):
    """Cog for all the main commands."""
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def error_embed(message: str, description: str = '', color: discord.Color = discord.Color.red()) -> discord.Embed:
        """Create an error embed with the message and description provided"""
        err_embed = discord.Embed(title=message, color=color)
        if description:
            err_embed.description = description
        return err_embed

    @commands.Cog.listener()
    async def on_command_error(self, ctx: Context, exception: Exception) -> None:
        """
        When an error is thrown, this command catches it and will send an error embed regarding:
            - cooldown errors
        """
        if 'cooldown' in str(exception).lower():
            await ctx.send(embed=self.error_embed("Slow your horses!", str(exception)))
        else:
            raise exception

    @commands.command(aliases=["confession", "anon"])
    async def anonymous(self, ctx: Context, *, message: str):
        await ctx.purge(limit=1)
        await ctx.send(embed=discord.Embed(title="Anonymous Message",
                                           description=message, color=discord.Color.blue()))
        

def setup(bot):
    bot.add_cog(MainCommands(bot))
