import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
import json
from datetime import datetime, timedelta, timezone
import calendar
import os
from dotenv import load_dotenv
import asyncio
import aiohttp
import difflib
import traceback
import re
import sqlite3
import resource
import time
from ftplib import FTP
from pathlib import Path

load_dotenv()
DATABASE_WEEK = 'app/data/game/week_charts.db'
DATABASE_NAME = 'app/data/game/map_stats.db'
MAPPER_DATA_FILE = 'app/data/charts/mapper_map.txt'
NOTIFY_PATH = '/app/shared_data/notification.txt'
USER_DATA = '/app/shared_data/user_data.db'

time_min = int(os.getenv('MINUTES_FUNC2'))
time_sec = time_min*60

def create_popular_maps_json(main_massiv_site):
    output_file="app/site/servers/server_info.json"
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        existing_data = {
            "server_list": [],
            "metadata": {
                "last_updated": "",
                "source": "Ruby Bot Ze",
            }
        }
    
    existing_servers = {server["server_ip"]: server for server in existing_data["server_list"]}
    
    for info in main_massiv_site:
        server_ip = info[1]
        map_data = {
            "server_name": info[0],
            "server_ip": server_ip,
            "map_name": info[2],
            "players_now": info[3],
            "players_max": info[4],
            "image_map": info[5],
            "link_map": info[6],
            "last_update": datetime.now().isoformat()
        }
        existing_servers[server_ip] = map_data
    
    updated_server_list = list(existing_servers.values())
    
    result = {
        "server_list": updated_server_list,
        "metadata": {
            "last_updated": datetime.now().isoformat(),
            "source": "Ruby Bot Ze",
        }
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)


def update_players_info(players_data):
    output_file = "app/site/servers/server_info.json"
    
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return
    existing_servers = {server["server_ip"]: server for server in existing_data["server_list"]}
    for server_info in players_data:
        server_ip = server_info[0]
        players_now = server_info[1]
        
        if server_ip in existing_servers:
            existing_servers[server_ip]["players_now"] = players_now
        else:
            pass
    updated_server_list = list(existing_servers.values())
    result = {
        "server_list": updated_server_list,
        "metadata": {
            "last_updated": datetime.now().isoformat(),
            "source": "Ruby Bot Ze",
        }
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

def update_temp_server(msg_id, map_name, server_name, user_id):
    conn = sqlite3.connect('app/data/game/temp_server.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO maps_now (msg_id, map_name, server_name, user_id) VALUES (?, ?, ?, ?)", (msg_id, map_name, server_name, user_id))
    conn.commit()
    conn.close()

def check_temp_server(map_name, server_name):
    conn = None
    try:
        conn = sqlite3.connect('app/data/game/temp_server.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, msg_id, user_id, map_name FROM maps_now WHERE server_name=?", (server_name,))
        results = cursor.fetchall()
        
        output = []
        for result in results:
            db_id, msg_id, user_id, db_map_name = result
            if db_map_name != map_name:
                cursor.execute("DELETE FROM maps_now WHERE msg_id=?", (msg_id,))
                output.append((msg_id, user_id))
        
        conn.commit()
        return output if output else None
    except sqlite3.Error as e:
        return None
    finally:
        if conn:
            conn.close()

def get_fastest_growing_maps():
    conn = sqlite3.connect(DATABASE_WEEK)
    cursor = conn.cursor()
    
    time_limit = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    
    query = '''
        SELECT map_name, COUNT(*) as play_count
        FROM week_charts
        WHERE timestamp >= ?
        GROUP BY map_name
        ORDER BY play_count DESC
        LIMIT 10
    '''
    
    cursor.execute(query, (time_limit,))
    results = cursor.fetchall()
    
    conn.close()
    
    return results

    
def write_to_file(user_id, message):
    with open(NOTIFY_PATH, "a", encoding="utf-8") as file:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file.write(f"{timestamp}|{user_id}|{message}\n")

def get_user_ids_with_map_and_filter(map_name, server_ip):
    conn = sqlite3.connect(USER_DATA)
    cursor = conn.cursor()
    user_ids = []

    cursor.execute("SELECT tg_id, maps, filter FROM users")
    results = cursor.fetchall()

    for user_id, maps_str, filter_json_str in results:
        maps_list = [m.strip() for m in maps_str.split(',') if m.strip()]
        if map_name in maps_list:
            filter_data = json.loads(filter_json_str) if filter_json_str else {}
            if map_name in filter_data:
                ips = filter_data[map_name]
                if ips:
                    ip_list = [ip.strip() for ip in ips[0].split(',')]
                    if server_ip in ip_list:
                        user_ids.append(user_id)
                else:
                    user_ids.append(user_id)

            else:
                user_ids.append(user_id)
                

    conn.close()
    return user_ids
def get_top_mappers(min_minutes=15, limit=100):
    mappers_map = {}
    try:
        with open(MAPPER_DATA_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                match = re.match(r'[^<]*<id_split#qI48>(?P<author>[^<]*)<author_split#8N~1>(?P<maps>.*)', line)
                if match:
                  author = match.group('author')
                  maps = match.group('maps').split('<map_split>')
                  mappers_map[author] = maps
    except FileNotFoundError:
         return []
    
    conn = sqlite3.connect(DATABASE_WEEK)
    cursor = conn.cursor()
    
    mappers_playtime = {}
    for author, maps in mappers_map.items():
         total_minutes = 0
         for map_name in maps:
              cursor.execute('''
              SELECT COUNT(*) FROM week_charts WHERE map_name = ?
              ''', (map_name,))
              count = cursor.fetchone()[0]
              total_minutes += count * time_min
         if total_minutes > 0:
              mappers_playtime[author] = total_minutes

    conn.close()
    sorted_mappers = sorted(mappers_playtime.items(), key=lambda item: item[1], reverse=True)
    filtered_mappers = [(author, minutes) for author, minutes in sorted_mappers if minutes >= min_minutes]
    return filtered_mappers[:limit]

async def get_server_info(json_data):
    try:
        data = json.loads(json_data) if isinstance(json_data, str) else json_data
        server = data.get('response', {}).get('servers', [{}])[0]
        return (
            server.get('max_players'),
            server.get('players'),
            server.get('map'),
            server.get('name'),
        )
    except (KeyError, IndexError, json.JSONDecodeError, TypeError) as e:
        return None, None, None, None


async def fetch_and_process_data(url):
    async with aiohttp.ClientSession() as session:
        response = await asyncio.wait_for(session.get(url), timeout=2.0)
        async with response:
            response.raise_for_status()
            json_data = await response.json(content_type=None)
            if not json_data.get("response"):
                return None, None, None, None
            return await get_server_info(json_data)


def find_closest_match(map_name, map_list):
    if not map_list:
        return None

    closest_match = difflib.get_close_matches(map_name, map_list, n=1, cutoff=0.8)

    if closest_match:
        return closest_match[0]
    else:
        return None

def get_map_info(map):
    with open ('app/data/main/maps.txt', 'r',encoding='UTF-8') as f:
        flag_first = 0
        index_map_name = [((i.split('<map_name>'))[0]).lower() for i in f]
        f2 = open ('app/data/main/maps.txt', 'r',encoding='UTF-8')
        all_data_file = [i for i in f2]
        f2.close()
        best_match = find_closest_match(map, index_map_name)
        if best_match:
            i = all_data_file[index_map_name.index(best_match)]
            flag_first = 1
            image = (((i.split('<image>'))[0]).split('<addon>'))[1]
            link = 'https://s2ze.com/maps/'+(((i.split('<map_name>'))[1]).split('<addon>'))[0]
            if '<color>' in i:
                color = ((i.split('<color>'))[1])
                color_int = int(color, 16)
                return image,link,color_int,(((i.split('<map_name>'))[1]).split('<addon>'))[0]
            else:
                color = '0x111f48'
                color_int = int(color, 16)
                return image,link,color_int,None
        if flag_first == 0:
            return False

def get_clinet_server_name(ip_server):
    conn = sqlite3.connect('app/data/client/tracking.db')
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id FROM tracking WHERE server_ip = ?", (ip_server,))
    result = cursor.fetchall()
    return result

def update_server_data(ip_server, server_name, players_server, map_server):
    conn = sqlite3.connect('app/data/game/server_stats.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, server_name FROM servers WHERE ip_server = ?", (ip_server,))
    result = cursor.fetchone()
    
    if result:
      server_id, old_server_name = result
      if old_server_name != server_name:
         cursor.execute("UPDATE servers SET server_name = ? WHERE id = ?", (server_name, server_id))
    else:
      cursor.execute("INSERT INTO servers (ip_server, server_name) VALUES (?, ?)", (ip_server, server_name))
      server_id = cursor.lastrowid
   
    cursor.execute("INSERT INTO server_stats (server_id, players_server, map_server) VALUES (?, ?, ?)", (server_id, players_server, map_server))
    
    conn.commit()
    conn.close()

def add_file_path(file_path: str):
    path = Path(file_path)
    if not path.exists():
        return False
    
    with sqlite3.connect('app/data/task_maps.db') as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO file_paths (file_name, file_path) VALUES (?, ?)',
            (path.name, str(path.absolute()))
        )
        conn.commit()
    return True
    
def add_map_check(ip_server, map_name):
   
    conn = sqlite3.connect(DATABASE_WEEK)
    cursor = conn.cursor()
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
        INSERT INTO week_charts (ip_server, map_name, timestamp)
        VALUES (?, ?, ?)
    ''', (ip_server, map_name, timestamp))

    conn.commit()
    conn.close()

def get_top_maps(limit=100):
    conn = sqlite3.connect(DATABASE_WEEK)
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT map_name, COUNT(*) AS count
    FROM week_charts
    GROUP BY map_name
    ORDER BY count DESC
    LIMIT ?
    ''', (limit,))
    
    map_counts = cursor.fetchall()
    conn.close()
    
    top_maps = []
    for map_name, count in map_counts:
        total_minutes = count * time_min
        top_maps.append((map_name, total_minutes))
    return top_maps

def delete_old_maps():
    conn = sqlite3.connect(DATABASE_WEEK)
    cursor = conn.cursor()
    
    week_ago = datetime.now() - timedelta(days=7)
    week_ago_str = week_ago.strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
        DELETE FROM week_charts
        WHERE timestamp < ?
    ''', (week_ago_str,))

    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_count

def update_map_playtime(map_name, minutes):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT total_minutes FROM map_stats WHERE map_name = ?', (map_name,))
    result = cursor.fetchone()
    
    if result:
        current_minutes = result[0]
        new_minutes = current_minutes + int(minutes)
        cursor.execute(
            'UPDATE map_stats SET total_minutes = ?, last_played = ? WHERE map_name = ?',
            (new_minutes, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), map_name)
        )
    else:
        cursor.execute(
            'INSERT INTO map_stats (map_name, total_minutes, last_played) VALUES (?, ?, ?)',
            (map_name, minutes, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )

    conn.commit()
    conn.close()
def get_all_servers():
    conn = sqlite3.connect('app/data/charts/servers.db')
    cursor = conn.cursor()
    cursor.execute("SELECT ip_address, port FROM servers")
    servers = cursor.fetchall()
    conn.close()
    return [f"{ip}:{port}" for ip, port in servers]

def update_server_files(server_ip, new_players_count, addon):
    ip_formatted = server_ip.replace(".", "_").replace(":", "+")
    search_prefix = f"on_{ip_formatted}"
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for root, _, files in os.walk(f"app/data/maps/{addon}/"):
        for file in files:
            if file.startswith(search_prefix) and file.endswith(".json"):
                file_path = os.path.join(root, file)
                with open(file_path, 'r+', encoding='utf-8') as f:
                    data = json.load(f)
                    new_entry = {
                        "timestamp": current_time,
                        "online_players": new_players_count
                    }
                    data.append(new_entry)
                    f.seek(0)
                    json.dump(data, f, indent=4, ensure_ascii=False)
                    f.truncate()

class func2(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.loop_task2.start()
        self.cooldowns = {}
        self.log_channel_id = 1270598846606741505
        self.main_channel_id = 1271382329809702912

    def _print_formatted(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[func2] [{timestamp}] [{level}] {message}\n{'='*60}")

    async def _send_report(self, error=None, context="", status_message=None):
        channel = self.bot.get_channel(self.log_channel_id)
        if not channel:
            self._print_formatted("Log channel not found!", level="ERROR")
            return

        if error:
            embed = discord.Embed(
                title="🚨 func2 ERROR REPORT",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Context", value=f"```{context[:1000]}```", inline=False)
            embed.add_field(name="Error", value=f"```{str(error)[:1000]}```", inline=False)
            traceback_info = traceback.format_exc()
            embed.add_field(name="Traceback", value=f"```{traceback_info[:1000]}```", inline=False)
            await channel.send(content="<@772320334606368788>", embed=embed)
        elif status_message:
            embed = discord.Embed(
                title="ℹ️ func2",
                description=status_message,
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            await channel.send(embed=embed)

    async def _generate_final_report(self, start_time, servers_processed, maps_updated):
        execution_time = time.time() - start_time
        mins, secs = divmod(execution_time, 60)
        memory_used = 0
        try:
            if os.name == 'posix':
                memory_used = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            else:
                import ctypes
                PROCESS_QUERY_INFORMATION = 0x0400
                PROCESS_VM_READ = 0x0010
                handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, os.getpid())
                process_memory = ctypes.c_ulonglong()
                ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(process_memory), ctypes.sizeof(process_memory))
                memory_used = process_memory.value / (1024 * 1024)
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception as e:
            self._print_formatted(f"Memory monitoring error: {str(e)}", level="WARNING")

        deleted_count = delete_old_maps()
        top_maps = get_top_maps(limit=5)
        top_mappers = get_top_mappers(limit=5)
        
        embed = discord.Embed(
            title="📊 func2 - FINAL REPORT",
            color=0x00ff00,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="📈 Processing Stats",
            value=(
                f"• Servers Processed: **{servers_processed}\n**"
                f"• Maps Updated: **{maps_updated}\n**"
                f"• Old Records Deleted: **{deleted_count}\n**"
                f"• Execution Time: **{int(mins)}m {int(secs)}s**\n"
                f"• Memory Used: **{memory_used:.2f} MB**"
            ),
            inline=False
        )
        
        top_maps_str = "\n".join([f"{i}. {map} - {mins}m" for i, (map, mins) in enumerate(top_maps, 1)])
        top_mappers_str = "\n".join([f"{i}. {mapper} - {mins}m" for i, (mapper, mins) in enumerate(top_mappers, 1)])
        
        embed.add_field(name="🏆 Top Maps", value=top_maps_str or "No data", inline=True)
        embed.add_field(name="👑 Top Mappers", value=top_mappers_str or "No data", inline=True)
        
        if execution_time > time_sec * 1.5:
            embed.add_field(
                name="⚠️ Performance Warning",
                value="Execution took longer than expected!",
                inline=False
            )
        
        embed.set_footer(text=f"Cycle completed at {datetime.utcnow().strftime('%H:%M:%S UTC')}")
        
        return embed

    @tasks.loop(seconds=time_sec)
    async def loop_task2(self):
        try:
            start_time = time.time()
            servers_processed = 0
            maps_updated = 0
            key_os = os.getenv('KEY')
            channel = self.bot.get_channel(1271382329809702912)
            channel2 = self.bot.get_channel(1270598846606741505)
            channel3 = self.bot.get_channel(1284168743047397446)
            channel_np = self.bot.get_channel(1386010425165873203)
            channel_mappers = self.bot.get_channel(1310989584779313242)
            main_massiv_site = []
            players_data_site = []
            if channel:
                self._print_formatted("**STARTING PROCESSING**")
                server = get_all_servers()
                for i in server:
                    try:
                        servers_processed += 1
                        flag_maps_now = 0
                        url = "https://api.steampowered.com/IGameServersService/GetServerList/v1/?key="+key_os+"&filter=addr\\"+str(i)
                        ip_server = i  
                        max_players, players_server, map_server, server_name = await fetch_and_process_data(url)
                        date_play_now = datetime.utcnow()
                        utc_time_play_now = '<t:'+str(calendar.timegm(date_play_now.utctimetuple()))+':R>'  
                        if (max_players is not None) and (players_server is not None) and (map_server is not None) and (server_name is not None):
                            if (ip_server.replace('\n','') == '46.174.53.69:27019') or (ip_server.replace('\n','') == '74.91.124.21:27015') or (ip_server.replace('\n','') == '87.98.228.196:27040') or (ip_server.replace('\n','') == '14.6.92.207:27015') or (ip_server.replace('\n','') == '178.33.160.187:27015'):
                                update_server_data(str(ip_server).replace('\n',''), str(server_name).replace('\n',''), str(players_server).replace('\n',''), str(map_server).replace('\n',''))
                            flag_inf = 0
                            try:
                                if get_map_info(map_server):
                                    flag_inf = 1
                                    inf_img,inf_lnk,color,addon_name = get_map_info(map_server)
                                    inf_img = inf_img.replace('?imw=116&imh=65&ima=fit&impolicy=Letterbox&imcolor=%23000000&letterbox=false','?imw=5000&imh=5000&ima=fit&impolicy=Letterbox&imcolor=%23000000&letterbox=false')
                                    inf_img = inf_img.replace('imw=200', 'imw=5000')
                                    inf_img = inf_img.replace('imh=112', 'imh=5000')
                                    inf_img = inf_img.replace('letterbox=true', 'letterbox=false')
                                else:
                                    color = 1122120
                                    addon_name = None
                            except:
                                color = 1122120
                                flag_inf = 0
                                addon_name = None
                            map_now = open('app/data/charts/map_now.txt','r+')
                            maps_now = [i.replace('\n','') for i in map_now]
                            for i in range(len(maps_now)):
                                ip_server = ip_server.replace('\n', '')
                                maps_now2 = maps_now[i].replace('\n', '')
                                if ip_server in maps_now2:
                                    flag_maps_now += 1
                                    split_map_now = maps_now2.split('$')
                                    if split_map_now[1] != map_server:
                                        print('Ip server: '+ip_server+' Old map: '+ split_map_now[1]+' ; New map: '+ str(map_server))
                                        if flag_inf == 1:
                                            main_massiv_site.append([server_name,ip_server,map_server,int(players_server),int(max_players),inf_img,inf_lnk])
                                        else:
                                            main_massiv_site.append([server_name,ip_server,map_server,int(players_server),int(max_players),'https://images.steamusercontent.com/ugc/63720412782104540/4A950EBE1CBF496CCB8E581DD5A68AA63F668EA0/?imw=5000&imh=5000&ima=fit&impolicy=Letterbox&imcolor=%23000000&letterbox=false','https://steamcommunity.com/app/730/workshop/'])
                                        maps_updated += 1
                                        try:
                                            if addon_name:
                                                time_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                                                time_m = [{
                                                    "timestamp": time_now,
                                                    "online_players": players_server
                                                }]
                                                output_data = f'app/data/maps/{addon_name}/on_{ip_server.replace(".","_").replace(":","+")}-{datetime.now(timezone.utc).strftime("%Y-%m-%dH-%M-%SZ")}.json'
                                                with open(output_data, 'w', encoding='utf-8') as f:
                                                    json.dump(time_m, f, indent=4, ensure_ascii=False)

                                                file_name = output_data.split('/')[-1].replace('on_','off_')
                                                map_file_path = f'app/data/maps/{addon_name}/{addon_name}.json'
                                                with open(map_file_path, 'r', encoding='utf-8') as f:
                                                    map_data = json.load(f)
                                                new_entry = {
                                                    "timestamp": time_now,
                                                    "name": file_name,
                                                    "server-name": server_name,
                                                    "server-ip": ip_server
                                                }
                                                map_data['mapstime'].append(new_entry)
                                                with open(map_file_path, 'w', encoding='utf-8') as f:
                                                    json.dump(map_data, f, indent=4, ensure_ascii=False)

                                                add_file_path(output_data)
                                        except:
                                            pass

                                        info_temp_client_all = check_temp_server(map_server,ip_server)

                                        if info_temp_client_all:
                                            for info_temp_client in info_temp_client_all:
                                                user_temp = await self.bot.fetch_user(info_temp_client[1])
                                                dm_channel = user_temp.dm_channel or await user_temp.create_dm()
                                                message_temp = await dm_channel.fetch_message(info_temp_client[0])
                                                embed = message_temp.embeds[0]
                                                new_embed = discord.Embed.from_dict(embed.to_dict())
                                                new_embed.description = embed.description.replace('Status: **Enabled**', 'Status: **Disabled**')
                                                await message_temp.edit(embed=new_embed)

                                        if flag_inf == 1:
                                            text_play_now = ''
                                            text_play_now += '**'+str(server_name)+'**'
                                            conncect_np = 'https://s2ze.com/connect.php?ip='+str(ip_server)
                                            text_play_now += '\n'
                                            text_play_now += 'Map name: **['+str(map_server)+"]("+inf_lnk+")**"
                                            text_play_now += '\n'
                                            text_play_now += 'Players: **'+ str(players_server)+'/'+str(max_players)+'**'
                                            text_play_now += '\n'
                                            text_play_now += 'Connect: '+'**['+str(ip_server)+']'+'('+str(conncect_np)+')**'
                                            text_play_now += '\n'
                                            text_play_now += '-# Time launch:'+utc_time_play_now
                                            embed_play_now = discord.Embed(color =discord.Colour(color))
                                            embed_play_now.description = text_play_now
                                            embed_play_now.set_thumbnail(url = inf_img)
                                            message_np = await channel_np.send(embed = embed_play_now)
                                            message_id = message_np.id
                                        else:
                                            text_play_now = ''
                                            text_play_now += '**'+str(server_name)+'**'
                                            conncect_np = 'https://s2ze.com/connect.php?ip='+str(ip_server)
                                            text_play_now += '\n'
                                            text_play_now += 'Map name: **'+str(map_server)+"**"
                                            text_play_now += '\n'
                                            text_play_now += 'Players: **'+ str(players_server)+'/'+str(max_players)+'**'
                                            text_play_now += '\n'
                                            text_play_now += 'Connect: '+'**['+str(ip_server)+']'+'('+str(conncect_np)+')**'
                                            text_play_now += '\n'
                                            text_play_now += '-# Time launch:'+utc_time_play_now
                                            embed_play_now = discord.Embed(color =discord.Colour(color))
                                            embed_play_now.description = text_play_now
                                            message_np = await channel_np.send(embed = embed_play_now)
                                            message_id = message_np.id
                                            
                                        mapsp_np = str(message_id)+'$'+str(ip_server)+'\n'
                                        old_sp_np = ''
                                        old_sp_np2 = ''
                                        f_np = open('app/data/now_playing/id_collection.txt', 'r')
                                        flag_new_server_np = 0
                                        for i in f_np:
                                            if ip_server in i:
                                                    old_sp_np = i
                                                    old_sp_np2 = i
                                                    flag_new_server_np += 1
                                                    break
                                        if flag_new_server_np == 0:
                                            with open ('app/data/now_playing/id_collection.txt', 'a') as f:
                                                f.write(mapsp_np)
                                                print(mapsp_np+'Map_sp')
                                        else:
                                            ip_old_np = (old_sp_np.split('$'))[0]
                                            msg = await channel_np.fetch_message(ip_old_np)
                                            await msg.delete()
                                            with open ('app/data/now_playing/id_collection.txt', 'r') as f:
                                                old_data = f.read()
                                            new_data_np = old_data.replace(old_sp_np2, mapsp_np)
                                            with open ('app/data/now_playing/id_collection.txt', 'w') as f:
                                                f.write(new_data_np)

                                        maps_now_new  = ip_server+'$'+str(map_server)
                                        with open ('app/data/charts/map_now.txt', 'r') as f:
                                            old_data1 = f.read()
                                        new_data1 = old_data1.replace(maps_now2, maps_now_new)
                                        with open ('app/data/charts/map_now.txt', 'w') as f:
                                            f.write(new_data1)
                                            
                                        conn = sqlite3.connect('app/data/client/notify_list.db')
                                        c = conn.cursor()
                                        c.execute("""
                                            SELECT client_id
                                            FROM notifications
                                            WHERE map_name = ?
                                            AND (map_filter IS NULL OR map_filter = '' OR map_filter LIKE '%' || ? || '%')
                                        """, (map_server, ip_server))
                                        users = c.fetchall()
                                        conn.close()
                                        if users:
                                            for user in users:
                                                user_id = user[0] 
                                                user = await self.bot.fetch_user(user_id) 
                                                if flag_inf == 1:
                                                    textn = ''
                                                    textn += 'Now Playing: **['+str(map_server)+']('+inf_lnk+')**'
                                                    textn += '\n'
                                                    textn += 'Players Online: **'+str(players_server)+'/'+str(max_players)+'**'
                                                    textn += '\n'
                                                    conncectn = 'https://s2ze.com/connect.php?ip='+ip_server
                                                    textn += 'Quick Join: **['+ip_server+']('+conncectn+')**\n'
                                                    textn += 'Status: **Enabled**\n'
                                                    textn += f'-# Use the `/server {ip_server}` command to get up-to-date information about the server.'
                                                    embedn = discord.Embed(color =discord.Colour(color), title = str(server_name))
                                                    embedn.description = textn
                                                    embedn.set_thumbnail(url = inf_img)
                                                    message_clinet = await user.send(embed = embedn)
                                                    print('send message')
                                                else:
                                                    textn = ''
                                                    textn += 'Now Playing: **'+str(map_server)+'**'
                                                    textn += '\n'
                                                    textn += 'Players Online: **'+str(players_server)+'/'+str(max_players)+'**'
                                                    textn += '\n'
                                                    conncectn = 'https://s2ze.com/connect.php?ip='+ip_server
                                                    textn += 'Quick Join: **['+ip_server+']('+conncectn+')**\n'
                                                    textn += 'Status: **Enabled**\n'
                                                    textn += f'-# Use the `/server {ip_server}` command to get up-to-date information about the server.'
                                                    embedn = discord.Embed(color =discord.Colour(color), title = str(server_name))
                                                    embedn.description = textn
                                                    message_clinet = await user.send(embed = embedn)
                                                    print('send message')
                                                update_temp_server(message_clinet.id, map_server,ip_server,user_id)
                                        server_clinet = get_clinet_server_name(ip_server)
                                        if server_clinet:
                                            for channel_custom in server_clinet:
                                                channel_custom_send = self.bot.get_channel(int(channel_custom[0]))
                                                if flag_inf == 1:
                                                    text_play_now = ''
                                                    text_play_now += '**'+str(server_name)+'**'
                                                    conncect_np = 'https://s2ze.com/connect.php?ip='+str(ip_server)
                                                    text_play_now += '\n'
                                                    text_play_now += 'Map name: **['+str(map_server)+"]("+inf_lnk+")**"
                                                    text_play_now += '\n'
                                                    text_play_now += 'Players: **'+ str(players_server)+'/'+str(max_players)+'**'
                                                    text_play_now += '\n'
                                                    text_play_now += 'Connect: '+'**['+str(ip_server)+']'+'('+str(conncect_np)+')**'
                                                    text_play_now += '\n'
                                                    text_play_now += '-# Time launch:'+utc_time_play_now
                                                    embed_play_custom = discord.Embed(color = discord.Colour(color))
                                                    embed_play_custom.description = text_play_now
                                                    embed_play_custom.set_thumbnail(url = inf_img)
                                                    await channel_custom_send.send(embed = embed_play_custom)
                                                else:
                                                    text_play_now = ''
                                                    text_play_now += '**'+str(server_name)+'**'
                                                    conncect_np = 'https://s2ze.com/connect.php?ip='+str(ip_server)
                                                    text_play_now += '\n'
                                                    text_play_now += 'Map name: **'+str(map_server)+"**"
                                                    text_play_now += '\n'
                                                    text_play_now += 'Players: **'+ str(players_server)+'/'+str(max_players)+'**'
                                                    text_play_now += '\n'
                                                    text_play_now += 'Connect: '+'**['+str(ip_server)+']'+'('+str(conncect_np)+')**'
                                                    text_play_now += '\n'
                                                    text_play_now += '-# Time launch:'+utc_time_play_now
                                                    embed_play_custom = discord.Embed(color = discord.Colour(color))
                                                    embed_play_custom.description = text_play_now
                                                    await channel_custom_send.send(embed = embed_play_custom)
                                    else:
                                        players_data_site.append([ip_server,players_server])
                                        try:
                                            if addon_name:
                                                print(update_server_files(ip_server,players_server,addon_name))
                                        except:
                                            pass
                                    break
                            if flag_maps_now == 0:
                                map_now_info = str(ip_server+'$'+map_server)
                                map_now_info = map_now_info.replace('\n','')
                                print('add server in map_now.txt '+ map_now_info)
                                map_now.write(map_now_info)
                                map_now.write('\n')
                            
                            map_now.close()
                            print(f'Server: {server_name}, map: {map_server}, players: {players_server}')
                            if (int(players_server) >= 25) and (str(map_server)[:3] == 'ze_'):
                                add_map_check(str(ip_server).replace('\n',''), str(map_server).replace('\n',''))
                                update_map_playtime(str(map_server).replace('\n',''), int(str(time_min).replace('\n','')))
                            if (int(players_server) >= 0) and (str(map_server)[:3] == 'ze_'):
                                flag_act_map = 0
                                clent_map = open('app/data/client/client_name_map.txt','r',encoding='UTF-8')
                                for i in clent_map:
                                    if map_server in i: 
                                        flag_act_map = 1
                                        clent_map.close()
                                        break
                                if flag_act_map == 0:
                                    with open ('app/data/client/client_name_map.txt', 'a') as f:
                                        f.write(map_server)
                                        f.write('\n')
                                    if flag_inf == 1:
                                        text_n = ''
                                        conncect = 'https://s2ze.com/connect.php?ip='+str(ip_server)
                                        text_n += 'Server name: **' + str(server_name)+'**'
                                        text_n += '\n'
                                        text_n += 'Map name: **['+str(map_server)+']('+inf_lnk+')**'
                                        text_n += '\n'
                                        text_n += 'Players: **'+ str(players_server)+' / '+str(max_players)+'**'
                                        text_n += '\n'
                                        text_n += 'Connect: '+'**['+str(ip_server)+']'+'('+str(conncect)+')**'
                                        date_n = datetime.utcnow()
                                        utc_time_n = '<t:'+str(calendar.timegm(date_n.utctimetuple()))+':R>'
                                        text_n += '\n'
                                        text_n += '-# '+utc_time_n
                                        embed2 = discord.Embed(color = color, title = 'The '+ str(map_server) +' map is launched for the first time!')
                                        embed2.description = text_n
                                        embed2.set_thumbnail(url = inf_img)
                                        await channel3.send('||<@&1284426751174512681>|| Play now on the **'+str(map_server)+'**!')
                                        message = await channel3.send(embed = embed2)
                                        get_server_send_pl = get_clinet_server_name('play_new_maps')
                                        if get_server_send_pl:
                                            for channel_custom in get_server_send_pl:
                                                channel_cstm = self.bot.get_channel(int(channel_custom[0]))
                                                await channel_cstm.send(embed = embed2)
                                    else:
                                        text_n = ''
                                        conncect = 'https://s2ze.com/connect.php?ip='+str(ip_server)
                                        text_n += 'Server name: **' + str(server_name)+'**'
                                        text_n += '\n'
                                        text_n += 'Map name: **'+str(map_server)+'**'
                                        text_n += '\n'
                                        text_n += 'Players: **'+ str(players_server)+' / '+str(max_players)+'**'
                                        text_n += '\n'
                                        text_n += 'Connect: '+'**['+str(ip_server)+']'+'('+str(conncect)+')**'
                                        date_n = datetime.utcnow()
                                        utc_time_n = '<t:'+str(calendar.timegm(date_n.utctimetuple()))+':R>'
                                        text_n += '\n'
                                        text_n += '-# '+utc_time_n
                                        embed2 = discord.Embed(color = color, title = 'The '+ str(map_server) +' map is launched for the first time!')
                                        embed2.description = text_n
                                        await channel3.send('||<@&1284426751174512681>|| Play now on the **'+str(map_server)+'**!')
                                        get_server_send_pl = get_clinet_server_name('play_new_maps')
                                        message = await channel3.send(embed = embed2)
                                        get_server_send_pl = get_clinet_server_name('play_new_maps')
                                        if get_server_send_pl:
                                            for channel_custom in get_server_send_pl:
                                                channel_cstm = self.bot.get_channel(int(channel_custom[0]))
                                                await channel_cstm.send(embed = embed2)
                    except Exception as e:
                        self._print_formatted(f"Error processing server: {str(e)}", level="ERROR")
                        await self._send_report(error=e, context=f"Processing server {i}")
                update_players_info(players_data_site)
                create_popular_maps_json(main_massiv_site)
                deleted_count = delete_old_maps()
                self._print_formatted(f"Cleaned database: removed {deleted_count} old records")
                date_21344 = datetime.utcnow()
                utc_time = '<t:'+str(calendar.timegm(date_21344.utctimetuple()))+':R>'
                top_mappers = get_top_mappers()
                mapper_update = ''
                for i, (mapper, minutes) in enumerate(top_mappers, 1):
                    mapper_update += (f"{i}. {mapper} - {minutes} minutes\n")

                if len(mapper_update) > 4030:
                    mapper_update = mapper_update[:4030]
                mapper_update += '-# Last update: '+utc_time
                embed_mapper = discord.Embed(color = 0x111f48, title = 'The 100 Most Popular ZE Mappers [WEEK]')
                embed_mapper.description = mapper_update
                try:
                    message_mapper = await channel_mappers.fetch_message(1310996128904384595)
                    await message_mapper.edit(embed = embed_mapper)
                except Exception as e:
                    await self._send_report(error=e, context="Updating mappers leaderboard")

                final_embed = await self._generate_final_report(start_time, servers_processed, maps_updated)
                await channel2.send(embed=final_embed)
            else:
                print("Channel not found.")
        except Exception as e:
            self._print_formatted(f"CRITICAL ERROR: {str(e)}", level="CRITICAL")
            await self._send_report(error=e, context="Main processing loop")

    @loop_task2.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

def setup(bot):
    bot.add_cog(func2(bot))