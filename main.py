import discord
from discord.ext import commands, tasks
import json
import requests
import asyncio
import os
from datetime import datetime

with open('data/secret.json') as secret_file:
    secret_data = json.load(secret_file)
    bot_token = secret_data['token']

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='?', intents=intents, help_command=None)

cache_time = None
status_messages = [
    "{users} total users",
    "{messages} messages saved",
    "prefix ?"
]

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    download_data.start()
    update_status.start()

def format_time_difference(time_diff):
    minutes, seconds = divmod(int(time_diff.total_seconds()), 60)
    time_str = ""
    if minutes > 0:
        time_str += f"{minutes} minute{'s' if minutes != 1 else ''}"
    if seconds > 0:
        if time_str:
            time_str += " "
        time_str += f"{seconds} second{'s' if seconds != 1 else ''}"
    return time_str

@bot.command(name='top')
async def top(ctx):
    try:
        with open('data/download/top.json', 'r') as top_file:
            top_data = json.load(top_file)
        top_users = sorted(top_data.items(), key=lambda item: item[1], reverse=True)[:10]
        embed = discord.Embed(title="Top 10 Users", color=0x00ff00)
        for rank, (user, score) in enumerate(top_users, start=1):
            embed.add_field(name=f"{rank}. {user}", value=f"Score: {score}", inline=False)
        if cache_time:
            now = datetime.now()
            time_diff = now - cache_time
            time_str = format_time_difference(time_diff)
            if time_str:
                embed.set_footer(text=f"Last cached time: {time_str} ago")
        await ctx.send(embed=embed)
    except Exception as error:
        await ctx.send("There was an error fetching the top 10 users.")
        print(error)

@bot.command()
async def user(ctx, username: str):
    try:
        with open('data/download/users.json', 'r') as users_file:
            users_data = json.load(users_file)
        if username in users_data:
            user_data = users_data[username]
            total_messages = len(user_data)
            recent_messages = user_data[-5:] if len(user_data) >= 5 else user_data
            recent_messages.reverse()
            recent_str = '\n'.join([f"{msg['message_time']}: {msg['content']}" for msg in recent_messages])
            embed = discord.Embed(title=f"User: {username}", description=f"Total Messages: {total_messages}\nRecent Messages:\n{recent_str}", color=discord.Color.blue())
            
            if cache_time:
                now = datetime.now()
                time_diff = now - cache_time
                time_str = format_time_difference(time_diff)
                if time_str:
                    embed.set_footer(text=f"Last cached time: {time_str} ago")
            
            file_name = f"{username}_messages.txt"
            with open(file_name, 'w') as file:
                all_messages = '\n'.join([f"{msg['message_time']}: {msg['content']}" for msg in user_data])
                file.write(all_messages)
            file = discord.File(file_name, filename=file_name)
            await ctx.send(file=file, embed=embed)
            os.remove(file_name)
        else:
            embed = discord.Embed(title="Error", description="User not found or has not sent any messages yet.", color=discord.Color.red())
            await ctx.send(embed=embed)
    except IndexError:
        embed = discord.Embed(title="Error", description="Please specify a username after ?user.", color=discord.Color.red())
        await ctx.send(embed=embed)
    except Exception as error:
        embed = discord.Embed(title="Error", description=f"An error occurred: {error}", color=discord.Color.red())
        await ctx.send(embed=embed)

@bot.command()
async def total(ctx):
    try:
        total_messages = read_total_messages()
        total_users = count_users()
        embed = discord.Embed(title="Total Messages and Users Logged", color=discord.Color.green())
        embed.add_field(name="Total Messages", value=str(total_messages), inline=False)
        embed.add_field(name="Total Users", value=str(total_users), inline=False)
        if cache_time:
            now = datetime.now()
            time_diff = now - cache_time
            time_str = format_time_difference(time_diff)
            if time_str:
                embed.set_footer(text=f"Last cached time: {time_str} ago")
        await ctx.send(embed=embed)
    except Exception as error:
        embed = discord.Embed(title="Error", description=f"An error occurred: {error}", color=discord.Color.red())
        await ctx.send(embed=embed)

@bot.command()
async def help(ctx, command_name: str = None):
    if command_name is None:
        embed = discord.Embed(title="Help", description="List of available commands:", color=discord.Color.blue())
        embed.add_field(name="?top", value="Show the top 10 users by score.", inline=False)
        embed.add_field(name="?user <username>", value="Show information about a specific user.", inline=False)
        embed.add_field(name="?total", value="Show the total number of messages and users logged.", inline=False)
        embed.add_field(name="?help [command]", value="Show detailed information about a specific command.", inline=False)
    else:
        if command_name == "top":
            embed = discord.Embed(title="Help: ?top", description="Show the top 10 users by score.", color=discord.Color.blue())
        elif command_name == "user":
            embed = discord.Embed(title="Help: ?user <username>", description="Show information about a specific user.\n\nArguments:\n- username: The username of the user to show information about.", color=discord.Color.blue())
        elif command_name == "total":
            embed = discord.Embed(title="Help: ?total", description="Show the total number of messages and users logged.", color=discord.Color.blue())
        else:
            embed = discord.Embed(title="Help", description="Command not found.", color=discord.Color.red())
    await ctx.send(embed=embed)

async def download_json(url, filename):
    response = requests.get(url)
    if response.status_code == 200:
        with open(filename, 'wb') as file:
            file.write(response.content)

@tasks.loop(minutes=2)
async def download_data():
    global cache_time
    urls = [
        ("http://nuh.pet/top.json", "data/download/top.json"),
        ("http://nuh.pet/users", "data/download/users.json"),
        ("http://nuh.pet/total.json", "data/download/total.json")
    ]
    for url, filename in urls:
        await download_json(url, filename)
        print(f"Downloaded {url} to {filename}")
    cache_time = datetime.now()

@tasks.loop(minutes=1)
async def update_status():
    await bot.wait_until_ready()
    total_users = count_users()
    total_messages = read_total_messages()
    statuses = [status.format(users=total_users, messages=total_messages) for status in status_messages]
    for status in statuses:
        await bot.change_presence(status=discord.Status.dnd, activity=discord.Game(name=status))
        await asyncio.sleep(20)

def count_users():
    with open('data/download/users.json', 'r') as users_file:
        users_data = json.load(users_file)
    return len(users_data)

def read_total_messages():
    with open('data/download/total.json', 'r') as total_file:
        total_data = json.load(total_file)
    return total_data['count']

bot.run(bot_token)
