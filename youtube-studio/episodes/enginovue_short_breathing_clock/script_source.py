"""Short: "The Clocks of Paris That Breathed" (links to enginovue_paris_air_clocks).

Facts: ../enginovue_paris_air_clocks/research/02_mechanics.md and factcheck_report.md (La Nature 1880,
Nature 1880, Berly 1881). Narration is written for this Short; it does not reuse the long video's sentences.
Run:  python script_source.py   -> frames.txt
"""

from studio.pipeline.scriptgen import Script

s = Script(__file__, "The Clocks of Paris That Breathed")

s.shot("B", "close", "h", "-", "Часы на стене парижской квартиры, трубка уходит в стену",
       "In 1880s Paris, thousands of clocks could not keep time on their own.",
       "An elegant wooden wall clock with a white dial hangs on a papered wall of a Parisian apartment in the 1880s; "
       "a thin dark rubber tube runs from the bottom of its case down into the wall. Warm lamp light.",
       CHAPTER="The clocks that breathed", AMB="a_clock_room", MUSIC="m2_invention",
       SFX="clock_tick @0 -8dB max=3")
s.shot("B", "macro", "h", "-", "Трубка у часов, в ней светится струйка воздуха",
       "Once a minute, they breathed.",
       "Close view of the thin rubber tube entering the bottom of the wooden clock case; a soft turquoise glow of "
       "air travels up inside the tube.",
       SFX="air_hiss @0.3 -8dB max=2")
s.shot("A", "cutaway", "h", "-", "Разрез стены: тонкая свинцовая труба поднимается к часам",
       "A puff of compressed air came up a thin lead pipe.",
       "Cutaway of an apartment wall: inside the wall a thin grey lead pipe rises from the floor up to a wall clock "
       "hanging above; a turquoise puff of air moves up the pipe.")
s.shot("A", "cutaway", "h", "-", "Открытый корпус часов: внизу резиновый мех",
       "It inflated a small rubber bellows.",
       "Cutaway of the back of a wall clock with the case opened: at the bottom a small round concertina-shaped "
       "rubber bellows, swelling with air, connected to the thin tube; brass parts above it.",
       SFX="bellows_puff @0.2 -6dB")
s.shot("A", "cutaway", "h", "-", "Мех поднимает латунный рычаг",
       "The bellows lifted a lever.",
       "Cutaway of the clock mechanism: the swollen rubber bellows at the bottom pushes up a long thin brass lever "
       "that pivots on the axle of a toothed brass wheel above.",
       ANIM="the rubber bellows swells and lifts the brass lever a short way, then holds || static camera || "
            "clock case and wheel stay still")
s.shot("A", "macro", "h", "60 teeth", "Собачка толкает колесо с 60 зубцами на один зуб",
       "A hooked pawl on the lever nudged a sixty-tooth wheel ahead by one tooth.",
       "Macro view of a brass ratchet wheel with sixty fine teeth and a small hooked pawl on the end of a brass "
       "lever pushing one tooth; a second small catch rests on the wheel to stop it slipping back.",
       SFX="ratchet_click @0.6 -6dB")
s.shot("A", "macro", "h", "-", "Упоры ограничивают ход рычага",
       "Stops limited its swing: one puff, exactly one minute.",
       "Macro view of the brass lever between two small brass stop pins that limit its travel, the toothed wheel "
       "behind it, clean light background.")
s.shot("B", "close", "h", "1 puff = 1 minute", "Циферблат: минутная стрелка сдвинулась на деление",
       "Sixty puffs, one turn of the minute hand.",
       "Close view of a round white clock dial with black Roman numerals and black hands, the minute hand just "
       "stepped forward one minute mark, a small turquoise glow at its tip.",
       SFX="ratchet_click @0.1 -10dB")
s.shot("A", "cutaway", "h", "-", "Воздух выпущен: мех опал, рычаг опустился",
       "Then the air was let out, and the lever dropped back to wait.",
       "Cutaway of the clock mechanism: the rubber bellows at the bottom is flat and empty, the brass lever has "
       "dropped down to rest, the toothed wheel above stays in place.",
       SFX="air_hiss @0.3 -12dB max=1.5")
s.shot("B", "cutaway", "h", "-", "Разрез улицы: железная труба в канализации, бежит импульс",
       "Every breath came from one central station, through iron mains in the sewers.",
       "Cutaway of a Paris street in the 1880s: above, cobbles and a lamp post with a round clock; below, an arched "
       "stone sewer tunnel with an iron pipe fixed along its wall, a turquoise pulse travelling along the pipe.",
       ANIM="a turquoise pulse travels along the iron pipe in the sewer, water ripples in the channel || slow "
            "tilt down from the street to the sewer || street, tunnel and pipe stay still",
       AMB="a_sewer", SFX="air_hiss @0.4 -10dB")
s.shot("A", "wide", "h", "4,000+ clocks · late 1881", "Фасад парижского дома, в окнах одинаковые часы",
       "By late 1881, more than four thousand clocks in central Paris ran on air.",
       "A tall Haussmann apartment building in Paris at dusk seen from the street, many windows lit warmly, in "
       "each window a small round clock dial showing the same time.",
       AMB="a_street_1880")
s.shot("B", "medium", "h", "-", "Ночь, дождь, часы на фонаре стоят",
       "Until one night in 1910, when a flood stopped them all. That story is on our channel.",
       "Night street in Paris in 1910 in steady rain, a cast-iron lamp post carrying a round clock dial whose hands "
       "stand still at about ten to eleven, rain water covering the cobbles below, warm gas light.",
       FX="rain", AMB="a_flood_night", SFX="clock_tick @0 -10dB max=1.5")

if __name__ == "__main__":
    s.write()
