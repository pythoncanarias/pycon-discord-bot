import logging

import discord
from discord.ext import commands

from configuration import Config
from error import AlreadyRegisteredError, NotFoundError
from helpers.channel_logging import log_to_channel
from helpers.eventbrite_connector import EventbriteOrder

config = Config()
order_ins = EventbriteOrder()

EMOJI_POINT = "\N{WHITE LEFT POINTING BACKHAND INDEX}"
EMOJI_ONE = "1️⃣"
EMOJI_TWO = "2️⃣"
EMOJI_THREE = "3️⃣"
ZERO_WIDTH_SPACE = "\N{ZERO WIDTH SPACE}"
REGISTERED_LIST = {}

_logger = logging.getLogger(f"bot.{__name__}")


class RegistrationButton(discord.ui.Button["Registro"]):
    def __init__(self, x: int, y: int, label: str, style: discord.ButtonStyle):
        super().__init__(style=discord.ButtonStyle.secondary, label=ZERO_WIDTH_SPACE, row=y)
        self.x = x
        self.y = y
        self.label = label
        self.style = style

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None

        # Launch the modal form
        await interaction.response.send_modal(RegistrationForm())


class RegistrationForm(discord.ui.Modal, title="Registro PyConES23"):
    order = discord.ui.TextInput(
        label="N. de Pedido",
        required=True,
        min_length=10,
        max_length=12,
        placeholder="Número de 10 dígitos que viene luego de un '#'",
    )

    name = discord.ui.TextInput(
        label="Full Name",
        required=True,
        min_length=3,
        max_length=50,
        style=discord.TextStyle.short,
        placeholder="Tu nombre completo como está en tu ticket",
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Assign the role to the user and send a confirmation message."""

        roles = await order_ins.get_roles(
            name=self.name.value,
            order=self.order.value,
        )
        _logger.info("Asignando %r roles=%r", self.name.value, roles)
        for role in roles:
            role = discord.utils.get(interaction.guild.roles, id=role)
            await interaction.user.add_roles(role)
        nickname = self.name.value[:32]  # Limit to the max length
        await interaction.user.edit(nick=nickname)
        await log_to_channel(
            channel=interaction.client.get_channel(config.REG_LOG_CHANNEL_ID),
            interaction=interaction,
            name=self.name.value,
            order=self.order.value,
            roles=roles,
        )
        await interaction.response.send_message(
            f"Gracias {self.name.value}, ¡ya tienes tu registro!\n\nTambién, tu nickname fue"
            f" cambiado al nombre que usaste para registrar tu ticket. Este es también el nombre que"
            f" estará en tu credencial en la conferencia, lo que significa que tu nickname puede ser"
            f" tu 'credencial virtual' de la conferencia.",
            ephemeral=True,
            delete_after=20,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        # Make sure we know what the error actually is
        _logger.error("Ocurrió un error!", exc_info=error)

        # log error message in discord channel
        await log_to_channel(
            channel=interaction.client.get_channel(config.REG_LOG_CHANNEL_ID),
            interaction=interaction,
            error=error,
        )
        if isinstance(error, AlreadyRegisteredError):
            _msg = "¡Ya te registraste! Si crees que no es verdad"
        elif isinstance(error, NotFoundError):
            _msg = "No podemos encontrar tu ticket, verifica nuevamente la información que ingresaste, o"
        else:
            _msg = "Algo no salió bien, "
        _msg += f" pide ayuda en <#{config.REG_HELP_CHANNEL_ID}>"
        await interaction.response.send_message(_msg, ephemeral=True, delete_after=180)


class RegistrationView(discord.ui.View):
    def __init__(self):
        # We don't timeout to have a persistent View
        super().__init__(timeout=None)
        self.value = None
        self.add_item(
            RegistrationButton(0, 0, f"Registrate aquí {EMOJI_POINT}", discord.ButtonStyle.green)
        )


class Registration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.guild = None
        _logger.info("Cog 'Registration' has been initialized")

    @commands.Cog.listener()
    async def on_ready(self):
        if self.guild is None:
            self.guild = self.bot.get_guild(config.GUILD)

        reg_channel = self.bot.get_channel(config.REG_CHANNEL_ID)

        await reg_channel.purge()
        await order_ins.fetch_data()
        order_ins.load_registered()

        _title = "Te damos la bienvenida al discord de la PyConES23 🎉🐍"
        _desc = (
            "Sigue los siguientes paso para completar el registro:\n\n"
            f'{EMOJI_ONE} Haz clic en el botón verde "Registrate Aquí {EMOJI_POINT}".\n\n'
            f'{EMOJI_TWO} Rellena el "Número de pedido" (que encuentras en el email de Eventbrite cuando '
            'adquiriste tu entrada con el asunto: "Tus entradas para el evento PyConES 2023 '
            'Tenerife", sin "#") y "Nombre Completo" (como está en la misma orden).\n\n'
            f'{EMOJI_THREE} Haz clic "Submit". Verificaremos tu ticket  y te asignaremos el rol basado en el tipo..\n\n'
            f"¿Tienes algún problema? Pide ayuda en el canal <#{config.REG_HELP_CHANNEL_ID}>.\n\n"
            "¡Nos vemos en el servidor! 🐍💻🎉"
        )

        view = RegistrationView()
        embed = discord.Embed(
            title=_title,
            description=_desc,
            colour=0xFF8331,
        )

        await reg_channel.send(embed=embed, view=view)
