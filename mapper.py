import discord
from discord.ext import commands
import aiohttp
from bs4 import BeautifulSoup
import asyncio
from steam.steamid import SteamID
import sqlite3
import os
from dotenv import load_dotenv
import json
    
DATABASE_NAME = "app/data/game/map_stats.db"
async def fetch_player_data(steamid, token):
    url = f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?key={token}&steamids={steamid}&format=json"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.text()
                    return extract_player_data(data)
                else:
                    return []
    except aiohttp.ClientError as e:
        print(f"Ошибка подключения: {e}")
        return []

def extract_player_data(api_response_json):
    try:
        data = json.loads(api_response_json)
        players = data.get("response", {}).get("players", [])
        result = []

        for player in players:
            player_data = {}
            player_data["personaname"] = player.get("personaname")
            player_data["profileurl"] = player.get("profileurl")
            player_data["avatarfull"] = player.get("avatarfull")
            result.append(player_data)

        return result

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"Ошибка при обработке JSON: {e}")
        return []
    
async def fetch_map_data(steamid, token, appid=730):
    url = f"https://api.steampowered.com/IPublishedFileService/GetUserFiles/v1/?key={token}&steamid={steamid}&appid={appid}&numperpage=10000"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.text()
                    return extract_map_data(data)
                else:
                    return []
    except aiohttp.ClientError as e:
        return []

def extract_map_data(api_response_json):
    try:
        data = json.loads(api_response_json)
        publishedfiledetails = data.get("response", {}).get("publishedfiledetails", [])
        result = []

        for item in publishedfiledetails:
            map_data = {}
            map_data["title"] = item.get("title")
            vote_data = item.get("vote_data", {})
            map_data["votes_up"] = vote_data.get("votes_up")
            map_data["votes_down"] = vote_data.get("votes_down")

            result.append(map_data)

        return result

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return []
    
def get_map_data_by_name(map_name):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT 
            total_minutes
        FROM map_stats
        WHERE LOWER(map_name) = LOWER(?)
    ''', (map_name,))

    data = cursor.fetchone()
    conn.close()

    if data:
        return {
            'total_minutes': data[0]
        }
    else:
        return None

async def get_first_workshop_author_link(url):
    author_link = None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    first_workshop_item = soup.find('div', class_='workshopItem')
                    
                    if first_workshop_item:
                        author_link_element = first_workshop_item.find('a', class_='workshop_author_link')
                        if author_link_element:
                            author_link = author_link_element['href']
                else:
                   return None
    except aiohttp.ClientError as e:
        return None
    except Exception as e:
        return None
    return author_link

@commands.slash_command(name="mapper", description ='Get information about mapper maps')
async def mapper(ctx: discord.ApplicationContext, map_name: str):
    await ctx.defer()
    user_id = str(ctx.author.id)
    f = open('app/data/client/vip_clients.txt','r')
    vip_pass = False
    for i in f:
        if user_id in i:
            vip_pass = True
            break
    f.close()
    url = 'https://steamcommunity.com/workshop/browse/?appid=730&searchtext='+str(map_name)
    try:
        author_link = await get_first_workshop_author_link(url)
        steamid = SteamID.from_url(author_link)
        token = os.getenv('KEY')
        appid = 730
        player_data = await fetch_player_data(steamid, token)
        map_data = await fetch_map_data(steamid, token, appid)
        creator = player_data[0]['personaname']
        profileurl = player_data[0]['profileurl']
        avatar = player_data[0]['avatarfull']
        text = f'**Mapper: [{creator}]({profileurl})**\n'
        main_len = 3900
        main_len -= len(text)
        if map_data:
            count = 0
            for map_info in map_data:
                count += 1
                title_map = map_info['title']
                votes_up = map_info['votes_up']
                votes_down = map_info['votes_down']
                map_time = get_map_data_by_name(map_info['title'])
                if main_len > 0:
                    if map_time:
                        small_text = f'{count}. **{title_map}** || :thumbsup: {votes_up} | :thumbsdown: {votes_down} || Time - **{map_time["total_minutes"]}** minutes\n'
                        text += small_text
                        main_len -= len(small_text)
                    else:
                        small_text = f'{count}. **{title_map}** || :thumbsup: {votes_up} | :thumbsdown: {votes_down}||\n'
                        text += small_text
                        main_len -= len(small_text)
                else:
                    break
        embed = discord.Embed(color = 0x111f48)
        embed.set_image(url = avatar)
        embed.description = text
        await ctx.respond(embed = embed)
        
    except Exception as e:
        await ctx.respond('There is no such map. Enter the full map name',ephemeral=True)

def setup(bot: discord.Bot):
    bot.add_application_command(mapper)