import discord
from discord.ext import commands
from discord.ui import Select, View, Button
import sqlite3
import os

BOT_OWNER_ID = 772320334606368788

def init_db():
    if not os.path.exists('app/data/client/tracking.db'):
        conn = sqlite3.connect('app/data/client/tracking.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE tracking
                     (guild_id INTEGER, channel_id INTEGER, server_ip TEXT, user_id INTEGER)''')
        conn.commit()
        conn.close()

init_db()

class ConfirmationButtons(View):
    def __init__(self, channel, server_ip, guild_id, user_id):
        super().__init__(timeout=60)
        self.channel = channel
        self.server_ip = server_ip
        self.guild_id = guild_id
        self.user_id = user_id
        self.confirmed = None
        
    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        conn = sqlite3.connect('app/data/client/tracking.db')
        c = conn.cursor()

        if interaction.user.id != BOT_OWNER_ID:
            c.execute("SELECT * FROM tracking WHERE channel_id=? AND server_ip=?", 
                     (self.channel.id, self.server_ip))
            if c.fetchone():
                await interaction.response.edit_message(
                    content="❌ Error: **This IP already exists in this channel!**",
                    view=None
                )
                conn.close()
                self.stop()
                return

            c.execute("SELECT COUNT(*) FROM tracking WHERE user_id=?", (self.user_id,))
            user_count = c.fetchone()[0]
            if user_count >= 10:
                await interaction.response.edit_message(
                    content="❌ Error: **You can't track more than 10 servers total!**",
                    view=None
                )
                conn.close()
                self.stop()
                return
            
            c.execute("SELECT * FROM tracking WHERE guild_id=? AND server_ip=?", 
                     (self.guild_id, self.server_ip))
            if c.fetchone():
                await interaction.response.edit_message(
                    content="❌ Error: **This IP already exists on this Discord server!**",
                    view=None
                )
                conn.close()
                self.stop()
                return
            
            c.execute("SELECT COUNT(*) FROM tracking WHERE guild_id=?", (self.guild_id,))
            guild_count = c.fetchone()[0]
            if guild_count >= 5:
                await interaction.response.edit_message(
                    content="❌ Error: This Discord server can't track **more than 5 servers!**",
                    view=None
                )
                conn.close()
                self.stop()
                return
        
        c.execute("INSERT INTO tracking VALUES (?, ?, ?, ?)",
                 (self.guild_id, self.channel.id, self.server_ip, self.user_id))
        conn.commit()
        conn.close()
        
        await interaction.response.edit_message(
            content=f"✅ Configuration **saved!**\n"
                   f"• Server ID: `{self.guild_id}`\n"
                   f"• Channel: **{self.channel.mention}**\n"
                   f"• Server IP: `{self.server_ip}`",
            view=None
        )
        self.confirmed = True
        self.stop()
        
    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="❌ All actions have been **canceled**",
            view=None
        )
        self.confirmed = False
        self.stop()

class ChannelSelect(Select):
    def __init__(self, channels, server_ip, guild_id, user_id):
        self.server_ip = server_ip
        self.guild_id = guild_id
        self.user_id = user_id
        options = [
            discord.SelectOption(
                label=channel.name,
                value=str(channel.id),
                description=f"Select {channel.name}"
            ) for channel in channels
        ]
        super().__init__(
            placeholder="Choose a channel...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(int(self.values[0]))
        confirmation_view = ConfirmationButtons(channel, self.server_ip, self.guild_id, self.user_id)
        await interaction.response.send_message(
            f"**Please confirm your configuration**:\n"
            f"• Server ID: `{self.guild_id}`\n"
            f"• Channel: **{channel.mention}**\n"
            f"• Server IP: `{self.server_ip}`",
            view=confirmation_view,
            ephemeral=True
        )
        await confirmation_view.wait()

class ChannelSelectView(View):
    def __init__(self, channels, server_ip, guild_id, user_id):
        super().__init__()
        self.add_item(ChannelSelect(channels, server_ip, guild_id, user_id))

@commands.slash_command(name="add_server", description="Configure server tracking")
@commands.guild_only()
@commands.has_permissions(administrator=True)
async def add_server(ctx: discord.ApplicationContext, server_ip: str = discord.Option(description="The server IP address to track")):
    guild_id = ctx.guild.id
    user_id = ctx.user.id
    text_channels = [channel for channel in ctx.guild.channels 
                    if isinstance(channel, discord.TextChannel)]
    if not text_channels:
        await ctx.respond("**No text channels found on this server!**", ephemeral=True)
        return
    view = ChannelSelectView(text_channels, server_ip, guild_id, user_id)
    await ctx.respond("Please select a **channel** for tracking:", view=view, ephemeral=True)

def setup(bot):
    bot.add_application_command(add_server)