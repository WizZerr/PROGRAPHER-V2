from __future__ import annotations

# CLIP performs better with natural English prompts.
# The API returns Hebrew labels.
PROMPT_GROUPS = {
    "scene": [
        ("wedding_ceremony", "טקס חתונה", "a professional photograph of a wedding ceremony"),
        ("wedding_reception", "קבלת פנים או אולם חתונה", "a professional photograph at a wedding reception hall"),
        ("dance_floor", "רחבת ריקודים", "a professional event photograph on a crowded dance floor"),
        ("couple_portrait", "פורטרט זוגי", "a professional portrait photograph of a couple"),
        ("single_portrait", "פורטרט יחיד", "a professional portrait photograph of one person"),
        ("group_photo", "צילום קבוצתי", "a professional posed group photograph at an event"),
        ("outdoor_event", "אירוע בחוץ", "a professional event photograph outdoors"),
        ("indoor_event", "אירוע בתוך אולם", "a professional event photograph indoors"),
        ("detail_shot", "צילום פרטים", "a professional close detail photograph of event decoration rings flowers food or objects"),
        ("night_event", "אירוע לילה", "a professional event photograph at night"),
    ],
    "lighting": [
        ("natural_daylight", "אור יום טבעי", "a photograph lit mainly by natural daylight"),
        ("golden_hour", "שעת זהב", "a photograph lit by warm golden hour sunlight"),
        ("overcast", "אור רך ומעונן", "a photograph in soft overcast daylight"),
        ("flash", "פלאש דומיננטי", "a photograph lit mainly by camera flash"),
        ("warm_tungsten", "תאורה חמה", "a photograph under warm tungsten indoor lighting"),
        ("mixed_light", "תאורה מעורבת", "a photograph with mixed daylight and artificial lighting"),
        ("colored_led", "תאורת LED צבעונית", "a photograph under colorful blue purple red or green LED event lighting"),
        ("backlight", "תאורה אחורית", "a strongly backlit photograph"),
        ("low_light", "תאורה חלשה", "a photograph in very low light or darkness"),
        ("balanced_light", "תאורה מאוזנת", "a photograph with clean balanced professional lighting"),
    ],
    "people": [
        ("no_people", "ללא אנשים", "a photograph with no people visible"),
        ("one_person", "אדם אחד", "a photograph of one person"),
        ("couple", "שני אנשים", "a photograph of exactly two people"),
        ("small_group", "קבוצה קטנה", "a photograph of a small group of three to eight people"),
        ("crowd", "קהל", "a photograph of a large crowd of people"),
    ],
    "framing": [
        ("close_up", "קלוז אפ", "a close up portrait photograph"),
        ("half_body", "חצי גוף", "a half body portrait photograph"),
        ("full_body", "גוף מלא", "a full body portrait photograph"),
        ("wide", "פריים רחב", "a wide environmental event photograph"),
        ("detail", "פריים פרטים", "a tight detail photograph of an object"),
    ],
    "technical": [
        ("soft_balanced", "אור רך ומאוזן", "a technically clean photograph with soft balanced light"),
        ("strong_backlight", "Backlight חזק", "a photograph with strong backlight and dark foreground subjects"),
        ("high_dynamic_range", "טווח דינמי גבוה", "a photograph with very bright highlights and very dark shadows"),
        ("low_light_noise", "סיכון לרעש בתאורה חלשה", "a dark low light photograph likely to contain high ISO noise"),
        ("warm_cast", "נטייה חמה", "a photograph with a strong warm orange yellow color cast"),
        ("cool_cast", "נטייה קרה", "a photograph with a strong cool blue color cast"),
        ("mixed_color_cast", "צבעי תאורה מעורבים", "a photograph with mixed competing color casts on people"),
        ("harsh_flash", "פלאש קשיח", "a photograph with harsh direct flash and strong facial highlights"),
        ("colored_skin_light", "תאורה צבעונית על עור", "a photograph where colored event lighting strongly affects skin tones"),
    ],
}
