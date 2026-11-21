# Fact-check report — The Air-Powered Clocks of Paris (2026-11-21)

Method: four research passes (history, mechanics, power network, 1910 flood; `research/*.md`), then three
independent fact-checkers on shots #1–45, #46–87 and #88–118 against primary sources: La Nature (Hospitalier,
1880), Nature (1880), Berly (Journal of the Society of Arts, 1881), Kennedy (1889, in Idell 1892), Histoire de la
SUDAC (1996), Dikeç (Urban History, 2025), Payer, Mayrhofer (1882), DRIEAT 1910 bulletins, Archives de Paris,
Le Petit Parisien (23 Jan 1910), POP Mérimée PA00133012. All fixes below were applied to `script_source.py`.

## Corrections applied (34)
| Shot | Was | Now | Reason / source |
|---|---|---|---|
| 5 | For thirty years | For nearly thirty years | 15 Mar 1880 → 21 Jan 1910 |
| 6 | from a single machine room | from one central plant | in 1910 the air came from quai de la Gare (SUDAC) |
| 10 | The same pipes grew into a network … | The same company went on to build a far bigger network … | power used separate 300 mm mains (SUDAC p.12, Kennedy) |
| 11 | minutes within a week | minutes within a month | arithmetic |
| 18 | moved forward together, once a minute | at first every two minutes, later every minute | Berly 1881 on Vienna |
| 25 | master clock upstairs | above them, the master clock and a shop | SUDAC sources conflict on the floor |
| 27 | one Paris hotel | the Hôtel Meurice | Berly 1881 ("148 pneumatic clocks") |
| 28 | By the end of 1881 | By late 1881 | Berly, published 2 Dec 1881 |
| 30 | to the whole city | across central Paris | 1881 service: 1st and 2nd arrondissements (Berly) |
| 44 | Once a day | At first, once a day | La Nature 1880: stopgap until an electric link |
| 53 | the pulse arrived around fifteen seconds | could not move until at least fifteen seconds | 340 m/s is the minimum; friction slows the rise |
| 58 | forty-second pause let the pipes settle | twenty seconds of pressure was enough despite the losses | Berly; no source links the 40 s to leaks |
| 64 | could never move it two teeth | each breath moved the wheel just one tooth | stops limit travel; the click prevents double steps |
| 70 | wind their chimes | wind their striking spring | Nature 1880, Berly |
| 72 | the company signed a treaty | Victor Popp signed a treaty … customers' premises | SUDAC p.21 (in his own name) |
| 76 | He counted 225 | A list he was given showed 225 … nearly all motors | Kennedy 1889 |
| 81 | over long pipes much of the work was lost | lost as heat when squeezed and cold when expanding | Kennedy's table: the main lost very little |
| 83 | about half … came out as useful work | ~10 hp per 20 hp at the plant counting coke; 35 without heating | Kennedy 1889 summary |
| 86 | The clock network had become an energy network | The clock company had become an energy company | separate networks |
| 87 | most of its money | almost all of its money | ~97 % of revenue in 1900 (SUDAC p.55) |
| 92 | pressure in the pipes fell away | the pipes lost their pressure | wording |
| 96 | metro lines were under water | metro lines were flooded too | DRIEAT 29 Jan, Archives de Paris |
| 98 | pipes blown clear | water had to be purged from the pipes | SUDAC p.56 |
| 100 | never a good business | never much of a business | per-dial profit after 1883, thin margin |
| 104 | electric clock networks were taking over | radio time signals were spreading, electric clocks offered a simpler alternative | SUDAC p.69 |
| 113 | Then industry left … old lifts were replaced | After that, industry moved out … last air-driven lifts disappeared | SUDAC pp.121–124 |
| 114 | Paris shut down its public network | the city ended the concession, public supply … came to an end | SUDAC pp.135–136 (SUDAC Air Service continued privately) |
| 115 | The great plant … iron hall … protected | Part of the great plant on the former quai de la Gare … metal hall and brick chimney … listed | POP Mérimée PA00133012 |
| 117 | Paris told the time by breathing | part of Paris told the time by breathing | ~100 public dials, ≤7,800 private |
| titles | ~15 s · 5 km; ~50% | ≥15 s · 5 km; 10 hp per 20 hp | as above |

## Confirmed key facts (selection)
- 21 Jan 1910 (Friday) evening, all pneumatic clocks stopped between 10:48 and 10:53 (Le Petit Parisien 23 Jan 1910; SUDAC "22h53"); plant at quai de la Gare flooded; back 3 Feb after 13 days (SUDAC).
- Seine ~1 m/day; peak 8.62 m at Austerlitz on 28 Jan 1910; ~20,000 buildings flooded (DRIEAT, Archives de Paris).
- Vienna service from 24 Feb 1877; ~3½ years; judged too inaccurate (Payer, Mayrhofer 1882). Mayrhofer telegraph engineer and patent holder; Popp and Resch (Payer, Wien Museum).
- 1878 silver medal; Nov 1878 trial in the sewers; 15 Mar 1880 inauguration; 7 rue Sainte-Anne; 5 c/day (SUDAC, Berly, La Nature).
- Station: 8 m³ at 5 atm; 0.7 atm distribution; two movements; 20 s air / 40 s vented at the 60th second; self-winding pistons; duplicate clock, alarms; daily manual correction to the Observatory (La Nature 1880, Nature 1880, Berly 1881).
- Ten 27 mm wrought-iron mains in the sewers; lead 15/6/3 mm; rubber bellows, lever and pawl, 60-tooth wheel; clocks within ~4 s in 1881 (Dikeç).
- Power: 1886 treaty; Saint-Fargeau, 5 atm, 300 mm main, >2,000 ihp at peak (Kennedy 1889); 225 installations; users list; dynamos; cold exhaust in a beer cellar; quai de la Gare 1892, 4 × 1,800 hp; 163.6 km of mains in 1900; electricity ~97 % of revenue (SUDAC).
- End: 1880 revenue 16.90 F vs cost 60.70 F per dial; peak 7,800 dials (1884); 5,018 dials / 919 subscribers (1926); licence expired 1 Mar 1927, not renewed; customers to Magneta; pipes removed (SUDAC).
- Later: 525 km (1930), 941 km (1970); sales peak 1973; concession ended 1994; plant hall and chimney listed 1994; ENSA Paris-Val de Seine since 2007.

## Competitor errors we avoid
"flash flood"; "all clocks stopped at exactly 10:50"; "created in 1880 by Popp"; "pulse took up to a minute";
"hundreds of km through sewers and metro tunnels" for the clock network; "30 cents a day".

## Remaining caveats
- Single-source items (SUDAC): 13-day interruption and the purge; Magneta. Popp's death year unknown (not used).
- The 1910 newspaper quote is via a secondary transcription linking RetroNews (Gallica blocked automated access).
