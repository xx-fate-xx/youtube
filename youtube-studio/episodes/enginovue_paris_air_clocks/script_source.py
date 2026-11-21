"""Script + storyboard source for "The Air-Powered Clocks of Paris" -> frames.txt.

Edit the SHOTS table, then run:  python script_source.py   (writes frames.txt with timecodes estimated
from word counts at WPS words per second; the narration later re-times every shot exactly).
Facts and sources: research/*.md and factcheck_report.md.
"""

from __future__ import annotations

import re
from pathlib import Path

WPS = 2.55
MIN_S = 2

# (mode, shot, era, title, RU, VO, SCENE, extra lines)
S = []


def shot(mode, kind, era, title, ru, vo, scene, **extra):
    S.append((mode, kind, era, title, ru, vo, scene, extra))


# ---------------------------------------------------------------- 1. The night the clocks stopped
shot("B", "medium", "h", "21 Jan 1910", "Ночь, уличные часы на фонаре под дождём",
     "On the night of Friday, the 21st of January 1910, the clocks of Paris began to stop.",
     "Night street in Paris in 1910, steady rain, wet cobblestones reflecting warm gas lamps. In the centre a cast-iron street lamp post carries a round white clock dial with black hands near eleven o'clock; Haussmann stone buildings behind, dark windows.",
     ANIM="rain falls steadily, the gas flame flickers, the minute hand twitches once and then stays still || very slow push-in toward the clock dial || buildings and lamp post stay still",
     CHAPTER="The night the clocks stopped", AMB="a_flood_night", MUSIC="m1_night", FX="rain",
     SFX="clock_tick @0.2 -8dB max=3")
shot("B", "close", "h", "-", "Часы в квартире, стрелки замерли",
     "Not all of them. Only the ones that breathed.",
     "Close view of an elegant wall clock in a dim Parisian apartment at night, a thin flexible tube running from the bottom of its wooden case down into the wall; a candle on a side table.",
     FX="lamp", SFX="air_hiss @0.4 -10dB max=2")
shot("B", "wide", "h", "between 10:48 and 10:53", "Бульвар ночью, общественные часы встали",
     "Between ten forty-eight and ten fifty-three that evening, every pneumatic clock in the city stood still,",
     "Wide view of a Paris boulevard at night in the rain, a tall cast-iron public clock column in the foreground with its round dial lit by gas lamps, a few late passers-by with umbrellas looking up at it.",
     AMB="a_street_1880")
shot("A", "medium", "h", "-", "Холл отеля и гостиная с такими же часами",
     "on lamp posts, in hotel lobbies, in offices and in private apartments.",
     "Split composition: on the left a lavish 1900s hotel lobby with a wall clock above the reception desk, on the right a cosy bourgeois living room with a mantel clock; both clocks show the same time.")
shot("B", "cutaway", "h", "-", "Разрез: труба в канализации под улицей",
     "For nearly thirty years their hands had been moved by puffs of compressed air,",
     "Cutaway of a Paris street at night: above, cobbles and a lamp post with a clock; below, an arched stone sewer tunnel with a thin iron pipe fixed along its wall, a faint turquoise glow pulsing along the pipe.",
     ANIM="a turquoise glow travels along the pipe in the sewer, water ripples in the channel || slow tilt down from the street to the sewer || street, tunnel and pipe stay still",
     AMB="a_sewer", SFX="air_hiss @0.5 -8dB")
shot("B", "wide", "h", "-", "Машинный зал станции сжатого воздуха",
     "sent through pipes under the streets from one central plant.",
     "Wide view of a 19th-century machine room with large green steam engines and air compressors, polished brass gauges, belts and flywheels, warm lamp light, one worker in overalls small in the scene.",
     AMB="a_machine_room", SFX="steam_engine @0 -10dB max=4")
shot("B", "dynamic", "h", "quai de la Gare", "Вода заливает станцию на набережной",
     "That night, the flooded river Seine had reached the air plant on the quai de la Gare.",
     "Dramatic low angle at night: brown river water pouring through the arched doorway of a large brick industrial hall on a Paris riverbank, a tall brick chimney behind, lamps reflected in the rising water.",
     AMB="a_flood_night", SFX="water_rush @0 -6dB")
shot("B", "close", "h", "-", "Стрелка манометра падает к нулю",
     "No air, no time.",
     "Close-up of a large brass pressure gauge on a pipe, the needle near zero, water droplets on the glass, dark machine room behind.",
     CAMERA="snap", SFX="boom @0 -8dB")
shot("A", "medium", "h", "-", "Мастерская с воздушным мотором",
     "But the clocks were only the beginning.",
     "A small 1890s Paris workshop: a compact air motor on the floor connected by a leather belt to a lathe, a craftsman in an apron at work, a thin air pipe coming down the wall.",
     AMB="a_workshop", SFX="lathe @0.3 -12dB max=3")
shot("A", "wide", "-", "1880 → 1994", "Схема: трубы растут от станции по всему городу",
     "The same company went on to build a far bigger network that carried power to thousands of customers, and it kept running until 1994.",
     "Stylised map-like view of Paris seen from above at dusk, the Seine as a curving band, glowing turquoise pipelines spreading outward from the centre like the branches of a tree, small icons of workshops and lifts at their ends.",
     ANIM="turquoise lines grow outward from the centre and branch across the city || slow pull-back over the city || the river and city blocks stay still",
     AMB="-", SFX="data_whoosh @0.5 -12dB")

# ---------------------------------------------------------------- 2. A city of many times
shot("A", "close", "h", "-", "Механизм часов, маятник",
     "Every mechanical clock drifts. A few seconds a day turn into minutes within a month.",
     "Close-up of the open brass movement of a 19th-century pendulum clock, gears and escapement, the pendulum bob swinging, on a clean pale background.",
     CHAPTER="One time for a whole city", AMB="a_clock_room", MUSIC="m2_invention -1dB", SFX="clock_tick @0 -10dB")
shot("A", "medium", "h", "-", "Часовщик подводит уличные часы с лестницы",
     "Each one had to be checked and set by hand.",
     "A clockmaker in a long coat standing on a wooden ladder against a Paris lamp post, opening the glass of a street clock to move its hands, a pocket watch in his other hand.",
     AMB="a_street_1880")
shot("A", "wide", "h", "-", "Поезд и телеграфные столбы",
     "Railways and the telegraph made those minutes matter.",
     "Wide view of a 19th-century steam train crossing a French countryside, a line of telegraph poles and wires running alongside, small station building in the distance.",
     SFX="locomotive @0.3 -12dB max=4")
shot("A", "infographic", "-", "-", "Одни главные часы и много подчинённых",
     "Cities wanted one shared time, kept by one master clock and copied everywhere else.",
     "Clean infographic: one large master clock in the centre with thin lines radiating to many smaller clock dials arranged around it in a circle, plain pale background, generous empty space.",
     AMB="-")
shot("A", "medium", "h", "-", "Вена, улица 1870-х",
     "Electric time signals already existed. But in Vienna, a different idea was tried: air.",
     "A Vienna street in the 1870s with ornate stone buildings and a horse-drawn tram, a slender street clock on a post in the foreground, soft daylight.",
     ANIM="the tram rolls slowly past, pedestrians walk, the clock hand moves one step || gentle pan from left to right || buildings and clock post stay still",
     AMB="a_street_1880", SFX="horse_carriage @0 -12dB max=3")
shot("A", "close", "h", "-", "Чертёж патента: часы и трубка",
     "A Viennese telegraph engineer, Carl Albert Mayrhofer, patented clocks driven by pulses of air.",
     "Close view of a 19th-century technical drawing on cream paper pinned to a drafting table: a clock case with a small bellows inside and a pipe below, drawn in ink with compass and ruler beside it; no readable text.",
     SFX="quill @0 -12dB max=3")
shot("A", "medium", "h", "Vienna · Feb 1877", "Монтаж первых уличных часов в Вене",
     "With Victor Popp and the clockmaker Ernst Resch, the system went into service in Vienna in February 1877.",
     "Three workmen in 1870s clothes installing a street clock on a post in a Vienna square, one on a ladder, another holding a coil of thin pipe, a gentleman in a top hat supervising from a distance.",
     TITLE="Vienna | Feb 1877")
shot("A", "wide", "h", "-", "Три уличных часа одновременно переходят",
     "Street clocks fed by a pipe all moved forward together: at first every two minutes, later every minute.",
     "Wide view of a Vienna street with three street clocks on posts at different distances, all showing the same time, light snow on the pavements.",
     AMB="-")
shot("A", "medium", "h", "~3½ years", "Чиновники качают головами",
     "Vienna was not convinced. After about three and a half years, the clocks were judged too inaccurate.",
     "Three city officials in dark frock coats around a table in a Vienna council room, one shaking his head while pointing at a pocket watch, papers on the table.",
     AMB="a_quiet_room")
shot("A", "wide", "h", "-", "Поезд въезжает в Париж",
     "Popp took the idea to Paris.",
     "Wide view of a steam train arriving under the iron-and-glass roof of a Paris station in the late 1870s, steam clouds, porters with trolleys.",
     ANIM="steam billows, the train slows to a stop, porters walk || slow push-in toward the train || station roof stays still",
     AMB="a_street_1880", SFX="steam_engine @0.2 -12dB max=3")

# ---------------------------------------------------------------- 3. Paris says yes
shot("A", "wide", "h", "1878", "Всемирная выставка 1878 года",
     "At the 1878 World's Fair in Paris, the air clocks won a silver medal.",
     "Wide view of the 1878 Paris Exposition Universelle: the great iron-and-glass exhibition hall, crowds in 1870s clothes, flags; in the foreground a display stand with a clock and pipes behind a velvet rope.",
     CHAPTER="Paris says yes", AMB="a_crowd", SFX="crowd_murmur @0 -14dB max=4")
shot("A", "cutaway", "h", "-", "Разрез: рабочие кладут трубу в канализации",
     "That November, the city allowed a trial: pipes laid in the sewers, and clocks on street lamps.",
     "Cutaway: workers with lanterns fixing a thin iron pipe along the wall of a stone sewer tunnel, while above ground a lamp post with a small clock dial is being fitted.",
     AMB="a_sewer", SFX="metal_clank @0.5 -12dB max=2")
shot("A", "medium", "h", "15 Mar 1880", "Торжественный запуск, первые часы на улице",
     "On the 15th of March 1880, the public service opened.",
     "A small crowd of Parisians in 1880 clothes gathered around a new lamp-post clock on a boulevard, a gentleman checking his pocket watch against it, spring morning light.",
     AMB="a_street_1880")
shot("A", "wide", "h", "7 rue Sainte-Anne", "Здание станции в центре Парижа",
     "Its heart was a building at 7 rue Sainte-Anne, in the centre of Paris.",
     "Wide view of a narrow Haussmann-style Paris street with a six-storey stone building, a ground-floor shopfront with large windows and clocks displayed inside, horse carriages passing.",
     ANIM="carriages pass, people walk along the pavement, smoke rises from a chimney || slow pan from left to right || buildings stay still",
     TITLE="Central station | 7 rue Sainte-Anne")
shot("A", "cutaway", "h", "-", "Разрез здания: компрессоры, часы, магазин",
     "Compressors in the basement; above them, the master clock and a shop where anyone could sign up.",
     "Cutaway of the building in three levels: in the basement a steam engine and air compressors, on the first floor a tall master clock in a glass case, on the ground floor a shop counter where a lady in a bonnet speaks to a clerk.",
     AMB="a_machine_room", SFX="shop_bell @2.5 -12dB")
shot("A", "close", "h", "5 centimes a day", "Монеты на прилавке",
     "A clock cost five centimes a day, and less for a second or a third.",
     "Close-up of a polished wooden shop counter with a few small French bronze coins and a small wall clock standing on it, soft window light.",
     AMB="-", SFX="coins @0.3 -10dB")
shot("A", "medium", "h", "-", "Холл гостиницы, много часов",
     "Hotels loved it: the Hôtel Meurice alone had a hundred and forty-eight of them.",
     "A grand 1880s hotel corridor seen in perspective with many identical small wall clocks above every door, a bellboy in uniform carrying a suitcase.",
     AMB="a_quiet_room")
shot("A", "infographic", "-", "4,000+ clocks · 750 buildings", "Схема: дома, подключённые к сети",
     "By late 1881, more than four thousand clocks were connected in seven hundred and fifty buildings.",
     "Clean infographic of a cluster of simple Paris building facades seen from the front, small glowing clock icons in many windows, connected by thin lines below, plain pale background.",
     AMB="-")
shot("A", "medium", "h", "50 years · 1881", "Подписание концессии в мэрии",
     "In 1881 the city granted a fifty-year concession to distribute time. Not a monopoly, but the right to use its streets and sewers.",
     "A formal council room in the Paris Hôtel de Ville, gilded ceiling, an official signing a document at a large desk while two company men in frock coats watch.",
     AMB="a_quiet_room", SFX="quill @0.5 -12dB max=3", TITLE="50-year concession | 1881")
shot("B", "wide", "h", "-", "Ночной Париж с высоты, пульсация",
     "Paris now had a heartbeat. Once a minute, a puff of air went out across central Paris.",
     "Night view over Paris rooftops and chimneys in the 1880s, the Seine with gas-lit bridges, a soft turquoise pulse spreading outward from the centre beneath the city like a ripple.",
     ANIM="a soft turquoise ring of light pulses outward from the centre once, chimneys smoke gently || slow push-in over the rooftops || rooftops and river stay still",
     AMB="a_street_1880", SFX="air_hiss @0.8 -10dB")

# ---------------------------------------------------------------- 4. The master clock
shot("B", "wide", "h", "-", "Паровая машина и компрессоры",
     "Inside rue Sainte-Anne, a steam engine drove the air compressors.",
     "Wide view of a basement machine room: a steam engine with a large flywheel driving two piston air compressors through a belt, pipes and valves, warm lamp light.",
     CHAPTER="The master clock", AMB="a_machine_room", SFX="compressor @0 -10dB max=4")
shot("B", "medium", "h", "5 atm", "Большой резервуар",
     "They filled a storage tank of about eight cubic metres at five atmospheres.",
     "A large riveted iron air tank lying on brackets in the machine room, a pressure gauge and a valve wheel on top, a worker for scale.",
     SFX="metal_creak @0.5 -12dB max=3")
shot("B", "close", "h", "0.7 atm", "Регулятор давления",
     "A regulator let it into a second tank at just seven tenths of an atmosphere.",
     "Close-up of a brass pressure regulator between two pipes, a small float chamber and a gauge, polished metal reflecting lamp light.",
     SFX="air_hiss @0.3 -12dB max=2")
shot("A", "medium", "h", "-", "Главные часы в стеклянном шкафу",
     "The master clock had two separate movements.",
     "A tall master clock in a wood-and-glass case standing in a clean room, two brass clock movements side by side inside the case with two weights hanging below.",
     AMB="a_clock_room")
shot("A", "close", "h", "-", "Левый механизм с маятником",
     "The left one was a precise pendulum clock that kept the time.",
     "Close-up of the left brass movement with its long pendulum and seconds dial, gleaming gears, plain background inside the case.",
     ANIM="the pendulum swings steadily, the seconds hand advances || slow push-in toward the movement || case and gears stay still",
     SFX="clock_tick @0 -10dB")
shot("A", "close", "h", "-", "Правый механизм и золотник",
     "The right one had a single job: moving the valve.",
     "Close-up inside a tall wooden clock case: a small brass clock movement with gear wheels and a cam disc, a thin brass rod running from the cam down to a small brass slide valve fitted on a narrow pipe at the bottom of the case. It is a delicate clockwork mechanism, not an engine: no flywheel, no crank, no piston. Plain dark background inside the case.",
     SFX="valve_clunk @1 -8dB")
shot("A", "infographic", "-", "-", "График: 20 секунд воздух, 40 секунд сброс",
     "At the sixtieth second of every minute, the valve opened the city's mains to the air tank.",
     "Clean light infographic background with a small valve and pipe drawn on the left side and a large empty plain area on the right for a chart.",
     GFX="pulse_cycle", AMB="-")
shot("A", "cutaway", "h", "20 s", "Разрез трубы: воздух идёт",
     "For twenty seconds, air pushed into the pipes.",
     "Clean cutaway of a pipe with the valve open, small turquoise arrows of air flowing from a tank into the pipe toward the right.",
     ANIM="turquoise arrows of air stream through the pipe || static camera || pipe and tank stay still",
     SFX="air_hiss @0 -8dB max=3")
shot("A", "cutaway", "h", "40 s", "Разрез: сброс в атмосферу",
     "Then the valve flipped, and for forty seconds the pipes were vented to the open air.",
     "Clean cutaway of the same pipe and valve, the valve now turned so the pipe connects to a small vent opening upward, a few faint arrows leaving the vent.",
     SFX="valve_clunk @0.3 -8dB; air_hiss @0.6 -12dB max=2")
shot("A", "close", "h", "-", "Стрелка секунд на главных часах",
     "Twenty seconds on, forty off. Every minute, day and night.",
     "Close-up of the seconds dial of the master clock, the hand passing the twelve, crisp brass and enamel.",
     SFX="clock_tick @0 -10dB")
shot("A", "medium", "h", "-", "Гири часов",
     "The clock even wound itself.",
     "Two heavy brass clock weights hanging on chains inside the lower part of the master clock case, a small air cylinder with a piston beside each.",
     AMB="a_clock_room")
shot("A", "cutaway", "h", "-", "Поршни поднимают гири",
     "Every minute, air pistons lifted its weights by exactly as much as they had fallen.",
     "Clean cutaway of a small air cylinder whose piston pushes a lever that lifts a clock weight on a chain, arrows showing the upward motion.",
     ANIM="the piston rises and lifts the weight a short distance, then stops || static camera || cylinder and frame stay still",
     SFX="bellows_puff @0.4 -10dB")
shot("A", "medium", "h", "-", "Запасные часы и звонок тревоги",
     "A spare clock and valve stood ready, and alarms rang if a pulse failed.",
     "A second identical master clock standing beside the first in the room, an electric alarm bell on the wall between them, a technician in a waistcoat checking a gauge.",
     SFX="alarm_bell @0.5 -12dB max=2")
shot("A", "wide", "h", "Paris Observatory", "Парижская обсерватория",
     "At first, once a day, the clock was compared with the Paris Observatory, and the few seconds it had gained or lost were corrected by hand.",
     "Wide view of the Paris Observatory building with its domes in clear morning light, a gentleman in a frock coat walking toward it with a pocket chronometer in his hand.",
     AMB="a_street_1880")

# ---------------------------------------------------------------- 5. Time through the sewers
shot("B", "cutaway", "h", "10 mains", "Разрез: десять магистралей расходятся",
     "From rue Sainte-Anne, ten separate mains spread out under the streets.",
     "Underground cutaway below a Paris street: from one central valve box, ten thin iron pipes spread outward into different sewer tunnels, lanterns lighting the stone arches.",
     CHAPTER="Time through the sewers", AMB="a_sewer", SFX="water_drip @0 -10dB")
shot("B", "medium", "h", "27 mm", "Труба на стене коллектора",
     "They were wrought-iron pipes just twenty-seven millimetres wide, laid in the sewers.",
     "Inside an arched stone sewer tunnel lit by a lantern, a thin dark iron pipe fixed to the wall with brackets runs into the distance above the water channel, a sewer worker in boots for scale.",
     ANIM="lantern light flickers, water flows slowly in the channel || slow push-in along the tunnel || pipe and walls stay still",
     FX="lamp", SFX="water_drip @0.6 -12dB")
shot("A", "infographic", "-", "-", "Схема: одна линия сломалась, остальные работают",
     "If one main failed, the others kept working.",
     "Clean infographic: a central box with ten pipes radiating outward, one pipe shown broken with a small gap, the other nine glowing turquoise, plain pale background.")
shot("A", "cutaway", "h", "15 mm", "Разрез дома: трубка в лестничной клетке",
     "At each building, lead pipes took over: fifteen millimetres in the stairwell,",
     "Cutaway of a Paris apartment building showing the stairwell with a thin grey lead pipe climbing up the wall from the cellar to the upper floors.",
     AMB="a_quiet_room")
shot("A", "close", "h", "6 mm → 3 mm", "Тонкая трубка к часам",
     "six in each apartment, and finally a tube of just three millimetres to the clock.",
     "Close-up of a thin lead pipe on an apartment wall narrowing into a very thin flexible tube that enters the bottom of a wall clock case.",
     ANIM="a faint turquoise pulse travels along the thin tube into the clock || slow tilt up along the tube to the clock || wall and clock case stay still")
shot("A", "medium", "-", "-", "Вопрос: как быстро идёт импульс",
     "How fast does a puff of air travel down a pipe?",
     "A long straight pipe drawn across a clean pale background with a small puff of air at its left end, simple and bold.",
     AMB="-", SFX="air_hiss @0.3 -12dB max=2")
shot("A", "infographic", "-", "-", "График: скорость фронта давления",
     "The front of the pressure wave moves at roughly the speed of sound, about three hundred and forty metres per second.",
     "Clean light infographic background with a pipe running along the bottom edge and a large empty plain area above it for a chart.",
     GFX="pulse_speed")
shot("A", "infographic", "-", "~3 s per km", "Километр за три секунды",
     "That is about three seconds for every kilometre.",
     "Clean infographic: a straight pipe with distance markers along it, a small turquoise pulse moving along it and a simple stopwatch drawn above, plain pale background.")
shot("A", "wide", "h", "≥15 s · 5 km", "Карта: дальние часы получают импульс",
     "A clock five kilometres away could not move until at least fifteen seconds after the valve opened.",
     "Stylised view over Paris rooftops in daylight with a thin turquoise line running from the centre to a lamp-post clock far away near the edge of the city.",
     ANIM="a turquoise pulse travels from the centre along the line to the distant clock || slow pan from left to right || rooftops stay still")
shot("A", "close", "h", "-", "Задвижка открыта, давление растёт",
     "That is one reason the valve stayed open for twenty seconds: the far ends needed time to fill.",
     "Close-up of a pressure gauge on a distant pipe, the needle rising, a clock dial blurred in the background.",
     SFX="air_hiss @0.2 -12dB max=3")
shot("A", "medium", "h", "within ~4 s", "Инженеры сверяют часы",
     "In 1881, engineers found that the public clocks agreed with each other within about four seconds.",
     "Two 1880s engineers on a Paris boulevard, one holding a pocket chronometer and the other writing in a notebook, a lamp-post clock behind them.",
     AMB="a_street_1880")
shot("A", "close", "h", "-", "Два карманных хронометра рядом",
     "Not perfect, but far better than clocks set one by one by hand.",
     "Close-up of two open pocket chronometers lying side by side on a notebook, showing the same time, a pencil beside them.",
     SFX="clock_tick @0 -12dB")
shot("B", "medium", "h", "-", "Утечка воздуха на стыке трубы",
     "Leaks were unavoidable.",
     "A joint of an iron pipe in a dark sewer tunnel with a small visible jet of escaping air disturbing a cobweb, lantern light.",
     AMB="a_sewer", SFX="air_hiss @0 -10dB max=2")
shot("A", "infographic", "-", "-", "Схема: утечка влияет только на часы дальше",
     "But a leak only weakened the clocks beyond it, and twenty seconds of pressure was enough to drive clocks kilometres away despite the losses.",
     "Clean infographic: a pipe with a small leak in the middle, clocks before the leak glowing turquoise, clocks after it dimmer, plain pale background.",
     ANIM="the clocks before the leak tick forward, the ones after it tick weakly || static camera || pipe and clocks stay in place",
     AMB="-")

# ---------------------------------------------------------------- 6. A clock that breathes
shot("A", "medium", "h", "-", "Часы в квартире",
     "The clock at the end of the line was simple.",
     "A simple wall clock with a white enamel dial and black hands hanging in a calm Parisian apartment, a window with lace curtains, soft daylight.",
     CHAPTER="A clock that breathes", AMB="a_quiet_room")
shot("A", "cutaway", "h", "-", "Разрез корпуса: резиновые мехи",
     "Inside sat a small bellows made of soft rubber.",
     "Clean cutaway of the clock case showing a small concertina-shaped rubber bellows at the bottom, the thin air tube entering it, the movement above.",
     SFX="bellows_puff @0.5 -12dB")
shot("A", "macro", "h", "-", "Мехи надуваются",
     "When the pulse arrived, the bellows swelled and pushed a rod upward.",
     "Macro view of the rubber bellows expanded, a thin vertical rod above it pushed upward, brass parts, plain dark background.",
     ANIM="the bellows inflates and lifts the rod, then holds || static camera || the clock frame stays still",
     SFX="bellows_puff @0.2 -8dB")
shot("A", "macro", "h", "-", "Рычаг с собачкой",
     "The rod raised a lever that carried a small hooked pawl.",
     "Macro view of a brass lever pivoted at one end, a small hooked pawl attached to it resting against a toothed wheel, clean background.")
shot("A", "macro", "h", "60 teeth", "Колесо с 60 зубьями",
     "The pawl pushed a wheel with sixty teeth forward by exactly one tooth.",
     "Macro view of a brass ratchet wheel with sixty evenly spaced teeth, the pawl engaging one tooth, clean background.",
     SFX="ratchet_click @0.6 -8dB")
shot("A", "close", "h", "-", "Упоры ограничивают ход рычага",
     "Stops limited the lever's travel, so each breath moved the wheel just one tooth.",
     "Close view of the lever between two small brass stop pins on a plate, the ratchet wheel beside it, clean background.")
shot("A", "macro", "h", "-", "Защёлка не даёт колесу вернуться",
     "A second catch held the wheel so it could not slip back.",
     "Macro view of a balanced brass detent resting in the teeth on the other side of the ratchet wheel, clean background.",
     SFX="ratchet_click @0.4 -12dB")
shot("A", "cutaway", "h", "-", "Мехи опадают, рычаг падает",
     "When the pipes were vented, the bellows sank and the lever dropped back, ready for the next minute.",
     "Clean cutaway of the mechanism with the bellows collapsed and the lever lowered, small arrows showing the downward motion.",
     SFX="air_hiss @0.2 -14dB max=2")
shot("A", "close", "h", "1 pulse = 1 minute", "Минутная стрелка шагает",
     "One pulse, one tooth, one minute. Sixty pulses, one turn of the minute hand.",
     "Close-up of the white enamel dial, the minute hand having just moved one step, crisp black numerals as simple marks without readable digits.",
     SFX="ratchet_click @0.2 -10dB")
shot("A", "macro", "h", "-", "Шестерни часовой стрелки",
     "A small set of gears turned the hour hand.",
     "Macro view of a small brass gear train behind the dial connecting the minute arbor to the hour wheel, clean background.",
     ANIM="the small gears turn slowly as the minute wheel steps || slow orbit around the gears || frame stays still")
shot("A", "medium", "h", "-", "Часовщик чинит лопнувшие мехи",
     "A burst bellows or a missed pulse left a clock behind until someone came to reset it.",
     "A clock repairman in a waistcoat opening the case of a wall clock in an apartment, a torn rubber bellows in his hand and a small toolbox on a chair.")
shot("A", "close", "h", "-", "Часы с боем и вторые мехи",
     "Clocks that struck the hours had a second bellows to wind their striking spring.",
     "Close view inside a mantel clock with a small bell on top and two rubber bellows inside the case, one feeding the striking mechanism.",
     SFX="clock_chime @0.3 -10dB")

# ---------------------------------------------------------------- 7. From time to power
shot("A", "medium", "h", "-", "Инженер смотрит на трубу и мотор",
     "But air could do far more than move a minute hand.",
     "A 1880s engineer in a frock coat standing in a workshop doorway looking at an air pipe on the wall and a small idle motor on the floor.",
     CHAPTER="From time to power", AMB="a_workshop")
shot("A", "medium", "h", "1886", "Подписание договора о силовом воздухе",
     "In 1886 Victor Popp signed a treaty with Paris to deliver motive power straight to customers' premises.",
     "A city official and two company directors shaking hands across a desk with a document on it, a large map of Paris on the wall behind them.",
     AMB="a_quiet_room", SFX="quill @0.3 -12dB max=2")
shot("B", "wide", "h", "Rue Saint-Fargeau", "Станция на улице Сен-Фаржо",
     "The company's plant on rue Saint-Fargeau, in Belleville, sent air at five atmospheres into a cast-iron main thirty centimetres wide.",
     "Wide exterior view of a large 1880s brick power station with tall chimneys on a hilly Paris street in Belleville, smoke rising, a horse cart delivering coal.",
     ANIM="smoke rises from the chimneys, the cart moves slowly || slow pan from left to right || buildings stay still",
     AMB="a_machine_room", SFX="steam_engine @0 -12dB max=4", TITLE="Rue Saint-Fargeau | 5 atm")
shot("B", "medium", "h", "2,000+ hp", "Большие паровые машины",
     "By 1889, at peak hours, its engines produced well over two thousand horsepower.",
     "Inside the power station: a row of large steam engines with huge flywheels and polished rods, engineers on a gallery, warm light.",
     SFX="compressor @0 -10dB max=4")
shot("A", "medium", "h", "1889", "Английский инженер с блокнотом",
     "That year the British engineer Alexander Kennedy came to test it.",
     "A British engineer in a tweed suit with a notebook and a pressure indicator instrument standing beside an air motor in a workshop, a French workman explaining.",
     AMB="a_workshop")
shot("A", "infographic", "-", "225 installations", "Схема: много маленьких моторов",
     "A list he was given showed two hundred and twenty-five installations, nearly all motors from half a horsepower to fifty.",
     "Clean infographic: a grid of small motor icons of different sizes connected by thin pipes to one main line, plain pale background.")
shot("A", "wide", "h", "-", "Мастерская: токарные станки и пилы",
     "Lathes and saws, bookbinders, umbrella makers, the sewing machines of tailors,",
     "Wide view of a busy 1880s Paris workshop with lathes, a circular saw and sewing machines driven by belts from an overhead shaft, an air motor in the corner, workers at their benches.",
     ANIM="belts run, the saw spins, workers move || slow pan from left to right || walls and machines stay in place",
     SFX="lathe @0 -12dB max=3; sewing_machine @2 -12dB max=3")
shot("A", "medium", "h", "-", "Обжарка кофе и типография",
     "coffee roasters, confectioners, and the printing presses of Le Figaro.",
     "A 19th-century printing hall with a large rotary press printing newspapers, a pile of fresh sheets, a pressman in an apron, an air pipe on the wall.",
     SFX="printing_press @0 -12dB max=4")
shot("A", "close", "h", "-", "Воздушный мотор крутит динамо",
     "Some motors turned dynamos and made electric light.",
     "Close view of a compact air motor on a workbench connected by a belt to a small dynamo, a wire leading to a glowing electric bulb on a stand. No people in this shot.",
     SFX="dynamo_hum @0 -12dB max=3")
shot("B", "medium", "h", "-", "Холодный выхлоп замораживает графины",
     "And expanding air turns cold: one restaurant piped the exhaust into its beer cellar and froze carafes of water.",
     "A stone beer cellar under a restaurant, a pipe blowing cold misty air over barrels and shelves with glass carafes covered in frost, a waiter with a lantern looking surprised.",
     FX="lamp", SFX="ice_crack @0.5 -10dB")
shot("A", "infographic", "-", "-", "Схема потерь энергии",
     "Air was not free energy. Much of the engines' work was lost as heat when the air was squeezed, and more when it expanded cold in the motor.",
     "Clean infographic: a compressor at a plant on the left, a long pipe, and a motor on the right; a wide energy arrow loses chunks as red heat at the compressor and as blue cold at the motor, but stays almost the same width along the pipe, plain pale background.",
     ANIM="heat shimmers off the compressor and frost forms at the motor while the arrow flows || static camera || plant and motor icons stay still",
     AMB="-")
shot("A", "close", "h", "-", "Маленькая печь подогревает воздух",
     "Kennedy found that heating the air in a small coke stove just before the motor",
     "Close view of a small cast-iron coke stove with a coil of pipe inside, glowing coals, connected to an air motor beside it.",
     FX="fire", SFX="fire_crackle @0 -12dB max=3")
shot("A", "infographic", "-", "10 hp per 20 hp", "Схема: 10 л.с. у мотора на 20 л.с. станции",
     "meant a motor four miles away got about ten horsepower for every twenty spent at the plant, counting the coke. Without heating, it took thirty-five.",
     "Clean infographic in 19th-century style: on the left a small brick steam power plant with one tall chimney, on the right a cast-iron air motor with a flywheel, a wide arrow from the plant narrowing to half its width at the motor, and just before the motor a small cast-iron stove with glowing coke coals. No modern buildings, no cooling towers, no gas flames, plain pale background.")
shot("B", "wide", "h", "Quai de la Gare · 1892", "Большая станция на набережной",
     "In 1892 a much larger plant opened on the quai de la Gare, beside the Seine.",
     "Wide view of a large brick-and-iron industrial hall with a tall brick chimney on the bank of the Seine in the 1890s, barges on the river unloading coal.",
     ANIM="smoke rises, a barge drifts slowly, water ripples || slow push-in toward the hall || building and chimney stay still",
     AMB="a_machine_room", TITLE="Quai de la Gare | 1892")
shot("B", "medium", "h", "4 × 1,800 hp", "Четыре огромные паровые машины",
     "Four steam engines of eighteen hundred horsepower each drove its compressors.",
     "Inside a vast hall: four giant vertical steam engines with towering cylinders and flywheels, iron galleries, engineers small in the scene.",
     SFX="steam_engine @0 -10dB max=4")
shot("A", "infographic", "-", "-", "График: рост сети в километрах",
     "The clock company had become an energy company: by 1900 it had more than a hundred and sixty kilometres of power mains.",
     "A small 1890s brick compressed-air plant with one chimney, drawn as a simple icon in the lower-left corner only. Plain soft pale-blue background filling the whole frame, completely empty in the middle and on the right. No frames, no boxes, no cards, no panels, no borders, no screens.",
     GFX="network_km", CAMERA="push_in", AMB="-")
shot("A", "medium", "h", "-", "Контора: счета за электричество",
     "And by then, it was selling electricity as well. By 1900, almost all of its money came from it.",
     "A 1900 company office with clerks at desks, ledgers, an electric lamp on each desk and a large electricity meter on the wall.",
     AMB="a_quiet_room")

# ---------------------------------------------------------------- 8. The night the river came in
shot("B", "wide", "h", "Jan 1910", "Дождь над Сеной, вода поднимается",
     "Which brings us back to January 1910.",
     "Wide view of the Seine in Paris in January 1910 under heavy grey sky and rain, the river very high and brown, almost touching the arches of a stone bridge.",
     CHAPTER="The night the river came in", AMB="a_flood_night", MUSIC="m3_flood", SFX="rain @0 -10dB max=4")
shot("B", "medium", "h", "~1 m per day", "Наводнение ползёт по улице",
     "After heavy rain, the Seine was rising by about a metre a day.",
     "A Paris street with water slowly covering the cobbles, people walking on improvised wooden planks laid on trestles, a man in a bowler hat looking at the water.",
     ANIM="the water rises a little, a person crosses the planks || slow push-in along the street || buildings stay still",
     SFX="water_rush @0 -14dB max=3")
shot("B", "wide", "h", "-", "Медленный подъём, не внезапный",
     "This was not a flash flood. It crept up, day after day.",
     "Wide view of a Paris quay at dusk with the river level marked against the stone wall, water lapping at the top steps, lamp posts reflected in the water.",
     AMB="a_flood_night")
shot("B", "dynamic", "h", "quai de la Gare", "Вода в машинном зале",
     "On the evening of the 21st, the water got into the compressed-air plant on the quai de la Gare.",
     "Dramatic view inside the large machine hall at night: brown water spreading across the floor between the huge steam engines, lanterns reflected, two workers wading.",
     ANIM="water spreads across the floor, lantern light trembles || slow handheld sway || engines stay still",
     CAMERA="sway", SFX="water_rush @0 -8dB")
shot("B", "close", "h", "-", "Остановившийся маховик",
     "The compressors stopped, and the pipes lost their pressure.",
     "Close-up of a large flywheel standing still in dark flooded water, a pressure gauge on a pipe beside it with the needle at zero.",
     SFX="steam_engine @0 -12dB max=2; boom @1.2 -10dB")
shot("B", "medium", "h", "22:48–22:53", "Часы на фонаре остановились",
     "And between ten forty-eight and ten fifty-three, the pneumatic clocks of Paris stopped, all within a few minutes.",
     "A lamp-post clock on a wet night boulevard showing about ten to eleven, rain falling, a lone passer-by with an umbrella looking up at it.",
     AMB="a_flood_night")
shot("B", "medium", "h", "-", "Лифт застыл между этажами",
     "Lifts and workshop motors driven by air stopped too.",
     "A Parisian apartment building stairwell at night with an ornate iron cage lift stopped between floors, a resident with a candle looking up.",
     FX="lamp", SFX="metal_creak @0.3 -12dB max=3")
shot("B", "wide", "h", "8.62 m · 28 Jan", "Пик наводнения, лодки на улицах",
     "The river kept rising for a week. It peaked on the 28th of January at eight point six two metres on the Austerlitz gauge.",
     "Wide view of a flooded Paris street at the peak of the 1910 flood, small rowing boats carrying people between buildings, water up to the first-floor windows of shops.",
     ANIM="boats glide slowly, oars dip, water ripples || slow pan from left to right || buildings stay still",
     SFX="oars @0 -12dB max=4")
shot("B", "wide", "h", "~20,000 buildings", "Затопленные подвалы и метро",
     "Around twenty thousand buildings were flooded, and most metro lines were flooded too.",
     "Wide view of a flooded metro station entrance with ornate cast-iron railings, steps disappearing into brown water, workers with a pump hose.",
     AMB="a_flood_night", SFX="water_drip @0 -12dB")
shot("A", "medium", "h", "3 Feb 1910", "Часы снова идут",
     "The air clocks came back on the 3rd of February, after thirteen days of silence.",
     "A bright winter morning on a Paris boulevard with mud on the pavement, a workman on a ladder checking a lamp-post clock while a woman compares it with her small watch.",
     AMB="a_street_1880", SFX="clock_tick @0.5 -10dB", TITLE="13 days | 3 Feb 1910")
shot("A", "medium", "h", "-", "Рабочие продувают трубы",
     "First, the water had to be purged from the pipes.",
     "Workers opening a valve on a pipe in a sewer-access shaft, a spray of muddy water and air blowing out, one worker holding a lantern.",
     SFX="air_hiss @0 -8dB max=3")
shot("A", "wide", "h", "-", "Париж снова живёт",
     "Paris was keeping time again.",
     "Wide view of a Paris boulevard after the flood, people back on the pavements, horse carriages and an early automobile, a lamp-post clock in the foreground.",
     ANIM="people walk, a carriage passes, the clock hand steps once || slow push-in toward the clock || buildings stay still",
     SFX="horse_carriage @0 -14dB max=3")

# ---------------------------------------------------------------- 9. Losing to electricity
shot("A", "medium", "h", "-", "Бухгалтерская книга",
     "But the clocks were never much of a business.",
     "A large open ledger on a desk with columns of handwritten figures shown as abstract lines, a pen and an inkwell, a clock on the wall behind.",
     CHAPTER="Losing to electricity", AMB="a_quiet_room")
shot("A", "infographic", "-", "16.90 F vs 60.70 F", "Доход и расход на один циферблат",
     "In 1880 each dial earned the company about seventeen francs a year and cost it about sixty.",
     "Clean infographic: a small stack of coins on the left and a much taller stack on the right, a clock dial icon between them, plain pale background.")
shot("A", "infographic", "-", "-", "График: число частных часов",
     "The number of private clocks peaked around 1884 at about seventy-eight hundred, then slowly fell.",
     "A small round 19th-century wall clock drawn as a simple icon in the lower-left corner only. Plain soft pale-blue background filling the whole frame, completely empty in the middle and on the right. No frames, no boxes, no cards, no panels, no borders, no screens.",
     GFX="clock_count")
shot("A", "medium", "h", "1926", "Мастерская с электрическими часами",
     "By 1926 about five thousand were left, with fewer than a thousand subscribers.",
     "A 1920s Paris clock shop with modern electric wall clocks on display, wires instead of tubes, a salesman showing one to a customer.",
     AMB="a_quiet_room")
shot("A", "medium", "h", "-", "Радио и электрические часы",
     "Radio time signals were spreading, and electric clocks now offered a simpler alternative.",
     "A 1920s living room with a wooden radio set on a table, a family listening, an electric wall clock above, soft lamp light.",
     ANIM="the family leans toward the radio, the lamp glows || slow push-in toward the radio || furniture stays still",
     FX="lamp", SFX="radio_static @0 -12dB max=3")
shot("A", "close", "h", "1 Mar 1927", "Документ об окончании разрешения",
     "On the 1st of March 1927, the company's licence for the clock service ran out, and it chose not to renew it.",
     "Close-up of an official document on a desk with a wax seal and an old fountain pen, the paper covered with abstract handwriting lines, a closed pocket watch beside it.",
     SFX="paper_rustle @0.3 -12dB")
shot("A", "medium", "h", "Magneta", "Рабочие снимают трубки",
     "Its customers went to an electric clock firm, Magneta, and the city removed the pipes.",
     "Workers in caps pulling thin lead tubes out of a building wall and loading them on a handcart, an electrician fitting an electric clock nearby.",
     SFX="metal_clank @0.4 -12dB max=2")
shot("A", "close", "h", "1880–1927", "Старые воздушные часы на стене, пыль",
     "After forty-seven years, the time of Paris no longer travelled by air.",
     "Close-up of an old pneumatic wall clock hanging disconnected, its tube cut short, dust on the case, soft afternoon light.",
     AMB="-")
shot("B", "wide", "h", "-", "Станция продолжает работать",
     "The air itself kept flowing.",
     "Wide night view of the brick compressed-air plant on the Seine with lit windows and smoke from its chimney, the river calm.",
     AMB="a_machine_room")
shot("B", "close", "h", "-", "Остановившиеся часы на фоне",
     "Only the clocks went quiet.",
     "Close-up of a still clock dial in a dark room, a thin beam of light across it.")

# ---------------------------------------------------------------- 10. The network that outlived them
shot("A", "infographic", "-", "-", "График роста сети до 1970",
     "The power network kept growing: five hundred and twenty-five kilometres of mains in 1930, and nine hundred and forty-one by 1970.",
     "A short section of cast-iron pipe drawn as a simple icon in the lower-left corner only. Plain soft pale-blue background filling the whole frame, completely empty in the middle and on the right. No frames, no boxes, no cards, no panels, no borders, no screens.",
     CHAPTER="The network that outlived them", GFX="network_km", CAMERA="pull_out", AMB="-")
shot("A", "medium", "h", "-", "Гидропневматический лифт в доме 1900-х",
     "It lifted elevators in the elegant buildings of western Paris,",
     "An elegant early-1900s Paris apartment building hall with a wrought-iron cage lift rising, a lady in a long dress inside, polished brass.",
     AMB="a_quiet_room", SFX="lift_gate @0.3 -12dB")
shot("A", "wide", "m", "-", "Отбойные молотки на стройке",
     "drove jackhammers on building sites and tools in garages and print shops.",
     "Wide view of a 1960s Paris street works site with workers using pneumatic jackhammers, a compressed-air hose running from a street connection, Haussmann buildings behind.",
     ANIM="the jackhammers vibrate, dust puffs rise || slow pan from left to right || buildings stay still",
     AMB="a_modern_city", SFX="jackhammer @0 -12dB max=3")
shot("A", "infographic", "-", "peak 1973", "Пик продаж воздуха",
     "Its air sales peaked in 1973. After that, industry moved out of the city, and the last air-driven lifts disappeared.",
     "Clean infographic: a simple curve rising to a peak and falling, small icons of a factory leaving and a modern lift, plain pale background.")
shot("A", "wide", "m", "1994", "Последний клапан закрывается",
     "In 1994 the city ended the concession, and the public supply of compressed air across Paris came to an end.",
     "A 1990s engineer in a hard hat closing a large valve wheel in an old pump hall, iron pipes around, soft daylight from tall windows.",
     AMB="a_machine_room", SFX="valve_clunk @0.8 -8dB")
shot("A", "wide", "m", "-", "Здание станции сегодня",
     "Part of the great plant on the former quai de la Gare still stands. Its metal hall and brick chimney are a listed monument.",
     "Present-day view of a restored 1890s brick-and-iron industrial hall with a tall brick chimney beside the Seine in Paris, people walking along the quay, clear blue sky.",
     ANIM="clouds drift, people walk along the quay || slow push-in toward the chimney || building stays still",
     AMB="a_modern_city")
shot("A", "medium", "m", "-", "Студенты-архитекторы в старом зале",
     "Today it is part of a school of architecture.",
     "Architecture students working at drawing tables and models inside a bright restored iron-and-brick industrial hall with tall windows.",
     AMB="a_quiet_room")
shot("B", "wide", "h", "-", "Ночной Париж 1880-х, пульс по городу",
     "For forty-seven years, part of Paris told the time by breathing.",
     "Night view over 1880s Paris rooftops with a soft turquoise pulse spreading outward from the centre, warm windows, the Seine with lit bridges.",
     AMB="a_street_1880")
shot("B", "medium", "h", "-", "Финал: часы на фонаре в дождь, замирают",
     "And on one flooded night in 1910, the whole city held its breath.",
     "Night street in Paris in 1910 in the rain, a lamp-post clock dial glowing softly, its hands still at about ten to eleven, water covering the cobbles below, warm gas light.",
     ANIM="rain falls, ripples spread on the water, the gas flame flickers, the clock hands stay still || very slow pull-back from the clock || lamp post and buildings stay still",
     AI_CLIP="yes", SFX="clock_tick @0 -12dB max=2")

DEFAULT_ANIM = ("subtle natural motion, light and small details move gently || gentle camera drift || "
                "main subjects and buildings stay still")
ORDER = ("CHAPTER", "TITLE", "GFX", "FX", "CAMERA", "AMB", "SFX", "MUSIC", "AI_CLIP")


def main() -> None:
    out = ['# The Air-Powered Clocks of Paris — generated by script_source.py (edit there, not here).',
           '# Header: #n | m:ss | mode | shot | characters | era | title. Syntax: studio/pipeline/frames.py.', '']
    t = 0.0
    for i, (mode, kind, era, title, ru, vo, scene, extra) in enumerate(S, 1):
        sec = int(round(t))
        out.append(f"#{i} | {sec // 60}:{sec % 60:02d} | {mode} | {kind} | - | {era} | {title}")
        out += [f"RU: {ru}", f"VO: {vo}", f"SCENE: {scene}"]
        anim = extra.get("ANIM") or (DEFAULT_ANIM if i % 5 == 0 else "")
        if anim:
            out.append(f"ANIM: {anim}")
        for k in ORDER:
            if k in extra:
                out.append(f"{k}: {extra[k]}")
        out.append("")
        t += max(MIN_S, round(len(vo.split()) / WPS + 0.4))
    end = int(round(t))
    Path(__file__).with_name("frames.txt").write_text("\n".join(out), encoding="utf-8")
    cfg = Path(__file__).with_name("episode.yaml")        # keep the storyboard end in sync
    cfg.write_text(re.sub(r'^storyboard_end: ".*"', f'storyboard_end: "{end // 60}:{end % 60:02d}"',
                          cfg.read_text(encoding="utf-8"), flags=re.M), encoding="utf-8")
    words = sum(len(s[5].split()) for s in S)
    print(f"shots={len(S)} words={words} est={end // 60}:{end % 60:02d} storyboard_end")


if __name__ == "__main__":
    main()
