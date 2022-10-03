import pickle


class GuildState(object):
    def __init__(self, guild_id, data, owner):
        self.id = guild_id
        self.data = data
        self.owner = owner

    def __del__(self):
        self.owner.save(self.id)


class State(object):
    def __init__(self, state_path):
        self.path = state_path
        self.states = {}
        try:
            with open(state_path, 'rb') as state:
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
            with open(self.path, 'wb') as state_file:
                pickle.dump(self.states, state_file)
        except Exception as e:
            print("Failed to save state: {}".format(e))
