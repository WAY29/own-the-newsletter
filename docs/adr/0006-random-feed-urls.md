# Random Feed URLs

RSS feeds are accessed through unguessable random URLs without an additional token parameter or authenticated session because many feed readers handle plain URLs more reliably than browser-style authentication. The random URL is therefore the access barrier, so feed identifiers must be high entropy, feeds must not be publicly indexed, and operational logs should avoid exposing full feed URLs.
