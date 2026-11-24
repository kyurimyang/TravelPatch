// Switches for finished features that are deliberately not shown yet.

/** The way between two places ("대중교통 약 20분") on the patch cards.
 *  OFF until the times are real: the server only has estimates while Google's matrix method is
 *  unavailable (no billing account, decision 2026-11-25), and an estimate must not be shown as
 *  "the time it takes". To turn on: set this to true AND set ROUTES_TRAVEL_ENABLED=1 on the
 *  server (see backend/app/services/routes_client.py). */
export const SHOW_LEG_CHIPS = false
