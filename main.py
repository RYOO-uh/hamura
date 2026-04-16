import discord
from discord.ext import commands
import random
import datetime
import asyncio
import math
import json
import os
import io

# ═══════════════════════════════════════════════════════════
#  Configuration
# ═══════════════════════════════════════════════════════════
PREFIX   = "+"
TOKEN    = "MTQ3OTYzNzI3Nzc3MTgyOTMwOQ.GEGOXR.xZu3RRq0rbaZaX4D4MnUNalshum2CtlhrUYE0g"
OWNER_IDS = {1492625647070085170, 1492625643291021354}

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# ── Commandes accessibles à tout le monde ────────────────
PUBLIC_CMDS = {
    # Divertissement
    "8ball", "flip", "roll", "rps", "joke", "compliment", "roast", "meme", "color",
    # XP / Niveaux
    "rank", "leaderboard", "levelrole",
    # Économie & Casino
    "balance", "daily", "work", "give", "rob", "richest",
    "blackjack", "bj", "slots", "coinflip", "cf", "casino",
    # Aide publique
    "cmd",
}

# ── Commandes accessibles au staff (+ owner) ─────────────
STAFF_IDS = {1492625658747289733}

STAFF_CMDS = {
    # Modération
    "kick", "ban", "unban", "mute", "unmute",
    "clear", "nuke", "warn", "warns", "clearwarns",
    # Vocal
    "vcmove", "vcmute", "vcunmute",
    # Aide
    "cmds",
}

OWNER_ROLES = {1492625635934474542, 1479936680281772172, 1394067178780622910,
               1492625637280714950, 1492625642548891879}

def has_owner_role(member):
    if not hasattr(member, "roles"):
        return False
    return any(r.id in OWNER_ROLES for r in member.roles)

_orig_has_permissions = commands.has_permissions
def _owner_bypass_has_permissions(**perms):
    original_check = _orig_has_permissions(**perms)
    async def predicate(ctx):
        if ctx.author.id in OWNER_IDS or has_owner_role(ctx.author):
            return True
        return await original_check.predicate(ctx)
    return commands.check(predicate)
commands.has_permissions = _owner_bypass_has_permissions

@bot.check
async def owner_gate(ctx):
    is_owner = ctx.author.id in OWNER_IDS or has_owner_role(ctx.author)
    if ctx.command and ctx.command.name in PUBLIC_CMDS:
        return True
    if ctx.command and ctx.command.name in STAFF_CMDS:
        return ctx.author.id in STAFF_IDS or is_owner
    return is_owner

# ── Stockage en mémoire ──────────────────────────────────
warns      = {}
economy    = {}
afk_users  = {}
last_daily = {}
work_cooldown = {}
rob_cooldown  = {}

xp_data          = {}
xp_cooldown      = {}
xp_level_rewards = {}

mod_log_config   = {}
auto_role_config = {}

import time as _time
channel_msg_times = {}

react_roles     = {}
auto_mod_config = {}
logs_config      = {}
ticket_notes     = {}
active_giveaways = {}

LOG_TYPES = ["ticket", "message", "moderation", "boost", "role", "channel", "voice", "flux"]

# ═══════════════════════════════════════════════════════════
#  PERSISTANCE JSON
# ═══════════════════════════════════════════════════════════
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def _path(name):  return os.path.join(DATA_DIR, name + ".json")

def _load(name, default=None):
    p = _path(name)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default if default is not None else {}

def _save(name, data):
    with open(_path(name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _int_keys(d):        return {int(k): v for k, v in d.items()}
def _int_keys_nested(d): return {int(k): {int(k2): v2 for k2, v2 in v.items()} for k, v in d.items()}

def load_all():
    global warns, economy, last_daily, xp_data, xp_level_rewards
    global welcome_config, leave_config, ticket_config
    global mod_log_config, auto_role_config, react_roles, auto_mod_config, logs_config
    global open_tickets, claimed_tickets, ticket_types_map, afk_users
    warns            = _int_keys(_load("warns"))
    economy          = _int_keys(_load("economy"))
    last_daily_raw   = _int_keys(_load("last_daily"))
    last_daily.update({k: datetime.date.fromisoformat(v) for k, v in last_daily_raw.items()})
    xp_data          = _int_keys_nested(_load("xp_data"))
    xp_lvl_raw       = _int_keys(_load("xp_level_rewards"))
    xp_level_rewards = {gid: {int(lvl): rid for lvl, rid in d.items()}
                        for gid, d in xp_lvl_raw.items()}
    welcome_config   = _int_keys(_load("welcome_config"))
    leave_config     = _int_keys(_load("leave_config"))
    ticket_config    = _int_keys(_load("ticket_config"))
    mod_log_config   = _int_keys(_load("mod_log_config"))
    auto_role_config = _int_keys(_load("auto_role_config"))
    react_roles_raw  = _int_keys(_load("react_roles"))
    react_roles      = {gid: {int(mid): emojis for mid, emojis in msgs.items()}
                        for gid, msgs in react_roles_raw.items()}
    auto_mod_config  = _int_keys(_load("auto_mod_config"))
    logs_config.update(_int_keys(_load("logs_config")))
    open_tickets.update(_int_keys(_load("open_tickets")))
    claimed_tickets.update(_int_keys(_load("claimed_tickets")))
    ticket_types_map.update(_int_keys(_load("ticket_types_map")))
    afk_users.update(_int_keys(_load("afk_users")))
    ticket_notes.update(_int_keys(_load("ticket_notes")))
    active_giveaways.update({int(k): v for k, v in _load("active_giveaways").items()})

def save_warns():         _save("warns",           {str(k): v for k, v in warns.items()})
def save_economy():       _save("economy",          {str(k): v for k, v in economy.items()})
def save_daily():         _save("last_daily",       {str(k): str(v) for k, v in last_daily.items()})
def save_xp():            _save("xp_data",          {str(g): {str(u): x for u, x in d.items()} for g, d in xp_data.items()})
def save_xp_rewards():    _save("xp_level_rewards", {str(g): {str(l): r for l, r in d.items()} for g, d in xp_level_rewards.items()})
def save_welcome():       _save("welcome_config",   {str(k): v for k, v in welcome_config.items()})
def save_leave():         _save("leave_config",     {str(k): v for k, v in leave_config.items()})
def save_ticket():        _save("ticket_config",    {str(k): v for k, v in ticket_config.items()})
def save_modlog():        _save("mod_log_config",   {str(k): v for k, v in mod_log_config.items()})
def save_autorole():      _save("auto_role_config", {str(k): v for k, v in auto_role_config.items()})
def save_reactroles():    _save("react_roles",      {str(g): {str(m): e for m, e in msgs.items()} for g, msgs in react_roles.items()})
def save_automod():       _save("auto_mod_config",  {str(k): v for k, v in auto_mod_config.items()})
def save_open_tickets():   _save("open_tickets",      {str(k): v for k, v in open_tickets.items()})
def save_claimed():        _save("claimed_tickets",   {str(k): v for k, v in claimed_tickets.items()})
def save_ticket_types():   _save("ticket_types_map",  {str(k): v for k, v in ticket_types_map.items()})
def save_logs_config():    _save("logs_config",       {str(k): v for k, v in logs_config.items()})
def save_afk():           _save("afk_users",        {str(k): v for k, v in afk_users.items()})
def save_ticket_notes():  _save("ticket_notes",      {str(k): v for k, v in ticket_notes.items()})
def save_giveaways():     _save("active_giveaways",  {str(k): v for k, v in active_giveaways.items()})

# ── Config bienvenue / départ ────────────────────────────
welcome_config = {}
leave_config   = {}

def default_welcome():
    return {
        "channel": None,
        "message": "Bienvenue {user} sur **{server}** ! Nous sommes maintenant **{count}** membres. 🎉",
        "title":   "👋 Nouveau membre !",
        "color":   0x5865F2,
        "show_avatar":    True,
        "show_thumbnail": True,
        "show_banner":    False,
        "show_timestamp": True,
        "footer":    "",
        "image_url": "",
        "enabled":   True,
    }

def default_leave():
    return {
        "channel": None,
        "message": "**{username}** a quitté le serveur. Il reste **{count}** membres.",
        "title":   "🚪 Au revoir",
        "color":   0xED4245,
        "show_avatar":    True,
        "show_thumbnail": True,
        "show_timestamp": True,
        "footer":    "",
        "image_url": "",
        "enabled":   True,
    }

# ── Config tickets ───────────────────────────────────────
ticket_config    = {}
open_tickets     = {}
claimed_tickets: dict[int, int] = {}
ticket_types_map: dict[int, str] = {}

def default_ticket_config():
    return {
        "category":     None,
        "support_role": None,
        "log_channel":  None,
        "message":      "🎫 Click the button below to open a support ticket.",
        "button_label": "Open a Ticket",
        "button_emoji": "🎫",
        "counter":      0,
    }

# ═══════════════════════════════════════════════════════════
#  UTILITAIRES
# ═══════════════════════════════════════════════════════════
def parse_color(value: str):
    try:    return int(value.strip().lstrip("#"), 16)
    except: return None

def format_message(template: str, member: discord.Member) -> str:
    return (template
            .replace("{user}",     member.mention)
            .replace("{username}", member.display_name)
            .replace("{server}",   member.guild.name)
            .replace("{count}",    str(member.guild.member_count)))

# ── Couleurs des embeds ──────────────────────────────────
C_PRIMARY  = 0x5865F2
C_SUCCESS  = 0x57F287
C_ERROR    = 0xED4245
C_WARN     = 0xFEE75C
C_GOLD     = 0xF1C40F
C_MOD      = 0xEB459E
C_TICKET   = 0x00B0F4
C_FUN      = 0x9B59B6
C_INFO     = 0x3498DB

LIGNE = "▬" * 12

def make_mod_embed(action, target, mod, reason, color):
    e = discord.Embed(
        title=f"⚖️ {action}",
        color=color,
        timestamp=datetime.datetime.utcnow())
    e.add_field(name="👤 Membre",       value=f"{target.mention}\n`{target}`", inline=True)
    e.add_field(name="🛡️ Modérateur",  value=str(mod),                         inline=True)
    e.add_field(name="📝 Raison",       value=reason,                            inline=False)
    e.set_thumbnail(url=target.display_avatar.url)
    e.set_footer(text=f"ID : {target.id}")
    return e

def build_event_embed(cfg: dict, member: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        title=format_message(cfg["title"], member),
        description=format_message(cfg["message"], member),
        color=cfg["color"])
    if cfg.get("show_avatar") and cfg.get("show_thumbnail"):
        embed.set_thumbnail(url=member.display_avatar.url)
    if cfg.get("image_url"):
        embed.set_image(url=cfg["image_url"])
    if cfg.get("show_timestamp"):
        embed.timestamp = datetime.datetime.utcnow()
    if cfg.get("footer"):
        embed.set_footer(text=format_message(cfg["footer"], member))
    return embed

def get_wcfg(gid): return welcome_config.setdefault(gid, default_welcome())
def get_lcfg(gid): return leave_config.setdefault(gid, default_leave())
def get_tcfg(gid): return ticket_config.setdefault(gid, default_ticket_config())

# ── XP ────────────────────────────────────────────────────
def get_xp(gid, uid):      return xp_data.setdefault(gid, {}).get(uid, 0)
def add_xp(gid, uid, amt): xp_data.setdefault(gid, {})[uid] = get_xp(gid, uid) + amt
def xp_to_level(xp):       return int(math.sqrt(xp / 100))
def level_to_xp(lvl):      return lvl * lvl * 100

def xp_progress_bar(xp):
    lvl    = xp_to_level(xp)
    cur    = xp - level_to_xp(lvl)
    nxt    = level_to_xp(lvl + 1) - level_to_xp(lvl)
    filled = int(10 * cur / nxt) if nxt else 10
    return "█" * filled + "░" * (10 - filled), cur, nxt

# ── Logs system ──────────────────────────────────────────
def get_lchan(guild, log_type: str):
    cfg = logs_config.get(guild.id, {})
    cid = cfg.get(log_type)
    if not cid: return None
    return guild.get_channel(cid)

async def send_log(guild, log_type: str, embed: discord.Embed):
    ch = get_lchan(guild, log_type)
    if ch:
        try: await ch.send(embed=embed)
        except discord.Forbidden: pass

# ── Journal de modération ──────────────────────────────────
async def log_mod_action(guild, action, target, mod, reason, color):
    e = discord.Embed(title=f"⚖️ {action}", color=color,
                      timestamp=datetime.datetime.utcnow())
    e.add_field(name="👤 Membre",      value=f"{target} (`{target.id}`)", inline=True)
    e.add_field(name="🛡️ Modérateur", value=str(mod),                     inline=True)
    e.add_field(name="📝 Raison",      value=reason,                        inline=False)
    cid = mod_log_config.get(guild.id)
    if cid:
        ch = guild.get_channel(cid)
        if ch:
            try: await ch.send(embed=e)
            except discord.Forbidden: pass
    await send_log(guild, "moderation", e)

# ═══════════════════════════════════════════════════════════
#  ÉVÉNEMENTS
# ═══════════════════════════════════════════════════════════
@bot.event
async def on_ready():
    load_all()
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching,
                                  name=f"{PREFIX}cmds | Prêt !"))
    print(f"✅  Connecté : {bot.user}  (ID: {bot.user.id})")
    print(f"📋  Préfixe  : {PREFIX}")
    print(f"💾  Données  : chargées depuis {DATA_DIR}/")
    print("─" * 45)


@bot.event
async def on_member_join(member):
    rid = auto_role_config.get(member.guild.id)
    if rid:
        role = member.guild.get_role(rid)
        if role:
            try: await member.add_roles(role, reason="Rôle automatique")
            except discord.Forbidden: pass
    amod = auto_mod_config.get(member.guild.id, {})
    if amod.get("dm_welcome") and amod.get("dm_welcome_msg"):
        try:
            await member.send(format_message(amod["dm_welcome_msg"], member))
        except discord.Forbidden: pass
    cfg = welcome_config.get(member.guild.id, default_welcome())
    if cfg["enabled"]:
        channel = (member.guild.get_channel(cfg["channel"]) if cfg["channel"]
                   else member.guild.system_channel)
        if channel:
            await channel.send(embed=build_event_embed(cfg, member))
    e = discord.Embed(
        title="📥 Membre arrivé",
        description=f"{member.mention} **{member}** a rejoint le serveur.",
        color=0x57F287, timestamp=datetime.datetime.utcnow())
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="Compte créé le", value=discord.utils.format_dt(member.created_at, "D"))
    e.set_footer(text=f"ID : {member.id}")
    await send_log(member.guild, "flux", e)


@bot.event
async def on_member_remove(member):
    cfg = leave_config.get(member.guild.id, default_leave())
    if cfg["enabled"]:
        channel = (member.guild.get_channel(cfg["channel"]) if cfg["channel"]
                   else member.guild.system_channel)
        if channel:
            await channel.send(embed=build_event_embed(cfg, member))
    e = discord.Embed(
        title="📤 Membre parti",
        description=f"**{member}** a quitté le serveur.",
        color=0xED4245, timestamp=datetime.datetime.utcnow())
    e.set_thumbnail(url=member.display_avatar.url)
    e.set_footer(text=f"ID : {member.id}")
    await send_log(member.guild, "flux", e)


@bot.event
async def on_raw_reaction_add(payload):
    if payload.member and payload.member.bot: return
    role_id = react_roles.get(payload.guild_id, {}).get(payload.message_id, {}).get(str(payload.emoji))
    if not role_id: return
    guild = bot.get_guild(payload.guild_id)
    role  = guild.get_role(role_id) if guild else None
    if role and payload.member:
        try: await payload.member.add_roles(role, reason="Rôle réaction")
        except discord.Forbidden: pass


@bot.event
async def on_raw_reaction_remove(payload):
    role_id = react_roles.get(payload.guild_id, {}).get(payload.message_id, {}).get(str(payload.emoji))
    if not role_id: return
    guild  = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id) if guild else None
    role   = guild.get_role(role_id) if guild else None
    if role and member:
        try: await member.remove_roles(role, reason="Rôle réaction retiré")
        except discord.Forbidden: pass


@bot.event
async def on_message_delete(message):
    if not message.guild or message.author.bot: return
    e = discord.Embed(
        title="🗑️ Message supprimé",
        color=0xED4245, timestamp=datetime.datetime.utcnow())
    e.add_field(name="Auteur",  value=f"{message.author.mention} (`{message.author.id}`)", inline=False)
    e.add_field(name="Salon",   value=message.channel.mention, inline=True)
    e.add_field(name="Contenu", value=message.content[:1020] or "*Vide / fichier*", inline=False)
    e.set_footer(text=f"ID message : {message.id}")
    await send_log(message.guild, "message", e)


@bot.event
async def on_message_edit(before, after):
    if not before.guild or before.author.bot: return
    if before.content == after.content: return
    e = discord.Embed(
        title="✏️ Message modifié",
        color=0xFEE75C, timestamp=datetime.datetime.utcnow())
    e.add_field(name="Auteur",  value=f"{before.author.mention} (`{before.author.id}`)", inline=False)
    e.add_field(name="Salon",   value=before.channel.mention, inline=True)
    e.add_field(name="Avant",   value=before.content[:512] or "*Vide*", inline=False)
    e.add_field(name="Après",   value=after.content[:512] or "*Vide*",  inline=False)
    e.set_footer(text=f"ID message : {before.id}")
    await send_log(before.guild, "message", e)


@bot.event
async def on_member_update(before, after):
    guild = after.guild
    if before.roles != after.roles:
        added   = [r for r in after.roles  if r not in before.roles]
        removed = [r for r in before.roles if r not in after.roles]
        if added or removed:
            e = discord.Embed(
                title="🎭 Rôles modifiés",
                color=0x5865F2, timestamp=datetime.datetime.utcnow())
            e.add_field(name="Membre",    value=f"{after.mention} (`{after.id}`)", inline=False)
            if added:   e.add_field(name="➕ Ajouté(s)",  value=" ".join(r.mention for r in added),   inline=False)
            if removed: e.add_field(name="➖ Retiré(s)", value=" ".join(r.mention for r in removed), inline=False)
            await send_log(guild, "role", e)
    if before.premium_since is None and after.premium_since is not None:
        e = discord.Embed(
            title="🚀 Nouveau Boost !",
            description=f"{after.mention} **{after}** vient de booster le serveur ! 💜",
            color=0xFF73FA, timestamp=datetime.datetime.utcnow())
        e.set_thumbnail(url=after.display_avatar.url)
        e.add_field(name="Total boosts", value=str(guild.premium_subscription_count))
        e.add_field(name="Niveau",       value=str(guild.premium_tier))
        await send_log(guild, "boost", e)


@bot.event
async def on_guild_role_create(role):
    e = discord.Embed(
        title="✅ Rôle créé",
        description=f"**{role.name}** (`{role.id}`)",
        color=role.color.value or 0x57F287, timestamp=datetime.datetime.utcnow())
    e.add_field(name="Couleur",      value=str(role.color))
    e.add_field(name="Mentionnable", value="Oui" if role.mentionable else "Non")
    await send_log(role.guild, "role", e)


@bot.event
async def on_guild_role_delete(role):
    e = discord.Embed(
        title="🗑️ Rôle supprimé",
        description=f"**{role.name}** (`{role.id}`)",
        color=0xED4245, timestamp=datetime.datetime.utcnow())
    await send_log(role.guild, "role", e)


@bot.event
async def on_guild_channel_create(channel):
    e = discord.Embed(
        title="✅ Salon créé",
        description=f"{channel.mention} **{channel.name}**",
        color=0x57F287, timestamp=datetime.datetime.utcnow())
    if channel.category:
        e.add_field(name="Catégorie", value=channel.category.name)
    e.set_footer(text=f"ID : {channel.id}")
    await send_log(channel.guild, "channel", e)


@bot.event
async def on_guild_channel_delete(channel):
    e = discord.Embed(
        title="🗑️ Salon supprimé",
        description=f"**#{channel.name}**",
        color=0xED4245, timestamp=datetime.datetime.utcnow())
    if channel.category:
        e.add_field(name="Catégorie", value=channel.category.name)
    e.set_footer(text=f"ID : {channel.id}")
    await send_log(channel.guild, "channel", e)


@bot.event
async def on_guild_channel_update(before, after):
    changes = []
    if before.name != after.name:
        changes.append(f"**Nom :** `{before.name}` → `{after.name}`")
    if getattr(before, "topic", None) != getattr(after, "topic", None):
        changes.append(f"**Topic :** `{before.topic or '—'}` → `{after.topic or '—'}`")
    if not changes: return
    e = discord.Embed(
        title="🔧 Salon modifié",
        description=f"{after.mention}\n" + "\n".join(changes),
        color=0xFEE75C, timestamp=datetime.datetime.utcnow())
    e.set_footer(text=f"ID : {after.id}")
    await send_log(after.guild, "channel", e)


@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel == after.channel: return
    if before.channel is None:
        e = discord.Embed(
            title="🔊 Vocal — Connexion",
            description=f"{member.mention} **{member}** a rejoint **{after.channel.name}**",
            color=0x57F287, timestamp=datetime.datetime.utcnow())
    elif after.channel is None:
        e = discord.Embed(
            title="🔇 Vocal — Déconnexion",
            description=f"{member.mention} **{member}** a quitté **{before.channel.name}**",
            color=0xED4245, timestamp=datetime.datetime.utcnow())
    else:
        e = discord.Embed(
            title="🔄 Vocal — Changement",
            description=f"{member.mention} **{member}** : **{before.channel.name}** → **{after.channel.name}**",
            color=0xFEE75C, timestamp=datetime.datetime.utcnow())
    e.set_footer(text=f"ID : {member.id}")
    await send_log(member.guild, "voice", e)


@bot.event
async def on_message(message):
    if message.author.bot: return

    # AFK
    if message.author.id in afk_users:
        del afk_users[message.author.id]
        save_afk()
        await message.channel.send(
            embed=discord.Embed(
                description=f"👋 Bienvenue de retour {message.author.mention} ! Statut AFK retiré.",
                color=C_SUCCESS))
    for user in message.mentions:
        if user.id in afk_users:
            await message.channel.send(
                embed=discord.Embed(
                    description=f"💤 **{user.display_name}** est AFK : *{afk_users[user.id]}*",
                    color=C_WARN))

    # XP
    if message.guild:
        uid  = message.author.id
        gid  = message.guild.id
        now  = datetime.datetime.utcnow()
        last = xp_cooldown.get(uid)
        if last is None or (now - last).total_seconds() >= 60:
            xp_cooldown[uid] = now
            gain    = random.randint(15, 25)
            old_lvl = xp_to_level(get_xp(gid, uid))
            add_xp(gid, uid, gain)
            save_xp()
            new_lvl = xp_to_level(get_xp(gid, uid))
            if new_lvl > old_lvl:
                e = discord.Embed(
                    title="🎉 Niveau supérieur !",
                    description=f"{message.author.mention} a atteint le **niveau {new_lvl}** ! 🚀",
                    color=C_GOLD)
                e.set_thumbnail(url=message.author.display_avatar.url)
                await message.channel.send(embed=e)
                rewards = xp_level_rewards.get(gid, {})
                if new_lvl in rewards:
                    role = message.guild.get_role(rewards[new_lvl])
                    if role:
                        try: await message.author.add_roles(role, reason=f"Récompense niveau {new_lvl}")
                        except discord.Forbidden: pass

    # Anti-spam automatique
    if message.guild:
        cid    = message.channel.id
        now_ts = _time.time()
        times  = channel_msg_times.setdefault(cid, [])
        times.append(now_ts)
        channel_msg_times[cid] = [t for t in times if now_ts - t <= 10]
        if len(channel_msg_times[cid]) >= 8 and message.channel.slowmode_delay == 0:
            try:
                await message.channel.edit(slowmode_delay=5)
                await message.channel.send(
                    embed=discord.Embed(
                        description="⚠️ **Slowmode 5s** activé automatiquement (spam détecté).",
                        color=C_WARN),
                    delete_after=15)
                await asyncio.sleep(30)
                await message.channel.edit(slowmode_delay=0)
            except discord.Forbidden: pass

    await bot.process_commands(message)


# ═══════════════════════════════════════════════════════════
#  AIDE  (+help)
# ═══════════════════════════════════════════════════════════
CATEGORIES_HELP = {
    "moderation": {
        "emoji": "🛠️",
        "nom": "Modération",
        "commandes": [
            ("+kick <membre> [raison]",     "Expulse un membre du serveur."),
            ("+ban <membre> [raison]",      "Bannit définitivement un membre."),
            ("+unban <nom#tag>",            "Débannit un membre banni."),
            ("+mute <membre> [durée] [raison]", "Rend un membre muet (en minutes)."),
            ("+unmute <membre>",            "Retire le mutisme d'un membre."),
            ("+clear [nombre] [membre]",    "Supprime des messages dans le salon."),
            ("+nuke [raison]",              "Recrée le salon (efface tous les messages)."),
            ("+warn <membre> [raison]",     "Avertit un membre."),
            ("+warns [membre]",             "Affiche les avertissements d'un membre."),
            ("+clearwarns <membre>",        "Supprime tous les avertissements d'un membre."),
            ("+tempban <membre> <durée> [raison]", "Ban temporaire auto-levé (ex: `2h`, `1j`)."),
            ("+tempmute <membre> <durée> [raison]","Mute temporaire auto-levé (ex: `30m`, `2h`)."),
            ("+addrole <membre> <rôle>",    "Ajoute un rôle à un membre."),
            ("+removerole <membre> <rôle>", "Retire un rôle d'un membre."),
            ("+massrole <add/remove> <rôle>","Ajoute ou retire un rôle à tous les membres."),
        ]
    },
    "vocal": {
        "emoji": "🔊",
        "nom": "Vocal",
        "commandes": [
            ("+vcmove <membre> <salon>",    "Déplace un membre vers un salon vocal."),
            ("+vcmute <membre>",            "Mute un membre en vocal."),
            ("+vcunmute <membre>",          "Démute un membre en vocal."),
        ]
    },
    "divertissement": {
        "emoji": "🎉",
        "nom": "Divertissement",
        "commandes": [
            ("+8ball <question>",           "Pose une question à la boule magique."),
            ("+flip",                       "Lance une pièce (face ou pile)."),
            ("+roll [faces]",               "Lance un dé (6 faces par défaut)."),
            ("+rps <pierre|papier|ciseaux>","Pierre, papier, ciseaux contre le bot."),
            ("+joke",                       "Affiche une blague aléatoire."),
            ("+compliment [membre]",        "Fait un compliment à un membre."),
            ("+roast [membre]",             "Taquine gentiment un membre."),
            ("+meme",                       "Affiche un mème aléatoire."),
            ("+color",                      "Génère une couleur aléatoire."),
        ]
    },
    "statistiques": {
        "emoji": "📊",
        "nom": "Statistiques",
        "commandes": [
            ("+stats",                      "Affiche les statistiques du serveur."),
            ("+userstats [membre]",         "Affiche les stats d'un membre."),
            ("+info [membre]",              "Informations détaillées sur un membre."),
            ("+avatar [membre]",            "Affiche l'avatar d'un membre."),
            ("+ping",                       "Affiche la latence du bot."),
            ("+uptime",                     "Temps de fonctionnement du bot."),
            ("+roles",                      "Liste tous les rôles du serveur."),
        ]
    },
    "economie": {
        "emoji": "💰",
        "nom": "Économie",
        "commandes": [
            ("+balance [membre]",              "Affiche le solde d'un membre."),
            ("+daily",                         "Réclame ta récompense journalière."),
            ("+work",                          "Travaille pour gagner des pièces (cooldown 4h)."),
            ("+give <membre> <montant>",       "Transfère des pièces à un membre."),
            ("+rob <membre>",                  "Tente de voler un membre (40% succès, cooldown 1h)."),
            ("+richest",                       "Classement des membres les plus riches."),
            ("+blackjack <mise>",              "Joue au blackjack contre le croupier (max 10 000 🪙)."),
            ("+slots <mise>",                  "Tente ta chance à la machine à sous (max 5 000 🪙)."),
            ("+coinflip <mise> <pile/face>",   "Parie sur pile ou face (max 10 000 🪙)."),
        ]
    },
    "xp": {
        "emoji": "⭐",
        "nom": "XP / Niveaux",
        "commandes": [
            ("+rank [membre]",              "Affiche le rang et l'XP d'un membre."),
            ("+leaderboard",                "Classement XP du serveur."),
            ("+levelrole <niveau> <rôle>",  "Attribue un rôle à un niveau donné."),
        ]
    },
    "salons": {
        "emoji": "🔒",
        "nom": "Salons",
        "commandes": [
            ("+lock [#salon]",              "Bloque les messages @everyone dans le salon."),
            ("+delock [#salon]",            "Déverrouille le salon."),
            ("+hide [#salon]",              "Cache le salon à @everyone."),
            ("+seek [#salon]",              "Rend le salon visible à @everyone."),
            ("+slowmode <secondes> [#salon]","Définit un slowmode (0 = désactivé)."),
        ]
    },
    "utilitaire": {
        "emoji": "🔧",
        "nom": "Utilitaire",
        "commandes": [
            ("+giveaway <durée> <gagnants> <lot>", "Lance un giveaway (ex: `1h 1 Nitro`)."),
            ("+gend <ID>",                  "Termine un giveaway en avance."),
            ("+greroll <ID> [gagnants]",    "Reroll un ou plusieurs gagnants."),
            ("+poll <question> <opt1> <opt2>...",   "Crée un sondage."),
            ("+embed [#salon]",             "Crée un embed personnalisé."),
            ("+afk [raison]",              "Passe en mode AFK."),
            ("+calc <expression>",          "Calcule une expression mathématique."),
            ("+weather [ville]",            "Météo fictive d'une ville."),
            ("+say <message>",             "Fait parler le bot (modérateurs)."),
        ]
    },
    "tickets": {
        "emoji": "🎫",
        "nom": "Tickets",
        "commandes": [
            ("+ticket panel",               "Envoie le panel de tickets dans le salon."),
            ("+close",                      "Ferme le ticket actuel + transcript .txt dans les logs."),
            ("+claim",                      "Prend en charge le ticket (staff)."),
            ("+add <membre>",               "Ajoute un membre au ticket."),
            ("+remove <membre>",            "Retire un membre du ticket."),
            ("+remind",                     "Rappelle la personne qui a ouvert le ticket."),
            ("+rename <nom>",               "Renomme le salon du ticket."),
        ]
    },
    "reactroles": {
        "emoji": "🎭",
        "nom": "Rôles Réaction",
        "commandes": [
            ("+rr <msg_id> <emoji> <rôle>", "Associe un emoji à un rôle sur un message."),
            ("+listrr",                     "Liste les rôles réaction configurés."),
        ]
    },
    "config": {
        "emoji": "⚙️",
        "nom": "Configuration",
        "commandes": [
            ("+wlcmciao",                   "Assistant de configuration (arrivée/départ)."),
            ("+modlog [#salon]",            "Configure le journal de modération."),
            ("+autorole [rôle]",            "Rôle attribué automatiquement aux nouveaux membres."),
            ("+autowarn <nombre>",          "Mute automatique après X avertissements."),
            ("+dmwelcome <on/off> [msg]",   "Message de bienvenue en DM."),
            ("+logs",                       "Affiche les salons de logs configurés."),
            ("+logs set <type> [#salon]",   "Configure un salon de log (ticket, message, moderation...)."),
            ("+logs off <type>",            "Désactive un type de log."),
        ]
    },
    "owner": {
        "emoji": "🔐",
        "nom": "Owner",
        "commandes": [
            ("+help [catégorie]",           "Affiche l'aide complète par catégorie."),
            ("+cmds",                       "Liste toutes les commandes du bot."),
            ("+grnt",                       "Liste les commandes réservées aux owners."),
        ]
    },
}


@bot.command(name="help")
async def help_cmd(ctx, categorie: str = None):
    if categorie is None:
        e = discord.Embed(
            title="📖 Aide — Liste des catégories",
            description=(
                f"Utilise **`{PREFIX}help <catégorie>`** pour voir les commandes détaillées.\n"
                f"Utilise **`{PREFIX}cmds`** pour voir toutes les commandes d'un coup.\n"
                f"{'▬' * 14}\n"
            ),
            color=C_PRIMARY,
            timestamp=datetime.datetime.utcnow())

        col1 = ""
        col2 = ""
        cats = list(CATEGORIES_HELP.items())
        mid  = math.ceil(len(cats) / 2)
        for key, data in cats[:mid]:
            col1 += f"{data['emoji']} **{data['nom']}**\n`{PREFIX}help {key}`\n\n"
        for key, data in cats[mid:]:
            col2 += f"{data['emoji']} **{data['nom']}**\n`{PREFIX}help {key}`\n\n"

        e.add_field(name="\u200b", value=col1.strip(), inline=True)
        e.add_field(name="\u200b", value=col2.strip(), inline=True)
        total = sum(len(d["commandes"]) for d in CATEGORIES_HELP.values())
        e.set_footer(text=f"{total} commandes disponibles  •  Préfixe : {PREFIX}  •  Demandé par {ctx.author}",
                     icon_url=ctx.author.display_avatar.url)
        if ctx.guild and ctx.guild.icon:
            e.set_thumbnail(url=ctx.guild.icon.url)
        return await ctx.send(embed=e)

    match = None
    for key, data in CATEGORIES_HELP.items():
        if categorie.lower() in key or categorie.lower() in data["nom"].lower():
            match = (key, data)
            break

    if not match:
        return await ctx.send(embed=discord.Embed(
            description=f"❌ Catégorie inconnue. Catégories disponibles :\n" +
                        ", ".join(f"`{k}`" for k in CATEGORIES_HELP),
            color=C_ERROR))

    key, data = match
    desc = f"{data['emoji']} **{data['nom']}**\n{'▬' * 14}\n\n"
    for cmd, explication in data["commandes"]:
        desc += f"**`{cmd}`**\n└ {explication}\n\n"

    e = discord.Embed(
        title=f"{data['emoji']} Aide — {data['nom']}",
        description=desc.strip(),
        color=C_PRIMARY,
        timestamp=datetime.datetime.utcnow())
    e.set_footer(text=f"Préfixe : {PREFIX}  •  Demandé par {ctx.author}",
                 icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=e)


# ═══════════════════════════════════════════════════════════
#  COMMANDES  (+cmds)
# ═══════════════════════════════════════════════════════════
@bot.command(name="cmds")
async def cmds_cmd(ctx):
    sections = [
        ("🛠️ Modération",    ["+kick", "+ban", "+unban", "+tempban", "+mute", "+unmute", "+tempmute",
                               "+clear", "+nuke", "+warn", "+warns", "+clearwarns",
                               "+addrole", "+removerole", "+massrole"]),
        ("🔒 Salons",         ["+lock", "+delock", "+hide", "+seek", "+slowmode"]),
        ("🔊 Vocal",          ["+vcmove", "+vcmute", "+vcunmute"]),
        ("🎉 Divertissement", ["+8ball", "+flip", "+roll", "+rps", "+joke",
                               "+compliment", "+roast", "+meme", "+color"]),
        ("⭐ XP / Niveaux",   ["+rank", "+leaderboard", "+levelrole"]),
        ("💰 Économie",       ["+balance", "+daily", "+work", "+give", "+rob", "+richest",
                               "+blackjack", "+slots", "+coinflip"]),
        ("🔐 Owner (`+grnt`)", ["+stats", "+userstats", "+info", "+avatar", "+ping", "+uptime", "+roles",
                                "+giveaway", "+greroll", "+gend", "+poll", "+embed", "+afk", "+calc", "+weather", "+say",
                                "+ticket panel", "+close", "+claim", "+add", "+remove", "+remind", "+rename",
                                "+rr", "+listrr",
                                "+wlcmciao", "+modlog", "+autorole", "+autowarn", "+dmwelcome",
                                "+logs set", "+logs off", "+logs",
                                "+help", "+grnt"]),
    ]
    total = sum(len(c) for _, c in sections)

    e = discord.Embed(
        title=f"📋 Toutes les commandes — préfixe `{PREFIX}`",
        description=(
            f"**{total} commandes** disponibles sur ce serveur.\n"
            f"`{PREFIX}help <catégorie>` pour les détails  •  `{PREFIX}wlcmciao` pour configurer\n"
            f"{'▬' * 14}"
        ),
        color=C_PRIMARY,
        timestamp=datetime.datetime.utcnow())

    for section, cmds in sections:
        e.add_field(
            name=f"{section}  ·  {len(cmds)} cmd{'s' if len(cmds) > 1 else ''}",
            value="  ".join(f"`{c}`" for c in cmds),
            inline=False)

    e.set_footer(text=f"Demandé par {ctx.author}  •  {PREFIX}help pour les descriptions",
                 icon_url=ctx.author.display_avatar.url)
    if ctx.guild and ctx.guild.icon:
        e.set_thumbnail(url=ctx.guild.icon.url)
    await ctx.send(embed=e)


# ═══════════════════════════════════════════════════════════
#  CASINO  (+casino)
# ═══════════════════════════════════════════════════════════
@bot.command(name="casino")
async def casino(ctx):
    e = discord.Embed(
        title="🎰 Casino — Commandes disponibles",
        description=(
            f"Bienvenue au casino ! Tente ta chance avec ces jeux.\n"
            f"{'▬' * 16}\n"
        ),
        color=0xFFD700,
        timestamp=datetime.datetime.utcnow())

    e.add_field(
        name="🃏 Blackjack",
        value=(f"`{PREFIX}blackjack <mise>`  ·  alias `{PREFIX}bj`\n"
               f"└ Joue contre le croupier. Tape `hit` ou `stand`.\n"
               f"└ Blackjack naturel → ×2.5  •  Victoire → ×2\n"
               f"└ Mise max : **10 000 🪙**"),
        inline=False)

    e.add_field(
        name="🎰 Machine à sous",
        value=(f"`{PREFIX}slots <mise>`\n"
               f"└ 3 rouleaux : 🍒 🍋 🍊 ⭐ 💎 7️⃣\n"
               f"└ 3 identiques → Jackpot (jusqu'à ×12)  •  2 identiques → ×1.5\n"
               f"└ Mise max : **5 000 🪙**"),
        inline=False)

    e.add_field(
        name="🪙 Pile ou Face",
        value=(f"`{PREFIX}coinflip <mise> <pile/face>`  ·  alias `{PREFIX}cf`\n"
               f"└ Parie sur pile ou face, 50/50.\n"
               f"└ Victoire → ×2\n"
               f"└ Mise max : **10 000 🪙**"),
        inline=False)

    e.add_field(
        name="💼 Travailler",
        value=(f"`{PREFIX}work`\n"
               f"└ Gagne entre **100 et 500 🪙** en travaillant.\n"
               f"└ Cooldown : **4 heures**"),
        inline=True)

    e.add_field(
        name="🦹 Voler",
        value=(f"`{PREFIX}rob <membre>`\n"
               f"└ 40% de succès — vole 10-30% du solde.\n"
               f"└ Si raté : amende 50-250 🪙\n"
               f"└ Cooldown : **1 heure**"),
        inline=True)

    e.add_field(
        name="\u200b",
        value=(f"{'▬' * 16}\n"
               f"💰 Solde : `{PREFIX}balance`  •  🎁 Daily : `{PREFIX}daily`\n"
               f"💸 Don : `{PREFIX}give <membre> <montant>`  •  🏆 Richesse : `{PREFIX}richest`"),
        inline=False)

    if ctx.guild and ctx.guild.icon:
        e.set_thumbnail(url=ctx.guild.icon.url)
    e.set_footer(text=f"Bonne chance, {ctx.author.display_name} ! 🍀",
                 icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=e)


# ═══════════════════════════════════════════════════════════
#  CMD PUBLIC  (+cmd) — divertissement & XP/niveaux
# ═══════════════════════════════════════════════════════════
@bot.command(name="cmd")
async def cmd_public(ctx):
    e = discord.Embed(
        title="📋 Commandes — Divertissement & Niveaux",
        description=(
            f"Préfixe : **`{PREFIX}`**\n"
            f"{'▬' * 16}"
        ),
        color=C_FUN,
        timestamp=datetime.datetime.utcnow())

    e.add_field(
        name="🎉 Divertissement",
        value=("`+8ball` `+flip` `+roll` `+rps`\n"
               "`+joke` `+compliment` `+roast`\n"
               "`+meme` `+color`"),
        inline=True)

    e.add_field(
        name="⭐ XP / Niveaux",
        value=("`+rank` `+leaderboard`\n"
               "`+levelrole`"),
        inline=True)

    e.add_field(
        name="💰 Économie & Casino",
        value=("`+balance` `+daily` `+work`\n"
               "`+give` `+rob` `+richest`\n"
               "`+blackjack` `+slots` `+coinflip`\n"
               "`+casino` pour les détails"),
        inline=False)

    e.set_footer(text=f"Demandé par {ctx.author}",
                 icon_url=ctx.author.display_avatar.url)
    if ctx.guild and ctx.guild.icon:
        e.set_thumbnail(url=ctx.guild.icon.url)
    await ctx.send(embed=e)


# ═══════════════════════════════════════════════════════════
#  OWNER CMDS  (+grnt)
# ═══════════════════════════════════════════════════════════
@bot.command(name="grnt")
async def grnt_cmd(ctx):
    e = discord.Embed(
        title="🔐 Commandes Owner",
        description=(
            f"Commandes réservées aux owners uniquement.\n"
            f"{'▬' * 16}"
        ),
        color=0xFF4500,
        timestamp=datetime.datetime.utcnow())

    e.add_field(
        name="📊 Statistiques",
        value="`+stats` `+userstats` `+info`\n`+avatar` `+ping` `+uptime` `+roles`",
        inline=False)

    e.add_field(
        name="🔧 Utilitaire",
        value="`+giveaway` `+greroll` `+gend`\n`+poll` `+embed` `+afk`\n`+calc` `+weather` `+say`",
        inline=False)

    e.add_field(
        name="🔒 Salons",
        value="`+lock` `+delock`\n`+hide` `+seek` `+slowmode`",
        inline=False)

    e.add_field(
        name="🎫 Tickets",
        value="`+ticket panel` `+close` `+claim`\n`+add` `+remove` `+remind`",
        inline=True)

    e.add_field(
        name="🎭 Rôles Réaction",
        value="`+rr` `+listrr`",
        inline=True)

    e.add_field(
        name="⚙️ Config",
        value="`+wlcmciao` `+modlog` `+autorole`\n`+autowarn` `+dmwelcome`\n`+logs` `+logs set` `+logs off`",
        inline=False)

    e.add_field(
        name="📖 Aide",
        value="`+help` `+cmds` `+grnt`",
        inline=False)

    e.set_footer(text=f"Demandé par {ctx.author}",
                 icon_url=ctx.author.display_avatar.url)
    if ctx.guild and ctx.guild.icon:
        e.set_thumbnail(url=ctx.guild.icon.url)
    await ctx.send(embed=e)


# ═══════════════════════════════════════════════════════════
#  MODÉRATION
# ═══════════════════════════════════════════════════════════
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="Aucune raison"):
    await member.kick(reason=reason)
    await ctx.send(embed=make_mod_embed("👢 Expulsion", member, ctx.author, reason, C_WARN))
    await log_mod_action(ctx.guild, "Expulsion", member, ctx.author, reason, C_WARN)

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="Aucune raison"):
    await member.ban(reason=reason)
    await ctx.send(embed=make_mod_embed("🔨 Bannissement", member, ctx.author, reason, C_ERROR))
    await log_mod_action(ctx.guild, "Bannissement", member, ctx.author, reason, C_ERROR)

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, username):
    bans = [entry async for entry in ctx.guild.bans()]
    for entry in bans:
        if str(entry.user) == username:
            await ctx.guild.unban(entry.user)
            return await ctx.send(embed=discord.Embed(
                title="✅ Débannissement",
                description=f"**{entry.user}** a été débanni avec succès.",
                color=C_SUCCESS))
    await ctx.send(embed=discord.Embed(
        description="❌ Utilisateur introuvable dans la liste des bans.", color=C_ERROR))

def _parse_duration(s: str):
    units = {"s": 1, "m": 60, "h": 3600, "j": 86400, "d": 86400}
    if len(s) < 2:
        return None
    unit = s[-1].lower()
    if unit not in units or not s[:-1].isdigit():
        return None
    return int(s[:-1]) * units[unit]

def _fmt_duration(seconds: int) -> str:
    if seconds < 60:    return f"{seconds}s"
    if seconds < 3600:  return f"{seconds//60}min"
    if seconds < 86400: return f"{seconds//3600}h"
    return f"{seconds//86400}j"


@bot.command(name="tempban")
@commands.has_permissions(ban_members=True)
async def tempban(ctx, member: discord.Member, duration: str, *, reason="Aucune raison"):
    secs = _parse_duration(duration)
    if not secs:
        return await ctx.send(embed=discord.Embed(
            description="❌ Format invalide. Exemples : `10m`, `2h`, `1j`", color=C_ERROR))
    label = f"🔨 Ban temporaire ({_fmt_duration(secs)})"
    await member.ban(reason=f"[Tempban {_fmt_duration(secs)}] {reason}")
    await ctx.send(embed=make_mod_embed(label, member, ctx.author, reason, C_ERROR))
    await log_mod_action(ctx.guild, label, member, ctx.author, reason, C_ERROR)
    async def _unban():
        await asyncio.sleep(secs)
        try:
            await ctx.guild.unban(member, reason="Tempban expiré")
            await log_mod_action(ctx.guild, "🔓 Tempban expiré", member, bot.user,
                                 f"Durée : {_fmt_duration(secs)}", C_SUCCESS)
        except Exception: pass
    asyncio.create_task(_unban())


@bot.command(name="tempmute")
@commands.has_permissions(manage_roles=True)
async def tempmute(ctx, member: discord.Member, duration: str, *, reason="Aucune raison"):
    secs = _parse_duration(duration)
    if not secs:
        return await ctx.send(embed=discord.Embed(
            description="❌ Format invalide. Exemples : `10m`, `2h`, `1j`", color=C_ERROR))
    role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not role:
        role = await ctx.guild.create_role(name="Muted")
        for ch in ctx.guild.channels:
            await ch.set_permissions(role, send_messages=False, speak=False)
    await member.add_roles(role, reason=f"[Tempmute {_fmt_duration(secs)}] {reason}")
    label = f"🔇 Mute temporaire ({_fmt_duration(secs)})"
    await ctx.send(embed=make_mod_embed(label, member, ctx.author, reason, 0x747F8D))
    await log_mod_action(ctx.guild, label, member, ctx.author, reason, 0x747F8D)
    async def _unmute():
        await asyncio.sleep(secs)
        if role in member.roles:
            try:
                await member.remove_roles(role, reason="Tempmute expiré")
                await log_mod_action(ctx.guild, "🔊 Tempmute expiré", member, bot.user,
                                     f"Durée : {_fmt_duration(secs)}", C_SUCCESS)
            except Exception: pass
    asyncio.create_task(_unmute())


@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, duration: int = 10, *, reason="Aucune raison"):
    role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not role:
        role = await ctx.guild.create_role(name="Muted")
        for ch in ctx.guild.channels:
            await ch.set_permissions(role, send_messages=False, speak=False)
    await member.add_roles(role, reason=reason)
    label = f"🔇 Mute ({duration} min)"
    await ctx.send(embed=make_mod_embed(label, member, ctx.author, reason, 0x747F8D))
    await log_mod_action(ctx.guild, label, member, ctx.author, reason, 0x747F8D)
    await asyncio.sleep(duration * 60)
    if role in member.roles:
        await member.remove_roles(role)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    role = discord.utils.get(ctx.guild.roles, name="Muted")
    if role and role in member.roles:
        await member.remove_roles(role)
        await ctx.send(embed=discord.Embed(
            title="🔊 Mute levé",
            description=f"{member.mention} peut à nouveau parler.",
            color=C_SUCCESS))
    else:
        await ctx.send(embed=discord.Embed(
            description="❌ Ce membre n'est pas muet.", color=C_ERROR))

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 10, member: discord.Member = None):
    amount = min(max(amount, 1), 1000)
    await ctx.message.delete()
    check   = (lambda m: m.author == member) if member else None
    deleted = await ctx.channel.purge(limit=amount, check=check)
    msg = await ctx.send(embed=discord.Embed(
        title="🧹 Nettoyage effectué",
        description=(f"**{len(deleted)}** message(s) supprimé(s)"
                     + (f" de **{member.display_name}**" if member else "") + "."),
        color=C_WARN))
    await asyncio.sleep(4)
    await msg.delete()

@bot.command()
@commands.has_permissions(manage_channels=True)
async def nuke(ctx, *, reason="Nuke"):
    channel = ctx.channel
    confirm = discord.Embed(
        title="💣 Confirmation — Nuke",
        description=(f"Es-tu sûr de vouloir **nuker** {channel.mention} ?\n"
                     f"**TOUS** les messages seront supprimés définitivement.\n\n"
                     f"Tape `oui` pour confirmer ou `non` pour annuler. *(30s)*"),
        color=C_ERROR)
    await ctx.send(embed=confirm)

    def check(m):
        return (m.author == ctx.author and m.channel == ctx.channel
                and m.content.lower() in ("oui", "non", "yes", "no"))
    try:
        rep = await bot.wait_for("message", check=check, timeout=30)
    except asyncio.TimeoutError:
        return await ctx.send(embed=discord.Embed(
            description="⏱️ Temps écoulé. Nuke annulé.", color=C_ERROR))
    if rep.content.lower() not in ("oui", "yes"):
        return await ctx.send(embed=discord.Embed(
            description="❌ Nuke annulé.", color=C_ERROR))

    position   = channel.position
    overwrites = channel.overwrites
    topic      = channel.topic
    slowmode   = channel.slowmode_delay
    nsfw       = channel.is_nsfw()
    category   = channel.category
    name       = channel.name
    await channel.delete(reason=f"Nuke par {ctx.author}")
    new_ch = await ctx.guild.create_text_channel(
        name=name,
        overwrites=overwrites,
        category=category,
        topic=topic,
        slowmode_delay=slowmode,
        nsfw=nsfw,
        reason=f"Nuke par {ctx.author} — {reason}")
    await new_ch.edit(position=position)
    e = discord.Embed(
        title="💥 Salon nuké !",
        description=f"Recréé par {ctx.author.mention}\n*Raison : {reason}*",
        color=C_ERROR, timestamp=datetime.datetime.utcnow())
    e.set_footer(text="Boom 💣")
    await new_ch.send(content=ctx.author.mention, embed=e)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="Aucune raison"):
    warns.setdefault(member.id, []).append(
        {"reason": reason, "date": str(datetime.date.today())})
    total = len(warns[member.id])
    save_warns()
    label = f"⚠️ Avertissement #{total}"
    await ctx.send(embed=make_mod_embed(label, member, ctx.author, reason, C_WARN))
    await log_mod_action(ctx.guild, label, member, ctx.author, reason, C_WARN)
    limit = auto_mod_config.get(ctx.guild.id, {}).get("warn_limit", 0)
    if limit and total >= limit:
        role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not role:
            role = await ctx.guild.create_role(name="Muted")
            for ch in ctx.guild.channels:
                await ch.set_permissions(role, send_messages=False, speak=False)
        if role not in member.roles:
            await member.add_roles(role, reason=f"Mute auto ({total} warns)")
            await ctx.send(embed=discord.Embed(
                title="🔇 Mute automatique",
                description=f"{member.mention} a été muté automatiquement après **{total} avertissements**.",
                color=C_ERROR))
            await log_mod_action(ctx.guild, f"Mute auto ({total} warns)", member,
                                 bot.user, "Limite d'avertissements atteinte", C_ERROR)

@bot.command(name="warns")
async def warns_cmd(ctx, member: discord.Member = None):
    member = member or ctx.author
    w = warns.get(member.id, [])
    e = discord.Embed(
        title=f"⚠️ Avertissements — {member.display_name}",
        color=C_WARN,
        timestamp=datetime.datetime.utcnow())
    e.set_thumbnail(url=member.display_avatar.url)
    e.description = ("\n".join(
        f"**#{i+1}** `{x['date']}` — {x['reason']}" for i, x in enumerate(w))
        or "✅ Aucun avertissement trouvé.")
    e.set_footer(text=f"Total : {len(w)} avertissement(s)  •  ID : {member.id}")
    await ctx.send(embed=e)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clearwarns(ctx, member: discord.Member):
    warns[member.id] = []
    save_warns()
    await ctx.send(embed=discord.Embed(
        title="✅ Avertissements effacés",
        description=f"Tous les avertissements de **{member.display_name}** ont été supprimés.",
        color=C_SUCCESS))


# ═══════════════════════════════════════════════════════════
#  GESTION DES RÔLES  (+addrole +removerole)
# ═══════════════════════════════════════════════════════════

@bot.command(name="addrole")
@commands.has_permissions(manage_roles=True)
async def addrole(ctx, member: discord.Member, *, role: discord.Role):
    if role >= ctx.guild.me.top_role:
        return await ctx.send(embed=discord.Embed(
            description="❌ Je ne peux pas attribuer un rôle supérieur ou égal au mien.", color=C_ERROR))
    if role in member.roles:
        return await ctx.send(embed=discord.Embed(
            description=f"❌ {member.mention} a déjà le rôle {role.mention}.", color=C_ERROR))
    await member.add_roles(role, reason=f"Ajouté par {ctx.author}")
    await ctx.send(embed=discord.Embed(
        title="✅ Rôle ajouté",
        description=f"{role.mention} a été ajouté à {member.mention} par {ctx.author.mention}.",
        color=C_SUCCESS))
    await log_mod_action(ctx.guild, "✅ Rôle ajouté", member, ctx.author,
                         f"Rôle : {role.name}", C_SUCCESS)


@bot.command(name="removerole")
@commands.has_permissions(manage_roles=True)
async def removerole(ctx, member: discord.Member, *, role: discord.Role):
    if role >= ctx.guild.me.top_role:
        return await ctx.send(embed=discord.Embed(
            description="❌ Je ne peux pas retirer un rôle supérieur ou égal au mien.", color=C_ERROR))
    if role not in member.roles:
        return await ctx.send(embed=discord.Embed(
            description=f"❌ {member.mention} n'a pas le rôle {role.mention}.", color=C_ERROR))
    await member.remove_roles(role, reason=f"Retiré par {ctx.author}")
    await ctx.send(embed=discord.Embed(
        title="✅ Rôle retiré",
        description=f"{role.mention} a été retiré à {member.mention} par {ctx.author.mention}.",
        color=C_SUCCESS))
    await log_mod_action(ctx.guild, "✅ Rôle retiré", member, ctx.author,
                         f"Rôle : {role.name}", C_SUCCESS)


@bot.command(name="massrole")
@commands.has_permissions(manage_roles=True)
async def massrole(ctx, action: str, *, role: discord.Role):
    action = action.lower()
    if action not in ("add", "remove", "ajouter", "retirer"):
        return await ctx.send(embed=discord.Embed(
            description="❌ Action invalide. Utilise `add` ou `remove`.", color=C_ERROR))
    if role >= ctx.guild.me.top_role:
        return await ctx.send(embed=discord.Embed(
            description="❌ Je ne peux pas gérer un rôle supérieur ou égal au mien.", color=C_ERROR))
    adding = action in ("add", "ajouter")
    msg = await ctx.send(embed=discord.Embed(
        description=f"⏳ {'Ajout' if adding else 'Retrait'} du rôle {role.mention} en cours...",
        color=C_WARN))
    count = 0
    for member in ctx.guild.members:
        try:
            if adding and role not in member.roles:
                await member.add_roles(role, reason=f"Massrole par {ctx.author}")
                count += 1
            elif not adding and role in member.roles:
                await member.remove_roles(role, reason=f"Massrole par {ctx.author}")
                count += 1
        except discord.Forbidden:
            pass
    await msg.edit(embed=discord.Embed(
        title=f"✅ Massrole terminé",
        description=(f"Rôle {role.mention} **{'ajouté à' if adding else 'retiré de'}** "
                     f"**{count}** membre(s)."),
        color=C_SUCCESS))


# ═══════════════════════════════════════════════════════════
#  GESTION DE SALONS  (+lock +delock +hide +seek +slowmode)
# ═══════════════════════════════════════════════════════════

@bot.command(name="lock")
@commands.has_permissions(manage_channels=True)
async def lock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(embed=discord.Embed(
        title="🔒 Salon verrouillé",
        description=f"{channel.mention} a été **verrouillé** par {ctx.author.mention}.",
        color=C_ERROR))
    await log_mod_action(ctx.guild, "🔒 Salon verrouillé", ctx.author, ctx.author,
                         f"Salon : {channel.name}", C_ERROR)


@bot.command(name="delock")
@commands.has_permissions(manage_channels=True)
async def delock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(embed=discord.Embed(
        title="🔓 Salon déverrouillé",
        description=f"{channel.mention} a été **déverrouillé** par {ctx.author.mention}.",
        color=C_SUCCESS))
    await log_mod_action(ctx.guild, "🔓 Salon déverrouillé", ctx.author, ctx.author,
                         f"Salon : {channel.name}", C_SUCCESS)


HIDE_ROLE_ID = 1492625662392013062

@bot.command(name="hide")
@commands.has_permissions(manage_channels=True)
async def hide(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    role = ctx.guild.get_role(HIDE_ROLE_ID)
    target = role if role else ctx.guild.default_role
    await channel.set_permissions(target, read_messages=False)
    await ctx.send(embed=discord.Embed(
        title="🙈 Salon caché",
        description=f"{channel.mention} est maintenant **invisible** pour {target.mention}.",
        color=C_WARN))
    await log_mod_action(ctx.guild, "🙈 Salon caché", ctx.author, ctx.author,
                         f"Salon : {channel.name}", C_WARN)


@bot.command(name="seek")
@commands.has_permissions(manage_channels=True)
async def seek(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    role = ctx.guild.get_role(HIDE_ROLE_ID)
    target = role if role else ctx.guild.default_role
    await channel.set_permissions(target, read_messages=True)
    await ctx.send(embed=discord.Embed(
        title="👁️ Salon visible",
        description=f"{channel.mention} est maintenant **visible** pour {target.mention}.",
        color=C_SUCCESS))
    await log_mod_action(ctx.guild, "👁️ Salon visible", ctx.author, ctx.author,
                         f"Salon : {channel.name}", C_SUCCESS)


@bot.command(name="slowmode")
@commands.has_permissions(manage_channels=True)
async def slowmode_cmd(ctx, secondes: int = 0, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    if not 0 <= secondes <= 21600:
        return await ctx.send(embed=discord.Embed(
            description="❌ La durée doit être entre **0** et **21600** secondes.", color=C_ERROR))
    await channel.edit(slowmode_delay=secondes)
    if secondes == 0:
        desc = f"✅ Slowmode **désactivé** sur {channel.mention}."
    else:
        desc = f"✅ Slowmode défini à **{secondes}s** sur {channel.mention}."
    await ctx.send(embed=discord.Embed(description=desc, color=C_SUCCESS))


# ═══════════════════════════════════════════════════════════
#  ASSISTANT DE CONFIGURATION  (+wlcmciao)
# ═══════════════════════════════════════════════════════════
async def _run_setup_wizard(ctx, config_dict, kind: str):
    gid   = ctx.guild.id
    cfg   = config_dict.setdefault(gid, default_welcome() if kind == "welcome" else default_leave())
    label = "Bienvenue" if kind == "welcome" else "Départ"

    def wait_msg():
        return bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
            timeout=60)

    color_hex       = f"#{cfg['color']:06X}"
    channel_display = f"<#{cfg['channel']}>" if cfg['channel'] else '*Non défini*'
    intro = discord.Embed(
        title=f"⚙️ Assistant — {label}",
        description=(
            "Réponds aux **7 questions**. Tape `skip` pour conserver la valeur actuelle.\n\n"
            "**Variables disponibles :**\n"
            "`{user}` → mention  •  `{username}` → nom  •  "
            "`{server}` → serveur  •  `{count}` → nb membres\n\n"
            f"**Config actuelle :**\n"
            f"• Salon     : {channel_display}\n"
            f"• Titre     : `{cfg['title']}`\n"
            f"• Couleur   : `{color_hex}`\n"
            f"• Pied      : `{cfg['footer'] or 'Aucun'}`\n"
            f"• Avatar    : {'✅' if cfg['show_avatar'] else '❌'}\n"
            f"• Vignette  : {'✅' if cfg.get('show_thumbnail', True) else '❌'}\n"
            f"• Horodatage: {'✅' if cfg['show_timestamp'] else '❌'}\n"
            f"• Activé    : {'✅' if cfg['enabled'] else '❌'}"
        ),
        color=cfg["color"])
    await ctx.send(embed=intro)
    await asyncio.sleep(0.5)

    steps = [
        ("**1/7** — Quel salon ? *(mention ou ID — `skip`)*",                "channel",   "channel"),
        ("**2/7** — Titre de l'embed ? *(texte, variables OK — `skip`)*",    "title",     "text"),
        ("**3/7** — Message ? *(variables OK — `skip`)*",                    "message",   "text"),
        ("**4/7** — Couleur ? (`#RRGGBB`)\n*(ex : `#5865F2` — `skip`)*",    "color",     "color"),
        ("**5/7** — Pied de page ? *(`none` pour supprimer — `skip`)*",      "footer",    "text"),
        ("**6/7** — URL d'image personnalisée ? *(`none` — `skip`)*",        "image_url", "text"),
        ("**7/7** — Activer ou désactiver ? (`on` / `off` — `skip`)",        "enabled",   "bool"),
    ]

    for question, key, kind2 in steps:
        await ctx.send(question)
        try:
            rep = await wait_msg()
        except asyncio.TimeoutError:
            await ctx.send("⏱️ Temps écoulé. Config sauvegardée jusqu'ici.")
            break
        val = rep.content.strip()
        if val.lower() == "skip": continue
        if kind2 == "channel":
            if rep.channel_mentions:        cfg[key] = rep.channel_mentions[0].id
            elif val.isdigit():             cfg[key] = int(val)
            else: await ctx.send("❌ Salon invalide, étape ignorée.")
        elif kind2 == "color":
            parsed = parse_color(val)
            if parsed is not None: cfg[key] = parsed
            else: await ctx.send("❌ Couleur invalide (ex : `#FF5733`), étape ignorée.")
        elif kind2 == "bool":
            cfg[key] = val.lower() in ("on", "oui", "yes", "true", "1")
        else:
            cfg[key] = "" if val.lower() in ("none", "aucun") else val

    if kind == "welcome": save_welcome()
    else: save_leave()

    color_hex = f"#{cfg['color']:06X}"
    summary = discord.Embed(
        title="✅ Configuration sauvegardée !",
        color=cfg["color"],
        timestamp=datetime.datetime.utcnow())
    summary.add_field(name="Salon",    value=f"<#{cfg['channel']}>" if cfg["channel"] else "*Non défini*")
    summary.add_field(name="Activé",   value="✅" if cfg["enabled"] else "❌")
    summary.add_field(name="Titre",    value=cfg["title"],          inline=False)
    summary.add_field(name="Message",  value=cfg["message"][:200],  inline=False)
    summary.add_field(name="Couleur",  value=color_hex)
    summary.add_field(name="Pied",     value=cfg["footer"] or "*Aucun*",           inline=False)
    summary.add_field(name="Image",    value=cfg.get("image_url") or "*Aucune*",   inline=False)
    summary.set_footer(text=f"Modifié par {ctx.author}")
    await ctx.send(embed=summary)


@bot.command(name="wlcmciao")
@commands.has_permissions(manage_guild=True)
async def wlcmciao(ctx):
    menu = discord.Embed(
        title="⚙️ Configuration du serveur",
        description=(
            "Que souhaites-tu configurer ?\n\n"
            "**`1`** — 👋 Messages d'**arrivée**\n"
            "**`2`** — 🚪 Messages de **départ**\n\n"
            "*Tape le numéro ou `annuler`*"
        ),
        color=C_PRIMARY)
    await ctx.send(embed=menu)

    def check(m): return m.author == ctx.author and m.channel == ctx.channel
    try:
        rep = await bot.wait_for("message", check=check, timeout=60)
    except asyncio.TimeoutError:
        return await ctx.send(embed=discord.Embed(
            description="⏱️ Temps écoulé.", color=C_ERROR))

    choix = rep.content.strip()
    if choix == "1":   await _run_setup_wizard(ctx, welcome_config, "welcome")
    elif choix == "2": await _run_setup_wizard(ctx, leave_config, "leave")
    elif choix.lower() in ("annuler", "cancel"):
        await ctx.send(embed=discord.Embed(
            description="❌ Configuration annulée.", color=C_ERROR))
    else:
        await ctx.send(embed=discord.Embed(
            description="❌ Choix invalide. Utilise `1` ou `2`.", color=C_ERROR))


# ═══════════════════════════════════════════════════════════
#  SYSTÈME DE TICKETS
# ═══════════════════════════════════════════════════════════

TICKET_TYPES = {
    "plainte": {
        "label": "Plainte",  "emoji": "🏮", "desc": "accusations - défenses",
        "roles": [1492625653038579854, 1492625657803571270],
        "category_id": 1492625787180941495,
    },
    "support": {
        "label": "Support",  "emoji": "📨", "desc": "problèmes / aides - questions",
        "roles": [1492625653038579854, 1492625657803571270],
        "category_id": 1492625788443296004,
    },
    "staff": {
        "label": "Staff",    "emoji": "🔔", "desc": "recrutement staff - rank up / demote",
        "roles": [1492625655756619848, 1492625653038579854, 1492625649842651136, 1492625647070085170],
        "category_id": 1492625789454389442,
    },
    "crown": {
        "label": "Crown",    "emoji": "👑", "desc": "demande de décale - fusions - partenariats",
        "roles": [1492625649842651136, 1492625647070085170, 1492625643291021354],
        "category_id": 1492625790414622852,
    },
}


def is_ticket_staff(member: discord.Member, channel_id: int) -> bool:
    ttype = ticket_types_map.get(channel_id)
    if not ttype:
        return False
    member_role_ids = {r.id for r in member.roles}
    return bool(member_role_ids & set(TICKET_TYPES[ttype]["roles"]))


async def _create_ticket(interaction: discord.Interaction, ticket_type: str, note: str):
    guild = interaction.guild
    user  = interaction.user
    cfg   = get_tcfg(guild.id)
    tinfo = TICKET_TYPES[ticket_type]

    for ch_id, uid in open_tickets.items():
        if uid == user.id:
            ch = guild.get_channel(ch_id)
            if ch:
                return await interaction.followup.send(
                    f"❌ Tu as déjà un ticket ouvert : {ch.mention}", ephemeral=True)

    cfg["counter"] += 1
    name = f"ticket-{ticket_type}-{cfg['counter']:04d}-{user.name[:10]}"
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user:               discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me:           discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }
    staff_mentions = [user.mention]
    for role_id in tinfo["roles"]:
        role = guild.get_role(role_id)
        if role:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            staff_mentions.append(role.mention)

    category  = guild.get_channel(tinfo["category_id"])
    ticket_ch = await guild.create_text_channel(
        name=name, overwrites=overwrites, category=category,
        reason=f"Ticket {ticket_type} ouvert par {user}")
    open_tickets[ticket_ch.id] = user.id
    ticket_types_map[ticket_ch.id] = ticket_type
    ticket_notes[ticket_ch.id] = note
    save_open_tickets()
    save_ticket_types()
    save_ticket_notes()

    embed = discord.Embed(
        title=f"{tinfo['emoji']} Ticket {tinfo['label']} #{cfg['counter']:04d}",
        description=(
            f"Bonjour {user.mention} ! Le staff sera avec toi dans quelques instants.\n\n"
            f"**Catégorie :** {tinfo['label']} — {tinfo['desc']}\n\n"
            f"📝 **Note :** {note}\n\n"
            f"Utilise `{PREFIX}close` pour fermer ce ticket.\n"
            f"Utilise `{PREFIX}claim` pour le prendre en charge (staff).\n"
            f"Utilise `{PREFIX}remind` pour rappeler la personne qui a ouvert le ticket."
        ),
        color=C_TICKET,
        timestamp=datetime.datetime.utcnow())
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=f"Ouvert par {user}")
    await ticket_ch.send(content=" ".join(staff_mentions), embed=embed)

    ticket_log = discord.Embed(
        title="📂 Ticket Ouvert",
        description=f"{user.mention} a ouvert {ticket_ch.mention}",
        color=C_SUCCESS, timestamp=datetime.datetime.utcnow())
    ticket_log.add_field(name="Type",    value=f"{tinfo['emoji']} {tinfo['label']}", inline=True)
    ticket_log.add_field(name="Membre",  value=f"{user} (`{user.id}`)",               inline=True)
    ticket_log.add_field(name="📝 Note", value=note,                                  inline=False)
    ticket_log.set_footer(text=f"Ticket #{cfg['counter']:04d}")
    if cfg["log_channel"]:
        log_ch = guild.get_channel(cfg["log_channel"])
        if log_ch:
            try: await log_ch.send(embed=ticket_log)
            except discord.Forbidden: pass
    await send_log(guild, "ticket", ticket_log)

    await interaction.followup.send(f"✅ Ticket créé : {ticket_ch.mention}", ephemeral=True)


class TicketPanelSelect(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        options = [
            discord.SelectOption(
                label=v["label"], value=k, emoji=v["emoji"], description=v["desc"]
            )
            for k, v in TICKET_TYPES.items()
        ]
        select = discord.ui.Select(
            placeholder="Choisis un type de ticket...",
            options=options,
            custom_id="ticket_panel_select"
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        ticket_type = interaction.data["values"][0]
        user  = interaction.user
        guild = interaction.guild

        for ch_id, uid in open_tickets.items():
            if uid == user.id:
                ch = guild.get_channel(ch_id)
                if ch:
                    return await interaction.response.send_message(
                        f"❌ Tu as déjà un ticket ouvert : {ch.mention}", ephemeral=True)

        tinfo = TICKET_TYPES[ticket_type]
        try:
            dm_embed = discord.Embed(
                title=f"{tinfo['emoji']} {tinfo['label']} — Note requise",
                description=(
                    f"Tu viens d'ouvrir un ticket **{tinfo['label']}** sur **{guild.name}**.\n\n"
                    "Merci d'écrire ici ta **note / raison** pour ce ticket.\n"
                    "*(Tu as **2 minutes** pour répondre.)*"
                ),
                color=C_TICKET)
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ Je ne peux pas t'envoyer de DM. Active tes DMs et réessaie.", ephemeral=True)

        await interaction.response.send_message(
            "📩 Réponds à mon DM pour continuer l'ouverture du ticket.", ephemeral=True)

        def check(m):
            return m.author.id == user.id and isinstance(m.channel, discord.DMChannel)

        try:
            msg = await bot.wait_for("message", check=check, timeout=120)
        except asyncio.TimeoutError:
            return await user.send(embed=discord.Embed(
                description="⏱️ Temps écoulé. Ouvre un nouveau ticket si besoin.", color=C_ERROR))

        note = msg.content.strip() or "*(aucune note)*"
        await _create_ticket(interaction, ticket_type, note)


@bot.group(name="ticket", invoke_without_command=True)
@commands.has_permissions(manage_guild=True)
async def ticket_group(ctx):
    await ctx.send(embed=discord.Embed(
        description="❌ Commande inconnue. Utilise `+ticket panel`.", color=C_ERROR))


@ticket_group.command(name="panel")
@commands.has_permissions(manage_guild=True)
async def ticket_panel(ctx):
    embed = discord.Embed(
        title="__Support de Hamura__",
        description=(
            "Bienvenue sur le support de **Hamura** vous pouvez choisir entre différents ticket\n\n"
            "🏮 **Plainte**\naccusations - défenses\n\n"
            "📨 **Support**\nproblèmes / aides - questions\n\n"
            "🔔 **Staff**\nrecrutement staff - rank up / demote\n\n"
            "👑 **Crown**\ndemande de décale - fusions - partenariats"
        ),
        color=0x2b2d31)
    embed.set_footer(text="Hamura par Hamura")
    await ctx.send(embed=embed, view=TicketPanelSelect())


class TicketButton(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="Open a Ticket", style=discord.ButtonStyle.primary,
                       custom_id="open_ticket_btn", emoji="🎫")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user  = interaction.user
        cfg   = get_tcfg(guild.id)

        for ch_id, uid in open_tickets.items():
            if uid == user.id:
                ch = guild.get_channel(ch_id)
                if ch:
                    return await interaction.response.send_message(
                        f"❌ You already have an open ticket: {ch.mention}", ephemeral=True)

        cfg["counter"] += 1
        name = f"ticket-{cfg['counter']:04d}-{user.name[:10]}"
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user:               discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me:           discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        if cfg["support_role"]:
            role = guild.get_role(cfg["support_role"])
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        category  = guild.get_channel(cfg["category"]) if cfg["category"] else None
        ticket_ch = await guild.create_text_channel(
            name=name, overwrites=overwrites, category=category,
            reason=f"Ticket opened by {user}")
        open_tickets[ticket_ch.id] = user.id
        save_open_tickets()

        embed = discord.Embed(
            title=f"🎫 Ticket #{cfg['counter']:04d}",
            description=(f"Hello {user.mention}! The support team will be with you shortly.\n\n"
                         f"Use `{PREFIX}close` to close this ticket.\n"
                         f"Use `{PREFIX}claim` for staff to take ownership."),
            color=C_TICKET,
            timestamp=datetime.datetime.utcnow())
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"Opened by {user}")

        mention = user.mention
        if cfg["support_role"]:
            mention += f" | <@&{cfg['support_role']}>"
        await ticket_ch.send(content=mention, embed=embed, view=CloseTicketButton())

        if cfg["log_channel"]:
            log_ch = guild.get_channel(cfg["log_channel"])
            if log_ch:
                await log_ch.send(embed=discord.Embed(
                    title="📂 New Ticket Opened",
                    description=f"{user.mention} opened {ticket_ch.mention}",
                    color=C_SUCCESS, timestamp=datetime.datetime.utcnow()))

        await interaction.response.send_message(
            f"✅ Ticket created: {ticket_ch.mention}", ephemeral=True)


class CloseTicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Fermer le ticket", style=discord.ButtonStyle.red,
                       custom_id="close_ticket_btn", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = interaction.channel
        if ch.id not in open_tickets:
            return await interaction.response.send_message(
                "❌ Ce salon n'est pas un ticket.", ephemeral=True)
        cfg      = get_tcfg(interaction.guild.id)
        opener_id = open_tickets.get(ch.id)
        ttype    = ticket_types_map.get(ch.id)
        note     = ticket_notes.get(ch.id, "*(aucune note)*")

        await interaction.response.send_message(embed=discord.Embed(
            title="🔒 Fermeture du ticket",
            description=f"Fermé par {interaction.user.mention}. Suppression dans **5s**.",
            color=C_ERROR))

        lines = []
        async for msg in ch.history(limit=500, oldest_first=True):
            ts = msg.created_at.strftime("%d/%m/%Y %H:%M:%S")
            lines.append(f"[{ts}] {msg.author.display_name}#{msg.author.discriminator}: {msg.content}")
        transcript_text = "\n".join(lines) or "(aucun message)"

        close_log = discord.Embed(
            title="🔒 Ticket Fermé",
            description=f"**Salon :** `{ch.name}`\n**Fermé par :** {interaction.user.mention}",
            color=C_ERROR, timestamp=datetime.datetime.utcnow())
        close_log.add_field(name="👤 Ouvert par", value=f"<@{opener_id}>" if opener_id else "Inconnu", inline=True)
        if ttype:
            close_log.add_field(name="🏷️ Type", value=f"{TICKET_TYPES[ttype]['emoji']} {TICKET_TYPES[ttype]['label']}", inline=True)
        close_log.add_field(name="📝 Note",     value=note, inline=False)
        close_log.add_field(name="💬 Messages", value=f"{len(lines)} message(s)", inline=True)
        close_log.set_footer(text="Transcript joint en pièce jointe")

        await send_log(interaction.guild, "ticket", close_log)
        if cfg["log_channel"]:
            log_ch = interaction.guild.get_channel(cfg["log_channel"])
            if log_ch:
                try:
                    tf = discord.File(io.BytesIO(transcript_text.encode("utf-8")),
                                      filename=f"transcript-{ch.name}.txt")
                    await log_ch.send(embed=close_log, file=tf)
                except discord.Forbidden: pass

        if opener_id:
            opener = interaction.guild.get_member(opener_id)
            if opener:
                try:
                    dm = discord.Embed(
                        title="🔒 Ticket fermé",
                        description=(f"Ton ticket **{ch.name}** a été fermé par {interaction.user.mention}.\n\n"
                                     f"⭐ Comment évalues-tu le support ?"),
                        color=C_GOLD)
                    dm_msg = await opener.send(embed=dm)
                    for star in ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]:
                        await dm_msg.add_reaction(star)
                except discord.Forbidden: pass

        await asyncio.sleep(5)
        open_tickets.pop(ch.id, None)
        claimed_tickets.pop(ch.id, None)
        ticket_types_map.pop(ch.id, None)
        ticket_notes.pop(ch.id, None)
        save_open_tickets(); save_claimed(); save_ticket_types(); save_ticket_notes()
        await ch.delete(reason=f"Ticket fermé par {interaction.user}")


async def _run_ticket_wizard(ctx):
    gid = ctx.guild.id
    cfg = get_tcfg(gid)

    def wait_msg():
        return bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
            timeout=60)

    cat_display  = f"<#{cfg['category']}>"      if cfg['category']     else '*None*'
    role_display = f"<@&{cfg['support_role']}>" if cfg['support_role'] else '*None*'
    log_display  = f"<#{cfg['log_channel']}>"   if cfg['log_channel']  else '*None*'
    intro = discord.Embed(
        title="🎫 Ticket Setup Wizard",
        description=(
            "Answer **5 questions**. Type `skip` to keep the current value.\n\n"
            f"**Current config:**\n"
            f"• Category     : {cat_display}\n"
            f"• Support role : {role_display}\n"
            f"• Log channel  : {log_display}\n"
            f"• Button label : `{cfg['button_label']}`\n"
            f"• Button emoji : {cfg['button_emoji']}\n"
            f"• Tickets opened: `{cfg['counter']}`"
        ),
        color=C_TICKET)
    await ctx.send(embed=intro)

    steps = [
        ("**1/5** — **Category** for tickets? *(mention or ID — `skip`)*",  "category",     "channel"),
        ("**2/5** — **Support role**? *(mention or ID — `skip`)*",          "support_role", "role"),
        ("**3/5** — **Log channel**? *(mention or ID — `skip`)*",           "log_channel",  "channel"),
        ("**4/5** — **Button label**? *(free text — `skip`)*",              "button_label", "text"),
        ("**5/5** — **Button emoji**? *(e.g. 🎫 📩 — `skip`)*",             "button_emoji", "text"),
    ]
    for question, key, kind in steps:
        await ctx.send(question)
        try:
            rep = await wait_msg()
        except asyncio.TimeoutError:
            await ctx.send("⏱️ Timed out. Config saved."); break
        val = rep.content.strip()
        if val.lower() == "skip": continue
        if kind == "channel":
            if rep.channel_mentions: cfg[key] = rep.channel_mentions[0].id
            elif val.isdigit():      cfg[key] = int(val)
            else: await ctx.send("❌ Not recognized, step skipped.")
        elif kind == "role":
            if rep.role_mentions: cfg[key] = rep.role_mentions[0].id
            elif val.isdigit():   cfg[key] = int(val)
            else: await ctx.send("❌ Not recognized, step skipped.")
        else:
            cfg[key] = val

    await ctx.send("📌 Which channel should receive the **ticket panel**? *(mention it)*")
    try:
        rep = await wait_msg()
    except asyncio.TimeoutError:
        return await ctx.send("⏱️ Timed out.")

    panel_ch    = rep.channel_mentions[0] if rep.channel_mentions else ctx.channel
    panel_embed = discord.Embed(
        title="🎫 Support — Open a Ticket",
        description=cfg["message"],
        color=C_TICKET, timestamp=datetime.datetime.utcnow())
    if ctx.guild.icon:
        panel_embed.set_thumbnail(url=ctx.guild.icon.url)
        panel_embed.set_footer(text=ctx.guild.name, icon_url=ctx.guild.icon.url)

    save_ticket()
    await panel_ch.send(embed=panel_embed, view=TicketButton(gid))
    await ctx.send(embed=discord.Embed(
        description=f"✅ Ticket panel sent to {panel_ch.mention}!",
        color=C_SUCCESS))


@bot.command(name="close")
async def close_ticket(ctx):
    if ctx.channel.id not in open_tickets:
        return await ctx.send(embed=discord.Embed(
            description="❌ Ce salon n'est pas un ticket.", color=C_ERROR))
    opener_id = open_tickets.get(ctx.channel.id)
    is_opener = ctx.author.id == opener_id
    if not is_opener and not is_ticket_staff(ctx.author, ctx.channel.id) and ctx.author.id not in OWNER_IDS and not has_owner_role(ctx.author):
        return await ctx.send(embed=discord.Embed(
            description="❌ Tu n'as pas la permission de fermer ce ticket.", color=C_ERROR))
    cfg = get_tcfg(ctx.guild.id)

    await ctx.send(embed=discord.Embed(
        title="🔒 Fermeture du Ticket",
        description=f"Fermé par {ctx.author.mention}. Suppression dans **5s**.",
        color=C_ERROR))

    ttype = ticket_types_map.get(ctx.channel.id)
    note  = ticket_notes.get(ctx.channel.id, "*(aucune note)*")

    lines = []
    async for msg in ctx.channel.history(limit=500, oldest_first=True):
        ts = msg.created_at.strftime("%d/%m/%Y %H:%M:%S")
        lines.append(f"[{ts}] {msg.author.display_name}#{msg.author.discriminator}: {msg.content}")
    transcript_text = "\n".join(lines) or "(aucun message)"
    transcript_file = discord.File(
        io.BytesIO(transcript_text.encode("utf-8")),
        filename=f"transcript-{ctx.channel.name}.txt")

    close_log = discord.Embed(
        title="🔒 Ticket Fermé",
        description=f"**Salon :** `{ctx.channel.name}`\n**Fermé par :** {ctx.author.mention}",
        color=C_ERROR, timestamp=datetime.datetime.utcnow())
    close_log.add_field(name="👤 Ouvert par", value=f"<@{opener_id}>" if opener_id else "Inconnu", inline=True)
    if ttype:
        close_log.add_field(name="🏷️ Type",   value=f"{TICKET_TYPES[ttype]['emoji']} {TICKET_TYPES[ttype]['label']}", inline=True)
    close_log.add_field(name="📝 Note",        value=note, inline=False)
    close_log.add_field(name="💬 Messages",    value=f"{len(lines)} message(s)", inline=True)
    close_log.set_footer(text="Transcript joint en pièce jointe")

    await send_log(ctx.guild, "ticket", close_log)
    if cfg["log_channel"]:
        log_ch = ctx.guild.get_channel(cfg["log_channel"])
        if log_ch:
            try:
                transcript_file2 = discord.File(
                    io.BytesIO(transcript_text.encode("utf-8")),
                    filename=f"transcript-{ctx.channel.name}.txt")
                await log_ch.send(embed=close_log, file=transcript_file2)
            except discord.Forbidden: pass

    if opener_id:
        opener = ctx.guild.get_member(opener_id)
        if opener:
            try:
                dm = discord.Embed(
                    title="🔒 Ticket fermé",
                    description=(f"Ton ticket **{ctx.channel.name}** a été fermé par {ctx.author.mention}.\n\n"
                                 f"⭐ Comment évalues-tu le support ?"),
                    color=C_GOLD)
                dm_msg = await opener.send(embed=dm)
                for star in ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]:
                    await dm_msg.add_reaction(star)
            except discord.Forbidden: pass

    await asyncio.sleep(5)
    open_tickets.pop(ctx.channel.id, None)
    claimed_tickets.pop(ctx.channel.id, None)
    ticket_types_map.pop(ctx.channel.id, None)
    ticket_notes.pop(ctx.channel.id, None)
    save_open_tickets(); save_claimed(); save_ticket_types(); save_ticket_notes()
    await ctx.channel.delete(reason=f"Ticket fermé par {ctx.author}")


@bot.command(name="add")
async def add_ticket(ctx, member: discord.Member):
    if ctx.channel.id not in open_tickets:
        return await ctx.send(embed=discord.Embed(
            description="❌ Ce salon n'est pas un ticket.", color=C_ERROR))
    if not is_ticket_staff(ctx.author, ctx.channel.id) and ctx.author.id not in OWNER_IDS and not has_owner_role(ctx.author):
        return await ctx.send(embed=discord.Embed(
            description="❌ Tu n'as pas la permission d'ajouter quelqu'un à ce ticket.", color=C_ERROR))
    await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
    await ctx.send(embed=discord.Embed(
        description=f"✅ {member.mention} a été ajouté au ticket.",
        color=C_SUCCESS))


@bot.command(name="remove")
async def remove_ticket(ctx, member: discord.Member):
    if ctx.channel.id not in open_tickets:
        return await ctx.send(embed=discord.Embed(
            description="❌ Ce salon n'est pas un ticket.", color=C_ERROR))
    if not is_ticket_staff(ctx.author, ctx.channel.id) and ctx.author.id not in OWNER_IDS and not has_owner_role(ctx.author):
        return await ctx.send(embed=discord.Embed(
            description="❌ Tu n'as pas la permission de retirer quelqu'un de ce ticket.", color=C_ERROR))
    await ctx.channel.set_permissions(member, overwrite=None)
    await ctx.send(embed=discord.Embed(
        description=f"✅ {member.mention} a été retiré du ticket.",
        color=C_SUCCESS))


@bot.command(name="claim")
async def claim_ticket(ctx):
    if ctx.channel.id not in open_tickets:
        return await ctx.send(embed=discord.Embed(
            description="❌ Ce salon n'est pas un ticket.", color=C_ERROR))
    if not is_ticket_staff(ctx.author, ctx.channel.id) and ctx.author.id not in OWNER_IDS and not has_owner_role(ctx.author):
        return await ctx.send(embed=discord.Embed(
            description="❌ Tu n'as pas la permission de prendre en charge ce ticket.", color=C_ERROR))
    if ctx.channel.id in claimed_tickets:
        claimer = ctx.guild.get_member(claimed_tickets[ctx.channel.id])
        nom = claimer.mention if claimer else "quelqu'un"
        return await ctx.send(embed=discord.Embed(
            description=f"❌ Ce ticket est déjà pris en charge par {nom}.",
            color=C_ERROR))
    claimed_tickets[ctx.channel.id] = ctx.author.id
    save_claimed()
    await ctx.send(embed=discord.Embed(
        title="✋ Ticket Pris en Charge",
        description=f"{ctx.author.mention} gère maintenant ce ticket.",
        color=C_SUCCESS))


@bot.command(name="remind")
async def remind_cmd(ctx, minutes: int = None, *, message="Rappel !"):
    if ctx.channel.id in open_tickets:
        if not is_ticket_staff(ctx.author, ctx.channel.id) and ctx.author.id not in OWNER_IDS and not has_owner_role(ctx.author):
            return await ctx.send(embed=discord.Embed(
                description="❌ Tu n'as pas la permission d'envoyer un rappel dans ce ticket.", color=C_ERROR))
        opener_id = open_tickets.get(ctx.channel.id)
        if not opener_id:
            return await ctx.send(embed=discord.Embed(
                description="❌ Impossible de trouver l'auteur du ticket.", color=C_ERROR))
        opener  = ctx.guild.get_member(opener_id)
        mention = opener.mention if opener else f"<@{opener_id}>"
        ttype   = ticket_types_map.get(ctx.channel.id)
        tinfo   = TICKET_TYPES.get(ttype, {}) if ttype else {}
        custom  = f"\n\n*{message}*" if message != "Rappel !" else ""
        e = discord.Embed(
            title="🔔 Rappel",
            description=(
                f"Hey {mention} ! 👋\n\n"
                f"Le staff attend ta réponse pour traiter ton ticket.\n"
                f"Merci de répondre dès que possible afin que nous puissions t'aider au mieux."
                f"{custom}"
            ),
            color=0xF0A500,
            timestamp=datetime.datetime.utcnow())
        if tinfo:
            e.set_author(name=f"{tinfo.get('emoji','')} Ticket {tinfo.get('label','')}")
        e.set_footer(text=f"Rappel envoyé par {ctx.author.display_name}")
        if opener and opener.display_avatar:
            e.set_thumbnail(url=opener.display_avatar.url)
        try: await ctx.message.delete()
        except discord.Forbidden: pass
        await ctx.send(content=mention, embed=e)
        return
    if minutes is None:
        return await ctx.send(embed=discord.Embed(
            description=f"Usage: `{PREFIX}remind <minutes> [message]`", color=C_ERROR))
    await ctx.send(embed=discord.Embed(
        description=f"⏰ Rappel défini dans **{minutes} min** : *{message}*",
        color=C_INFO))
    await asyncio.sleep(minutes * 60)
    await ctx.send(embed=discord.Embed(
        title="⏰ Rappel !",
        description=f"{ctx.author.mention} — *{message}*",
        color=C_INFO))


@bot.command(name="rename")
async def rename_ticket(ctx, *, new_name: str):
    if ctx.channel.id not in open_tickets:
        return await ctx.send(embed=discord.Embed(
            description="❌ Ce salon n'est pas un ticket.", color=C_ERROR))
    if not is_ticket_staff(ctx.author, ctx.channel.id) and ctx.author.id not in OWNER_IDS and not has_owner_role(ctx.author):
        return await ctx.send(embed=discord.Embed(
            description="❌ Tu n'as pas la permission de renommer ce ticket.", color=C_ERROR))
    old_name = ctx.channel.name
    safe_name = new_name.lower().replace(" ", "-")[:90]
    await ctx.channel.edit(name=safe_name, reason=f"Renommé par {ctx.author}")
    await ctx.send(embed=discord.Embed(
        title="✏️ Ticket renommé",
        description=f"`{old_name}` → `{safe_name}`",
        color=C_SUCCESS))


# ═══════════════════════════════════════════════════════════
#  JOURNAL DE MODÉRATION  (+modlog)
# ═══════════════════════════════════════════════════════════
@bot.command(name="modlog")
@commands.has_permissions(manage_guild=True)
async def modlog(ctx, channel: discord.TextChannel = None):
    if channel is None:
        mod_log_config.pop(ctx.guild.id, None)
        save_modlog()
        return await ctx.send(embed=discord.Embed(
            description="✅ Journal de modération désactivé.", color=C_SUCCESS))
    mod_log_config[ctx.guild.id] = channel.id
    save_modlog()
    await ctx.send(embed=discord.Embed(
        title="🛡️ Journal de modération configuré",
        description=f"Les actions de modération seront enregistrées dans {channel.mention}.",
        color=C_SUCCESS))


# ═══════════════════════════════════════════════════════════
#  SYSTÈME DE LOGS  (+logs)
# ═══════════════════════════════════════════════════════════
@bot.group(name="logs", invoke_without_command=True)
@commands.has_permissions(manage_guild=True)
async def logs_cmd(ctx):
    gid = ctx.guild.id
    cfg = logs_config.get(gid, {})
    e = discord.Embed(
        title="📋 Configuration des Logs",
        description=(
            "Utilise `+logs set <type> <#salon>` pour configurer un salon.\n"
            "Utilise `+logs off <type>` pour désactiver un type.\n\n"
            f"**Types disponibles :** `{'` `'.join(LOG_TYPES)}`\n"
            f"{'▬' * 16}"
        ),
        color=C_PRIMARY, timestamp=datetime.datetime.utcnow())
    for lt in LOG_TYPES:
        cid = cfg.get(lt)
        val = f"<#{cid}>" if cid else "❌ Non configuré"
        e.add_field(name=f"`{lt}`", value=val, inline=True)
    await ctx.send(embed=e)


@logs_cmd.command(name="set")
@commands.has_permissions(manage_guild=True)
async def logs_set(ctx, log_type: str, channel: discord.TextChannel):
    lt = log_type.lower()
    if lt not in LOG_TYPES:
        return await ctx.send(embed=discord.Embed(
            description=f"❌ Type invalide. Choisis parmi : `{'` `'.join(LOG_TYPES)}`",
            color=C_ERROR))
    logs_config.setdefault(ctx.guild.id, {})[lt] = channel.id
    save_logs_config()
    await ctx.send(embed=discord.Embed(
        title="✅ Log configuré",
        description=f"Les logs **{lt}** seront envoyés dans {channel.mention}.",
        color=C_SUCCESS))


@logs_cmd.command(name="off")
@commands.has_permissions(manage_guild=True)
async def logs_off(ctx, log_type: str):
    lt = log_type.lower()
    if lt not in LOG_TYPES:
        return await ctx.send(embed=discord.Embed(
            description=f"❌ Type invalide. Choisis parmi : `{'` `'.join(LOG_TYPES)}`",
            color=C_ERROR))
    logs_config.setdefault(ctx.guild.id, {}).pop(lt, None)
    save_logs_config()
    await ctx.send(embed=discord.Embed(
        description=f"✅ Logs **{lt}** désactivés.",
        color=C_SUCCESS))


# ═══════════════════════════════════════════════════════════
#  RÔLE AUTOMATIQUE  (+autorole)
# ═══════════════════════════════════════════════════════════
@bot.command(name="autorole")
@commands.has_permissions(manage_roles=True)
async def autorole(ctx, role: discord.Role = None):
    if role is None:
        auto_role_config.pop(ctx.guild.id, None)
        save_autorole()
        return await ctx.send(embed=discord.Embed(
            description="✅ Rôle automatique désactivé.", color=C_SUCCESS))
    auto_role_config[ctx.guild.id] = role.id
    save_autorole()
    await ctx.send(embed=discord.Embed(
        title="✅ Rôle automatique configuré",
        description=f"{role.mention} sera attribué à chaque nouveau membre.",
        color=C_SUCCESS))


# ═══════════════════════════════════════════════════════════
#  XP / NIVEAUX  (+rank  +leaderboard  +levelrole)
# ═══════════════════════════════════════════════════════════
@bot.command(name="rank")
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    gid    = ctx.guild.id
    xp     = get_xp(gid, member.id)
    lvl    = xp_to_level(xp)
    bar, cur, nxt = xp_progress_bar(xp)
    pct = int(100 * cur / nxt) if nxt else 100

    e = discord.Embed(
        title=f"⭐ Rang de {member.display_name}",
        color=member.color if member.color.value else C_PRIMARY,
        timestamp=datetime.datetime.utcnow())
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="🏆 Niveau",       value=f"**{lvl}**",          inline=True)
    e.add_field(name="✨ XP total",     value=f"**{xp:,}**",         inline=True)
    e.add_field(name="📈 Prochain niv.", value=f"**{cur}/{nxt} XP**", inline=True)
    e.add_field(name="📊 Progression",  value=f"`{bar}` {pct}%",     inline=False)
    e.set_footer(text=f"Demandé par {ctx.author}  •  ID : {member.id}",
                 icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=e)


@bot.command(name="leaderboard", aliases=["lb"])
async def leaderboard(ctx):
    guild_xp = xp_data.get(ctx.guild.id, {})
    if not guild_xp:
        return await ctx.send(embed=discord.Embed(
            description="Personne n'a encore d'XP sur ce serveur.", color=C_PRIMARY))
    tri    = sorted(guild_xp.items(), key=lambda x: x[1], reverse=True)[:10]
    medals = ["🥇", "🥈", "🥉"]
    lines  = []
    for i, (uid, xp) in enumerate(tri):
        m    = ctx.guild.get_member(uid)
        name = m.display_name if m else f"ID {uid}"
        lvl  = xp_to_level(xp)
        pos  = medals[i] if i < 3 else f"`{i+1}.`"
        lines.append(f"{pos} **{name}** — Niv. {lvl} · {xp:,} XP")
    e = discord.Embed(
        title=f"🏆 Classement XP — {ctx.guild.name}",
        description="\n".join(lines),
        color=C_GOLD,
        timestamp=datetime.datetime.utcnow())
    if ctx.guild.icon:
        e.set_thumbnail(url=ctx.guild.icon.url)
    e.set_footer(text=f"Top {len(lines)} membres")
    await ctx.send(embed=e)


@bot.command(name="levelrole")
@commands.has_permissions(manage_roles=True)
async def levelrole(ctx, level: int, role: discord.Role):
    xp_level_rewards.setdefault(ctx.guild.id, {})[level] = role.id
    save_xp_rewards()
    await ctx.send(embed=discord.Embed(
        title="✅ Rôle de niveau configuré",
        description=f"{role.mention} sera attribué au **niveau {level}**.",
        color=C_SUCCESS))


# ═══════════════════════════════════════════════════════════
#  INFOS MEMBRE  (+info)
# ═══════════════════════════════════════════════════════════
@bot.command(name="info")
async def info_user(ctx, member: discord.Member = None):
    member = member or ctx.author
    gid    = ctx.guild.id
    xp     = get_xp(gid, member.id)
    lvl    = xp_to_level(xp)
    user_warns = warns.get(member.id, [])

    status_map = {
        discord.Status.online:    "🟢 En ligne",
        discord.Status.idle:      "🌙 Absent",
        discord.Status.dnd:       "🔴 Ne pas déranger",
        discord.Status.offline:   "⚫ Hors ligne",
        discord.Status.invisible: "👻 Invisible",
    }
    e = discord.Embed(
        title=f"🪪 {member}",
        color=member.color if member.color.value else C_PRIMARY,
        timestamp=datetime.datetime.utcnow())
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="🆔 ID",           value=str(member.id),                                    inline=True)
    e.add_field(name="📡 Statut",        value=status_map.get(member.status, "❓"),               inline=True)
    e.add_field(name="🤖 Bot",           value="✅" if member.bot else "❌",                      inline=True)
    e.add_field(name="📅 Créé le",       value=member.created_at.strftime("%d/%m/%Y"),            inline=True)
    e.add_field(name="📥 Rejoint le",    value=member.joined_at.strftime("%d/%m/%Y") if member.joined_at else "?",
                inline=True)
    e.add_field(name="✨ Booster",       value="✅" if member.premium_since else "❌",             inline=True)
    e.add_field(name="⭐ Niveau",        value=f"Niv. **{lvl}** ({xp:,} XP)",                   inline=True)
    e.add_field(name="⚠️ Avertissements", value=str(len(user_warns)),                             inline=True)
    roles = [r.mention for r in reversed(member.roles) if r.name != "@everyone"]
    e.add_field(name=f"🎭 Rôles ({len(roles)})",
                value=" ".join(roles)[:1024] if roles else "Aucun", inline=False)
    if user_warns:
        warn_text = "\n".join(
            f"**#{i+1}** `{w['date']}` — {w['reason']}"
            for i, w in enumerate(user_warns[-5:]))
        e.add_field(name="📋 Derniers avertissements (max 5)", value=warn_text, inline=False)
    e.set_footer(text=f"Demandé par {ctx.author}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=e)


# ═══════════════════════════════════════════════════════════
#  RÔLES RÉACTION  (+rr  +listrr)
# ═══════════════════════════════════════════════════════════
@bot.command(name="rr")
@commands.has_permissions(manage_roles=True)
async def reactionrole(ctx, message_id: int, emoji: str, role: discord.Role):
    try:
        msg = await ctx.channel.fetch_message(message_id)
    except discord.NotFound:
        return await ctx.send(embed=discord.Embed(
            description="❌ Message introuvable dans ce salon.", color=C_ERROR))
    react_roles.setdefault(ctx.guild.id, {}).setdefault(message_id, {})[emoji] = role.id
    save_reactroles()
    await msg.add_reaction(emoji)
    await ctx.send(embed=discord.Embed(
        title="✅ Rôle réaction ajouté",
        description=f"Réagir {emoji} sur [ce message]({msg.jump_url}) → {role.mention}",
        color=C_SUCCESS))


@bot.command(name="listrr")
@commands.has_permissions(manage_roles=True)
async def listreactionroles(ctx):
    guild_rr = react_roles.get(ctx.guild.id, {})
    if not guild_rr:
        return await ctx.send(embed=discord.Embed(
            description="Aucun rôle réaction configuré.", color=C_PRIMARY))
    lines = []
    for mid, emojis in guild_rr.items():
        for emoji, rid in emojis.items():
            role = ctx.guild.get_role(rid)
            lines.append(f"Message `{mid}` · {emoji} → {role.mention if role else f'Rôle ID {rid}'}")
    await ctx.send(embed=discord.Embed(
        title="🎭 Rôles Réaction",
        description="\n".join(lines),
        color=C_PRIMARY))


# ═══════════════════════════════════════════════════════════
#  AUTO-MOD  (+autowarn  +dmwelcome)
# ═══════════════════════════════════════════════════════════
@bot.command(name="autowarn")
@commands.has_permissions(manage_guild=True)
async def autowarn(ctx, limit: int):
    auto_mod_config.setdefault(ctx.guild.id, {})["warn_limit"] = limit
    save_automod()
    if limit == 0:
        return await ctx.send(embed=discord.Embed(
            description="✅ Mute automatique sur avertissements **désactivé**.", color=C_SUCCESS))
    await ctx.send(embed=discord.Embed(
        title="✅ Mute automatique configuré",
        description=f"Les membres seront mutés automatiquement après **{limit} avertissements**.",
        color=C_SUCCESS))


@bot.command(name="dmwelcome")
@commands.has_permissions(manage_guild=True)
async def dmwelcome(ctx, toggle: str, *, message: str = ""):
    amod  = auto_mod_config.setdefault(ctx.guild.id, {})
    actif = toggle.lower() in ("on", "oui", "yes", "true", "1")
    amod["dm_welcome"] = actif
    if message:
        amod["dm_welcome_msg"] = message
    save_automod()
    if actif and not amod.get("dm_welcome_msg"):
        return await ctx.send(embed=discord.Embed(
            description=f"⚠️ Activé, mais aucun message défini. Relance : `{PREFIX}dmwelcome on Ton message`",
            color=C_WARN))
    await ctx.send(embed=discord.Embed(
        title=f"{'✅ DM Bienvenue activé' if actif else '❌ DM Bienvenue désactivé'}",
        description=f"Message : *{amod.get('dm_welcome_msg', '')}*" if actif else "",
        color=C_SUCCESS if actif else C_ERROR))


# ═══════════════════════════════════════════════════════════
#  GIVEAWAY  (+giveaway  +greroll  +gend)
# ═══════════════════════════════════════════════════════════

async def _pick_giveaway_winners(msg, nb_winners):
    reaction = discord.utils.get(msg.reactions, emoji="🎉")
    users = [u async for u in reaction.users() if not u.bot] if reaction else []
    if not users:
        return [], users
    return random.sample(users, min(nb_winners, len(users))), users


@bot.command(name="giveaway")
@commands.has_permissions(manage_guild=True)
async def giveaway(ctx, duration: str, winners: int, *, prize: str):
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    unit  = duration[-1].lower()
    if unit not in units or not duration[:-1].isdigit():
        return await ctx.send(embed=discord.Embed(
            description="❌ Format invalide. Exemples : `30s`, `5m`, `2h`, `1d`",
            color=C_ERROR))
    seconds  = int(duration[:-1]) * units[unit]
    end_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)

    e = discord.Embed(
        title=f"🎉 GIVEAWAY",
        description=(
            f"**Lot :** {prize}\n\n"
            f"Réagis avec 🎉 pour participer !\n\n"
            f"🏆 **Gagnants :** {winners}\n"
            f"⏰ **Fin :** <t:{int(end_time.timestamp())}:R>\n"
            f"🎗️ **Organisé par :** {ctx.author.mention}"
        ),
        color=C_GOLD, timestamp=end_time)
    e.set_footer(text=f"Fin le {end_time.strftime('%d/%m/%Y à %H:%M')} UTC  •  ID : en cours...")
    msg = await ctx.send(embed=e)
    await msg.add_reaction("🎉")
    try: await ctx.message.delete()
    except discord.Forbidden: pass

    active_giveaways[msg.id] = {
        "channel_id":    ctx.channel.id,
        "prize":         prize,
        "winners":       winners,
        "organizer_id":  ctx.author.id,
        "end_timestamp": int(end_time.timestamp()),
        "ended":         False,
    }
    save_giveaways()

    e.set_footer(text=f"Fin le {end_time.strftime('%d/%m/%Y à %H:%M')} UTC  •  ID : {msg.id}")
    await msg.edit(embed=e)

    await asyncio.sleep(seconds)

    if not active_giveaways.get(msg.id, {}).get("ended", True):
        await _end_giveaway(ctx.guild, msg.id, ctx.channel)


async def _end_giveaway(guild, msg_id, channel=None):
    data = active_giveaways.get(msg_id)
    if not data or data.get("ended"):
        return
    data["ended"] = True
    save_giveaways()

    ch = channel or guild.get_channel(data["channel_id"])
    if not ch:
        return
    try:
        msg = await ch.fetch_message(msg_id)
    except discord.NotFound:
        return

    chosen, all_users = await _pick_giveaway_winners(msg, data["winners"])

    end_embed = discord.Embed(
        title="🎉 GIVEAWAY — TERMINÉ",
        description=(
            f"**Lot :** {data['prize']}\n\n"
            f"🏆 **Gagnants :** {data['winners']}\n"
            f"🎗️ **Organisé par :** <@{data['organizer_id']}>\n\n"
            f"**Participants :** {len(all_users)}"
        ),
        color=0x555555)
    end_embed.set_footer(text=f"Giveaway terminé  •  ID : {msg_id}")
    await msg.edit(embed=end_embed)

    if not chosen:
        await ch.send(embed=discord.Embed(
            title="🎊 Giveaway terminé — Aucun participant",
            description=f"Personne n'a participé au giveaway **{data['prize']}**.",
            color=C_ERROR))
        return

    mentions = " ".join(g.mention for g in chosen)
    await ch.send(
        content=mentions,
        embed=discord.Embed(
            title="🎊 Félicitations !",
            description=(
                f"**Lot :** {data['prize']}\n"
                f"**Gagnant(s) :** {mentions}\n\n"
                f"Bravo ! 🎉"
            ),
            color=C_GOLD))


@bot.command(name="gend")
@commands.has_permissions(manage_guild=True)
async def gend(ctx, message_id: int):
    data = active_giveaways.get(message_id)
    if not data:
        return await ctx.send(embed=discord.Embed(
            description=f"❌ Aucun giveaway actif avec l'ID `{message_id}`.", color=C_ERROR))
    if data.get("ended"):
        return await ctx.send(embed=discord.Embed(
            description="❌ Ce giveaway est déjà terminé.", color=C_ERROR))
    await _end_giveaway(ctx.guild, message_id)
    await ctx.send(embed=discord.Embed(
        description=f"✅ Giveaway `{message_id}` terminé manuellement.", color=C_SUCCESS))


@bot.command(name="greroll")
@commands.has_permissions(manage_guild=True)
async def greroll(ctx, message_id: int, nb_winners: int = 1):
    data = active_giveaways.get(message_id)
    if not data:
        return await ctx.send(embed=discord.Embed(
            description=f"❌ Aucun giveaway trouvé avec l'ID `{message_id}`.", color=C_ERROR))
    ch = ctx.guild.get_channel(data["channel_id"])
    if not ch:
        return await ctx.send(embed=discord.Embed(
            description="❌ Salon introuvable.", color=C_ERROR))
    try:
        msg = await ch.fetch_message(message_id)
    except discord.NotFound:
        return await ctx.send(embed=discord.Embed(
            description="❌ Message introuvable.", color=C_ERROR))

    chosen, _ = await _pick_giveaway_winners(msg, nb_winners)
    if not chosen:
        return await ctx.send(embed=discord.Embed(
            description="❌ Aucun participant pour le reroll.", color=C_ERROR))

    mentions = " ".join(g.mention for g in chosen)
    await ctx.send(
        content=mentions,
        embed=discord.Embed(
            title="🎲 Reroll !",
            description=(
                f"**Lot :** {data['prize']}\n"
                f"**Nouveau(x) gagnant(s) :** {mentions}"
            ),
            color=C_GOLD))


# ═══════════════════════════════════════════════════════════
#  COMMANDES VOCAL  (+vcmove  +vcmute  +vcunmute)
# ═══════════════════════════════════════════════════════════
@bot.command(name="vcmove")
@commands.has_permissions(move_members=True)
async def vcmove(ctx, member: discord.Member, *, channel: discord.VoiceChannel):
    if not member.voice:
        return await ctx.send(embed=discord.Embed(
            description=f"❌ {member.mention} n'est pas dans un salon vocal.", color=C_ERROR))
    await member.move_to(channel, reason=f"Déplacé par {ctx.author}")
    await ctx.send(embed=discord.Embed(
        title="🔊 Membre déplacé",
        description=f"{member.mention} a été déplacé vers **{channel.name}** par {ctx.author.mention}.",
        color=C_INFO))


@bot.command(name="vcmute")
@commands.has_permissions(mute_members=True)
async def vcmute(ctx, member: discord.Member):
    if not member.voice:
        return await ctx.send(embed=discord.Embed(
            description=f"❌ {member.mention} n'est pas dans un salon vocal.", color=C_ERROR))
    await member.edit(mute=True, reason=f"Mute vocal par {ctx.author}")
    await ctx.send(embed=discord.Embed(
        title="🔇 Mute vocal",
        description=f"{member.mention} a été muté en vocal par {ctx.author.mention}.",
        color=C_WARN))
    await log_mod_action(ctx.guild, "Mute vocal", member, ctx.author, "Mute vocal", C_WARN)


@bot.command(name="vcunmute")
@commands.has_permissions(mute_members=True)
async def vcunmute(ctx, member: discord.Member):
    if not member.voice:
        return await ctx.send(embed=discord.Embed(
            description=f"❌ {member.mention} n'est pas dans un salon vocal.", color=C_ERROR))
    await member.edit(mute=False, reason=f"Unmute vocal par {ctx.author}")
    await ctx.send(embed=discord.Embed(
        title="🔊 Mute vocal levé",
        description=f"{member.mention} peut à nouveau parler en vocal.",
        color=C_SUCCESS))


# ═══════════════════════════════════════════════════════════
#  CRÉATEUR D'EMBED  (+embed)
# ═══════════════════════════════════════════════════════════
@bot.command(name="embed")
@commands.has_permissions(manage_messages=True)
async def embed_builder(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel

    def wait_msg():
        return bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
            timeout=90)

    data = {"title": "", "description": "", "color": C_PRIMARY,
            "footer": "", "image": "", "thumbnail": "", "author": "", "fields": []}

    guide = discord.Embed(
        title="🎨 Créateur d'embed",
        description=(f"Réponds aux questions une par une.\n"
                     f"Tape `skip` pour laisser vide, `stop` pour passer à l'envoi.\n\n"
                     f"**Destination :** {channel.mention}"),
        color=C_PRIMARY)
    await ctx.send(embed=guide)
    await asyncio.sleep(0.5)

    steps = [
        ("**Titre** ? *(ou `skip`)*",                              "title"),
        ("**Description** ? *(ou `skip`)*",                        "description"),
        ("**Couleur** ? (`#RRGGBB`) *(ou `skip`)*",               "color"),
        ("**Pied de page** ? *(ou `skip`)*",                      "footer"),
        ("**URL de l'image principale** ? *(ou `skip`)*",         "image"),
        ("**URL de la vignette** (haut droite) ? *(ou `skip`)*",  "thumbnail"),
        ("**Texte auteur** (haut de l'embed) ? *(ou `skip`)*",    "author"),
    ]
    for question, key in steps:
        await ctx.send(question)
        try:
            rep = await wait_msg()
        except asyncio.TimeoutError:
            break
        val = rep.content.strip()
        if val.lower() == "stop":  break
        if val.lower() == "skip":  continue
        if key == "color":
            parsed = parse_color(val)
            data["color"] = parsed if parsed is not None else data["color"]
            if parsed is None:
                await ctx.send("❌ Couleur invalide, couleur par défaut conservée.")
        else:
            data[key] = val

    await ctx.send("Veux-tu ajouter des **champs** ? (`oui` / `non`)")
    try:
        rep = await wait_msg()
        if rep.content.strip().lower() in ("oui", "yes"):
            for i in range(1, 6):
                await ctx.send(f"**Champ {i}/5** — Nom ? (`stop` pour terminer)")
                try:
                    n = await wait_msg()
                    if n.content.strip().lower() == "stop": break
                    await ctx.send(f"**Champ {i}/5** — Valeur ?")
                    v = await wait_msg()
                    await ctx.send(f"**Champ {i}/5** — En ligne ? (`oui` / `non`)")
                    il = await wait_msg()
                    data["fields"].append({
                        "name":   n.content.strip(),
                        "value":  v.content.strip(),
                        "inline": il.content.strip().lower() in ("oui", "yes")})
                except asyncio.TimeoutError:
                    break
    except asyncio.TimeoutError:
        pass

    e = discord.Embed(color=data["color"], timestamp=datetime.datetime.utcnow())
    if data["title"]:       e.title       = data["title"]
    if data["description"]: e.description = data["description"]
    if data["footer"]:      e.set_footer(text=data["footer"])
    if data["image"]:       e.set_image(url=data["image"])
    if data["thumbnail"]:   e.set_thumbnail(url=data["thumbnail"])
    if data["author"]:
        e.set_author(name=data["author"], icon_url=ctx.author.display_avatar.url)
    for f in data["fields"]:
        e.add_field(name=f["name"], value=f["value"], inline=f["inline"])

    await ctx.send("👁️ **Aperçu :**", embed=e)
    await ctx.send(f"Envoyer dans {channel.mention} ? (`oui` / `non`)")
    try:
        confirm = await wait_msg()
        if confirm.content.strip().lower() in ("oui", "yes"):
            await channel.send(embed=e)
            await ctx.send(embed=discord.Embed(
                description=f"✅ Embed envoyé dans {channel.mention} !", color=C_SUCCESS))
        else:
            await ctx.send(embed=discord.Embed(
                description="❌ Envoi annulé.", color=C_ERROR))
    except asyncio.TimeoutError:
        await ctx.send(embed=discord.Embed(
            description="⏱️ Temps écoulé, envoi annulé.", color=C_ERROR))


# ═══════════════════════════════════════════════════════════
#  DIVERTISSEMENT
# ═══════════════════════════════════════════════════════════
@bot.command(name="8ball")
async def eight_ball(ctx, *, question):
    responses = [
        ("🟢", "Absolument !"),    ("🟢", "Définitivement."),   ("🟢", "Sans aucun doute."),
        ("🟡", "Peut-être…"),      ("🟡", "Difficile à dire."), ("🟡", "Pas sûr."),
        ("🔴", "Non."),            ("🔴", "Certainement pas."), ("🔴", "Mes sources disent non."),
    ]
    dot, ans = random.choice(responses)
    e = discord.Embed(title="🎱 Boule Magique", color=C_FUN)
    e.add_field(name="❓ Question", value=question,         inline=False)
    e.add_field(name="💬 Réponse",  value=f"{dot} **{ans}**", inline=False)
    e.set_footer(text=f"Demandé par {ctx.author}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=e)

@bot.command(name="flip")
async def flip(ctx):
    result = random.choice(["Face", "Pile"])
    await ctx.send(embed=discord.Embed(
        title="🪙 Lancer de pièce",
        description=f"**{result} !**",
        color=C_FUN))

@bot.command(name="roll")
async def roll(ctx, faces: int = 6):
    result = random.randint(1, faces)
    await ctx.send(embed=discord.Embed(
        title="🎲 Lancer de dé",
        description=f"Tu as obtenu **{result}** sur un d{faces} !",
        color=C_FUN))

@bot.command()
async def rps(ctx, choice: str):
    opts   = {"pierre": "🪨", "papier": "📄", "ciseaux": "✂️",
              "rock": "🪨", "paper": "📄", "scissors": "✂️"}
    wins_fr = {"pierre": "ciseaux", "papier": "pierre", "ciseaux": "papier"}
    wins_en = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
    choice  = choice.lower()
    if choice not in opts:
        return await ctx.send(embed=discord.Embed(
            description="❌ Choix invalide. Utilise `pierre`, `papier` ou `ciseaux`.",
            color=C_ERROR))
    fr_map  = {"rock": "pierre", "paper": "papier", "scissors": "ciseaux"}
    en_map  = {"pierre": "rock", "papier": "paper", "ciseaux": "scissors"}
    choice_fr  = fr_map.get(choice, choice)
    bot_choice = random.choice(["pierre", "papier", "ciseaux"])
    wins       = {"pierre": "ciseaux", "papier": "pierre", "ciseaux": "papier"}
    if choice_fr == bot_choice:         result = "🟡 Égalité !"
    elif wins[choice_fr] == bot_choice: result = "🟢 Tu gagnes !"
    else:                               result = "🔴 Tu perds !"
    e = discord.Embed(
        title="🪨📄✂️ Pierre Papier Ciseaux",
        description=(f"**Toi :** {opts[choice]} {choice_fr}\n"
                     f"**Bot :** {opts[bot_choice]} {bot_choice}\n\n"
                     f"{result}"),
        color=C_FUN)
    await ctx.send(embed=e)

@bot.command(name="joke")
async def joke(ctx):
    jokes = [
        ("Pourquoi les plongeurs plongent-ils toujours en arrière ?", "Parce que s'ils plongeaient en avant, ils tomberaient dans le bateau !"),
        ("Qu'est-ce qu'un crocodile qui surveille la cour ?", "Un sac à dents !"),
        ("Pourquoi Einstein était-il un génie ?", "Parce qu'il ne regardait pas la télé."),
        ("C'est l'histoire d'un canif.", "C'est un peu couteau, mais c'est une histoire courte !"),
        ("Pourquoi les développeurs préfèrent le mode sombre ?", "Parce que la lumière attire les bugs !"),
    ]
    q, r = random.choice(jokes)
    e = discord.Embed(title="😂 Blague du jour", color=C_FUN)
    e.add_field(name="❓", value=q,          inline=False)
    e.add_field(name="💬", value=f"||{r}||", inline=False)
    e.set_footer(text=f"Demandé par {ctx.author}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=e)

@bot.command()
async def compliment(ctx, member: discord.Member = None):
    target = member or ctx.author
    c = random.choice([
        "est absolument brillant(e) 🌟",
        "a un sourire qui illumine la pièce ☀️",
        "est incroyablement talentueux/talentueuse 🎯",
        "est la personne la plus créative que je connaisse 🎨",
        "rend tout meilleur juste en étant là 💖",
    ])
    e = discord.Embed(
        description=f"💖 {target.mention} {c}",
        color=0xFF69B4)
    await ctx.send(embed=e)

@bot.command(name="roast")
async def roast(ctx, member: discord.Member = None):
    target = member or ctx.author
    r = random.choice([
        "met probablement le lait avant les céréales 🥣",
        "mange sa soupe avec une fourchette 🍴",
        "prononce encore GIF avec un G dur 😤",
        "utilise encore Internet Explorer 💀",
        "tape avec deux doigts 👆",
    ])
    e = discord.Embed(
        description=f"🔥 {target.mention} {r}",
        color=0xFF4500)
    await ctx.send(embed=e)

@bot.command()
async def meme(ctx):
    urls = [
        "https://i.imgflip.com/1bij.jpg",
        "https://i.imgflip.com/4t0m5.jpg",
        "https://i.imgflip.com/26am.jpg",
    ]
    e = discord.Embed(title="😹 Mème aléatoire", color=discord.Color.random())
    e.set_image(url=random.choice(urls))
    e.set_footer(text=f"Demandé par {ctx.author}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=e)

@bot.command(name="color")
async def random_color(ctx):
    r, g, b = random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
    hex_str = f"#{r:02X}{g:02X}{b:02X}"
    e = discord.Embed(title="🎨 Couleur aléatoire", color=discord.Color.from_rgb(r, g, b))
    e.add_field(name="HEX", value=f"`{hex_str}`")
    e.add_field(name="RGB", value=f"`rgb({r}, {g}, {b})`")
    e.set_footer(text="La couleur de l'embed correspond !")
    await ctx.send(embed=e)


# ═══════════════════════════════════════════════════════════
#  STATS SERVEUR  (+stats)
# ═══════════════════════════════════════════════════════════
@bot.command(name="stats")
async def stats(ctx):
    g = ctx.guild
    online   = sum(1 for m in g.members
                   if m.status in (discord.Status.online, discord.Status.idle, discord.Status.dnd)
                   and not m.bot)
    in_voice = sum(1 for m in g.members if m.voice and not m.bot)

    e = discord.Embed(
        title=f"📊 Stats — {g.name} \U0000270f\ufe0f",
        color=C_PRIMARY,
        timestamp=datetime.datetime.utcnow())
    if g.icon:
        e.set_thumbnail(url=g.icon.url)
    e.add_field(name="👥 Membres",  value=str(g.member_count), inline=False)
    e.add_field(name="🟢 En ligne", value=str(online),         inline=False)
    e.add_field(name="🎙️ En vocal", value=str(in_voice),       inline=False)
    e.add_field(name="✨ Boosts",
                value=f"{g.premium_subscription_count} boost(s)\nNiveau {g.premium_tier}",
                inline=False)
    e.set_footer(text=f"ID : {g.id}")
    await ctx.send(embed=e)


# ═══════════════════════════════════════════════════════════
#  STATS UTILISATEUR  (+userstats)
# ═══════════════════════════════════════════════════════════
@bot.command(name="userstats")
async def userstats(ctx, member: discord.Member = None):
    member = member or ctx.author
    status_map = {
        discord.Status.online:    "🟢 En ligne",
        discord.Status.idle:      "🌙 Absent",
        discord.Status.dnd:       "🔴 Ne pas déranger",
        discord.Status.offline:   "⚫ Hors ligne",
        discord.Status.invisible: "👻 Invisible",
    }
    roles = [r.mention for r in reversed(member.roles) if r.name != "@everyone"]
    e = discord.Embed(
        title=f"👤 {member}",
        color=member.color if member.color.value else C_PRIMARY,
        timestamp=datetime.datetime.utcnow())
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="🆔 ID",          value=str(member.id),                                        inline=True)
    e.add_field(name="📛 Pseudo",       value=member.display_name,                                   inline=True)
    e.add_field(name="🤖 Bot",          value="✅" if member.bot else "❌",                           inline=True)
    e.add_field(name="📡 Statut",       value=status_map.get(member.status, "❓"),                    inline=True)
    e.add_field(name="🎙️ Vocal",       value="🔊 En vocal" if member.voice else "🔇 Pas en vocal",   inline=True)
    e.add_field(name="✨ Booster",      value="✅" if member.premium_since else "❌",                  inline=True)
    e.add_field(name="📅 Créé le",      value=member.created_at.strftime("%d/%m/%Y"),                 inline=True)
    e.add_field(name="📥 Rejoint le",   value=member.joined_at.strftime("%d/%m/%Y") if member.joined_at else "?",
                inline=True)
    if member.activity:
        e.add_field(name="🎮 Activité", value=str(member.activity.name), inline=True)
    e.add_field(name=f"🎭 Rôles ({len(roles)})",
                value=" ".join(roles)[:1024] if roles else "Aucun", inline=False)
    e.set_footer(text=f"ID : {member.id}")
    await ctx.send(embed=e)


# ── Autres commandes info ──────────────────────────────────
@bot.command()
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    e = discord.Embed(
        title=f"🖼️ Avatar de {member.display_name}",
        color=member.color if member.color.value else C_PRIMARY)
    e.set_image(url=member.display_avatar.url)
    e.set_footer(text=f"Demandé par {ctx.author}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=e)

@bot.command()
async def ping(ctx):
    ms    = round(bot.latency * 1000)
    color = (C_SUCCESS if ms < 100 else C_WARN if ms < 200 else C_ERROR)
    bar   = "█" * min(int(ms / 20), 10) + "░" * max(10 - int(ms / 20), 0)
    e = discord.Embed(title="🏓 Pong !", color=color)
    e.add_field(name="📶 Latence",  value=f"**{ms} ms**")
    e.add_field(name="📊 Qualité",  value=f"`{bar}`")
    await ctx.send(embed=e)

bot_start_time = datetime.datetime.utcnow()

@bot.command()
async def uptime(ctx):
    delta = datetime.datetime.utcnow() - bot_start_time
    h, rem = divmod(int(delta.total_seconds()), 3600)
    m, s   = divmod(rem, 60)
    e = discord.Embed(title="⏱️ Temps de fonctionnement", color=C_INFO)
    e.add_field(name="🕐 En ligne depuis", value=f"**{h}h {m}m {s}s**")
    e.set_footer(text=f"Démarré le {bot_start_time.strftime('%d/%m/%Y à %H:%M')} UTC")
    await ctx.send(embed=e)

@bot.command()
async def roles(ctx):
    liste = [r.mention for r in reversed(ctx.guild.roles) if r.name != "@everyone"]
    e = discord.Embed(
        title=f"🎭 Rôles du serveur — {ctx.guild.name}",
        description=" • ".join(liste) or "Aucun rôle.",
        color=C_PRIMARY)
    e.set_footer(text=f"{len(liste)} rôle(s) au total")
    await ctx.send(embed=e)


# ═══════════════════════════════════════════════════════════
#  ÉCONOMIE  (+balance  +daily  +give  +richest)
# ═══════════════════════════════════════════════════════════
def get_balance(uid): return economy.setdefault(uid, 0)

@bot.command(name="balance", aliases=["bal"])
async def balance(ctx, member: discord.Member = None):
    member = member or ctx.author
    bal = get_balance(member.id)
    e = discord.Embed(
        title="💰 Portefeuille",
        color=C_GOLD,
        timestamp=datetime.datetime.utcnow())
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name=member.display_name, value=f"**{bal:,}** 🪙")
    e.set_footer(text=f"Demandé par {ctx.author}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=e)

@bot.command()
async def daily(ctx):
    uid = ctx.author.id
    now = datetime.datetime.utcnow().date()
    if last_daily.get(uid) == now:
        return await ctx.send(embed=discord.Embed(
            description="❌ Tu as déjà réclamé ta récompense aujourd'hui. Reviens demain !",
            color=C_ERROR))
    gain = random.randint(100, 500)
    economy[uid] = get_balance(uid) + gain
    last_daily[uid] = now
    save_economy(); save_daily()
    e = discord.Embed(title="🎁 Récompense journalière", color=C_GOLD)
    e.set_thumbnail(url=ctx.author.display_avatar.url)
    e.add_field(name="Gagné",   value=f"**+{gain} 🪙**")
    e.add_field(name="Solde",   value=f"**{economy[uid]:,} 🪙**")
    e.set_footer(text="Reviens demain pour plus !")
    await ctx.send(embed=e)

@bot.command()
async def give(ctx, target: discord.Member, amount: int):
    if amount <= 0:
        return await ctx.send(embed=discord.Embed(
            description="❌ Le montant doit être positif.", color=C_ERROR))
    uid = ctx.author.id
    if get_balance(uid) < amount:
        return await ctx.send(embed=discord.Embed(
            description="❌ Solde insuffisant.", color=C_ERROR))
    economy[uid] -= amount
    economy[target.id] = get_balance(target.id) + amount
    save_economy()
    e = discord.Embed(title="💸 Transfert", color=C_GOLD)
    e.add_field(name="De",      value=ctx.author.mention)
    e.add_field(name="Vers",    value=target.mention)
    e.add_field(name="Montant", value=f"**{amount:,} 🪙**", inline=False)
    await ctx.send(embed=e)

@bot.command(name="richest")
async def richest(ctx):
    if not economy:
        return await ctx.send(embed=discord.Embed(
            description="Personne n'a encore de pièces.", color=C_PRIMARY))
    tri    = sorted(economy.items(), key=lambda x: x[1], reverse=True)[:10]
    medals = ["🥇", "🥈", "🥉"]
    lines  = []
    for i, (uid, s) in enumerate(tri):
        m    = ctx.guild.get_member(uid)
        name = m.display_name if m else f"ID {uid}"
        pos  = medals[i] if i < 3 else f"`{i+1}.`"
        lines.append(f"{pos} **{name}** — {s:,} 🪙")
    e = discord.Embed(
        title=f"💰 Membres les plus riches — {ctx.guild.name}",
        description="\n".join(lines),
        color=C_GOLD,
        timestamp=datetime.datetime.utcnow())
    if ctx.guild.icon:
        e.set_thumbnail(url=ctx.guild.icon.url)
    await ctx.send(embed=e)


# ═══════════════════════════════════════════════════════════
#  ÉCONOMIE — JEUX  (+blackjack  +slots  +coinflip  +work  +rob)
# ═══════════════════════════════════════════════════════════

# ── Blackjack ─────────────────────────────────────────────
_BJ_CARDS   = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
_BJ_SUITS   = ["♠", "♥", "♦", "♣"]

def _draw(): return (random.choice(_BJ_CARDS), random.choice(_BJ_SUITS))

def _card_val(c):
    if c[0] in ("J", "Q", "K"): return 10
    if c[0] == "A":              return 11
    return int(c[0])

def _hand_val(hand):
    total = sum(_card_val(c) for c in hand)
    aces  = sum(1 for c in hand if c[0] == "A")
    while total > 21 and aces:
        total -= 10; aces -= 1
    return total

def _show_hand(hand):
    return "  ".join(f"`{c[0]}{c[1]}`" for c in hand)


@bot.command(name="blackjack", aliases=["bj"])
async def blackjack(ctx, mise: int):
    uid = ctx.author.id
    if mise <= 0:
        return await ctx.send(embed=discord.Embed(
            description="❌ La mise doit être positive.", color=C_ERROR))
    if mise > get_balance(uid):
        return await ctx.send(embed=discord.Embed(
            description="❌ Solde insuffisant.", color=C_ERROR))
    if mise > 10000:
        return await ctx.send(embed=discord.Embed(
            description="❌ Mise maximale : **10 000 🪙**.", color=C_ERROR))

    economy[uid] -= mise
    save_economy()

    player = [_draw(), _draw()]
    dealer = [_draw(), _draw()]

    def make_embed(reveal=False, result=None, color=C_GOLD):
        dealer_display = (_show_hand(dealer) + f"  →  **{_hand_val(dealer)}**") if reveal \
                         else f"`{dealer[0][0]}{dealer[0][1]}`  `??`"
        desc = (f"**🃏 Ta main :** {_show_hand(player)}  →  **{_hand_val(player)}**\n"
                f"**🎩 Croupier :** {dealer_display}\n\n")
        if result:
            desc += f"**{result}**"
        else:
            desc += "Tape **`hit`** pour tirer  •  **`stand`** pour rester"
        e = discord.Embed(title="🃏 Blackjack", description=desc, color=color,
                          timestamp=datetime.datetime.utcnow())
        e.set_footer(text=f"Mise : {mise:,} 🪙  •  {ctx.author.display_name}",
                     icon_url=ctx.author.display_avatar.url)
        return e

    if _hand_val(player) == 21:
        gain = int(mise * 2.5)
        economy[uid] += gain
        save_economy()
        return await ctx.send(embed=make_embed(
            reveal=True,
            result=f"🃏 BLACKJACK ! Tu gagnes **+{gain:,} 🪙** (×2.5) !",
            color=C_SUCCESS))

    msg = await ctx.send(embed=make_embed())

    def check(m):
        return (m.author == ctx.author and m.channel == ctx.channel
                and m.content.lower() in ("hit", "stand", "h", "s"))

    while _hand_val(player) < 21:
        try:
            rep = await bot.wait_for("message", check=check, timeout=30)
        except asyncio.TimeoutError:
            await msg.edit(embed=make_embed(
                reveal=True, result="⏱️ Temps écoulé — mise perdue.", color=C_ERROR))
            return

        if rep.content.lower() in ("stand", "s"):
            break
        player.append(_draw())
        if _hand_val(player) > 21:
            await msg.edit(embed=make_embed(
                reveal=True,
                result=f"💥 Bust ! Tu dépasses 21 — mise perdue.",
                color=C_ERROR))
            return
        await msg.edit(embed=make_embed())

    while _hand_val(dealer) < 17:
        dealer.append(_draw())

    pval = _hand_val(player)
    dval = _hand_val(dealer)

    if dval > 21 or pval > dval:
        gain = mise * 2
        economy[uid] += gain
        save_economy()
        result, color = f"🏆 Tu gagnes ! ({pval} vs {dval}) → **+{gain:,} 🪙**", C_SUCCESS
    elif pval == dval:
        economy[uid] += mise
        save_economy()
        result, color = f"🟡 Égalité ! ({pval}) — Mise remboursée.", C_WARN
    else:
        result, color = f"❌ Croupier gagne ! ({dval} vs {pval}) — mise perdue.", C_ERROR

    await msg.edit(embed=make_embed(reveal=True, result=result, color=color))


# ── Machine à sous ────────────────────────────────────────
_SLOT_SYM  = ["🍒", "🍋", "🍊", "⭐", "💎", "7️⃣"]
_SLOT_WGT  = [35,   28,   20,   10,    5,    2]
_SLOT_MULT = {"🍒": 1.5, "🍋": 2.0, "🍊": 2.5, "⭐": 3.5, "💎": 6.0, "7️⃣": 12.0}


@bot.command(name="slots")
async def slots(ctx, mise: int):
    uid = ctx.author.id
    if mise <= 0:
        return await ctx.send(embed=discord.Embed(
            description="❌ La mise doit être positive.", color=C_ERROR))
    if mise > get_balance(uid):
        return await ctx.send(embed=discord.Embed(
            description="❌ Solde insuffisant.", color=C_ERROR))
    if mise > 5000:
        return await ctx.send(embed=discord.Embed(
            description="❌ Mise maximale : **5 000 🪙**.", color=C_ERROR))

    economy[uid] -= mise
    reels = random.choices(_SLOT_SYM, weights=_SLOT_WGT, k=3)

    if reels[0] == reels[1] == reels[2]:
        mult  = _SLOT_MULT[reels[0]]
        gain  = int(mise * mult)
        economy[uid] += gain
        save_economy()
        result = f"🎰 **JACKPOT ×{mult:.1f} !**  →  **+{gain:,} 🪙**"
        color  = C_SUCCESS
    elif len(set(reels)) == 2:
        gain  = int(mise * 1.5)
        economy[uid] += gain
        save_economy()
        result = f"✨ **Deux identiques ×1.5 !**  →  **+{gain:,} 🪙**"
        color  = C_WARN
    else:
        save_economy()
        result = f"💸 **Rien...**  →  **-{mise:,} 🪙**"
        color  = C_ERROR

    e = discord.Embed(title="🎰 Machine à sous", color=color,
                      timestamp=datetime.datetime.utcnow())
    e.description = (
        f"╔══════════════╗\n"
        f"║  {reels[0]}  {reels[1]}  {reels[2]}  ║\n"
        f"╚══════════════╝\n\n"
        f"{result}"
    )
    e.set_footer(text=f"Mise : {mise:,} 🪙  •  Solde : {get_balance(uid):,} 🪙")
    await ctx.send(embed=e)


# ── Pari pile ou face ─────────────────────────────────────
@bot.command(name="coinflip", aliases=["cf"])
async def coinflip_bet(ctx, mise: int, choix: str):
    uid   = ctx.author.id
    choix = choix.lower()
    if choix not in ("pile", "face", "p", "f"):
        return await ctx.send(embed=discord.Embed(
            description="❌ Choix invalide. Utilise `pile` ou `face`.", color=C_ERROR))
    if mise <= 0:
        return await ctx.send(embed=discord.Embed(
            description="❌ La mise doit être positive.", color=C_ERROR))
    if mise > get_balance(uid):
        return await ctx.send(embed=discord.Embed(
            description="❌ Solde insuffisant.", color=C_ERROR))
    if mise > 10000:
        return await ctx.send(embed=discord.Embed(
            description="❌ Mise maximale : **10 000 🪙**.", color=C_ERROR))

    choix_full = "pile" if choix in ("pile", "p") else "face"
    economy[uid] -= mise
    resultat = random.choice(["pile", "face"])

    if choix_full == resultat:
        gain = mise * 2
        economy[uid] += gain
        save_economy()
        color  = C_SUCCESS
        result = f"🟢 **Gagné !**  →  **+{gain:,} 🪙**"
    else:
        save_economy()
        color  = C_ERROR
        result = f"🔴 **Perdu !**  →  **-{mise:,} 🪙**"

    e = discord.Embed(title="🪙 Pile ou Face", color=color,
                      timestamp=datetime.datetime.utcnow())
    e.description = (f"**Ton choix :** {choix_full}  {'✅' if choix_full == resultat else '❌'}\n"
                     f"**Résultat :**  {resultat}\n\n"
                     f"{result}")
    e.set_footer(text=f"Mise : {mise:,} 🪙  •  Solde : {get_balance(uid):,} 🪙")
    await ctx.send(embed=e)


# ── Travailler ────────────────────────────────────────────
_JOBS = [
    ("👨‍💻 Développeur",     "Tu as codé une appli toute la nuit.",         250, 500),
    ("🍕 Livreur de pizza", "Tu as livré 47 pizzas ce soir.",               100, 250),
    ("🎨 Artiste",          "Tu as vendu une peinture à un musée.",         150, 350),
    ("🔧 Mécanicien",       "Tu as réparé des voitures au garage.",         200, 400),
    ("🎮 Streamer",         "Tes viewers ont fait des dons généreusement.", 180, 450),
    ("📦 Livreur",          "Tu as livré 200 colis sans te perdre.",        120, 300),
    ("🧑‍🍳 Cuisinier",       "Ton restaurant était complet ce soir.",        200, 500),
    ("🎵 Musicien",         "Tu as joué dans un bar bondé.",                130, 320),
    ("🏗️ Ouvrier",          "Tu as bossé dur sur un chantier.",             150, 380),
    ("✍️ Écrivain",         "Ton article a été publié en ligne.",           100, 280),
]


@bot.command(name="work")
async def work(ctx):
    uid      = ctx.author.id
    now      = _time.time()
    last     = work_cooldown.get(uid, 0)
    cooldown = 4 * 3600

    if now - last < cooldown:
        reste = int(cooldown - (now - last))
        h, r  = divmod(reste, 3600)
        m, s  = divmod(r, 60)
        return await ctx.send(embed=discord.Embed(
            description=f"😴 Tu es épuisé ! Reviens dans **{h}h {m}m {s}s**.",
            color=C_ERROR))

    job, desc, min_g, max_g = random.choice(_JOBS)
    gain = random.randint(min_g, max_g)
    economy[uid] = get_balance(uid) + gain
    work_cooldown[uid] = now
    save_economy()

    e = discord.Embed(title=f"💼 {job}", color=C_GOLD,
                      timestamp=datetime.datetime.utcnow())
    e.description = f"*{desc}*"
    e.add_field(name="💵 Salaire",  value=f"**+{gain:,} 🪙**")
    e.add_field(name="💰 Solde",    value=f"**{economy[uid]:,} 🪙**")
    e.set_footer(text="Recharge dans 4h")
    e.set_thumbnail(url=ctx.author.display_avatar.url)
    await ctx.send(embed=e)


# ── Vol ───────────────────────────────────────────────────
@bot.command(name="rob")
async def rob(ctx, target: discord.Member):
    uid = ctx.author.id
    tid = target.id
    now = _time.time()

    if target == ctx.author:
        return await ctx.send(embed=discord.Embed(
            description="❌ Tu ne peux pas te voler toi-même.", color=C_ERROR))
    if target.bot:
        return await ctx.send(embed=discord.Embed(
            description="❌ Impossible de voler un bot.", color=C_ERROR))

    last = rob_cooldown.get(uid, 0)
    if now - last < 3600:
        reste = int(3600 - (now - last))
        m, s  = divmod(reste, 60)
        return await ctx.send(embed=discord.Embed(
            description=f"🚔 Tu te fais encore trop remarquer ! Attends **{m}m {s}s**.",
            color=C_ERROR))

    if get_balance(tid) < 100:
        return await ctx.send(embed=discord.Embed(
            description=f"❌ {target.mention} n'a pas assez de pièces à voler (min. 100 🪙).",
            color=C_ERROR))

    rob_cooldown[uid] = now

    if random.random() < 0.40:
        pct    = random.uniform(0.10, 0.30)
        stolen = int(get_balance(tid) * pct)
        economy[tid] = max(0, get_balance(tid) - stolen)
        economy[uid] = get_balance(uid) + stolen
        save_economy()
        e = discord.Embed(
            title="🦹 Vol réussi !",
            description=(f"Tu as dérobé **{stolen:,} 🪙** à {target.mention} !\n"
                         f"*(environ {int(pct*100)}% de leur solde)*"),
            color=C_SUCCESS, timestamp=datetime.datetime.utcnow())
        e.set_thumbnail(url=target.display_avatar.url)
    else:
        amende = random.randint(50, 250)
        economy[uid] = max(0, get_balance(uid) - amende)
        save_economy()
        e = discord.Embed(
            title="🚔 Pris en flagrant délit !",
            description=(f"Tu as été arrêté en tentant de voler {target.mention}.\n"
                         f"Amende : **{amende:,} 🪙** confisquée."),
            color=C_ERROR, timestamp=datetime.datetime.utcnow())
        e.set_thumbnail(url=ctx.author.display_avatar.url)

    e.set_footer(text=f"Ton solde : {get_balance(uid):,} 🪙")
    await ctx.send(embed=e)


# ═══════════════════════════════════════════════════════════
#  UTILITAIRE  (+afk  +calc  +weather  +poll  +say)
# ═══════════════════════════════════════════════════════════
@bot.command()
async def afk(ctx, *, reason="AFK"):
    afk_users[ctx.author.id] = reason
    save_afk()
    await ctx.send(embed=discord.Embed(
        description=f"💤 {ctx.author.mention} est maintenant AFK : *{reason}*",
        color=C_WARN))

@bot.command(name="calc")
async def calc(ctx, *, expression):
    safe = {"__builtins__": {}}
    safe.update({k: getattr(math, k) for k in dir(math) if not k.startswith("_")})
    try:
        result = eval(expression, safe)
        e = discord.Embed(title="🧮 Calculatrice", color=C_INFO)
        e.add_field(name="Expression", value=f"`{expression}`")
        e.add_field(name="Résultat",   value=f"**{result}**")
        await ctx.send(embed=e)
    except Exception:
        await ctx.send(embed=discord.Embed(
            description="❌ Expression invalide.", color=C_ERROR))

@bot.command(name="weather")
async def weather(ctx, *, city="Paris"):
    conditions = ["☀️ Ensoleillé", "🌧️ Pluvieux", "⛈️ Orageux",
                  "🌨️ Neigeux", "🌫️ Brumeux", "🌤️ Partiellement nuageux"]
    e = discord.Embed(
        title=f"🌍 Météo — {city}",
        description=(f"{random.choice(conditions)}\n"
                     f"🌡️ **{random.randint(-10, 40)}°C**\n"
                     f"💧 Humidité : {random.randint(10, 100)}%\n"
                     f"💨 Vent : {random.randint(0, 80)} km/h"),
        color=C_INFO)
    e.set_footer(text="⚠️ Données fictives, uniquement pour le fun !")
    await ctx.send(embed=e)

@bot.command()
async def poll(ctx, question: str, *options):
    if len(options) < 2:
        return await ctx.send(embed=discord.Embed(
            description="❌ Fournis au moins 2 options (entre guillemets).", color=C_ERROR))
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    desc   = "\n".join(f"{emojis[i]} {opt}" for i, opt in enumerate(options[:10]))
    e = discord.Embed(
        title=f"📊 {question}",
        description=desc,
        color=C_PRIMARY,
        timestamp=datetime.datetime.utcnow())
    e.set_footer(text=f"Sondage de {ctx.author}", icon_url=ctx.author.display_avatar.url)
    msg = await ctx.send(embed=e)
    for i in range(len(options[:10])):
        await msg.add_reaction(emojis[i])

@bot.command()
@commands.has_permissions(manage_messages=True)
async def say(ctx, *, message: str):
    await ctx.message.delete()
    await ctx.send(message)


# ═══════════════════════════════════════════════════════════
#  GESTIONNAIRE D'ERREURS
# ═══════════════════════════════════════════════════════════
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(embed=discord.Embed(
            description="❌ Tu n'as pas la permission d'utiliser cette commande.",
            color=C_ERROR))
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=discord.Embed(
            description=f"❌ Argument manquant. Utilise `{PREFIX}help` pour les détails.",
            color=C_ERROR))
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send(embed=discord.Embed(
            description="❌ Membre introuvable.", color=C_ERROR))
    elif isinstance(error, commands.BadArgument):
        await ctx.send(embed=discord.Embed(
            description="❌ Argument invalide.", color=C_ERROR))
    elif isinstance(error, commands.CommandNotFound):
        pass
    elif isinstance(error, commands.CheckFailure):
        pass
    else:
        raise error


# ═══════════════════════════════════════════════════════════
#  DÉMARRAGE
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    bot.run(TOKEN)