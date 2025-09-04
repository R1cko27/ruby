import discord
from discord.ext import commands
import sqlite3
import json
import aiohttp
from discord.ui import Button, View, Select
import os
from dotenv import load_dotenv

load_dotenv()

class NotifyListView(View):
    def __init__(self, maps_data, author_id):
        super().__init__(timeout=180)
        self.maps_data = maps_data
        self.author_id = author_id
        self.selected_map = None
        
        
        # Add map selection dropdown if there are any maps
        if maps_data:
            self.add_item(self.MapSelect(maps_data))
    
    async def update_embed(self, interaction):
        embed = discord.Embed(
            color=0x111f48, 
            title='Your Notification List'
        )
        
        # Create the main list view with numbering
        main_list = []
        main_list.append("```")
        for i, (map_name, map_filter) in enumerate(self.maps_data, start=1):
            if map_filter:
                main_list.append(f"{i}. {map_name} | Filter: {map_filter}")
            else:
                main_list.append(f"{i}. {map_name}")
        main_list.append("```")
        # Add detailed view for selected map if any
        if self.selected_map is not None:
            map_name, map_filter = self.maps_data[self.selected_map]
            map_details = await self.get_map_details(map_name)
            
            embed.add_field(
                name="🔍 Selected Map Details",
                value=map_details,
                inline=False
            )
        
        embed.description = "\n".join(main_list)
        embed.set_footer(text=f"Total notifications: {len(self.maps_data)}")
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def get_map_details(self, map_name):
        # Get basic info
        details = f"Map Name: **{map_name}**\n"
        if self.maps_data[self.selected_map][1]:
            details += f"Filter: **{self.maps_data[self.selected_map][1]}**\n"
        else:
            details += "Filter: **No filter**\n"
        
        # Get additional info from Steam
        steam_info,addon_info = await self.get_steam_info(map_name)
        if steam_info:
            details += "\n**Steam Workshop Info:**\n"
            
            # Safely access steam_info fields with fallbacks
            title = steam_info.get('title', 'Unknown')
            file_id = str(addon_info)
            subs = steam_info.get('subscriptions', 'Unknown')
            favs = steam_info.get('favorited', 'Unknown')
            file_size = round(int(steam_info.get('file_size', 0))/1048576)
            
            # Handle rating data safely
            vote_data = steam_info.get('vote_data', {})
            score = vote_data.get('score', 0)
            
            details += f"- Map name: **[{title}](https://s2ze.com/maps/{file_id})**\n"
            details += f"- Subscriptions: **{subs}**\n"
            details += f"- Favorited: **{favs}**\n"
            details += f"- Rating: **{self.stars(score)}**\n"
            details += f"- Size: **{file_size:.2f} MB**\n"
        
        # Get playtime stats
        stats = self.get_map_stats(map_name)
        if stats:
            details += "\n**Server Statistics:**\n"
            details += f"- Total Playtime: **{stats['total_minutes']} minutes**\n"
            details += f"- Last Played: {stats['last_played']}\n"
        
        return details
    
    async def get_steam_info(self, map_name):
        try:
            key = os.getenv('KEY')
            addon_link = f"https://api.steampowered.com/IPublishedFileService/QueryFiles/v1/?key={key}&appid=730&search_text={map_name}"
            addon = await self.fetch_and_process_data_name(addon_link)
            
            if addon:
                url = f"https://api.steampowered.com/IPublishedFileService/GetDetails/v1/?key={key}&includevotes=true&publishedfileids[0]={addon[0]}"
                return (await self.fetch_and_process_data(url), addon[0])
            return None
        except Exception:
            return None
    
    async def fetch_and_process_data(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                json_data = await response.json(content_type=None)
                return await self.get_server_info(json_data)
    
    async def fetch_and_process_data_name(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                json_data = await response.json(content_type=None)
                return await self.get_addon(json_data)
    
    async def get_server_info(self, json_data):
        try:
            data = json.loads(json_data) if isinstance(json_data, str) else json_data
            publishedfiledetails = data.get('response', {}).get('publishedfiledetails', [])
            if not publishedfiledetails:
                return None

            details = publishedfiledetails[0]
            return {
                'title': details.get('title'),
                'app_name': details.get('app_name'),
                'subscriptions': details.get('subscriptions'),
                'favorited': details.get('favorited'),
                'followers': details.get('followers'),
                'views': details.get('views'),
                'vote_data': details.get('vote_data'),
                'file_size': details.get('file_size'),
                'preview_url': details.get('preview_url'),
            }
        except (KeyError, IndexError, json.JSONDecodeError, TypeError):
            return None
    
    async def get_addon(self, json_data):
        try:
            data = json.loads(json_data) if isinstance(json_data, str) else json_data
            publishedfiledetails = data.get('response', {}).get('publishedfiledetails', [])
            if not publishedfiledetails:
                return None

            details = publishedfiledetails[0]
            return (details.get('publishedfileid'),)
        except (KeyError, IndexError, json.JSONDecodeError, TypeError):
            return None
    
    def stars(self, score):
        stars_count = round(float(score)*10)
        return '★' * stars_count + '☆' * (10 - stars_count)
    
    def get_map_stats(self, map_name):
        conn = sqlite3.connect('app/data/game/map_stats.db')
        cursor = conn.cursor()

        cursor.execute('''
            SELECT 
                last_played,
                total_minutes
            FROM map_stats
            WHERE map_name = ?
        ''', (map_name.lower(),))
        
        data = cursor.fetchone()
        conn.close()
        
        if data:
            return {
                'last_played': data[0],
                'total_minutes': data[1]
            }
        return None
    

    class MapSelect(Select):
        def __init__(self, maps_data):
            options = [
                discord.SelectOption(
                    label=f"{i+1}. {map_name[:45]}",
                    description=map_filter[:50] if map_filter else "No filter",
                    value=str(i))
                for i, (map_name, map_filter) in enumerate(maps_data)
            ]
            super().__init__(
                placeholder="Select a map to view details",
                options=options,
                row=1,
                max_values=1
            )
        
        async def callback(self, interaction):
            view = self.view
            if interaction.user.id != view.author_id:
                return await interaction.response.send_message("You can't control this menu!", ephemeral=True)
            
            view.selected_map = int(self.values[0])
            await view.update_embed(interaction)

@commands.slash_command(
    name="notify_list", 
    description='Check your notification list',
    help="""
    **Notification Commands:**
    `/notify_toggle` - Add/Delete map from your notification list
    `/notify_filter` - Add a filter to your map
    `/notify_wipe` - Clear your notification list
    `/notify_list` - Check your notification list
    """
)
async def notify_list(ctx: discord.ApplicationContext):
    conn = sqlite3.connect('app/data/client/notify_list.db')
    c = conn.cursor()
    c.execute("SELECT map_name, map_filter FROM notifications WHERE client_id = ?", (ctx.author.id,))
    maps = c.fetchall()
    conn.close()

    if not maps:
        embed = discord.Embed(
            color=0x111f48,
            title="Notification List",
            description="Your Notification List is empty."
        )
        embed.add_field(
            name="Available Commands",
            value="""
            `/notify_toggle` - Add/Delete map from notifications
            `/notify_filter` - Add a filter to your map
            `/notify_wipe` - Clear your notification list
            """,
            inline=False
        )
        return await ctx.respond(embed=embed, ephemeral=True)
    
    view = NotifyListView(maps, ctx.author.id)
    
    embed = discord.Embed(color=0x111f48, title='Your Notification List')
    
    # Create the main list with numbering
    main_list = []
    main_list.append("```")
    for i, (map_name, map_filter) in enumerate(maps, start=1):
        if map_filter:
            main_list.append(f"{i}. {map_name} | Filter: {map_filter}")
        else:
            main_list.append(f"{i}. {map_name}")
    main_list.append("```")
    embed.description = "\n".join(main_list)
    embed.set_footer(text=f"Total notifications: {len(maps)}")
    
    await ctx.respond(embed=embed, view=view, ephemeral=True)

def setup(bot: discord.Bot):
    bot.add_application_command(notify_list)