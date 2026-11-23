"""
music.py — wavelink 3.x rewrite
No ffmpeg required. Audio is handled by a remote Lavalink node.
Public node credentials are set via environment variables (see below).

Required env vars (set in Railway):
    LAVALINK_URI      — e.g. wss://lavalink.clxud.dev
    LAVALINK_PASSWORD — e.g. youshallnotpass

Optional:
    SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET — enables Spotify link support
      (wavelink handles Spotify natively via the Lavalink Spotify source plugin
       if the node has it; otherwise falls back to YouTube search per track)
"""

import asyncio
import os
import re

import discord
import wavelink
from discord import app_commands
from discord.ext import commands

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

LAVALINK_URI = os.getenv("LAVALINK_URI", "wss://lavalink.clxud.dev")
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")

SKIP_VOTES_REQUIRED = 2

SPOTIFY_URL_RE = re.compile(r"open\.spotify\.com/(track|album|playlist)/([a-zA-Z0-9]+)")
MAX_SPOTIFY_TRACKS = 50

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def music_embed(text: str, color: discord.Color = discord.Color.blurple()) -> discord.Embed:
    return discord.Embed(description=text, color=color)


def _fmt_duration(ms: int) -> str:
    """milliseconds → m:ss or h:mm:ss string."""
    s = ms // 1000
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# Per-guild state
# ---------------------------------------------------------------------------


class GuildMusicState:
    def __init__(self):
        self.skip_votes: set[int] = set()
        self.loop_song: bool = False
        self.autoplay: bool = True
        self.volume: int = 50  # wavelink uses 0-1000, but we expose 0-100 and scale
        self.text_channel: discord.abc.Messageable | None = None


# ---------------------------------------------------------------------------
# Now Playing control panel
# ---------------------------------------------------------------------------


class MusicControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def _player(self, interaction: discord.Interaction) -> wavelink.Player | None:
        return interaction.guild.voice_client  # type: ignore[return-value]

    def _state(self, interaction: discord.Interaction) -> GuildMusicState | None:
        cog: Music | None = interaction.client.get_cog("Music")  # type: ignore[assignment]
        if cog is None:
            return None
        return cog.get_state(interaction.guild)

    @discord.ui.button(emoji="⏯️", label="Pause/Resume", style=discord.ButtonStyle.secondary, custom_id="music_pauseresume")
    async def pause_resume(self, interaction: discord.Interaction, _button: discord.ui.Button):
        player = self._player(interaction)
        if not player:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        await player.pause(not player.paused)
        label = "⏸️ Paused." if player.paused else "▶️ Resumed."
        await interaction.response.send_message(label, ephemeral=True)

    @discord.ui.button(emoji="⏭️", label="Skip", style=discord.ButtonStyle.secondary, custom_id="music_skip")
    async def skip(self, interaction: discord.Interaction, _button: discord.ui.Button):
        cog: Music | None = interaction.client.get_cog("Music")  # type: ignore[assignment]
        state = self._state(interaction)
        player = self._player(interaction)
        if not cog or not state or not player:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        msg, _ = await cog._register_skip_vote(interaction, state, player)
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(emoji="⏹️", label="Stop", style=discord.ButtonStyle.danger, custom_id="music_stop")
    async def stop(self, interaction: discord.Interaction, _button: discord.ui.Button):
        player = self._player(interaction)
        state = self._state(interaction)
        if not player or not state:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        state.skip_votes.clear()
        state.loop_song = False
        await player.disconnect()
        await interaction.response.send_message("⏹️ Stopped and cleared the queue.", ephemeral=True)

    @discord.ui.button(emoji="📜", label="Queue", style=discord.ButtonStyle.secondary, custom_id="music_queue")
    async def show_queue(self, interaction: discord.Interaction, _button: discord.ui.Button):
        player = self._player(interaction)
        if not player or not player.current:
            await interaction.response.send_message("The queue is empty.", ephemeral=True)
            return
        embed = _build_queue_embed(player)
        await interaction.response.send_message(embed=embed, ephemeral=True)


def _build_queue_embed(player: wavelink.Player) -> discord.Embed:
    embed = discord.Embed(title="🎵 Music Queue", color=discord.Color.green())
    if player.current:
        requester = getattr(player.current, "_requester", None)
        who = requester.mention if requester else "Unknown"
        embed.add_field(
            name="Now Playing",
            value=f"**{player.current.title}** ({_fmt_duration(player.current.length)}) — {who}",
            inline=False,
        )
    upcoming = list(player.queue)
    if upcoming:
        lines = []
        for i, t in enumerate(upcoming[:10], start=1):
            req = getattr(t, "_requester", None)
            who = req.mention if req else "Unknown"
            lines.append(f"{i}. {t.title} ({_fmt_duration(t.length)}) — {who}")
        embed.add_field(name="Up Next", value="\n".join(lines), inline=False)
        if len(upcoming) > 10:
            embed.set_footer(text=f"...and {len(upcoming) - 10} more")
    return embed


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._states: dict[int, GuildMusicState] = {}
        bot.add_view(MusicControlView())

    def get_state(self, guild: discord.Guild) -> GuildMusicState:
        if guild.id not in self._states:
            self._states[guild.id] = GuildMusicState()
        return self._states[guild.id]

    # ------------------------------------------------------------------
    # Lavalink connection
    # ------------------------------------------------------------------

    async def cog_load(self):
        node = wavelink.Node(uri=LAVALINK_URI, password=LAVALINK_PASSWORD)
        await wavelink.Pool.connect(nodes=[node], client=self.bot, cache_capacity=100)

    # ------------------------------------------------------------------
    # wavelink events
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f"[music] Lavalink node ready: {payload.node.uri} | resumed={payload.resumed}")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        player: wavelink.Player = payload.player
        state = self._states.get(player.guild.id)
        if not state or not state.text_channel or not player.current:
            return
        track = player.current
        requester = getattr(track, "_requester", None)
        embed = discord.Embed(
            title="▶️ Now Playing",
            description=f"[{track.title}]({track.uri})",
            color=discord.Color.green(),
        )
        embed.add_field(name="Duration", value=_fmt_duration(track.length))
        embed.add_field(name="Requested by", value=requester.mention if requester else "Autoplay")
        try:
            await state.text_channel.send(embed=embed, view=MusicControlView())
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player: wavelink.Player = payload.player
        state = self._states.get(player.guild.id)
        if state:
            state.skip_votes.clear()

        # loop: re-insert the finished track at the front
        if state and state.loop_song and payload.track:
            await player.queue.put_wait(payload.track)

        # autoplay: wavelink's built-in autoplay handles this when enabled
        # nothing extra needed here

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player):
        """Fires when the player has been idle (empty queue, nothing playing) for a while."""
        state = self._states.get(player.guild.id)
        if state and state.text_channel:
            try:
                await state.text_channel.send(
                    embed=discord.Embed(
                        description="Queue's empty and I've been idle — disconnecting. Use `/play` to start again.",
                        color=discord.Color.orange(),
                    )
                )
            except discord.Forbidden:
                pass
        await player.disconnect()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        # Bot got disconnected externally
        if member.id == self.bot.user.id and before.channel and not after.channel:
            state = self._states.get(member.guild.id)
            if state:
                state.skip_votes.clear()
            return

        # Auto-leave when everyone else leaves
        if before.channel and member.id != self.bot.user.id:
            player: wavelink.Player | None = member.guild.voice_client  # type: ignore[assignment]
            if player and player.channel == before.channel:
                if all(m.bot for m in before.channel.members):
                    await asyncio.sleep(60)
                    if player.connected and player.channel and all(m.bot for m in player.channel.members):
                        await player.disconnect()

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    async def _ensure_voice(self, interaction: discord.Interaction) -> wavelink.Player | None:
        """Must be called after defer(). Connects/moves the player and returns it."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send("Join a voice channel first.", ephemeral=True)
            return None

        channel = interaction.user.voice.channel
        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]

        try:
            if player is None:
                player = await channel.connect(cls=wavelink.Player, deaf=True)
            elif player.channel != channel:
                await player.move_to(channel)
        except (discord.Forbidden, discord.ClientException) as e:
            await interaction.followup.send(f"Couldn't connect to your voice channel: `{e}`", ephemeral=True)
            return None

        player.inactive_timeout = 300  # disconnect after 5 min of silence
        return player

    async def _register_skip_vote(
        self, interaction: discord.Interaction, state: GuildMusicState, player: wavelink.Player
    ) -> tuple[str, bool]:
        if not player.current:
            return "Nothing to skip.", False
        if not interaction.user.voice or player.channel != interaction.user.voice.channel:
            return "You need to be in the voice channel to vote to skip.", False
        if interaction.user.id in state.skip_votes:
            return f"You already voted. {len(state.skip_votes)}/{SKIP_VOTES_REQUIRED} so far.", False

        state.skip_votes.add(interaction.user.id)
        if len(state.skip_votes) >= SKIP_VOTES_REQUIRED:
            await player.skip(force=True)
            return "⏭️ Skipped.", True
        return f"🗳️ Vote registered ({len(state.skip_votes)}/{SKIP_VOTES_REQUIRED}).", False

    async def _resolve_spotify(self, query: str, requester: discord.Member) -> list[wavelink.Playable] | str | None:
        """
        Resolves a Spotify link to a list of Playable tracks.
        Returns:
            list[Playable] on success
            str            on a user-facing error message
            None           if not a Spotify link
        """
        if "open.spotify.com" not in query:
            return None

        # wavelink handles Spotify natively if the Lavalink node has the
        # Spotify source plugin (most public nodes do). Falls back to YouTube
        # search automatically on nodes without it.
        try:
            tracks = await wavelink.Playable.search(query)
        except Exception as e:
            return f"Couldn't resolve that Spotify link: `{e}`"

        if not tracks:
            return "Couldn't find any tracks in that Spotify link."

        # Tag requester on each track
        result = []
        if isinstance(tracks, wavelink.Playlist):
            for t in tracks.tracks:
                t._requester = requester  # type: ignore[attr-defined]
            result = tracks.tracks[:MAX_SPOTIFY_TRACKS]
        else:
            for t in tracks:
                t._requester = requester  # type: ignore[attr-defined]
            result = list(tracks[:MAX_SPOTIFY_TRACKS])

        return result

    # ------------------------------------------------------------------
    # Slash commands
    # ------------------------------------------------------------------

    @app_commands.command(name="play", description="Queue up a song — search by name or drop a link")
    @app_commands.describe(query="Name it or paste a link (YouTube, SoundCloud, or Spotify track/album/playlist)")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        player = await self._ensure_voice(interaction)
        if player is None:
            return

        state = self.get_state(interaction.guild)
        state.text_channel = interaction.channel

        # --- Spotify ---
        if "open.spotify.com" in query:
            result = await self._resolve_spotify(query, interaction.user)
            if isinstance(result, str):
                await interaction.followup.send(result)
                return
            if result is None or len(result) == 0:
                await interaction.followup.send("Couldn't find anything from that Spotify link.")
                return
            await player.queue.put_wait(result)
            if not player.playing:
                await player.play(player.queue.get())
            await interaction.followup.send(
                embed=music_embed(f"🎧 Queued **{len(result)}** track(s) from Spotify.")
            )
            return

        # --- YouTube / SoundCloud / plain search ---
        try:
            tracks = await wavelink.Playable.search(query)
        except Exception as e:
            await interaction.followup.send(f"Search failed: `{e}`")
            return

        if not tracks:
            await interaction.followup.send("Couldn't find anything for that query.")
            return

        if isinstance(tracks, wavelink.Playlist):
            for t in tracks.tracks:
                t._requester = interaction.user  # type: ignore[attr-defined]
            await player.queue.put_wait(tracks.tracks)
            if not player.playing:
                await player.play(player.queue.get())
            await interaction.followup.send(
                embed=music_embed(f"📋 Queued playlist **{tracks.name}** ({len(tracks.tracks)} tracks).")
            )
        else:
            track = tracks[0]
            track._requester = interaction.user  # type: ignore[attr-defined]
            if player.playing or not player.queue.is_empty:
                await player.queue.put_wait(track)
                await interaction.followup.send(
                    embed=music_embed(f"➕ Queued **{track.title}** ({_fmt_duration(track.length)})")
                )
            else:
                await player.play(track)
                await interaction.followup.send(
                    embed=music_embed(f"▶️ Starting **{track.title}**...", discord.Color.green()),
                    ephemeral=True,
                )

    @app_commands.command(name="pause", description="Pause whatever's playing")
    async def pause(self, interaction: discord.Interaction):
        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
        if not player or not player.playing:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        await player.pause(True)
        await interaction.response.send_message(embed=music_embed("⏸️ Paused."))

    @app_commands.command(name="resume", description="Unpause it")
    async def resume(self, interaction: discord.Interaction):
        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
        if not player or not player.paused:
            await interaction.response.send_message("Nothing is paused.", ephemeral=True)
            return
        await player.pause(False)
        await interaction.response.send_message(embed=music_embed("▶️ Resumed."))

    @app_commands.command(name="skip", description="Vote to skip the current song (needs 2 votes)")
    async def skip(self, interaction: discord.Interaction):
        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
        state = self.get_state(interaction.guild)
        if not player:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        msg, skipped = await self._register_skip_vote(interaction, state, player)
        await interaction.response.send_message(
            embed=music_embed(msg) if skipped else msg,
            ephemeral=not skipped,
        )

    @app_commands.command(name="stop", description="Kill the music and wipe the queue")
    async def stop(self, interaction: discord.Interaction):
        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
        state = self.get_state(interaction.guild)
        state.skip_votes.clear()
        state.loop_song = False
        if player:
            player.queue.clear()
            await player.disconnect()
        await interaction.response.send_message(embed=music_embed("⏹️ Stopped and cleared the queue."))

    @app_commands.command(name="leave", description="Kick the bot out of voice")
    async def leave(self, interaction: discord.Interaction):
        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
        if player:
            player.queue.clear()
            await player.disconnect()
        await interaction.response.send_message(embed=music_embed("👋 Disconnected."))

    @app_commands.command(name="queue", description="What's queued up")
    async def queue_(self, interaction: discord.Interaction):
        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
        if not player or (not player.current and player.queue.is_empty):
            await interaction.response.send_message("The queue is empty.")
            return
        await interaction.response.send_message(embed=_build_queue_embed(player))

    @app_commands.command(name="queueremove", description="Remove a song from the queue by its position")
    @app_commands.describe(position="Position shown in /queue — 1 is next up")
    async def queueremove(self, interaction: discord.Interaction, position: app_commands.Range[int, 1, 9999]):
        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
        if not player:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        queue_list = list(player.queue)
        index = position - 1
        if index < 0 or index >= len(queue_list):
            await interaction.response.send_message(
                f"No song at position {position} — the queue only has {len(queue_list)} song(s).",
                ephemeral=True,
            )
            return
        removed = queue_list.pop(index)
        player.queue.clear()
        for t in queue_list:
            player.queue.put(t)
        req = getattr(removed, "_requester", None)
        who = req.mention if req else "Unknown"
        await interaction.response.send_message(
            embed=music_embed(f"🗑️ Removed **{removed.title}** ({who}) from the queue.")
        )

    @app_commands.command(name="nowplaying", description="What's playing right now")
    async def nowplaying(self, interaction: discord.Interaction):
        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
        if not player or not player.current:
            await interaction.response.send_message("Nothing is playing.")
            return
        track = player.current
        req = getattr(track, "_requester", None)
        embed = discord.Embed(
            title="Now Playing",
            description=f"[{track.title}]({track.uri})",
            color=discord.Color.green(),
        )
        embed.add_field(name="Duration", value=_fmt_duration(track.length))
        embed.add_field(name="Requested by", value=req.mention if req else "Autoplay")
        await interaction.response.send_message(embed=embed, view=MusicControlView())

    @app_commands.command(name="volume", description="Adjust the volume, 0-100")
    @app_commands.describe(percent="0-100")
    async def volume(self, interaction: discord.Interaction, percent: app_commands.Range[int, 0, 100]):
        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
        state = self.get_state(interaction.guild)
        state.volume = percent
        if player:
            await player.set_volume(percent * 10)  # wavelink scale: 0-1000
        await interaction.response.send_message(embed=music_embed(f"🔊 Volume set to {percent}%."))

    @app_commands.command(name="loop", description="Repeat the current song on/off")
    async def loop(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild)
        state.loop_song = not state.loop_song
        await interaction.response.send_message(
            embed=music_embed(f"🔁 Looping is now **{'on' if state.loop_song else 'off'}**.")
        )

    @app_commands.command(name="autoplay", description="Toggle auto-playing related songs when queue runs out")
    async def autoplay(self, interaction: discord.Interaction):
        player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
        state = self.get_state(interaction.guild)
        state.autoplay = not state.autoplay
        if player:
            player.autoplay = wavelink.AutoPlayMode.enabled if state.autoplay else wavelink.AutoPlayMode.disabled
        await interaction.response.send_message(
            embed=music_embed(f"🔀 Autoplay is now **{'on' if state.autoplay else 'off'}**.")
        )

    # ------------------------------------------------------------------
    # Error handler
    # ------------------------------------------------------------------

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        message = f"Something went wrong: `{error}`"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
