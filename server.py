from steam.steamid import SteamID
import discord
from discord.ext import commands
import aiohttp
import json
from dotenv import load_dotenv
import os
import difflib

async def fetch_and_process_data(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            json_data = await response.json(content_type=None)
            return await get_server_info(json_data)
    
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
        print(f"Ошибка: {e}, данные: {json_data}")
        return None, None, None, None
    
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
                return image,link,color_int
            else:
                color = '0x111f48'
                color_int = int(color, 16)
                return image,link,color_int
        if flag_first == 0:
            return False

def find_closest_match(map_name, map_list):
    if not map_list:
        return None

    closest_match = difflib.get_close_matches(map_name, map_list, n=1, cutoff=0.8)

    if closest_match:
        return closest_match[0]
    else:
        return None
@commands.slash_command(name="server", description="Check server info")
async def server(ctx: discord.ApplicationContext, server_ip: str):
    clent_id = ctx.author.id
    try:
        load_dotenv()
        key_os = os.getenv('KEY')
        url = "https://api.steampowered.com/IGameServersService/GetServerList/v1/?key="+key_os+"&filter=addr\\"+str(server_ip)
        max_players, players_server, map_server, server_name = await fetch_and_process_data(url)
        if (max_players is not None) and (players_server is not None) and (map_server is not None) and (server_name is not None):
            flag_inf = 0
            if get_map_info(map_server):
                flag_inf = 1
                inf_img,inf_lnk,color = get_map_info(map_server)
                inf_img = inf_img.replace('?imw=116&imh=65&ima=fit&impolicy=Letterbox&imcolor=%23000000&letterbox=false','?imw=5000&imh=5000&ima=fit&impolicy=Letterbox&imcolor=%23000000&letterbox=false')
                inf_img = inf_img.replace('imw=200', 'imw=5000')
                inf_img = inf_img.replace('imh=112', 'imh=5000')
                inf_img = inf_img.replace('letterbox=true', 'letterbox=false')
            else:
                color = 1122120

            if flag_inf == 1:
                text_play_now = ''
                conncect_np = 'https://s2ze.com/connect.php?ip='+str(server_ip)
                text_play_now += 'Map name: **['+str(map_server)+"]("+inf_lnk+")**"
                text_play_now += '\n'
                text_play_now += 'Players: **'+ str(players_server)+'/'+str(max_players)+'**'
                text_play_now += '\n'
                text_play_now += 'Connect: '+'**['+str(server_ip)+']'+'('+str(conncect_np)+')**'
                embed_play_now = discord.Embed(color =discord.Colour(color), title = str(server_name))
                embed_play_now.description = text_play_now
                embed_play_now.set_thumbnail(url = inf_img)
                await ctx.respond(embed = embed_play_now)
            else:
                text_play_now = ''
                conncect_np = 'https://s2ze.com/connect.php?ip='+str(server_ip)
                text_play_now += 'Map name: **'+str(map_server)+"**"
                text_play_now += '\n'
                text_play_now += 'Players: **'+ str(players_server)+'/'+str(max_players)+'**'
                text_play_now += '\n'
                text_play_now += 'Connect: '+'**['+str(server_ip)+']'+'('+str(conncect_np)+')**'
                embed_play_now = discord.Embed(color =discord.Colour(color), title = str(server_name))
                embed_play_now.description = text_play_now
                await ctx.respond(embed = embed_play_now)
                
        else:
            await ctx.respond("**Unknown server IP.**", ephemeral=True)
    except Exception as e:
        await ctx.respond("ERROR! Check the **server ip**", ephemeral=True)
        print(f'Error server.py : {e}')
def setup(bot: discord.Bot):
    bot.add_application_command(server)