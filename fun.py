import random
import time
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import database as db

# ---------------------------------------------------------------------------
# Ship helpers (unchanged)
# ---------------------------------------------------------------------------

def ship_percent() -> float:
    return round(random.uniform(0, 100), 2)


def ship_name(name_a: str, name_b: str) -> str:
    half_a = name_a[: max(1, len(name_a) // 2)]
    half_b = name_b[len(name_b) // 2:] or name_b
    return (half_a + half_b).title()


def heart_bar(pct: float, length: int = 14) -> str:
    filled = round((pct / 100) * length)
    return "❤️" * filled + "🤍" * (length - filled)


VERDICT_TIERS = [
    (90, ["Soulmates 💍", "Written in the stars ✨", "Endgame 💍", "Two halves of one whole 💫"]),
    (70, ["Strong match 💕", "This could really go somewhere 💕", "Certified cute 🥰", "Definitely a vibe 💕"]),
    (40, ["Could go either way 🤷", "Jury's still out 🤔", "50/50 energy 🤷", "Mid, but not impossible 😅"]),
    (15, ["...rough 💔", "Yikes, but not zero 😬", "Might need a miracle 💔", "Not looking great, chief 😅"]),
    (0,  ["Please don't 🚫", "Absolutely not 🚫", "Run 🏃", "The universe says no 🚫"]),
]


def verdict_for(pct: float) -> str:
    for threshold, options in VERDICT_TIERS:
        if pct >= threshold:
            return random.choice(options)
    return random.choice(VERDICT_TIERS[-1][1])


# ---------------------------------------------------------------------------
# 8-ball responses
# ---------------------------------------------------------------------------

EIGHTBALL_RESPONSES = [
    # positive
    ("It is certain.", discord.Color.green()),
    ("Without a doubt.", discord.Color.green()),
    ("You may rely on it.", discord.Color.green()),
    ("Yes, definitely.", discord.Color.green()),
    ("As I see it, yes.", discord.Color.green()),
    ("Most likely.", discord.Color.green()),
    ("Outlook good.", discord.Color.green()),
    ("Signs point to yes.", discord.Color.green()),
    # neutral
    ("Reply hazy, try again.", discord.Color.gold()),
    ("Ask again later.", discord.Color.gold()),
    ("Better not tell you now.", discord.Color.gold()),
    ("Cannot predict now.", discord.Color.gold()),
    ("Concentrate and ask again.", discord.Color.gold()),
    # negative
    ("Don't count on it.", discord.Color.red()),
    ("My reply is no.", discord.Color.red()),
    ("My sources say no.", discord.Color.red()),
    ("Outlook not so good.", discord.Color.red()),
    ("Very doubtful.", discord.Color.red()),
]

# ---------------------------------------------------------------------------
# Trivia question bank (no API needed — fully self-contained)
# ---------------------------------------------------------------------------

TRIVIA_QUESTIONS = [
    {
        "q": "What planet is closest to the Sun?",
        "options": ["Venus", "Mercury", "Mars", "Earth"],
        "answer": 1,
    },
    {
        "q": "How many sides does a hexagon have?",
        "options": ["5", "6", "7", "8"],
        "answer": 1,
    },
    {
        "q": "What is the chemical symbol for gold?",
        "options": ["Go", "Gd", "Au", "Ag"],
        "answer": 2,
    },
    {
        "q": "Who wrote 'Romeo and Juliet'?",
        "options": ["Charles Dickens", "Jane Austen", "William Shakespeare", "Mark Twain"],
        "answer": 2,
    },
    {
        "q": "What is the largest ocean on Earth?",
        "options": ["Atlantic", "Indian", "Arctic", "Pacific"],
        "answer": 3,
    },
    {
        "q": "How many bones are in the adult human body?",
        "options": ["196", "206", "216", "226"],
        "answer": 1,
    },
    {
        "q": "What year did World War II end?",
        "options": ["1943", "1944", "1945", "1946"],
        "answer": 2,
    },
    {
        "q": "Which element has the atomic number 1?",
        "options": ["Helium", "Hydrogen", "Lithium", "Carbon"],
        "answer": 1,
    },
    {
        "q": "What is the capital of Japan?",
        "options": ["Kyoto", "Osaka", "Tokyo", "Hiroshima"],
        "answer": 2,
    },
    {
        "q": "Who painted the Mona Lisa?",
        "options": ["Michelangelo", "Raphael", "Caravaggio", "Leonardo da Vinci"],
        "answer": 3,
    },
    {
        "q": "What is the speed of light (approx.) in km/s?",
        "options": ["150,000", "200,000", "250,000", "300,000"],
        "answer": 3,
    },
    {
        "q": "In what country is the Great Barrier Reef?",
        "options": ["Brazil", "USA", "Australia", "Indonesia"],
        "answer": 2,
    },
    {
        "q": "How many strings does a standard guitar have?",
        "options": ["4", "5", "6", "7"],
        "answer": 2,
    },
    {
        "q": "What is the powerhouse of the cell?",
        "options": ["Nucleus", "Ribosome", "Mitochondria", "Golgi apparatus"],
        "answer": 2,
    },
    {
        "q": "Which planet has the most moons?",
        "options": ["Jupiter", "Saturn", "Uranus", "Neptune"],
        "answer": 1,
    },
    {
        "q": "What language has the most native speakers worldwide?",
        "options": ["English", "Hindi", "Spanish", "Mandarin Chinese"],
        "answer": 3,
    },
    {
        "q": "What is 7 × 8?",
        "options": ["54", "56", "58", "64"],
        "answer": 1,
    },
    {
        "q": "Which country invented pizza?",
        "options": ["France", "Greece", "Italy", "Spain"],
        "answer": 2,
    },
    {
        "q": "How many continents are on Earth?",
        "options": ["5", "6", "7", "8"],
        "answer": 2,
    },
    {
        "q": "What is the longest river in the world?",
        "options": ["Amazon", "Mississippi", "Yangtze", "Nile"],
        "answer": 3,
    },
    {
        "q": "Which programming language was named after a snake?",
        "options": ["Cobra", "Python", "Viper", "Anaconda"],
        "answer": 1,
    },
    {
        "q": "What is H₂O more commonly known as?",
        "options": ["Hydrogen", "Oxygen", "Water", "Salt"],
        "answer": 2,
    },
    {
        "q": "How many players are on a standard soccer team?",
        "options": ["9", "10", "11", "12"],
        "answer": 2,
    },
    {
        "q": "What is the smallest prime number?",
        "options": ["0", "1", "2", "3"],
        "answer": 2,
    },
    {
        "q": "In which city is the Eiffel Tower?",
        "options": ["London", "Rome", "Berlin", "Paris"],
        "answer": 3,
    },
]

BUTTON_LABELS = ["🇦", "🇧", "🇨", "🇩"]
BUTTON_LETTERS = ["A", "B", "C", "D"]

TRIVIA_TIME_LIMIT = 20  # seconds before auto-expiry


class TriviaView(discord.ui.View):
    """Button-based trivia answer panel. Disables all buttons on first answer."""

    def __init__(self, question: dict, asker_id: int):
        super().__init__(timeout=TRIVIA_TIME_LIMIT)
        self.question = question
        self.asker_id = asker_id
        self.answered = False

        for i, label in enumerate(question["options"]):
            btn = discord.ui.Button(
                label=f"{BUTTON_LETTERS[i]}: {label}",
                custom_id=str(i),
                style=discord.ButtonStyle.secondary,
            )
            btn.callback = self._make_callback(i)
            self.add_item(btn)

    def _make_callback(self, index: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.asker_id:
                await interaction.response.send_message(
                    "This isn't your trivia question! Use `/trivia` to start your own.", ephemeral=True
                )
                return

            if self.answered:
                await interaction.response.defer()
                return

            self.answered = True
            self.stop()

            correct = index == self.question["answer"]
            correct_label = self.question["options"][self.question["answer"]]

            # Update scores in DB
            if correct:
                db.trivia_add_score(interaction.guild_id, interaction.user.id, 1)

            # Rebuild embed with result
            color = discord.Color.green() if correct else discord.Color.red()
            result_line = (
                f"✅ **Correct!** +1 point"
                if correct
                else f"❌ **Wrong!** The answer was **{BUTTON_LETTERS[self.question['answer']]}: {correct_label}**"
            )

            scores = db.trivia_get_score(interaction.guild_id, interaction.user.id)
            embed = discord.Embed(
                title="🧠 Trivia",
                description=f"**{self.question['q']}**\n\n{result_line}\n\nYour total score: **{scores}** point{'s' if scores != 1 else ''}",
                color=color,
            )

            # Disable all buttons and color-code
            for child in self.children:
                child.disabled = True
                if int(child.custom_id) == self.question["answer"]:
                    child.style = discord.ButtonStyle.success
                elif int(child.custom_id) == index and not correct:
                    child.style = discord.ButtonStyle.danger

            await interaction.response.edit_message(embed=embed, view=self)

        return callback

    async def on_timeout(self):
        correct_label = self.question["options"][self.question["answer"]]
        for child in self.children:
            child.disabled = True
            if int(child.custom_id) == self.question["answer"]:
                child.style = discord.ButtonStyle.success
        # Can't edit the message from here without the interaction — the
        # view just locks so the labels stay as a visual hint.


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---- Ship ----------------------------------------------------------------

    def _ship_embed(self, guild: discord.Guild, user_a: discord.Member, user_b: discord.Member) -> discord.Embed:
        override = db.get_ship_override(guild.id, user_a.id, user_b.id)
        pinned = override is not None

        if user_a.id == user_b.id and not pinned:
            pct, verdict = 100.0, "Self love 🪞✨"
            name = user_a.display_name
        else:
            pct = override if pinned else ship_percent()
            verdict = verdict_for(pct)
            name = user_a.display_name if user_a.id == user_b.id else ship_name(user_a.display_name, user_b.display_name)
        bar = heart_bar(pct)

        embed = discord.Embed(
            title=f"💘 {name}",
            description=f"{user_a.mention} × {user_b.mention}\n\n{bar}\n**{pct}%** · {verdict}",
            color=discord.Color.from_rgb(255, 105, 180),
        )
        if pinned:
            embed.set_footer(text="📌 Set by an admin")
        return embed

    @app_commands.command(name="ship", description="Ship two members and get a compatibility score")
    @app_commands.describe(user1="First person", user2="Second person (defaults to you)")
    async def ship(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member = None):
        target_b = user2 or interaction.user
        await interaction.response.send_message(embed=self._ship_embed(interaction.guild, user1, target_b))

    @commands.command(name="ship")
    async def ship_text(self, ctx: commands.Context, user1: discord.Member, user2: discord.Member = None):
        target_b = user2 or ctx.author
        await ctx.reply(embed=self._ship_embed(ctx.guild, user1, target_b), mention_author=False)

    @app_commands.command(name="shipset", description="[Admin] Pin a fixed compatibility % for two members")
    @app_commands.describe(user1="First person", user2="Second person", percent="The percent to always show (0-100)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def shipset(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member, percent: app_commands.Range[float, 0, 100]):
        db.set_ship_override(interaction.guild_id, user1.id, user2.id, percent, interaction.user.id)
        await interaction.response.send_message(
            f"📌 {user1.mention} × {user2.mention} will always ship at **{percent}%** until cleared with `/shipclear`.",
            ephemeral=True,
        )

    @app_commands.command(name="shipclear", description="[Admin] Remove a pinned ship percent, back to random")
    @app_commands.describe(user1="First person", user2="Second person")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def shipclear(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
        removed = db.remove_ship_override(interaction.guild_id, user1.id, user2.id)
        if removed:
            await interaction.response.send_message(f"🧹 Cleared the pinned percent for {user1.mention} × {user2.mention}.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{user1.mention} × {user2.mention} didn't have a pinned percent.", ephemeral=True)

    @commands.command(name="shipset")
    @commands.has_permissions(manage_guild=True)
    async def shipset_text(self, ctx: commands.Context, user1: discord.Member, user2: discord.Member, percent: float):
        percent = max(0.0, min(100.0, percent))
        db.set_ship_override(ctx.guild.id, user1.id, user2.id, percent, ctx.author.id)
        await ctx.reply(f"📌 {user1.mention} × {user2.mention} will now always ship at **{percent}%**.", mention_author=False)

    @commands.command(name="shipclear")
    @commands.has_permissions(manage_guild=True)
    async def shipclear_text(self, ctx: commands.Context, user1: discord.Member, user2: discord.Member):
        removed = db.remove_ship_override(ctx.guild.id, user1.id, user2.id)
        if removed:
            await ctx.reply(f"🧹 Cleared the pinned percent for {user1.mention} × {user2.mention}.", mention_author=False)
        else:
            await ctx.reply(f"{user1.mention} × {user2.mention} didn't have a pinned percent.", mention_author=False)

    # ---- Rickroll ------------------------------------------------------------

    def _rickroll_embed(self, sender: discord.Member, target: discord.Member = None) -> discord.Embed:
        if target and target.id != sender.id:
            desc = f"{target.mention} just got Rick Rolled by {sender.mention} 💀\n\nhttps://www.youtube.com/watch?v=dQw4w9WgXcQ"
        else:
            desc = f"{sender.mention} Rick Rolled the whole chat 💀\n\nhttps://www.youtube.com/watch?v=dQw4w9WgXcQ"
        embed = discord.Embed(
            title="🎵 Never Gonna Give You Up",
            description=desc,
            color=discord.Color.orange(),
        )
        return embed

    @app_commands.command(name="rickroll", description="Rickroll someone -- no disguise, it's just the song")
    @app_commands.describe(target="Optional -- mention someone to call them out")
    async def rickroll(self, interaction: discord.Interaction, target: discord.Member = None):
        await interaction.response.send_message(embed=self._rickroll_embed(interaction.user, target))

    @commands.command(name="rickroll")
    async def rickroll_text(self, ctx: commands.Context, target: discord.Member = None):
        await ctx.reply(embed=self._rickroll_embed(ctx.author, target), mention_author=False)

    # ---- 8-ball --------------------------------------------------------------

    @app_commands.command(name="8ball", description="Ask the magic 8-ball a yes/no question")
    @app_commands.describe(question="Your question")
    async def eightball(self, interaction: discord.Interaction, question: str):
        response, color = random.choice(EIGHTBALL_RESPONSES)
        embed = discord.Embed(color=color)
        embed.add_field(name="🎱 Question", value=question, inline=False)
        embed.add_field(name="Answer", value=f"**{response}**", inline=False)
        embed.set_footer(text=f"Asked by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

    @commands.command(name="8ball")
    async def eightball_text(self, ctx: commands.Context, *, question: str):
        response, color = random.choice(EIGHTBALL_RESPONSES)
        embed = discord.Embed(color=color)
        embed.add_field(name="🎱 Question", value=question, inline=False)
        embed.add_field(name="Answer", value=f"**{response}**", inline=False)
        embed.set_footer(text=f"Asked by {ctx.author.display_name}")
        await ctx.reply(embed=embed, mention_author=False)

    # ---- Coin flip -----------------------------------------------------------

    @app_commands.command(name="coinflip", description="Flip a coin")
    async def coinflip(self, interaction: discord.Interaction):
        result = random.choice(["Heads", "Tails"])
        emoji = "🪙" if result == "Heads" else "🪙"
        embed = discord.Embed(
            title=f"{emoji} Coin Flip",
            description=f"**{result}!**",
            color=discord.Color.gold(),
        )
        embed.set_footer(text=f"Flipped by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

    @commands.command(name="coinflip", aliases=["flip"])
    async def coinflip_text(self, ctx: commands.Context):
        result = random.choice(["Heads", "Tails"])
        embed = discord.Embed(
            title="🪙 Coin Flip",
            description=f"**{result}!**",
            color=discord.Color.gold(),
        )
        embed.set_footer(text=f"Flipped by {ctx.author.display_name}")
        await ctx.reply(embed=embed, mention_author=False)

    # ---- Dice ----------------------------------------------------------------

    @app_commands.command(name="dice", description="Roll one or more dice — e.g. /dice sides:20 count:2")
    @app_commands.describe(sides="Number of sides (default 6, max 1000)", count="Number of dice (default 1, max 10)")
    async def dice(
        self,
        interaction: discord.Interaction,
        sides: app_commands.Range[int, 2, 1000] = 6,
        count: app_commands.Range[int, 1, 10] = 1,
    ):
        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls)
        rolls_str = ", ".join(str(r) for r in rolls)
        desc = f"**Rolls:** {rolls_str}"
        if count > 1:
            desc += f"\n**Total:** {total}"
        embed = discord.Embed(
            title=f"🎲 {count}d{sides}",
            description=desc,
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"Rolled by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

    @commands.command(name="dice", aliases=["roll"])
    async def dice_text(self, ctx: commands.Context, dice_str: str = "1d6"):
        """Usage: ?dice [NdS] e.g. ?dice 2d20"""
        try:
            parts = dice_str.lower().split("d")
            count = int(parts[0]) if parts[0] else 1
            sides = int(parts[1])
            count = max(1, min(count, 10))
            sides = max(2, min(sides, 1000))
        except (ValueError, IndexError):
            await ctx.reply("Usage: `?dice 2d6` (number of dice d sides)", mention_author=False)
            return
        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls)
        rolls_str = ", ".join(str(r) for r in rolls)
        desc = f"**Rolls:** {rolls_str}"
        if count > 1:
            desc += f"\n**Total:** {total}"
        embed = discord.Embed(title=f"🎲 {count}d{sides}", description=desc, color=discord.Color.blurple())
        embed.set_footer(text=f"Rolled by {ctx.author.display_name}")
        await ctx.reply(embed=embed, mention_author=False)

    # ---- Trivia --------------------------------------------------------------

    def _trivia_question_embed(self, q: dict) -> discord.Embed:
        options_text = "\n".join(
            f"{BUTTON_LABELS[i]} {opt}" for i, opt in enumerate(q["options"])
        )
        embed = discord.Embed(
            title="🧠 Trivia",
            description=f"**{q['q']}**\n\n{options_text}",
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"You have {TRIVIA_TIME_LIMIT} seconds to answer · use the buttons below")
        return embed

    @app_commands.command(name="trivia", description="Get a random trivia question and answer with buttons")
    async def trivia(self, interaction: discord.Interaction):
        q = random.choice(TRIVIA_QUESTIONS)
        view = TriviaView(q, interaction.user.id)
        await interaction.response.send_message(embed=self._trivia_question_embed(q), view=view)

    @commands.command(name="trivia")
    async def trivia_text(self, ctx: commands.Context):
        q = random.choice(TRIVIA_QUESTIONS)
        view = TriviaView(q, ctx.author.id)
        await ctx.reply(embed=self._trivia_question_embed(q), view=view, mention_author=False)

    @app_commands.command(name="triviascore", description="Check your trivia score (or someone else's)")
    @app_commands.describe(member="Who to check (defaults to you)")
    async def triviascore(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        score = db.trivia_get_score(interaction.guild_id, target.id)
        embed = discord.Embed(
            title="🏆 Trivia Score",
            description=f"{target.mention} has **{score}** correct answer{'s' if score != 1 else ''}.",
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="triviatop", description="Trivia leaderboard for this server")
    async def triviatop(self, interaction: discord.Interaction):
        rows = db.trivia_top(interaction.guild_id, limit=10)
        if not rows:
            await interaction.response.send_message("No trivia scores yet — be the first with `/trivia`!", ephemeral=True)
            return
        lines = []
        medals = ["🥇", "🥈", "🥉"]
        for i, (user_id, score) in enumerate(rows):
            prefix = medals[i] if i < 3 else f"**#{i+1}**"
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else f"<@{user_id}>"
            lines.append(f"{prefix} {name} — {score} point{'s' if score != 1 else ''}")
        embed = discord.Embed(
            title="🏆 Trivia Leaderboard",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed)

    # ---- User info -----------------------------------------------------------

    @app_commands.command(name="userinfo", description="Get info about a member")
    @app_commands.describe(member="Who to look up (defaults to you)")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        roles = [r.mention for r in reversed(target.roles) if r.name != "@everyone"]
        roles_str = " ".join(roles[:15]) + (f" (+{len(roles)-15} more)" if len(roles) > 15 else "") if roles else "None"

        embed = discord.Embed(
            title=str(target),
            color=target.color if target.color != discord.Color.default() else discord.Color.blurple(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Display Name", value=target.display_name, inline=True)
        embed.add_field(name="ID", value=str(target.id), inline=True)
        embed.add_field(name="Bot", value="Yes" if target.bot else "No", inline=True)
        embed.add_field(name="Account Created", value=discord.utils.format_dt(target.created_at, "D"), inline=True)
        embed.add_field(name="Joined Server", value=discord.utils.format_dt(target.joined_at, "D") if target.joined_at else "Unknown", inline=True)
        embed.add_field(name="Boosting Since", value=discord.utils.format_dt(target.premium_since, "D") if target.premium_since else "Not boosting", inline=True)
        embed.add_field(name=f"Roles ({len(roles)})", value=roles_str or "None", inline=False)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

    @commands.command(name="userinfo", aliases=["whois", "ui"])
    async def userinfo_text(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        roles = [r.mention for r in reversed(target.roles) if r.name != "@everyone"]
        roles_str = " ".join(roles[:15]) + (f" (+{len(roles)-15} more)" if len(roles) > 15 else "") if roles else "None"
        embed = discord.Embed(title=str(target), color=target.color if target.color != discord.Color.default() else discord.Color.blurple())
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Display Name", value=target.display_name, inline=True)
        embed.add_field(name="ID", value=str(target.id), inline=True)
        embed.add_field(name="Bot", value="Yes" if target.bot else "No", inline=True)
        embed.add_field(name="Account Created", value=discord.utils.format_dt(target.created_at, "D"), inline=True)
        embed.add_field(name="Joined Server", value=discord.utils.format_dt(target.joined_at, "D") if target.joined_at else "Unknown", inline=True)
        embed.add_field(name="Boosting Since", value=discord.utils.format_dt(target.premium_since, "D") if target.premium_since else "Not boosting", inline=True)
        embed.add_field(name=f"Roles ({len(roles)})", value=roles_str, inline=False)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.reply(embed=embed, mention_author=False)

    # ---- Server info ---------------------------------------------------------

    @app_commands.command(name="serverinfo", description="Info about this server")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(
            title=guild.name,
            description=guild.description or "",
            color=discord.Color.blurple(),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        if guild.banner:
            embed.set_image(url=guild.banner.url)
        embed.add_field(name="Owner", value=f"<@{guild.owner_id}>", inline=True)
        embed.add_field(name="ID", value=str(guild.id), inline=True)
        embed.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, "D"), inline=True)
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Boost Level", value=f"Level {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)
        embed.add_field(name="Verification", value=str(guild.verification_level).title(), inline=True)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

    @commands.command(name="serverinfo", aliases=["si", "server"])
    async def serverinfo_text(self, ctx: commands.Context):
        guild = ctx.guild
        embed = discord.Embed(title=guild.name, description=guild.description or "", color=discord.Color.blurple())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Owner", value=f"<@{guild.owner_id}>", inline=True)
        embed.add_field(name="ID", value=str(guild.id), inline=True)
        embed.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, "D"), inline=True)
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Boost Level", value=f"Level {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)
        embed.add_field(name="Verification", value=str(guild.verification_level).title(), inline=True)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.reply(embed=embed, mention_author=False)

    # ---- Avatar --------------------------------------------------------------

    @app_commands.command(name="avatar", description="Get someone's full-size avatar")
    @app_commands.describe(member="Whose avatar (defaults to you)")
    async def avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        embed = discord.Embed(
            title=f"{target.display_name}'s Avatar",
            color=target.color if target.color != discord.Color.default() else discord.Color.blurple(),
        )
        embed.set_image(url=target.display_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

    @commands.command(name="avatar", aliases=["av", "pfp"])
    async def avatar_text(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        embed = discord.Embed(title=f"{target.display_name}'s Avatar", color=discord.Color.blurple())
        embed.set_image(url=target.display_avatar.url)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.reply(embed=embed, mention_author=False)

    # ---- Error handlers ------------------------------------------------------

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("You need the Manage Server permission to do that.", ephemeral=True)
        elif not interaction.response.is_done():
            await interaction.response.send_message(f"Error: {error}", ephemeral=True)

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply("You need the Manage Server permission to do that.", mention_author=False)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.reply("Couldn't find that member.", mention_author=False)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(
                f"Usage: `{ctx.prefix}ship <member> [member2]` / `{ctx.prefix}dice 2d6` / `{ctx.prefix}8ball <question>`",
                mention_author=False,
            )
        else:
            print(f"Fun prefix command error: {error}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
