from discord.ext import commands
import discord
from discord.ext.commands.context import Context


class MainCommands(commands.Cog):
    """Cog for all the main commands."""
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def error_embed(message: str, description: str = '', color: discord.Color = discord.Color.red()):
        err_embed = discord.Embed(title=message, color=color)
        if description:
            err_embed.description = description
        return err_embed

    @commands.Cog.listener()
    async def on_command_error(self, ctx: Context, exception: Exception):
        await ctx.send(embed=self.error_embed("Slow your horses!", str(exception)))
        

def setup(bot):
    bot.add_cog(MainCommands(bot))
