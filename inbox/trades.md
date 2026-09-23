# Trade log
#
# Add one trade per line, then commit. The next run applies it and clears the line.
# Lines starting with # are ignored.
#
# Accepted (case-insensitive):
#   buy NVO 80 usd        spent $80 on NVO
#   buy NVO 2 @ 38.40     bought 2 shares at $38.40
#   sell UBER 100 usd     sold $100 worth
#   sell UBER all         closed the position
#   deposit 50 usd
#   withdraw 50 usd
#
# Optional extras anywhere on the line: a date (2026-09-24), a fee (fee 0.35).
# Unsure of the exact fill price? Use the usd form — the dollar amount is what
# the books actually need.
