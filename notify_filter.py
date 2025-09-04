import discord
from discord.ext import commands
import sqlite3

def update_map_filter(db_name, client_id, map_name, map_filter):
    text = ''
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT map_filter FROM notifications
            WHERE client_id = ? AND map_name = ?
        """, (client_id, map_name))
        result = cursor.fetchone()

        if result:
            existing_filters = result[0]
            if existing_filters:
                filter_list = [f.strip() for f in existing_filters.split(',')]

                if map_filter in filter_list:
                    filter_list.remove(map_filter)
                    text = (f"The filter **{map_filter}** for the **{map_name}** map has been **removed**!")
                else:
                    filter_list.append(map_filter)
                    text = (f"**Added** a filter **{map_filter}** on the map **{map_name}**!")
                updated_filters = ', '.join(filter_list)
                cursor.execute("""
                    UPDATE notifications
                    SET map_filter = ?
                    WHERE client_id = ? AND map_name = ?
                """, (updated_filters, client_id, map_name))

            else:
                cursor.execute("""
                    UPDATE notifications
                    SET map_filter = ?
                    WHERE client_id = ? AND map_name = ?
                """, (map_filter, client_id, map_name))
                text = (f"**Added** a filter **{map_filter}** on the map **{map_name}**!")

        else:
            text = (f"The **{map_name}** map is **missing from your notification list**.\n**/notify_toggle** command - to add map\n**/notify_list** command - Check your notification list")
            conn.rollback() 

        conn.commit()

    except sqlite3.Error as e:
        text = (f"Unknown error. Use the /report command to report it.")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
    return text

@commands.slash_command(name="notify_filter", description='Add a filter to your map')
async def notify_filter(ctx: discord.ApplicationContext,map_name: str,server_ip:str):
    try:
        client_id = ctx.author.id
        if ',' in server_ip:
            await ctx.respond(f'It is **forbidden** to use the **"," symbol**', ephemeral=True)
        else:
            text = update_map_filter('app/data/client/notify_list.db', client_id, map_name, server_ip)
            await ctx.respond(f'{text}\n-# If there is a filter on the map, then notifications for this map will come only from servers that are in the filter.', ephemeral=True)
    except:
        await ctx.respond(f'Unknown error. Use the /report command to report it.', ephemeral=True)
def setup(bot: discord.Bot):
    bot.add_application_command(notify_filter)