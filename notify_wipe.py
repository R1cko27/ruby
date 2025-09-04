import discord
from discord.ext import commands
import sqlite3

@commands.slash_command(name="notify_wipe", description='Clear your notification list')
async def notify_wipe(ctx: discord.ApplicationContext):
    conn = sqlite3.connect('app/data/client/notify_list.db')
    c = conn.cursor()
    c.execute("DELETE FROM notifications WHERE client_id = ?", (ctx.author.id,))
    conn.commit()
    conn.close()
    await ctx.respond('Your Notification List is empty!', ephemeral=True)

def setup(bot: discord.Bot):
    bot.add_application_command(notify_wipe)