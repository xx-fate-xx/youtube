"""Short: "Why the First Atlantic Cable Was So Slow" (links to enginovue_cable_1858).

Facts: ../enginovue_cable_1858/factcheck_report.md and its sources (1861 joint committee report, Hunt 2021,
Bright 1903, S. P. Thompson 1910, Science Museum Group). Narration is written for this Short; it does not
reuse the long video's sentences.
Run:  python script_source.py   -> frames.txt
"""

from studio.pipeline.scriptgen import Script

s = Script(__file__, "Why the First Atlantic Cable Was So Slow")

s.shot("B", "medium", "h", "Aug 1858", "Телеграфист у аппарата, рядом песочные часы",
       "August 1858. With stops and repeats, Queen Victoria's message to America takes about sixteen hours.",
       "A Victorian telegraph office at night lit by an oil lamp: a tired operator in shirt sleeves and waistcoat "
       "sits at a brass telegraph key, a tall hourglass beside him, a thick cable end entering the wall.",
       CHAPTER="The slow cable", FX="lamp", AMB="a1_telegraph_office", MUSIC="m1_opening",
       SFX="s01_telegraph_key @0.3 -8dB max=3")
s.shot("A", "close", "h", "~100 words · ~16 hours", "Лист с коротким посланием королевы",
       "It's only about a hundred words.",
       "Close view of a single short handwritten letter on cream paper with a red wax seal, lying on a wooden "
       "telegraph desk next to a brass key, warm light. The handwriting is illegible squiggles.",
       SFX="s11_quill @0 -10dB max=2")
s.shot("A", "cutaway", "h", "-", "Разрез кабеля: медная жила в изоляции, вокруг морская вода",
       "The cable is a copper core in insulation, lying in salt water.",
       "Clean cross-section of an 1858 submarine telegraph cable on a plain light background: a bundle of copper "
       "wires in the centre, thick brown gutta-percha insulation around it, outer iron wires, and blue sea water "
       "drawn around the whole cable.",
       AMB="a5_underwater")
s.shot("A", "cutaway", "h", "-", "Кабель как длинный бак, который надо сначала наполнить",
       "It soaks up charge, like a tank that must fill first.",
       "A long submarine cable drawn as a transparent tube lying across the sea floor from left to right, slowly "
       "filling with glowing turquoise charge from one end, the far end still dark. Plain deep-blue background.",
       SFX="s28_data_pulse @0.5 -10dB")
s.shot("A", "infographic", "h", "-", "Чёткий импульс на входе, размытая волна на выходе",
       "So a crisp tap from Ireland reaches Newfoundland as a blurred swell.",
       "Two glass-fronted brass instruments facing each other across a stretch of sea: on the left a sharp bright "
       "turquoise flash leaves a cable end, on the right only a faint wide glow arrives. No numbers, no labels.",
       ANIM="a sharp turquoise flash leaves the left cable end and arrives on the right as a faint, wide glow || "
            "static camera || instruments and sea stay still")
s.shot("B", "medium", "h", "1855", "Молодой Томсон считает у доски",
       "In 1855, William Thomson showed the delay grows with the square of the length.",
       "A young William Thomson in a Glasgow university study, standing at a blackboard covered in chalk "
       "squiggles (no readable formulas), holding chalk, an oil lamp glowing.",
       chars="thomson", SFX="s12_chalk @0.4 -8dB max=2")
s.shot("A", "infographic", "h", "2× length → 4× delay", "Два кабеля: вдвое длиннее, вчетверо медленнее",
       "Double the cable, four times the delay.",
       "Two submarine cables drawn on a plain pale-blue background, one twice as long as the other, each with a "
       "small turquoise pulse crawling along it; the pulse on the long cable is far behind. No text or numbers.",
       SFX="s30_galvo_tick @0.5 -10dB")
s.shot("B", "close", "h", "-", "Зеркальный гальванометр: магнит с зеркальцем на нити",
       "His answer to faint signals: a tiny magnet and mirror on a silk thread.",
       "Close view of a mirror galvanometer of the 1850s: a small round brass coil housing with a tiny mirror "
       "hanging on a fine silk thread at its centre, an oil lamp shining a narrow beam onto it.",
       FX="lamp")
s.shot("B", "medium", "h", "-", "Пятно света прыгает по шкале",
       "The faintest current swung a spot of light: one way a dot, the other a dash.",
       "A dark telegraph room: a bright spot of lamp light reflected from the galvanometer mirror falls on a "
       "white paper scale on the wall; an operator watches it and writes on a pad.",
       ANIM="the spot of light jumps left, then right, along the white scale, the operator's pencil moves || "
            "static camera || instruments and walls stay still",
       FX="lamp", SFX="s30_galvo_tick @0.3 -6dB; s30_galvo_tick @1.4 -6dB")
s.shot("B", "dynamic", "h", "-", "Индукционная катушка, искры",
       "But its insulation was already flawed, and huge high-voltage induction coils likely made it worse.",
       "Dramatic low angle: a huge brass induction coil on a wooden bench throwing bright sparks between two "
       "terminals in a dark telegraph room, cables running off to the wall.",
       CAMERA="snap", SFX="s21_sparks @0 -6dB")
s.shot("B", "cutaway", "h", "early Sep 1858", "Вода проникает к меди, сигнал гаснет",
       "Within a month, nothing readable got through.",
       "Cutaway of the cable lying on the dark sea floor: a crack in the brown insulation lets sea water reach the "
       "copper core, a turquoise glow leaks out into the water and fades.",
       AMB="a5_underwater", SFX="s08_signal_fade @0 -8dB")
s.shot("A", "wide", "h", "-", "Пароход Great Eastern в море",
       "How they fixed it: full story on the channel.",
       "The giant iron steamship Great Eastern with four funnels and six masts at sea under a bright sky, a "
       "cable running from her stern into the water, gulls overhead.",
       AMB="a3_calm_sea", SFX="s09_steamship @0.5 -10dB")

if __name__ == "__main__":
    s.write()
