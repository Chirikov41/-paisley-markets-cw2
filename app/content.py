"""Static copy about the fictional market, kept in one place for templates."""

MARKET = {
    "name": "Paisley Christmas Markets",
    "year": 2026,
    "tagline": "Two winter weekends of makers, food and light in the heart of Paisley.",
    "location": "Abbey Close and Paisley Town Hall",
    "address": "Abbey Close, Paisley PA1 1JG",
    "weekends": [
        {"slug": "weekend-1", "label": "Weekend one", "dates": "Fri 27 - Sun 29 November 2026",
         "note": "Light switch-on, choir stage and the opening parade."},
        {"slug": "weekend-2", "label": "Weekend two", "dates": "Fri 4 - Sun 6 December 2026",
         "note": "Craft workshops, Santa's grotto and late-night shopping until 8pm."},
    ],
    "opening_hours": [
        ("Friday", "12:00 - 20:00"),
        ("Saturday", "10:00 - 20:00"),
        ("Sunday", "10:00 - 18:00"),
    ],
    "entry": "Free entry, no ticket required",
    "contact_email": "markets@paisley-christmas.example",
    "contact_phone": "0141 000 0000",
}

STALL_TYPES = [
    ("standard", "Standard pitch (3m x 3m)", "Timber hut with a counter and a 13A socket."),
    ("corner", "Corner pitch (3m x 3m, two open sides)", "Best for displays that wrap around."),
    ("food", "Food pitch (5m frontage)", "Includes extraction points and a gas safety check."),
    ("workshop", "Workshop space (marquee)", "Shared indoor space for drop-in activities."),
]

PREFERRED_DAYS = [
    ("weekend-1", "Weekend one (27-29 Nov)"),
    ("weekend-2", "Weekend two (4-6 Dec)"),
]
