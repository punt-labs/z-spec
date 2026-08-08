# Vox (text-to-speech)

Vox speaks for you. It exposes the `mic` MCP server, a set of `/` slash
commands, and Claude Code hooks that chime or narrate as a session runs.
This doc is how an *agent* drives vox — not how to develop vox itself.

**Pick your surface.** If the `mic` MCP tools are available (the vox plugin is
installed), use them — the MCP/slash section below. Otherwise — a CLI-only
install (`vox` on `PATH`, no plugin) — drive vox through the `vox` command line,
documented in the CLI section at the end. Both reach the same engine. The MCP
`mic:unmute` (you flipping your own mic on) and the CLI `vox say` (a discrete
invocation) are two doors to one synthesizer, not a contradiction.

Never `Read`, `Write`, or `Bash` the config files
`.punt-labs/vox/vox.md` or `.punt-labs/vox/vox.local.md`. All state is
reachable through the `mic` tools (or the `vox` CLI); touching the files
directly races the daemon.

## Enabling vox in a repo

Vox is per-repo: it chimes and narrates only where a human ran `enable` and
committed the `.punt-labs/vox/enabled` marker.

- `mic:enablement action="enable"` (or `/vox enable`) — turn vox on for this repo:
  deposit the guide, write the marker, add the `@`-import, register settings.
  Idempotent; re-running upgrades the deposited guide.
- `mic:enablement action="disable"` (or `/vox disable`) — turn it off: remove the
  import, marker, and settings. The `.punt-labs/vox/` subtree is left dormant.
- CLI equivalent: `vox enable` / `vox disable` (`vox disable --purge` also
  removes the subtree). Neither surface runs git — commit the marker via a PR.

## Speaking

- `mic:unmute` — synthesize and play text. Pass `text` (or a `segments`
  list for multi-voice). Mood tags are resolved from config; do not pass
  `vibe_tags` yourself unless the user asked for a specific delivery.
- `mic:speak` — toggle spoken notifications: `mode="y"` (voice) or
  `mode="n"` (chimes only).
- `mic:notify` — set the notification level: `"y"` (on task completion +
  permission prompts), `"n"` (off), `"c"` (continuous — also announces
  real-time signals).
- `mic:who` — list voices for the current provider (featured + full roster).
- `mic:status` — current provider, voice, notify/vibe state, and the
  authoritative music Program (read fresh from the daemon).

## Vibe (voice direction)

`mic:vibe` sets the session mood. You are the voice director: translate a
mood into 1–3 ElevenLabs expressive tags (`[frustrated]`, `[excited]`,
`[weary]`, `[sighs]`). `mode="manual"` pins your tags; `mode="auto"`
(default) lets tags update from session signals at each task completion;
`mode="off"` is neutral.

## Recordings

The daemon owns a recordings store; you address a recording by its bare store
id, never a path. One `mic:rec` tool takes a `subcommand`:

- `mic:rec subcommand="new"` — synthesize `text` into the store; returns the bare id.
- `mic:rec subcommand="list"` — list the stored recordings.
- `mic:rec subcommand="play"` — play a stored recording (by id) on the daemon host.
- `mic:rec subcommand="get"` — return a recording's bytes (base64) by id.
- `mic:rec subcommand="remove"` — delete a recording by id.

## Music

One `mic:music` tool takes a `subcommand`. **You author the prompts** — vox is
a pipe to ElevenLabs, it does not decide what a genre sounds like. On
`subcommand="on"` (and on every style/vibe change) write a `base_prompt` plus
exactly 12 genre-accurate `variations`, one per pool slot, and pass a human
`title` — a short album name coherent with the music, which becomes the album's
`name` and rides the ID3 `TALB`/`TIT2` frames (absent, voxd falls back to a
`{vibe}-{style}-{date}` slug).

- `mic:music subcommand="on"` — start or re-pool the background program from your
  `base_prompt` + 12 `variations`, with an optional `title`.
- `mic:music subcommand="stop"` — stop the program.
- `mic:music subcommand="play"` — replay a saved album (by id/name/tags) from
  disk; no generation, no credits. With no argument, replays the last-played
  album, or errors and lists the catalog when nothing has played yet.
- `mic:music subcommand="next"` — optional manual skip (playback auto-advances).
- `mic:music subcommand="prev"` — step to the previous part of the now-playing album.
- `mic:music subcommand="pause"` — suspend the current album in place.
- `mic:music subcommand="resume"` — resume the suspended album in place.
- `mic:music subcommand="list"` — list saved albums.
- `mic:music subcommand="status"` — current music state.

Guidance:

- Vary *within* the genre (form, tempo, mode, lead instrument, mood) — never
  drift to genre-alien instruments.
- **Never name an artist, band, composer, or copyrighted work.** ElevenLabs
  rejects those (`bad_prompt`) — describe the music itself instead.
- Music needs an ElevenLabs paid plan (~2,000 credits per ~3-minute track).
- Control actions produce no agent text: `on`, `stop`, `next`, `prev`, `pause`,
  and `resume` are fire-and-forget. Only `status` and `list` return data to report.

Catalog verbs (address a saved album by the id `list` prints):

- `mic:music subcommand="new"` — generate ONE track from a finished, verbatim
  prompt into a fresh single-track catalog album. It does not disturb the running program.
- `mic:music subcommand="get"` — export a saved album by id into a destination
  directory you name (`dest`); returns the written path/locator.
- `mic:music subcommand="remove"` — delete a saved album by id (refused while it is playing).

## Slash commands

- `/vox enable` — turn vox on for this repo; `/vox disable` — turn it off.
- `/vox model <name>` / `/vox provider <name>` — switch TTS engine mid-session.
- `/unmute [voice]` — enable voice mode, optionally set the session voice;
  `/unmute` (no argument) browses the roster.
- `/mute` — chimes only (spoken notifications off).
- `/vibe <mood>|auto|off` — set session mood.
- `/music on|stop|next|prev|pause|resume|play [<name>]|list|status` — background music.
- `/recap` — speak a 2–3 point summary of your last response.

## Driving vox from the CLI (no plugin)

When the `mic` tools are absent — a `--no-plugin` install — reach the same
engine by shelling out to the `vox` command. This section is always present, so
a plugin-less agent can drive vox with no MCP surface at all.

- `vox say "text"` — synthesize and play (the CLI counterpart to `mic:unmute`;
  a discrete invocation, not a session mic). `--voice`, `--provider`, and
  `--rate` refine it; text can also arrive on stdin.
- `vox notify normal|continuous` — set the per-repo notification level (normal is
  task-completion + permission prompts; continuous also announces signals).
- `vox voice <name>` — set the session voice; `vox voices` — list the roster.
- `vox vibe <mood>|auto|off` — set the session mood (same director role as
  `mic:vibe`).
- `vox music on|stop|next|prev|pause|resume|play [<name>]|list|status` — background music.
- `vox status` — current provider, voice, notify/vibe state.
- `vox enable` / `vox disable` — per-repo enablement, the CLI door to the marker.

Voice supplements text — it never replaces it. Whichever surface you use, show
your summary in the conversation as well as speaking it.

## Stop-hook continuation

When a Stop hook blocks with a `♪` phrase, write 1–2 sentences summarizing
what you just completed, then call `mic:unmute` with `ephemeral=true` (or, with
no plugin, `vox say`). Mood tags are already resolved in config — do not pass
`vibe_tags`. Emit no other output; the audio panel confirms.
