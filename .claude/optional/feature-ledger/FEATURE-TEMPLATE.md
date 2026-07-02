# Feature ledger — <TICKET or slice id>

Filesystem-only regression-catch record (no gbrain). Live copies go in
`.docs/po/features/<id>.md`. The `product-owner` agent reads these before `/plan`
and `/code-review` to flag regressions; append to it after a slice lands.

## Invariants (must stay true)
- <e.g. "an order can only be fulfilled once — `state` guards double-dispatch">

## Shipped behaviour
- <user-visible field / button / flow this feature introduced>

## Known edge cases / gotchas
- <the thing that will break if a future refactor is careless>

## Change history
- <YYYY-MM-DD> <slice id> — <what changed>
