"""Short: "The Night the Air Clocks of Paris Stopped" (links to enginovue_paris_air_clocks).

Facts: ../enginovue_paris_air_clocks/research/04_flood_1910.md and factcheck_report.md (Le Petit Parisien
23 Jan 1910, SUDAC history, DRIEAT 1910 bulletins, Archives de Paris). Narration is written for this Short;
it does not reuse the long video's sentences.
Run:  python script_source.py   -> frames.txt
"""

from studio.pipeline.scriptgen import Script

s = Script(__file__, "The Night the Air Clocks of Paris Stopped")

s.shot("B", "medium", "h", "21 Jan 1910", "Ночь, дождь, часы на фонаре",
       "Friday night, January 1910. Within minutes, the clocks of central Paris stopped.",
       "Night street in Paris in 1910 in steady rain, wet cobblestones reflecting warm gas lamps; a cast-iron lamp "
       "post carries a round white clock dial with black hands at about ten to eleven; stone buildings behind.",
       CHAPTER="The night the clocks stopped", FX="rain", AMB="a_flood_night", MUSIC="m1_night",
       SFX="clock_tick @0 -8dB max=2.5")
s.shot("B", "close", "h", "-", "Обычные часы в квартире идут, пневматические стоят",
       "Not the ordinary ones. Only the clocks that ran on air.",
       "A dim Parisian apartment at night: on the left a mantel clock with a swinging pendulum, on the right a wall "
       "clock with a thin rubber tube running from its case into the wall, its hands stopped. A candle on a table.",
       FX="lamp")
s.shot("B", "cutaway", "h", "-", "Разрез улицы: труба в канализации",
       "For nearly thirty years, a puff of compressed air had pushed their hands forward every minute.",
       "Cutaway of a Paris street at night: above, cobbles and a lamp post with a clock; below, an arched stone "
       "sewer tunnel with an iron pipe along its wall, a turquoise pulse of air travelling along it.",
       AMB="a_sewer", SFX="air_hiss @0.5 -8dB")
s.shot("B", "wide", "h", "quai de la Gare", "Станция сжатого воздуха на берегу Сены",
       "All that air came from one plant on the quai de la Gare, right on the Seine.",
       "A large 19th-century iron-and-glass industrial hall with brick walls, arched windows and a tall brick chimney on a stone quay "
       "beside the river Seine at night, warm light inside, dark water close below the quay wall.",
       AMB="a_machine_room", SFX="compressor @0 -10dB max=3")
s.shot("B", "wide", "h", "~1 m a day", "Сена поднимается у набережной",
       "And the river was rising, about a metre a day.",
       "Night view of the swollen brown river Seine in Paris lapping high against a stone quay wall, a stone bridge "
       "behind with gas lamps, rain falling.",
       ANIM="brown river water rises slowly against the stone quay, rain falls, lamp light shimmers on the water || "
            "static camera || bridge and quay stay still",
       FX="rain", AMB="a_flood_night", SFX="water_drip @0 -10dB max=3")
s.shot("B", "dynamic", "h", "-", "Вода врывается в машинный зал",
       "That evening, the water got into the plant.",
       "Dramatic low angle inside a 19th-century machine hall at night: muddy river water pours in through an "
       "arched doorway and spreads across the floor around large compressors and flywheels, lamps reflected.",
       SFX="water_rush @0 -6dB")
s.shot("B", "close", "h", "-", "Стрелка манометра падает",
       "No compressors, no pressure.",
       "Close view of a large brass pressure gauge on an iron pipe, the needle dropping toward zero, water droplets "
       "on the glass, dark flooded machine hall behind.",
       CAMERA="snap", SFX="boom @0 -8dB")
s.shot("B", "close", "h", "10:48 – 10:53 pm", "Циферблат на фонаре: стрелки замерли",
       "Between ten forty-eight and ten fifty-three that night, the hands froze.",
       "Close view of a round lamp-post clock dial at night in the rain, the hands stopped at about ten to eleven, "
       "rain drops running down the glass, warm gas light around it.",
       FX="rain", SFX="clock_tick @0 -10dB max=1")
s.shot("B", "wide", "h", "8.62 m · 28 Jan", "Затопленная улица, люди в лодках",
       "The Seine kept climbing for a week, and some twenty thousand buildings flooded.",
       "A flooded Paris street in January 1910 by day under a grey sky: stone buildings with water up to the "
       "ground floor windows, people in a small rowing boat and on a raised wooden walkway.",
       AMB="a_flood_night", SFX="oars @0.3 -8dB")
s.shot("A", "medium", "h", "13 days", "Мастер заново запускает уличные часы",
       "The air came back on the third of February, after thirteen days of silence.",
       "A winter morning in Paris in 1910: a clock repairman on a wooden ladder sets the hands of a cast-iron "
       "street clock, wet cobbles below, a few passers-by in coats.",
       ANIM="the repairman turns the clock hands with his hand, breath steam in the cold air || slow push-in "
            "toward the clock || ladder, buildings and passers-by stay still",
       AMB="a_street_1880", SFX="ratchet_click @1 -8dB")
s.shot("B", "wide", "h", "-", "Ночной Париж, по трубам снова бежит пульс",
       "How a city ran its clocks on air is on our channel.",
       "Night view over Paris rooftops in the 1900s with a soft turquoise pulse spreading through the streets from "
       "one glowing building by the river, warm windows, the Seine with lit bridges.",
       AMB="a_street_1880")

if __name__ == "__main__":
    s.write()
