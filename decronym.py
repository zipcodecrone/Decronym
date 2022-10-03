import discord
import os
from dotenv import load_dotenv
from datetime import datetime,timedelta
import state

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

state_path = os.path.join(os.path.dirname(__file__), 'decronym.state')

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

states = state.State(state_path)

N = 'acronyms'
C = 'cooldown'
DEFAULT_COOL_DOWN = timedelta(seconds=30)

@client.event
async def on_ready():
    await tree.sync()
    print(f"We have logged in as {client.user}")

@client.event
async def on_message(message: discord.Message):
    if not message.guild:
        return
    state = states.get(message.guild.id)
    if message.author != client.user:
        for key in state.data.setdefault(N, {}).keys():
            data = state.data[N][key]
            if message.channel.id in data:
                if data[message.channel.id] < datetime.now():
                    del data[message.channel.id]
            if message.channel.id not in data:
                if key in message.content.upper():
                    delta = DEFAULT_COOL_DOWN
                    if C in state.data:
                        delta = state.data[C]
                    data[message.channel.id] = datetime.now() + delta
                    await message.channel.send("", embed=discord.Embed(
                        title=key,
                        description=data['phrase']
                    ))

@tree.command()
async def add(ctx: discord.Interaction, acronym: str, phrase: str):
    """Adds a new acronym

    Args:
        ctx (discord.Interaction): Command context
        acronym (str): Acronym to store (will be stored in all uppercase)
        phrase (str): What the acronym means
    """
    state = states.get(ctx.guild.id)
    state.data.setdefault(N, {})[acronym.upper()] = {
        'phrase': phrase,
        'cooldown': {}
    }
    await ctx.response.send_message(f"Added acronym {acronym.upper()}: {phrase}", ephemeral=True)

@tree.command()
async def remove(ctx: discord.Interaction, acronym: str):
    """Removes a registered acronym

    Args:
        ctx (discord.Interaction): Command context
        acronym (str): The acronym to delete (case insensitive)
    """
    state = states.get(ctx.guild.id)
    to_remove = []
    for key in state.data.setdefault(N, {}).keys():
        if key.upper() == acronym.upper():
            to_remove.append(key)
    for remove in to_remove:
        del state.data.setdefault(N, {})[remove]
    if len(to_remove) == 0:
        await ctx.response.send_message(f"Acronym '{acronym}' not found.", ephemeral=True)
    else:
        await ctx.response.send_message(f"Deleted '{acronym}'.", ephemeral=True)


@tree.command()
async def list(ctx: discord.Interaction):
    """Lists registered acronyms

    Args:
        ctx (discord.Interaction): Command context
    """
    state = states.get(ctx.guild.id)
    resp = "**The following acronyms have been registered:**"
    for key in state.data.setdefault(N, {}).keys():
        resp += f"\n{key}: {state.data[N][key]['phrase']}"
    await ctx.response.send_message(resp, ephemeral=True)

@tree.command()
async def cooldown(ctx: discord.Interaction):
    """Displays the current cooldown

    Args:
        ctx (discord.Interaction): The command context
    """
    state = states.get(ctx.guild.id)
    if C in state.data:
        await ctx.response.send_message(f"Cooldown is set to: {state.data[C]}")
    else:
        await ctx.response.send_message(f"Cooldown is set to {DEFAULT_COOL_DOWN}")

@tree.command()
async def set_cooldown(ctx: discord.Interaction, cooldown_hours: float):
    """Sets the cooldown for acronym reminders

    Args:
        ctx (discord.Interaction): The command context
        cooldown (float): Number of hours to wait between expanding acronyms
    """
    state = states.get(ctx.guild.id)
    state.data[C] = timedelta(hours=cooldown_hours)
    await ctx.response.send_message(f"Cooldown set: {state.data[C]}", ephemeral=True)

client.run(os.getenv('BOT_TOKEN'))
