import discord
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pickle


class Acronym(object):
    def __init__(self, acronym: str, expansion: str):
        self.__acronym = acronym
        self.__search = acronym.upper()
        self.__expansion = expansion
        self.__channel_timeouts = {}
        self.__global_timeout = None

    def acronym(self) -> str:
        return self.__acronym

    def expansion(self) -> str:
        return self.__expansion

    def should_expand(self, channel_id: int) -> bool:
        if channel_id in self.__channel_timeouts:
            if self.__channel_timeouts[channel_id] < datetime.now():
                del self.__channel_timeouts[channel_id]
        if self.__global_timeout is not None:
            if self.__global_timeout < datetime.now():
                self.__global_timeout = None
        return (
            channel_id not in self.__channel_timeouts and self.__global_timeout == None
        )

    def is_within(self, message: str) -> bool:
        return self.__search in message.upper()

    async def expand(
        self,
        message: discord.Message,
        global_cooldown: timedelta,
        channel_cooldown: timedelta,
    ):
        if global_cooldown is not None:
            self.__global_timeout = datetime.now() + global_cooldown
        self.__channel_timeouts[message.channel.id] = datetime.now() + channel_cooldown
        await message.channel.send(
            "", embed=discord.Embed(title=self.__acronym, description=self.__expansion)
        )


class GuildState(object):
    CFG = "cfg"
    ACRONYMS = "acronyms"
    KNOWN_KEYS = [CFG, ACRONYMS]

    def __init__(self, guild_id: int, data: object, owner):
        self.__id = guild_id
        self.__data = data
        self.__owner = owner
        self.migrate_data()

    def migrate_data(self):
        to_delete = []
        for key in self.__data.keys():
            if key not in GuildState.KNOWN_KEYS:
                to_delete.append(key)
        for delete in to_delete:
            del self.__data[delete]

    def cfg(self, key, default):
        if GuildState.CFG not in self.__data:
            return default
        if key not in self.__data[GuildState.CFG]:
            return default
        return self.__data[GuildState.CFG][key]

    def set_cfg(self, key: str, value):
        self.__data.setdefault(GuildState.CFG, {})[key] = value

    def add_acronym(self, acronym: str, expansion: str):
        self.__data.setdefault(GuildState.ACRONYMS, {})[acronym] = Acronym(
            acronym, expansion
        )

    def remove_acronym(self, acronym: str) -> bool:
        to_remove = []
        for key in self.acronyms():
            if key.__search == acronym.upper():
                to_remove.append(key.acronym())
        for remove in to_remove:
            del self.__data[GuildState.ACRONYMS][remove]
        return len(to_remove) > 0

    def acronyms(self) -> list[Acronym]:
        return self.__data.setdefault(GuildState.ACRONYMS, {}).values()

    def __del__(self):
        self.__owner.save(self.__id)


class State(object):
    def __init__(self, state_path):
        self.path = state_path
        self.states = {}
        try:
            with open(state_path, "rb") as state:
                self.states = pickle.load(state)
        except Exception as e:
            print("Unable to load state: {}".format(e))

    def get(self, guild_id):
        return GuildState(guild_id, self.states.setdefault(guild_id, {}), self)

    def save(self, guild_id):
        if not self.states[guild_id]:
            print("Culling empty guild: {}".format(guild_id))
            del self.states[guild_id]

        try:
            with open(self.path, "wb") as state_file:
                pickle.dump(self.states, state_file)
        except Exception as e:
            print("Failed to save state: {}".format(e))


dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

state_path = os.path.join(os.path.dirname(__file__), "decronym.state")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

states = State(state_path)

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
        for acronym in state.acronyms():
            if acronym.should_expand(message.channel.id) and acronym.is_within(
                message.content
            ):
                await acronym.expand(
                    message,
                    state.cfg("global_cooldown", None),
                    state.cfg("cooldown", DEFAULT_COOL_DOWN),
                )


@tree.command()
async def add(ctx: discord.Interaction, acronym: str, phrase: str):
    """Adds a new acronym

    Args:
        ctx (discord.Interaction): Command context
        acronym (str): Acronym to store (will be stored in all uppercase)
        phrase (str): What the acronym means
    """
    state = states.get(ctx.guild.id)
    state.add_acronym(acronym, phrase)
    await ctx.response.send_message(
        f"Added acronym {acronym}: {phrase}", ephemeral=True
    )


@tree.command()
async def remove(ctx: discord.Interaction, acronym: str):
    """Removes a registered acronym

    Args:
        ctx (discord.Interaction): Command context
        acronym (str): The acronym to delete (case insensitive)
    """
    state = states.get(ctx.guild.id)
    if state.remove_acronym(acronym):
        await ctx.response.send_message(f"Deleted '{acronym}'.", ephemeral=True)
    else:
        await ctx.response.send_message(
            f"Acronym '{acronym}' not found.", ephemeral=True
        )


@tree.command()
async def list(ctx: discord.Interaction):
    """Lists registered acronyms

    Args:
        ctx (discord.Interaction): Command context
    """
    state = states.get(ctx.guild.id)
    resp = "**The following acronyms have been registered:**"
    for key in state.acronyms():
        resp += f"\n{key.acronym()}: {key.expansion()}"
    await ctx.response.send_message(resp, ephemeral=True)


@tree.command()
async def cooldown(ctx: discord.Interaction):
    """Displays the current cooldown

    Args:
        ctx (discord.Interaction): The command context
    """
    state = states.get(ctx.guild.id)
    await ctx.response.send_message(
        f"Cooldown is set to: {state.cfg('cooldown', DEFAULT_COOL_DOWN)}",
        ephemeral=True,
    )


@tree.command()
async def set_cooldown(ctx: discord.Interaction, cooldown_hours: float):
    """Sets the cooldown for acronym reminders

    Args:
        ctx (discord.Interaction): The command context
        cooldown (float): Number of hours to wait between expanding acronyms
    """
    state = states.get(ctx.guild.id)
    state.set_cfg("cooldown", timedelta(hours=cooldown_hours))
    await ctx.response.send_message(
        f"Cooldown is set to: {state.cfg('cooldown', DEFAULT_COOL_DOWN)}",
        ephemeral=True,
    )


@tree.command()
async def global_cooldown(ctx: discord.Interaction):
    """Displays the current global cooldown

    Args:
        ctx (discord.Interaction): The command context
    """
    state = states.get(ctx.guild.id)
    await ctx.response.send_message(
        f"global cooldown is set to: {state.cfg('global_cooldown', None)}",
        ephemeral=True,
    )


@tree.command()
async def set_global_cooldown(ctx: discord.Interaction, cooldown_hours: float):
    """Sets the global cooldown for acronym reminders

    Args:
        ctx (discord.Interaction): The command context
        global_cooldown (float): Number of hours to wait between expanding acronyms
    """
    state = states.get(ctx.guild.id)
    state.set_cfg("global_cooldown", timedelta(hours=cooldown_hours))
    await ctx.response.send_message(
        f"global cooldown is set to: {state.cfg('global_cooldown', None)}",
        ephemeral=True,
    )


client.run(os.getenv("BOT_TOKEN"))
