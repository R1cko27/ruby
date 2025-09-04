import discord
from discord.ext import commands
from discord.ui import Select, View, Button
import sqlite3
import os

BOT_OWNER_ID = 772320334606368788

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
                embed = discord.Embed(
                    title="❌ Error",
                    description="This tracker already exists in this channel!",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                conn.close()
                self.stop()
                return

            c.execute("SELECT COUNT(DISTINCT server_ip) FROM tracking WHERE user_id=? AND server_ip IN ('new_map', 'play_new_maps')", 
                     (self.user_id,))
            user_count = c.fetchone()[0]
            if user_count >= 3:
                embed = discord.Embed(
                    title="❌ Error",
                    description="You can't track more than 3 map trackers total!",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                conn.close()
                self.stop()
                return
            
            c.execute("SELECT * FROM tracking WHERE guild_id=? AND server_ip=?", 
                     (self.guild_id, self.server_ip))
            if c.fetchone():
                embed = discord.Embed(
                    title="❌ Error",
                    description="This tracker already exists on this Discord server!",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                conn.close()
                self.stop()
                return
            
            c.execute("SELECT COUNT(*) FROM tracking WHERE channel_id=?", (self.channel.id,))
            channel_count = c.fetchone()[0]
            if channel_count >= 2:
                embed = discord.Embed(
                    title="❌ Error",
                    description="This channel can't have more than 2 trackers!",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                conn.close()
                self.stop()
                return
        
        c.execute("INSERT INTO tracking VALUES (?, ?, ?, ?)",
                 (self.guild_id, self.channel.id, self.server_ip, self.user_id))
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            title="✅ Configuration saved!",
            color=discord.Color.green()
        )
        embed.add_field(name="Server ID", value=f"`{self.guild_id}`", inline=False)
        embed.add_field(name="Channel", value=f"{self.channel.mention}", inline=False)
        embed.add_field(name="Tracker Type", value=f"`{self.server_ip}`", inline=False)
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.confirmed = True
        self.stop()
        
    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        embed = discord.Embed(
            title="❌ Action canceled",
            description="All actions have been canceled",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.confirmed = False
        self.stop()

class TrackerTypeButtons(View):
    def __init__(self, channel, guild_id, user_id):
        super().__init__(timeout=60)
        self.channel = channel
        self.guild_id = guild_id
        self.user_id = user_id
        
    @discord.ui.button(label="New maps", style=discord.ButtonStyle.primary)
    async def new_maps(self, button: discord.ui.Button, interaction: discord.Interaction):
        confirmation_view = ConfirmationButtons(self.channel, "new_map", self.guild_id, self.user_id)
        embed = discord.Embed(
            title="Please confirm your configuration",
            color=discord.Color.blue()
        )
        embed.add_field(name="Server ID", value=f"`{self.guild_id}`", inline=False)
        embed.add_field(name="Channel", value=f"{self.channel.mention}", inline=False)
        embed.add_field(name="Tracker Type", value="`new_map`", inline=False)
        
        await interaction.response.edit_message(embed=embed, view=confirmation_view)
        await confirmation_view.wait()
        
    @discord.ui.button(label="Play New Maps", style=discord.ButtonStyle.primary)
    async def play_new_maps(self, button: discord.ui.Button, interaction: discord.Interaction):
        confirmation_view = ConfirmationButtons(self.channel, "play_new_maps", self.guild_id, self.user_id)
        embed = discord.Embed(
            title="Please confirm your configuration",
            color=discord.Color.blue()
        )
        embed.add_field(name="Server ID", value=f"`{self.guild_id}`", inline=False)
        embed.add_field(name="Channel", value=f"{self.channel.mention}", inline=False)
        embed.add_field(name="Tracker Type", value="`play_new_maps`", inline=False)
        
        await interaction.response.edit_message(embed=embed, view=confirmation_view)
        await confirmation_view.wait()

class ChannelSelect(Select):
    def __init__(self, channels, guild_id, user_id):
        self.guild_id = guild_id
        self.user_id = user_id
        
        channels = channels[:25]
        
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
        tracker_type_view = TrackerTypeButtons(channel, self.guild_id, self.user_id)
        
        embed = discord.Embed(
            title="**Please select tracker type:**",
            color=discord.Color.blue()
        )
        embed.add_field(name="Server ID", value=f"`{self.guild_id}`", inline=False)
        embed.add_field(name="Channel", value=f"{channel.mention}", inline=False)
        
        await interaction.response.edit_message(embed=embed, view=tracker_type_view)

class ChannelSelectView(View):
    def __init__(self, channels, guild_id, user_id):
        super().__init__()
        self.add_item(ChannelSelect(channels, guild_id, user_id))

@commands.slash_command(name="add_map_tracker", description="Add map tracking")
@commands.guild_only()
@commands.has_permissions(administrator=True)
async def add_map_tracker(ctx: discord.ApplicationContext):
    guild_id = ctx.guild.id
    user_id = ctx.user.id
    
    text_channels = [channel for channel in ctx.guild.channels 
                    if isinstance(channel, discord.TextChannel)]
    
    if not text_channels:
        embed = discord.Embed(
            title="❌ Error",
            description="No text channels found on this server!",
            color=discord.Color.red()
        )
        await ctx.respond(embed=embed, ephemeral=True)
        return
    
    if len(text_channels) > 25:
        text_channels = text_channels[:25]
        embed = discord.Embed(
            title="⚠️ Note",
            description="Only showing first 25 channels. Please use a more specific channel name if you don't see your channel.",
            color=discord.Color.orange()
        )
        await ctx.respond(embed=embed, ephemeral=True)
    
    embed = discord.Embed(
        title="Map Tracker Setup",
        description="Please select a channel for tracking:",
        color=discord.Color.blue()
    )
    
    view = ChannelSelectView(text_channels, guild_id, user_id)
    await ctx.respond(embed=embed, view=view, ephemeral=True)

def setup(bot):
    bot.add_application_command(add_map_tracker)