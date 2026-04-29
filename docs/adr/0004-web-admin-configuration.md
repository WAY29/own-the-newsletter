# Web Admin Configuration

The first version uses a web admin panel as the source of truth for IMAP accounts, recipient filters, and feed rules, while the configuration file only keeps startup-level settings and the administrator token. This is a deliberate break from static feed configuration because the product needs approachable personal administration, but it requires a protected admin surface and local persistence for settings that were previously imagined as config-file entries.
