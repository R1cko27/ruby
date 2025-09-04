import discord
from discord.ext import commands, tasks
import os
import random
import time
import asyncio
import sqlite3

IMAGE_FOLDER = "app/data/image"  
DATABASE_PATH = "app/data/games/user_scores.db"  

def init_db():
    if not os.path.exists(DATABASE_PATH):
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_scores (
            user_id INTEGER PRIMARY KEY,
            score INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def get_user_score(user_id):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT score FROM user_scores WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def update_user_score(user_id, score):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_scores (user_id, score) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET score = ?
    """, (user_id, score, score))
    conn.commit()
    conn.close()

async def get_random_map():
    maps = [f for f in os.listdir(IMAGE_FOLDER) if f.endswith('_1.jpg')]
    if not maps:
        return None, None
    selected = random.choice(maps)
    real_name = selected.rsplit('_1.jpg', 1)[0]
    return selected, real_name

def get_hint(correct, guess, hint_level):
    common_prefix = ""
    min_length = min(len(correct), len(guess))
    for i in range(min_length):
        if correct[i] == guess[i]:
            common_prefix += correct[i]
        else:
            break

    if common_prefix:
        hint = correct[:len(common_prefix) + 2]
    else:
        hint = correct[:hint_level + 1]
    return hint

class ZEGuesser(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}  
        init_db()

    async def update_score_timer(self, user_id):
        while user_id in self.active_games:
            await asyncio.sleep(1)  
            try:
                if user_id in self.active_games:  
                    game_data = self.active_games[user_id]
                    game_data['score'] = max(0, game_data['score'] - 2)  
            except Exception as e:
                print(f"Error in score timer: {e}")
                break  

    @commands.slash_command(name="ze_guesser", description="Guess the Zombie Escape map")
    async def ze_guesser(self, ctx: discord.ApplicationContext):
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.respond("This command is only available in private messages.", ephemeral=True)
            return
        user_id = ctx.author.id
        
        if user_id in self.active_games:
            await ctx.respond("Game is already active! Wait for it to finish.", ephemeral=True)
            return

        file, real_name = await get_random_map()
        
        if not file:
            await ctx.respond("No maps found for guessing!", ephemeral=True)
            return

        current_score = get_user_score(user_id)

        self.active_games[user_id] = {
            'real_name': real_name,
            'attempts': 3,
            'hint_level': 0,
            'file': file,
            'start_time': time.time(),  
            'score': 100,  
            'errors': 0,  
            'user_id': user_id,
            'current_score': current_score,  
            'channel_id': ctx.channel_id
        }

        asyncio.create_task(self.update_score_timer(user_id))

        with open(f'{IMAGE_FOLDER}/{file}', 'rb') as photo:
            file = discord.File(photo, filename="map.jpg")
            embed = discord.Embed(
                title="Guess the map name!",
                description="You have 3 attempts. Type the map name in chat.",
                color=discord.Color.blue()
            )
            embed.set_image(url="attachment://map.jpg")
            await ctx.respond(file=file, embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        user_id = message.author.id
        if user_id not in self.active_games:
            return

        game_data = self.active_games[user_id]
        if message.channel.id != game_data['channel_id']:
            return

        guess = message.content.strip().lower()
        correct = game_data['real_name'].lower()

        correct_no_suffix = correct.replace("_p", "").replace("_cs2", "")
        
        if guess == correct or guess == correct_no_suffix:
            final_score = game_data['score']
            user_id = game_data['user_id']
            current_score = game_data['current_score'] + final_score
            update_user_score(user_id, current_score)  

            with open(f'{IMAGE_FOLDER}/{game_data["real_name"]}.jpg', 'rb') as photo:
                file = discord.File(photo, filename="map.jpg")
                embed = discord.Embed(
                    title=f"✅ Correct!",
                    description=f"It's **{game_data['real_name']}**\nYou earned **{final_score}** points\nYour bank: **{current_score}**",
                    color=discord.Color.green()
                )
                embed.set_image(url="attachment://map.jpg")
                await message.channel.send(file=file, embed=embed)
            del self.active_games[user_id]
            return

        game_data['attempts'] -= 1
        game_data['errors'] += 1

        penalty = 10 * game_data['errors']
        game_data['score'] = max(0, game_data['score'] - penalty)
        
        if game_data['attempts'] > 0:
            hint = get_hint(correct, guess, game_data['hint_level'])
            game_data['hint_level'] = len(hint)
            embed = discord.Embed(
                title="❌ Incorrect!",
                description=f"Attempts left: **{game_data['attempts']}**\nHint: `{hint}...`\nPenalty: **-{penalty}** points.",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)
        else:
            user_id = game_data['user_id']
            current_score = max(0, game_data['current_score'] - 30)  
            update_user_score(user_id, current_score)  

            with open(f'{IMAGE_FOLDER}/{game_data["real_name"]}.jpg', 'rb') as photo:
                file = discord.File(photo, filename="map.jpg")
                embed = discord.Embed(
                    title="❌ No attempts left!",
                    description=f"Correct answer: **{correct}**\nPenalty: **-30** points.\nYour bank: **{current_score}**",
                    color=discord.Color.red()
                )
                embed.set_image(url="attachment://map.jpg")
                await message.channel.send(file=file, embed=embed)
            del self.active_games[user_id]

def setup(bot: discord.Bot):
    bot.add_cog(ZEGuesser(bot))