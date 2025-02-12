from .status_command import setup_status_command
from .add_config_command import setup_add_config_command
from .delete_config_command import setup_delete_config_command

class CommandManager:
    def __init__(self, bot):
        self.bot = bot
        self.setup_functions = [
            setup_status_command,
            setup_add_config_command,
            setup_delete_config_command
        ]

    def setup(self):
        """Setup all commands"""
        for setup_function in self.setup_functions:
            setup_function(self.bot) 