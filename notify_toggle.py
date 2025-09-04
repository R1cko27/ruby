import discord
from discord.ext import commands
import difflib
import sqlite3


class MyView(discord.ui.View):
    def __init__(self, map_name2: str, client_id: int, arg: str):
        super().__init__()
        self.map_name2 = map_name2
        self.client_id = client_id
        self.arg = arg

    async def update_notifications(self, client_id, map_name, interaction, add=True):
        conn = sqlite3.connect('app/data/client/notify_list.db')
        c = conn.cursor()
        if add:
            c.execute("INSERT INTO notifications (client_id, map_name) VALUES (?, ?)", (client_id, map_name))
            await interaction.response.send_message(f'<@{client_id}> Adding **{map_name}** to your map notifications!\nUse **/notify_list** to view a list of your maps', ephemeral=True)
        else:
            c.execute("DELETE FROM notifications WHERE client_id = ? AND map_name = ?", (client_id, map_name))
            await interaction.response.send_message(f'<@{client_id}> Remove **{map_name}** from your map notifications!', ephemeral=True)
        conn.commit()
        conn.close()

    @discord.ui.button(label='1', style=discord.ButtonStyle.blurple)
    async def button_callback(self, button, interaction):
        client_id = self.client_id
        map_name = self.map_name2
        conn = sqlite3.connect('app/data/client/notify_list.db')
        c = conn.cursor()
        c.execute("SELECT * FROM notifications WHERE client_id = ? AND map_name = ?", (client_id, map_name))
        if c.fetchone():
            await self.update_notifications(client_id, map_name, interaction, add=False)
        else:
            await self.update_notifications(client_id, map_name, interaction, add=True)
        conn.close()
        await interaction.message.delete()

    @discord.ui.button(label='2', style=discord.ButtonStyle.blurple)
    async def button_callback2(self, button, interaction):
        client_id = self.client_id
        map_name = self.arg
        conn = sqlite3.connect('app/data/client/notify_list.db')
        c = conn.cursor()
        c.execute("SELECT * FROM notifications WHERE client_id = ? AND map_name = ?", (client_id, map_name))
        if c.fetchone():
            await self.update_notifications(client_id, map_name, interaction, add=False)
        else:
            await self.update_notifications(client_id, map_name, interaction, add=True)
        conn.close()
        await interaction.message.delete()

    @discord.ui.button(label='3', style=discord.ButtonStyle.blurple)
    async def button_callback3(self, button, interaction):
        await interaction.message.delete()

@commands.slash_command(name="notify_toggle", description='Add / Delete map from your notification list')
async def notify_toggle(ctx: discord.ApplicationContext, map_name: str):
    await ctx.defer()
    arg = map_name
    maps_list = open('app/data/client/client_name_map.txt', encoding="utf-8")
    a = [i for i in maps_list]
    maps = difflib.get_close_matches(map_name, a)
    client_id = ctx.author.id
    if len(maps) != 0:
        map_name2 = maps[0].replace('\n', '')
        text = ''
        text1 = 'You mean the map: ' + map_name2 + '?'
        text += '\n'
        text += '**1.** Add/remove, **' + map_name2 + '** in your notification list'
        text += '\n'
        text += '**2.** Add/remove, **' + map_name + '** in your notification list'
        text += '\n'
        text += '**3.** Cancel'
        embed = discord.Embed(color=0x111f48, title=text1)
        embed.description = text
        print(map_name)
        if (not ('$') in map_name) and (not (';') in map_name):
            message = await ctx.respond(embed=embed, view=MyView(map_name2, client_id, arg), ephemeral=True)
        else:
            message = await ctx.respond('The characters **"$"** and **";"** are not allowed to be used', ephemeral=True)
    else:
        text = ''
        text1 = 'I dont have any information about this map'
        text += '\n'
        text += '**1.** Add/remove, **' + arg + '** in your notification list'
        text += '\n'
        text += '**2.** Add/remove, **' + arg + '** in your notification list'
        text += '\n'
        text += '**3.** Cancel'
        map_name2 = arg
        embed = discord.Embed(color=0x111f48, title=text1)
        embed.description = text
        if (not ('$') in map_name) and (not (';') in map_name):
            message = await ctx.respond(embed=embed, view=MyView(map_name2, client_id, arg), ephemeral=True)
        else:
            message = await ctx.respond('The characters **"$"** and **";"** are not allowed to be used', ephemeral=True)

def setup(bot: discord.Bot):
    bot.add_application_command(notify_toggle)