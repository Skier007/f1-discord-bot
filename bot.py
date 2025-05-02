import discord
from discord.ext import commands
from discord.ui import Button, View
from discord import app_commands
import os
from dotenv import load_dotenv
import random
import json

# Intents setzen
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Spieler-Daten (wird aus Datei geladen)
player_data = {}  # Format: {guild_id: {user_id: data}}
DATA_FILE = "spielerdaten.json"

# Teams
ALLOWED_TEAMS = [
    "Mercedes", "Red Bull", "Ferrari", "McLaren", "Aston Martin",
    "Alpine", "Williams", "RB", "Kick Sauber", "Haas",
    "Audi", "Cadillac"
]

# Reifentypen abhängig vom Wetter
REIFENWAHL = {
    "Sonne": ["Soft", "Medium", "Hard"],
    "Regen": ["Intermediate", "Full Wet"],
    "Wechselhaft": ["Medium", "Soft", "Intermediate"]
}

def team_anzahl(guild_id, team):
    return sum(1 for d in player_data.get(guild_id, {}).values() if d["team"] == team)

# ========== SPEICHERFUNKTIONEN ==========

def lade_daten():
    global player_data
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            player_data = json.load(f)
    else:
        player_data = {}

def speichere_daten():
    with open(DATA_FILE, "w") as f:
        json.dump(player_data, f, indent=2)

# ========== EVENTS ==========


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot ist online als {bot.user} und Slash Commands wurden synchronisiert.")

# ========== GETEILTE LOGIK ==========

async def run_qualifying_logic(user, guild, channel, send_func, followup_func):
    guild_id = str(guild.id)
    user_id = str(user.id)

    if guild_id not in player_data or user_id not in player_data[guild_id]:
        await send_func("❌ Du hast noch keine Karriere. Starte mit `/karriere`.")
        return

    wetter = random.choice(list(REIFENWAHL.keys()))
    reifenoptionen = REIFENWAHL[wetter]
    reifenliste = ", ".join(reifenoptionen)

    await send_func(embed=discord.Embed(
        title="🏁 Qualifying",
        description=f"Wetter: **{wetter}**\nVerfügbare Reifen: {reifenliste}\nBitte antworte im Chat mit deinem gewählten Reifen.",
        color=discord.Color.blue()
    ))

    def check(m):
        return m.author.id == user.id and m.channel.id == channel.id

    try:
        msg = await bot.wait_for('message', check=check, timeout=30)
        reifenwahl = msg.content.strip().title()

        if reifenwahl not in reifenoptionen:
            await followup_func("❌ Ungültiger Reifentyp. Qualifying abgebrochen.")
            return

        if random.random() < 0.05:
            embed = discord.Embed(
                title="💥 Unfall im Qualifying!",
                description="Du hast das Auto verloren – keine Rundenzeit.",
                color=discord.Color.red()
            )
            await followup_func(embed=embed)
            return

        mod = -3 if reifenwahl in ["Soft", "Intermediate"] else 2
        startplatz = max(1, min(20, random.randint(1, 20) + mod))
        player_data[guild_id][user_id]["startplatz"] = startplatz
        speichere_daten()

        embed = discord.Embed(
            title="📊 Qualifying abgeschlossen",
            description=f"Wetter: **{wetter}**\nReifen: **{reifenwahl}**\nStartplatz: **{startplatz}**",
            color=discord.Color.purple()
        )
        await followup_func(embed=embed)

    except Exception:
        await followup_func("⏰ Zeit abgelaufen. Bitte versuche es erneut.")

async def run_profil_logic(user, guild, send_func):
    guild_id = str(guild.id)
    user_id = str(user.id)

    if guild_id not in player_data or user_id not in player_data[guild_id]:
        await send_func("❌ Du hast noch keine Karriere.")
        return

    data = player_data[guild_id][user_id]
    embed = discord.Embed(title="👤 Fahrerprofil", color=discord.Color.blue())
    embed.add_field(name="Name", value=data["name"], inline=True)
    embed.add_field(name="Team", value=data["team"], inline=True)
    embed.add_field(name="Punkte", value=str(data["punkte"]), inline=True)
    embed.add_field(name="Rennen", value=str(data["rennen"]), inline=True)
    await send_func(embed=embed)

async def run_loeschen_logic(user, guild, send_func):
    guild_id = str(guild.id)
    user_id = str(user.id)

    if guild_id in player_data and user_id in player_data[guild_id]:
        del player_data[guild_id][user_id]
        speichere_daten()
        msg = "🗑️ Dein Fahrerprofil wurde gelöscht."
    else:
        msg = "ℹ️ Du hattest kein Fahrerprofil."

    await send_func(msg)

async def run_adminreset_logic(guild, send_func):
    guild_id = str(guild.id)
    player_data[guild_id] = {}
    speichere_daten()
    embed = discord.Embed(
        title="⚠️ Admin-Reset",
        description="Alle Fahrerprofile auf diesem Server wurden gelöscht.",
        color=discord.Color.dark_red()
    )
    await send_func(embed=embed)

async def run_rangliste_logic(guild, send_func):
    guild_id = str(guild.id)
    if guild_id not in player_data or not player_data[guild_id]:
        await send_func("📭 Es fährt noch niemand mit. Starte mit `/karriere`!")
        return

    rangliste = sorted(player_data[guild_id].items(), key=lambda x: x[1]["punkte"], reverse=True)

    embed = discord.Embed(
        title="🏆 F1 Fahrer-Rangliste",
        description="Alle aktiven Fahrer sortiert nach Punkten:",
        color=discord.Color.gold()
    )

    for i, (user_id, data) in enumerate(rangliste, start=1):
        embed.add_field(
            name=f"{i}. {data['name']} ({data['team']})",
            value=f"Punkte: **{data['punkte']}** | Rennen: {data['rennen']}",
            inline=False
        )

    await send_func(embed=embed)

async def run_karriere_logic(user, guild, channel, send_func, wait_func):
    guild_id = str(guild.id)
    user_id = str(user.id)

    if guild_id not in player_data:
        player_data[guild_id] = {}
    if user_id in player_data[guild_id]:
        await send_func(embed=discord.Embed(description="🏁 Du hast bereits eine Karriere gestartet!", color=discord.Color.orange()))
        return

    await send_func(embed=discord.Embed(description="🏎 Wie soll dein Fahrer heißen? (bitte antworte im Chat)", color=discord.Color.blue()))

    def check_name(m):
        return m.author.id == user.id and m.channel.id == channel.id

    try:
        msg_name = await wait_func('message', check=check_name, timeout=60)
        fahrername = msg_name.content.strip()

        teamliste = ", ".join(ALLOWED_TEAMS)
        await send_func(embed=discord.Embed(description=f"Wähle ein Team (max. 2 Fahrer pro Team):\n{teamliste}", color=discord.Color.blue()))

        msg_team = await wait_func('message', check=check_name, timeout=60)
        team = msg_team.content.strip().title()

        if team not in ALLOWED_TEAMS:
            await send_func(embed=discord.Embed(description="❌ Ungültiges Team. Karriere abgebrochen.", color=discord.Color.red()))
            return

        if team_anzahl(guild_id, team) >= 2:
            await send_func(embed=discord.Embed(description=f"❌ Das Team **{team}** ist bereits voll (2 Fahrer).", color=discord.Color.red()))
            return

        player_data[guild_id][user_id] = {
            "name": fahrername,
            "team": team,
            "punkte": 0,
            "rennen": 0
        }
        speichere_daten()

        await send_func(embed=discord.Embed(title="✅ Karriere gestartet!", description=f"Willkommen **{fahrername}** bei **{team}**!\nViel Erfolg! 🏁", color=discord.Color.green()))

    except Exception:
        await send_func(embed=discord.Embed(description="⏰ Zeit abgelaufen oder ein Fehler ist aufgetreten.", color=discord.Color.red()))

async def run_rennen_logic(user, guild, channel, send_func, wait_func):
    guild_id = str(guild.id)
    user_id = str(user.id)

    if guild_id not in player_data or user_id not in player_data[guild_id]:
        await send_func(embed=discord.Embed(description="❌ Du hast noch keine Karriere. Starte mit `/karriere`.", color=discord.Color.red()))
        return

    if "startplatz" not in player_data[guild_id][user_id]:
        await send_func(embed=discord.Embed(description="❌ Du musst zuerst ein Qualifying fahren mit `/qualifying`.", color=discord.Color.red()))
        return

    wetter = random.choice(list(REIFENWAHL.keys()))
    reifenoptionen = REIFENWAHL[wetter]
    reifenliste = ", ".join(reifenoptionen)

    await send_func(embed=discord.Embed(title="🚦 Strategieauswahl", description=f"Wetter: **{wetter}**\nWähle deinen Reifentyp:\n{reifenliste}", color=discord.Color.orange()))

    def check(m):
        return m.author.id == user.id and m.channel.id == channel.id

    try:
        msg = await wait_func('message', check=check, timeout=30)
        strategie = msg.content.strip().title()

        if strategie not in reifenoptionen:
            await send_func(embed=discord.Embed(description="❌ Ungültiger Reifentyp. Rennen abgebrochen.", color=discord.Color.red()))
            return

        startplatz = player_data[guild_id][user_id]["startplatz"]

        if random.random() < 0.1:
            del player_data[guild_id][user_id]["startplatz"]
            speichere_daten()
            await send_func(embed=discord.Embed(title="💥 Unfall!", description="Du bist im Rennen ausgefallen – technischer Defekt oder Unfall.", color=discord.Color.dark_red()))
            return

        platz = max(1, min(20, startplatz + random.randint(-5, 5)))
        punkte_vergabe = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
        punkte = punkte_vergabe[platz - 1] if platz <= 10 else 0

        player_data[guild_id][user_id]["punkte"] += punkte
        player_data[guild_id][user_id]["rennen"] += 1
        del player_data[guild_id][user_id]["startplatz"]
        speichere_daten()

        embed = discord.Embed(title="🏁 Rennen beendet!", color=discord.Color.green())
        embed.add_field(name="Wetter", value=wetter, inline=True)
        embed.add_field(name="Reifen", value=strategie, inline=True)
        embed.add_field(name="Zielplatz", value=f"Platz {platz}", inline=True)
        embed.add_field(name="Punkte", value=f"+{punkte}", inline=True)
        await send_func(embed=embed)

    except Exception:
        await send_func(embed=discord.Embed(description="⏰ Zeit abgelaufen. Bitte versuche es erneut.", color=discord.Color.red()))

# ========== PREFIX & SLASH ==========

@bot.command(name="qualifying")
async def qualifying_legacy(ctx):
    await run_qualifying_logic(
        user=ctx.author,
        guild=ctx.guild,
        channel=ctx.channel,
        send_func=lambda content=None, embed=None: ctx.send(content=content, embed=embed),
        followup_func=lambda content=None, embed=None: ctx.send(content=content, embed=embed)
    )    

@bot.tree.command(name="qualifying", description="Fahre ein Qualifying vor dem Rennen")
async def qualifying_slash(interaction: discord.Interaction):
    await run_qualifying_logic(
        user=interaction.user,
        guild=interaction.guild,
        channel=interaction.channel,
        send_func=lambda content=None, embed=None: interaction.response.send_message(content=content, embed=embed, ephemeral=True),
        followup_func=lambda content=None, embed=None: interaction.followup.send(content=content, embed=embed, ephemeral=True)
    )

@bot.command(name="profil")
async def profil_legacy(ctx):
    await run_profil_logic(ctx.author, ctx.guild, ctx.send)

@bot.tree.command(name="profil", description="Zeige dein Fahrerprofil")
async def profil_slash(interaction: discord.Interaction):
    await run_profil_logic(
        interaction.user,
        interaction.guild,
        lambda content=None, embed=None: interaction.response.send_message(content=content, embed=embed, ephemeral=True)
    )

@bot.command(name="löschen")
async def loeschen_legacy(ctx):
    await run_loeschen_logic(ctx.author, ctx.guild, ctx.send)

@bot.tree.command(name="löschen", description="Lösche dein eigenes Fahrerprofil")
async def loeschen_slash(interaction: discord.Interaction):
    await run_loeschen_logic(
        interaction.user,
        interaction.guild,
        lambda content=None, embed=None: interaction.response.send_message(content=content, embed=embed, ephemeral=True)
    )

@bot.command(name="adminreset")
@commands.has_permissions(administrator=True)
async def adminreset_legacy(ctx):
    await run_adminreset_logic(ctx.guild, ctx.send)

@bot.tree.command(name="adminreset", description="(Admin) Setzt alle Fahrer zurück")
@app_commands.checks.has_permissions(administrator=True)
async def adminreset_slash(interaction: discord.Interaction):
    await run_adminreset_logic(
        interaction.guild,
        lambda content=None, embed=None: interaction.response.send_message(content=content, embed=embed)
    )

@bot.command(name="rangliste")
async def rangliste_legacy(ctx):
    await run_rangliste_logic(ctx.guild, ctx.send)

@bot.tree.command(name="rangliste", description="Zeigt alle Fahrer und ihre Punkte")
async def rangliste_slash(interaction: discord.Interaction):
    await run_rangliste_logic(
        interaction.guild,
        lambda content=None, embed=None: interaction.response.send_message(content=content, embed=embed)
    )

@bot.command(name="karriere")
async def karriere_legacy(ctx):
    await run_karriere_logic(ctx.author, ctx.guild, ctx.channel, ctx.send, bot.wait_for)

@bot.tree.command(name="karriere", description="Starte deine eigene F1-Karriere")
async def karriere_slash(interaction: discord.Interaction):
    await run_karriere_logic(
        interaction.user,
        interaction.guild,
        interaction.channel,
        lambda content=None, embed=None: interaction.response.send_message(content=content, embed=embed, ephemeral=True),
        bot.wait_for
    )

@bot.command(name="rennen")
async def rennen_legacy(ctx):
    await run_rennen_logic(ctx.author, ctx.guild, ctx.channel, ctx.send, bot.wait_for)

@bot.tree.command(name="rennen", description="Wähle Strategie und fahre ein Rennen")
async def rennen_slash(interaction: discord.Interaction):
    await run_rennen_logic(
        interaction.user,
        interaction.guild,
        interaction.channel,
        lambda content=None, embed=None: interaction.response.send_message(content=content, embed=embed, ephemeral=True),
        bot.wait_for
    )

# ========== HILFE LOGIK ==========

async def run_hilfe_logic(send_func):
    embed = discord.Embed(
        title="📘 Formel 1 Karriere Bot – Hilfe",
        description="Hier sind alle verfügbaren Befehle:",
        color=discord.Color.blue()
    )
    embed.add_field(name="/karriere", value="Starte deine eigene F1-Karriere", inline=False)
    embed.add_field(name="/profil", value="Zeige dein Fahrerprofil", inline=False)
    embed.add_field(name="/qualifying", value="Fahre ein Qualifying vor dem Rennen", inline=False)
    embed.add_field(name="/rennen", value="Wähle Strategie und fahre ein Rennen", inline=False)
    embed.add_field(name="/rangliste", value="Zeigt alle Fahrer und ihre Punkte", inline=False)
    embed.add_field(name="/löschen", value="Lösche dein eigenes Fahrerprofil", inline=False)
    embed.add_field(name="/adminreset", value="(Admin) Setzt alle Fahrer zurück", inline=False)
    await send_func(embed=embed)

@bot.command(name="hilfe")
async def hilfe_legacy(ctx):
    await run_hilfe_logic(ctx.send)

@bot.tree.command(name="hilfe", description="Zeigt alle Befehle und deren Beschreibung")
async def hilfe_slash(interaction: discord.Interaction):
    await run_hilfe_logic(lambda content=None, embed=None: interaction.response.send_message(content=content, embed=embed, ephemeral=True))

# Lade Umgebungsvariablen und Daten
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
lade_daten()

# Bot starten
bot.run(TOKEN)
