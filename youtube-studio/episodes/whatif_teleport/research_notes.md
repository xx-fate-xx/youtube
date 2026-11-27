# Research notes: What If You Could Teleport? (Your Speed Comes Too)

Channel: Physics Says No · ~8 min · stickman "you" · 13+
Researched 2026-11-23. Calculations were done locally in Python. Rounding is shown. "OUR REASONING" means standard mechanics with no outside source quoted. "UNVERIFIED" means we could not confirm it from an authoritative page.

## 0. The rule (must be on screen, and the narration must choose one)

- **Option A (use this): you keep your velocity as seen from space**, in a frame centred on Earth that does not spin with it. The ground under you spins, so a jump to a place where the ground moves differently becomes a crash. All the beats below assume Option A.
- **Option B: you keep your velocity relative to the ground you left.** Most of the Earth-spin beats disappear, but the falling beats still work. Say this once in about 10 seconds ("If speed was measured against the ground, nothing would happen... but the ground isn't still").
- **Risk:** do not switch frames in the middle of the episode. The Sun-frame idea is dropped in beat 3.

---

## Beat 1: The falling window cleaner

**Claim:** Teleporting someone to the ground does not stop their fall. They arrive at the speed they already had. A rescue only works if you teleport them **right after the slip**, before they have gained speed. Teleporting them up does not help either. They keep their downward speed and start falling again.

**Numbers.** Model with air drag: v(t) = v_t·tanh(g·t/v_t), with g = 9.81 m/s² and v_t = 55 m/s (≈ 200 km/h, belly-down).

| time after slip | speed | fallen |
|---|---|---|
| 0.5 s | 18 km/h (11 mph) | 1.2 m |
| 1 s | 35 km/h (22 mph) | 4.9 m |
| 2 s | 68 km/h (42 mph) | 19 m |
| 3 s | 97 km/h (60 mph) | 42 m |
| 4.5 s | 132 km/h (82 mph) | 90 m (≈ ground, 300 ft) |

- A 300 ft (91 m) drop takes **≈ 4.5 s** and ends at **≈ 132 km/h / 82 mph** with drag. Without drag it would be 152 km/h.
- The speed reaches half of terminal velocity at ≈ 3.1 s and 99 % at ≈ 15 s.
- **Height of 30 floors:** the CTBUH height calculator uses floor-to-floor heights of about 3.1 m (residential) to 3.9 m (office). That puts 30 floors at about 93–117 m, so "≈ 300 ft" sits at the low, residential end. Say "about 30 floors up" and avoid a precise floor height. The CTBUH page came only from a third-party mirror (pdfcoffee): **UNVERIFIED** at heightcalculator.ctbuh.org.
- **Terminal velocity source:** LibreTexts *Body Physics* (Lawrence Davis, Umpqua Community College, OER), §8.04. Its worked example for a 90 kg skydiver gives **"120 MPH"**. §8.03 gives drag coefficient 1.0 (horizontal) and 0.70 (feet first). The FAI was **not** confirmed as a source for ≈ 200 km/h, so cite Davis instead.

**Everyday image:** "One second after slipping, you're falling as fast as a bike going downhill. After the full drop, it's a car on the motorway."

**Bonus beat (OUR REASONING), Portal loop:** teleport from just above the floor back to the ceiling over and over. You keep speeding up, but drag caps you at about 200 km/h after about 15 s. Each loop also gives you free height, which means free energy. A teleporter like that is a perpetual motion machine, which is a clean "Physics Says No" line.

**Risk:** the tanh model is idealised (constant drag, belly-down). Tumbling people fall at slightly different speeds. Round all figures and say "about".

---

## Beat 2: The spinning Earth (the core of the episode)

**Inputs (NASA Earth Fact Sheet):** "Equatorial radius (km) 6378.137" and "Sidereal rotation period (hrs) 23.9345".

**Calculation:** ω = 2π / (23.9345 × 3600 s) = 7.292×10⁻⁵ rad/s. Ground speed at the equator = ω·R = **465 m/s = 1,674 km/h = 1,040 mph**. At latitude φ, speed = 1,674 × cos φ.

| place | latitude | ground speed |
|---|---|---|
| Quito / Singapore | ~0° | 1,674 km/h (1,040 mph) |
| New York | 40.7° N | 1,269 km/h (789 mph) |
| Tokyo | 35.7° N | 1,360 km/h (845 mph) |
| London | 51.5° N | 1,042 km/h (**648 mph**) |
| North Pole | 90° | 0 |

**Watch out:** London is about **1,040 km/h**, while the equator is about **1,040 mph**. The same digits in different units could easily get mixed up in the script.

**Scenarios (Option A):**
1. **Equator → North Pole:** you arrive sliding sideways at **≈ 1,670 km/h**, because the ground at the pole only turns on the spot. The motion is all horizontal: you skid, you do not drop.
2. **Equator → the opposite side of the equator (antipode):** that ground moves the opposite way. Your speed relative to it is 2 × 465 = **930 m/s ≈ 3,350 km/h ≈ 2,080 mph**.
3. **New, and stronger: a quarter of the way around the equator.** Your old "east" points **straight up** if you jump 90° east, or **straight down** if you jump 90° west. Teleport from Quito (78.5° W) to 11.5° E, which is in Gabon (**geography to check on a map**), and you are thrown **up** at about 1,670 km/h. Jump 90° west instead, into the Pacific at about 168.5° W, and you are driven **down into the sea**. This is OUR REASONING from simple vector geometry. On top of the vertical motion, the ground there also slides sideways under you at 465 m/s.
4. **Comparison with sound:** NASA Glenn gives the speed of sound at sea level as "about 761 mph". So 1,040 mph ≈ **Mach 1.4**: you would cause a sonic boom in the air around you. This ties back to the super-speed episode's "sonic wall".

**Safe-distance rule (OUR REASONING):** for two points on a spinning rigid Earth, the speed mismatch is at most ω × distance.
- 1 km → 0.26 km/h (a slow stroll; safe)
- 10 km → 2.6 km/h (a walk)
- 100 km → 26 km/h (a fall off a bike)
- 1,000 km → 263 km/h (fatal)

The exact figure depends on direction; these are upper bounds. The line: **"Your commute is safe. Your holiday is not."**

**Surprise safe trip (OUR REASONING):** a point at the same longitude and the mirror latitude across the equator (for example 40.7° N → 40.7° S) has **exactly the same velocity vector**, so you arrive standing still. From New York (74° W) that point is on the Chilean coast. **UNVERIFIED geography: check on a map** (it may be offshore).

**Everyday image:** "At the equator, the ground under your feet is moving faster than a fighter jet... and you never feel it."
Avoid a specific jet speed: none was sourced. A safer version: "faster than sound."

**Risk:** frame confusion is the main risk. Show a globe seen from above the North Pole with arrows of different lengths. Never mention the Sun in this chapter.

---

## Beat 3: Earth's orbit (≈ 107,000 km/h): recommend NOT using it for jumps on Earth

**Fact (NASA Earth fact sheet):** "Mean orbital velocity (km/s) 29.78" = 107,200 km/h. The minimum and maximum are 29.29 and 30.29 km/s.

**Why it does not work for jumps on Earth:** every point on Earth shares the orbital velocity, so it cancels out. Option A and a "Sun frame" give the same result for any jump on Earth. The "12 hours later" version would need time travel, not teleportation. Even then, Earth's direction of travel turns only about 0.5° in 12 h, a mismatch of about 920 km/h. That is real but confusing. **Drop it.**

**Better replacement: teleport to the Moon or Mars.**
- **Moon:** NASA Moon fact sheet, "Mean orbital velocity 1.022 km/s" ≈ **3,680 km/h**. Teleport to the Moon and you arrive about that much out of step with it, plus or minus up to 465 m/s from Earth's spin. That is far more than the Moon's escape velocity of 2.38 km/s (same sheet), so **you miss the Moon's grip entirely** or hit the surface at rifle-like speed. "Rifle-like" is **UNVERIFIED**; say "faster than sound" instead.
- **Mars:** NASA Mars fact sheet, "Mean orbital velocity 24.08 km/s", against Earth's 29.78 km/s. The mismatch runs from about 5.7 km/s (planets on the same side of the Sun) to about 54 km/s (opposite sides). This is OUR REASONING, assuming idealised circular, coplanar orbits.

**Recommendation:** include the Moon as a one-line gag in the montage. Leave out the Sun frame.

---

## Beat 4: Altitude and depth (velocity is fine, the air isn't)

**Airliner cruise height: FAA Pilot's Handbook of Aeronautical Knowledge, Ch. 16, Figure 16-1 "Time of useful consciousness":**
"35,000 feet MSL 30 to 60 seconds" · "30,000 feet MSL 1 to 2 minutes" · "25,000 feet MSL 3 to 5 minutes" · "20,000 feet MSL 30 minutes or more"

**Air pressure:** NASA Glenn Earth Atmosphere Model, troposphere: p = 101.29·[(T+273.1)/288.08]^5.256 with T = 15.04 − 0.00649·h.
- 35,000 ft (10,668 m) → 23.9 kPa ≈ **24 % of sea-level air**, about one breath in four.
- 3,000 m → 69 %.

**Ears:** FAA PHAK Ch. 16 describes the eardrum bulging outward as you climb, and "fullness" and "clearing" sensations. Teleporting skips the gradual climb, so the change is instant. A painful pop is plausible; the size of the effect is **UNVERIFIED**.

**Deep sea (NOAA Ocean Service):** "For every 33 feet (10.06 meters) you go down, the pressure increases by one atmosphere."

**Depth of Challenger Deep:**
- **10,935 m ± 6 m.** Source: Greenaway et al. 2021, *Deep-Sea Research Part I* 178:103644 (NOAA authors), DOI 10.1016/j.dsr.2021.103644. Seen via search summary of the NOAA repository record only.
- NOAA NCEI quotes a 2010 survey: "10,994 meters (6.8 miles), plus or minus 40 meters".
- In the script, say **"about 11 km"**.

**Pressure calculation:** 10,935 / 10.06 + 1 ≈ **1,090 atm** ≈ 110 MPa ≈ 16,000 psi ≈ 1.1 tonnes per cm². This uses a constant-density approximation: real seawater is slightly compressible, so treat the figure as "about 1,000 atm".

**Everyday image:** "At the bottom of the deepest trench, every fingernail-sized patch of you carries the weight of a small car." 1 cm² × about 1.1 t; a small car is about 1 t, which is **UNVERIFIED** as a sourced figure but generic.

**Risk:** these beats are about *where* you land, not *speed*. Keep them to a short "other ways to die" montage so the speed premise stays the main thread.

---

## Beat 5: Arriving inside air (or a wall)

**OUR REASONING. No credible university or agency discussion was found.** The only relevant result was Davis, *Teleportation Physics Study* (2004), a report done for the US Air Force Research Laboratory under contract. It does not address this point.

- Your body is about 70 L. Arriving means about 70 L of air must be shoved aside instantly. That is roughly p·V ≈ 101 kPa × 0.07 m³ ≈ **7 kJ** of push, delivered in no time. The result is a **bang**, like a balloon bursting in reverse.
- Where you left, a 70 L hole of nothing collapses: a second **clap**.
- **Arriving inside a solid** means two things trying to fill the same space. Physics has no gentle answer. Play it as "Physics Says No".

**Everyday image:** "Every jump costs you two thunderclaps: one where you leave, one where you land." Thunder is the right analogy for a sudden pressure bang, but this beat is not sourced: keep it qualitative and add **no numbers**.

---

## Beat 6: The energy

**Standard:** NIST SP 811, Appendix B.8: "ton of TNT (energy equivalent) … 4.184 E+09" J (exact). That gives 1 kg TNT = 4.184 MJ.

**Calculation:** kinetic energy = ½·m·v², with m = 70 kg.

| speed | energy | in kg of TNT |
|---|---|---|
| 465 m/s (equator to pole) | 7.6 MJ | **≈ 1.8 kg TNT** |
| 930 m/s (antipode) | 30 MJ | ≈ 7.2 kg TNT |
| 1,022 m/s (Moon) | 37 MJ | ≈ 8.7 kg TNT |

**Car comparison:** a 1,500 kg car at 100 km/h has ½·1500·27.8² = 0.58 MJ. So **you, at equator speed, carry the crash energy of about 13 cars hitting a wall at motorway speed.** The car mass is an assumed typical value, not sourced.

**Everyday image:** prefer **"13 cars hitting a wall"**. TNT is less kid-friendly; the audience is 13+, so either works.

**Risk:** the energy goes into you and the ground. Do not imply an explosion crater.

---

## Beat 7: The good news

**ESA, Europe's Spaceport:** "Kourou lies at latitude 5°3', just over 500 km north of the equator." The Earth's rotation "increases the speed of a launcher by 460 m per second."
- Check: 465 × cos 5.05° = 463 m/s. ✔
- At Cape Canaveral (LC-39A, 28.6° N): 465 × cos 28.6° = **408 m/s ≈ 1,470 km/h (913 mph)**, computed by us. A NASA figure of "914 mph" was seen only second-hand, so **UNVERIFIED as a NASA quote**.

**Payoff:** orbit needs about 5 miles per second. NASA ISS facts: "a speed of five miles per second" ≈ 8 km/s. The equator gives a free **≈ 6 %** head start (463 / 7,800).

**The teleporting twist (OUR REASONING):**
1. Teleport a rocket, or yourself, to the equator **pointing east**. The planet's spin is no longer a trap: it is a gift.
2. Better: use the quarter-turn trick from beat 2 on purpose, so that Earth's spin throws you **upward**.

The end line: "The one time keeping your speed helps... is when you're trying to leave the planet."

**Alternative positive ending:** the mirror-latitude "safe twin city" (beat 2) as a practical travel tip.

---

## Recommended chapter order

1. **Cold open, window cleaner.** Teleport to the ground and they still hit at about 130 km/h. Teleport right after the slip and they're saved. This sets the rule.
2. **"The ground isn't still."** Earth spins at 1,670 km/h. Equator → North Pole means a sideways skid. Explain frames A and B in one line.
3. **Quarter-turn chaos.** Jump a quarter of the way around the world: east throws you into the sky, west drives you into the sea. The antipode doubles the speed. Energy: "13 cars".
4. **Safe-distance rule.** "Your commute is safe, your holiday is not" (1 km / 100 km / 1,000 km), plus the mirror-latitude safe twin.
5. **Other ways to die, montage.** Airliner height (30–60 s), trench (a car on a fingernail), the thunderclap pop, the Moon (miss it entirely).
6. **Payoff.** Rockets at the equator, ESA's 460 m/s, using the spin to leave the planet.

## 3 Short ideas (no numbers in the first 5 s)

1. **First frame:** stickman mid-air beside a skyscraper, teleport ring glowing below. **Line:** "Teleporting won't save you." (The falling window cleaner.)
2. **First frame:** stickman standing calmly on the equator line, globe spinning behind. **Line:** "You're already moving. Fast." (The pole skid.)
3. **First frame:** two stickmen on a globe, one in Quito, one in Gabon. **Line:** "Go east. Get launched." (The quarter-turn launch.)

## Sources used (all opened unless stated otherwise)

- NASA NSSDCA Earth Fact Sheet: https://nssdc.gsfc.nasa.gov/planetary/factsheet/earthfact.html
- NASA NSSDCA Moon Fact Sheet: https://nssdc.gsfc.nasa.gov/planetary/factsheet/moonfact.html
- NASA NSSDCA Mars Fact Sheet: https://nssdc.gsfc.nasa.gov/planetary/factsheet/marsfact.html
- NASA Glenn, Earth Atmosphere Model (metric): https://www.grc.nasa.gov/www/k-12/airplane/atmosmet.html
- NASA Glenn, Speed of Sound: https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/speed-of-sound-interactive/
- NASA Glenn, Terminal Velocity (formula only, no skydiver number): https://www.grc.nasa.gov/WWW/k-12/VirtualAero/BottleRocket/airplane/termvr.html
- NASA, Space Station Facts and Figures: https://www.nasa.gov/international-space-station/space-station-facts-and-figures/
- FAA, Pilot's Handbook of Aeronautical Knowledge (FAA-H-8083-25A) Ch. 16, Fig. 16-1, ears: https://www.faasafety.gov/files/notices/2014/Dec/FAA-H-8083-25A_Pilot's_Hdbk_of_Aeronautical_Knowledge_CH-16.pdf
- NOAA Ocean Service, water pressure: https://oceanservice.noaa.gov/facts/pressure.html
- NOAA NCEI, Challenger Deep: https://www.ncei.noaa.gov/node/239
- Greenaway et al. 2021, Deep-Sea Res. I 178:103644 (NOAA repository): https://repository.library.noaa.gov/view/noaa/33477 (seen via search summary only)
- NIST SP 811, Appendix B.8: https://www.nist.gov/pml/special-publication-811/nist-guide-si-appendix-b-conversion-factors/nist-guide-si-appendix-b8
- ESA, Europe's Spaceport: https://www.esa.int/Enabling_Support/Space_Transportation/Europe_s_Spaceport/Europe_s_Spaceport2
- Davis, L., *Body Physics: Motion to Metabolism* (Umpqua CC / LibreTexts), §8.03–8.04: https://phys.libretexts.org/Bookshelves/Conceptual_Physics/Body_Physics_-_Motion_to_Metabolism_(Davis)/08%3A_Skydiving
- CTBUH height calculator (third-party mirror only, so UNVERIFIED): https://pdfcoffee.com/ctbuh-tall-building-height-calculator-pdf-free.html

**Not used / failed:**
- The FAA AC 61-107B returned 403, so the PHAK was used instead.
- No FAI page was found for terminal velocity.
- No authoritative source was found for the air-displacement pop.
