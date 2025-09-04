import discord
from discord.ext import commands, tasks
from googletrans import Translator
from datetime import datetime
import calendar
from steam.steamid import SteamID
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import traceback
from PIL import Image
import requests
from io import BytesIO
import numpy as np
import logging
import sqlite3
import subprocess

def map_info1(url):
    try:
        response_map = requests.get(url)
        soup = BeautifulSoup(response_map.content)
        map_name = (soup.find('div', 'workshopItemTitle')).text
        c_hight = []
        for i in soup.find('div', 'detailsStatsContainerRight'):
            c_hight.append(i.text)
        height = c_hight[1]

        for link_img_map in soup.find_all('img'):
            if str(link_img_map.get('src'))[-4:] == 'true':
                link_img_map = link_img_map.get('src')
                break
        link_img_map = link_img_map.replace('imw=200', 'imw=5000')
        link_img_map = link_img_map.replace('imh=112', 'imh=5000')
        link_img_map = link_img_map.replace('letterbox=true', 'letterbox=false')

        creators_link = []
        creator_name = []

        creator_steam = soup.find('div', 'panel')
        friend_block = creator_steam.find_all('div', class_='friendBlockContent')

        for link_steam in creator_steam.find_all('a'):
            link_stem_profile = link_steam.get('href')
            creators_link.append(link_stem_profile)
        for mapper_once in friend_block:
            name = mapper_once.find(string=True, recursive=True).strip()
            creator_name.append(name)
        creator_info = [[creator_name[i], creators_link[i]] for i in range(len(creator_name))]

        return link_img_map,map_name,height,creator_info
    except:
        return 'None','None','None',[['None','None']]
    
def get_clinet_server_name(ip_server):
    conn = sqlite3.connect('app/data/client/tracking.db')
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id FROM tracking WHERE server_ip = ?", (ip_server,))
    result = cursor.fetchall()
    return result
def get_average_color_from_url(image_url):
    try:
        response = requests.get(image_url, stream=True, timeout=10)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))
        image.thumbnail((25, 25)) 
        if image.mode not in ('RGB', 'RGBA'):
          image = image.convert('RGB')
        image_array = np.array(image)
        average_color = tuple(np.round(np.mean(image_array, axis=(0, 1))).astype(int).tolist())
        hex_color = '0x{:02x}{:02x}{:02x}'.format(average_color[0], average_color[1], average_color[2])

        return hex_color
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка загрузки изображения: {e}")
        return None
    except Exception as e:
        logging.error(f"Ошибка при обработке изображения: {e}")
        return None
    
def get_color(map_name):
    with open('app/data/main/maps.txt', 'r', encoding='UTF-8') as f:
        a = [i for i in f]
        for i in a:
            if map_name in i:
                try:
                    color = (i.split('<color>')[1]).replace('\n','')
                    return int(color, 16)
                except:
                    return 1122120
        return 1122120
    
async def first_check(session, url):
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            steam_maps_name = soup.find('div', 'workshopBrowseItems')
            map_name = (steam_maps_name.find('a')).get('href')

            for link_img_map in soup.find_all('img'):
                if str(link_img_map.get('src'))[-4:] == 'true':
                    link_img_map = link_img_map.get('src')
                    break
            link_img_map = link_img_map.replace('imw=200', 'imw=5000')
            link_img_map = link_img_map.replace('imh=112', 'imh=5000')
            link_img_map = link_img_map.replace('letterbox=true', 'letterbox=false')
            return map_name,link_img_map
    except aiohttp.ClientError as e:
        print(f"[Func 1] Ошибка HTTP-запроса first_check: {e}")
        return []
    except Exception as e:
        print(f"[Func 1] Ошибка парсинга first_check: {e}")
        return []

async def map_info(session, url):
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')

            map_name = (soup.find('div', 'workshopItemTitle')).text
            c_hight = []
            for i in soup.find('div', 'detailsStatsContainerRight'):
                c_hight.append(i.text)
            height = c_hight[1]

            creators_link = []
            creator_name = []

            creator_steam = soup.find('div', 'panel')
            friend_block = creator_steam.find_all('div', class_='friendBlockContent')

            for link_steam in creator_steam.find_all('a'):
                link_stem_profile = link_steam.get('href')
                creators_link.append(link_stem_profile)
            for mapper_once in friend_block:
                name = mapper_once.find(string=True, recursive=True).strip()
                creator_name.append(name)
            creator_info = [[creator_name[i], creators_link[i]] for i in range(len(creator_name))]

            return map_name,height,creator_info
    except aiohttp.ClientError as e:
        print(f"[Func 1] Ошибка HTTP-запроса map_info: {e}")
        return []
    except Exception as e:
        print(f"[Func 1] Ошибка парсинга map_info: {e}")
        return []

async def change_log(session, url):
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            p_tag = soup.find('p', id=True)
            if p_tag:
                text = ''.join(str(x).replace('<br/>', '\n').replace('<b>','').replace('</b>','') for x in p_tag.contents)
                cleaned_text = text.strip()
                return cleaned_text
    except aiohttp.ClientError as e:
        print(f"[Func 1] Ошибка HTTP-запроса change_log: {e}")
        return []
    except Exception as e:
        print(f"[Func 1] Ошибка парсинга change_log: {e}")
        return []
    
async def name_fast(session, url):
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            map_name = (soup.find('div', 'workshopItemTitle')).text
            return map_name
    except aiohttp.ClientError as e:
        print(f"[Func 1] Ошибка HTTP-запроса name_fast: {e}")
        return []
    except Exception as e:
        print(f"[Func 1] Ошибка парсинга name_fast: {e}")
        return []
    
async def first_check_start(url):
    url = str(url)
    async with aiohttp.ClientSession() as session:
        links = await first_check(session, url)
        return links
    
async def map_info_start(url):
    url = str(url)
    async with aiohttp.ClientSession() as session:
        links = await map_info(session, url)
        return links
    
async def map_changelog_start(url):
    url = str(url)
    async with aiohttp.ClientSession() as session:
        links = await change_log(session, url)
        return links
    
async def map_name_fast(url):
    url = str(url)
    async with aiohttp.ClientSession() as session:
        links = await name_fast(session, url)
        return links
    
def update_mapper_map(mapper_id, map_name, filename="app/data/charts/mapper_map.txt"):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            existing_data = f.readlines()
    except FileNotFoundError:
        existing_data = []

    id_map = {}
    for line in existing_data:
        parts = line.strip().split("<id_split#qI48>")
        if len(parts) == 2:
            id_val = parts[0].strip()
            id_map[id_val] = line

    for entry in mapper_id:
        try:
            author_id, author_name = entry
            author_id_str = str(author_id)
            
            if author_id_str in id_map:
                id_map[author_id_str] = id_map[author_id_str].replace('\n','') + f"<map_split>{map_name}\n"
            else:
              id_map[author_id_str] = f"{author_id_str}<id_split#qI48>{author_name}<author_split#8N~1>{map_name}\n"
        except (IndexError, TypeError) as e:
            print(f"Ошибка обработки данных: {e}, данные: {entry}. Пропускаем.")
            continue


    with open(filename, "w", encoding="utf-8") as f:
        for line in id_map.values():
            f.write(line)

class func1(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.loop_task.start()
        self.log_channel_id = 1270598846606741505
        self.stats = {
            'maps_processed': 0,
            'maps_updated': 0,
            'new_maps_added': 0,
            'errors': 0
        }

    @tasks.loop(seconds=90)
    async def loop_task(self):
            try:
                start_time = datetime.now()
                self.stats = {k: 0 for k in self.stats}
                channel2 = self.bot.get_channel(self.log_channel_id)
                g = open('app/data/map_time_update.txt', 'r')
                last_addon = g.read(250)
                g.close()
                self._print_formatted("Starting map monitoring cycle")
                try:
                    link_steam_addon2, link_img_map = await first_check_start('https://steamcommunity.com/workshop/browse/?appid=730&searchtext=ze_&browsesort=lastupdated&section=&actualsort=lastupdated')
                    addon = str(((link_steam_addon2.split('id=')[1]).split('&'))[0])
                    self.stats['maps_processed'] += 1
                    text = ''
                    if str(last_addon) != str(link_steam_addon2):
                        map_name2 = (await (map_name_fast("https://steamcommunity.com/sharedfiles/filedetails/?id="+addon)))
                        if (str(map_name2)[:3]) == 'ze_':
                            gfl_flag = 1
                            f = open('app/data/map_time_update.txt', 'w')
                            f.write(str(link_steam_addon2))
                            f.close()
                            map_name,height,creator_info = await (map_info_start('https://steamcommunity.com/sharedfiles/filedetails/?id='+addon))
                            link_steam_addon2 = f'https://s2ze.com/maps/{addon}'
                            title = ''
                            text += 'Map name: ['
                            text += map_name
                            text += ']('
                            text += link_steam_addon2
                            text += ')'
                            for i in creator_info:
                                text += '\n'
                                text += ('Creator: '+'['+i[0]+']('+i[1]+')')
                                if i[1] == 'https://steamcommunity.com/id/gflze':
                                    gfl_flag = 0
                            text += '\n'
                            text += 'File Size: **'+height+'**'

                            q = open('app/data/addons.txt', 'r')
                            if not(str(addon)) in q.read():
                                self.stats['new_maps_added'] += 1
                                channel_new = self.bot.get_channel(1321123363732590656)#1321123363732590656
                                l = open('app/data/addons.txt', 'a')
                                l.write(str(addon))
                                l.write('\n')
                                l.close()

                                mapper_id =[]
                                for i in creator_info:
                                    mapper_id.append([(str(SteamID.from_url(i[1]))),i[0]])
 
                                if gfl_flag == 1:
                                    update_mapper_map(mapper_id, map_name.lower())
                                
                                try:
                                    subprocess.run(["python", "upload_data_map.py", addon])
                                except Exception as e:
                                    traceback_info_512 = traceback.format_exc()
                                    pass
                                
                                if gfl_flag == 0:
                                    title += '***GFL REUPLOAD MAP: ***'
                                else:
                                    await channel_new.send('||<@&1284418003261329419>|| **↓↓↓ THE NEW MAP IS BELOW! ↓↓↓**')
                                    title += '***NEW MAP: ***'
                                date = datetime.utcnow()
                                utc_time = '<t:'+str(calendar.timegm(date.utctimetuple()))+':R>'
                                text += '\n'
                                text += 'Release - ' + utc_time
                                text += '\n\n<:logo_3:1347235640756015164> - [Ruby Bot. Join us!](https://discord.gg/e9JSa7Kvwv)'
                                try:
                                    custom_color_new = get_average_color_from_url(link_img_map)
                                    embed_new = discord.Embed(color = int(custom_color_new, 16), title = str(title)+str(map_name))
                                except Exception as e:
                                    embed_new = discord.Embed(color = 0x111f48, title = str(title)+str(map_name))
                                    traceback_info_3 = traceback.format_exc()
                                    pass
                                embed_new.description = text
                                embed_new.set_image(url = link_img_map)
                                message_new = await channel_new.send(embed = embed_new)
                                await message_new.add_reaction('<:green_up:1312455176074035221>')
                                await message_new.add_reaction('<:red_down:1312455178926166128>')
                                custom_send = get_clinet_server_name('new_map')
                                if custom_send:
                                    for i in custom_send:
                                        channel_custom = self.bot.get_channel(int(i[0]))
                                        await channel_custom.send(embed = embed_new)
                                
                                await channel2.send('Bot send new message')
                                await channel2.send('____________________')
                            else:
                                self.stats['maps_updated'] += 1
                                channel = self.bot.get_channel(1267337177583452241)
                                change_log_str = await (map_changelog_start('https://steamcommunity.com/sharedfiles/filedetails/changelog/'+addon))
                                translator = Translator()
                                language = translator.detect(change_log_str).lang
                                flag_lang = 0
                                if str(language) != 'en':
                                    flag_lang = 1
                                    en_change_log = translator.translate(change_log_str, dest='en')
                                    en_change_log = en_change_log.text
                                else:
                                    en_change_log = change_log_str

                                title += 'Addon update: '
                                date = datetime.utcnow()
                                utc_time = '<t:'+str(calendar.timegm(date.utctimetuple()))+':R>'
                                text += '\n'
                                text += 'Changelog - ' + utc_time + ' :'
                                text += '\n'
                                text += '```'
                                text += en_change_log
                                text += '```'
                                if flag_lang == 1:
                                    text += '\n'
                                    text += '*Changelog translated from **'+language+'**'
                                try:
                                    custom_color = hex(get_color(map_name))
                                    embed = discord.Embed(color = int(custom_color, 16), title = str(title)+str(map_name2))
                                except Exception as e:
                                    embed = discord.Embed(color = 0x111f48, title = str(title)+str(map_name2))
                                    traceback_info_2 = traceback.format_exc()
                                    pass
                                embed.description = text
                                embed.set_image(url = link_img_map)
                                message = await channel.send(embed = embed)

                                await message.add_reaction('<:green_up:1312455176074035221>')
                                await message.add_reaction('<:red_down:1312455178926166128>')
                        else:
                            pass
                    else:   
                        pass
                except Exception as e:
                    self.stats['errors'] += 1
                    self._print_formatted(f"Error processing map: {str(e)}", level="ERROR")
                    traceback_info = traceback.format_exc()
                    await channel2.send(f'<@772320334606368788> Error in func1 {e}\n```{traceback_info[:1500]}```')
            except Exception as e:
                self.stats['errors'] += 1
                self._print_formatted(f"CRITICAL ERROR: {str(e)}", level="CRITICAL")
                traceback_info = traceback.format_exc()
                await channel2.send(f'<@772320334606368788> CRITICAL ERROR in func1 {e}\n```{traceback_info[:1500]}```')
            finally:
                execution_time = (datetime.now() - start_time).total_seconds()
                self._print_formatted(f"Cycle completed in {execution_time:.2f} seconds")

    def _print_formatted(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[func1] [{timestamp}] [{level}] {message}\n{'='*60}")

    @loop_task.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()
def setup(bot):
    bot.add_cog(func1(bot))