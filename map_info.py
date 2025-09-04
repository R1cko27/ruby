import discord
from discord.ext import commands
import sqlite3
import json
import aiohttp
import asyncio
from dotenv import load_dotenv
import os
import datetime

async def get_server_info(json_data):
    try:
        data = json.loads(json_data) if isinstance(json_data, str) else json_data
        publishedfiledetails = data.get('response', {}).get('publishedfiledetails', [])
        if not publishedfiledetails:
            return None, None, None, None

        details = publishedfiledetails[0]
        return (
            details.get('title'),
            details.get('app_name'),
            details.get('subscriptions'),
            details.get('favorited'),
            details.get('followers'),
            details.get('views'),
            details.get('vote_data'),
            details.get('file_size'),
            details.get('preview_url'),
        )
    except (KeyError, IndexError, json.JSONDecodeError, TypeError) as e:
        print(f"Ошибка: {e}, данные: {json_data}")
        return None, None, None, None
async def get_addon(json_data):
    try:
        data = json.loads(json_data) if isinstance(json_data, str) else json_data
        publishedfiledetails = data.get('response', {}).get('publishedfiledetails', [])
        if not publishedfiledetails:
            return None

        details = publishedfiledetails[0]
        return (
            details.get('publishedfileid'),
        )
    except (KeyError, IndexError, json.JSONDecodeError, TypeError) as e:
        print(f"Ошибка: {e}, данные: {json_data}")
        return None
async def fetch_and_process_data(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            json_data = await response.json(content_type=None)
            return await get_server_info(json_data)
async def fetch_and_process_data_name(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            json_data = await response.json(content_type=None)
            return await get_addon(json_data)

def starts(score):
    stars = (round(float(score)*10))
    star = [['☆'] for i in range(10)]
    for i in range(stars):
        star[i][0] = '★'
    text = ''
    for i in range(len(star)):
        text += star[i][0]
    return(text)
DATABASE_NAME = 'app/data/game/map_stats.db'
def get_map_data(map_name):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT 
            last_played,
            total_minutes
        FROM map_stats
        WHERE map_name = ?
    ''', (map_name,))
    
    data = cursor.fetchone()
    conn.close()
    
    if data:
       return {
            'last_played': data[0],
            'total_minutes': data[1]
       }
    else:
        return None
    
@commands.slash_command(name="map_info", description="Find information about map in Steam Workshop")
async def map_info(ctx: discord.ApplicationContext, map_name: str):
    await ctx.defer()
    load_dotenv()
    key = os.getenv('KEY')
    addon_link = f"https://api.steampowered.com/IPublishedFileService/QueryFiles/v1/?key={key}&appid=730&search_text={map_name}"
    addon = await fetch_and_process_data_name(addon_link)
    if addon:
        url = f"https://api.steampowered.com/IPublishedFileService/GetDetails/v1/?key={key}&includevotes=true&publishedfileids[0]={addon[0]}"
        title,app_name,subscriptions,favorited,followers,views,vote_data,file_size,preview_url = await fetch_and_process_data(url)
        star = starts(str(vote_data["score"]))
        embed = discord.Embed(color = 0x111f48)
        embed.add_field(name='Map Name', value=f'[{title}](https://s2ze.com/maps/{addon[0]})', inline=True)
        embed.add_field(name='Size', value=f'{round(int(file_size)/1048576)} MB', inline=True)
        embed.add_field(name='Game', value=app_name, inline=True)
        embed.add_field(name='Views', value=views, inline=True)
        embed.add_field(name='Subscriptions', value=subscriptions, inline=True)
        embed.add_field(name='Favorited', value=favorited, inline=True)
        embed.add_field(name=' ', value=' ', inline=False)
        embed.add_field(name='Votes :thumbsup:', value=vote_data["votes_up"], inline=True)
        embed.add_field(name='Votes :thumbsdown:', value=vote_data["votes_down"], inline=True)
        embed.add_field(name='Score', value=star, inline=True)
        embed.set_image(url = preview_url)
        message = await ctx.respond(embed = embed)
    else:
        await ctx.respond('Sorry, but I dont seem to have any information about this map.')

def setup(bot: discord.Bot):
    bot.add_application_command(map_info)