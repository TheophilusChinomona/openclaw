# Pruned Extensions

Channel extensions removed from this fork because they are not used in our deployment.
The `upstream-resolve` skill reads this file to auto-keep deletions during upstream merges.

To restore any extension from upstream:
```bash
git checkout upstream/main -- extensions/<name>
```

## Removed

signal, line, slack, irc, mattermost, nextcloud-talk, imessage,
bluebubbles, synology-chat, zalo, zalouser, feishu, googlechat,
matrix, msteams, nostr, tlon, twitch

## Kept

whatsapp, telegram, discord, paperclip-orchestration
