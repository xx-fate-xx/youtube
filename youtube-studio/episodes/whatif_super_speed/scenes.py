"""Visual sequences for the super-speed pilot, script v2 (rescues). Shot numbers: frames.txt (76 shots, made by
script_source.py from the approved script.md). Uncovered shots render as placeholder cards.

Story 1 (shots 1-17) happens at one tower: a tall painted background (bg/tower.png: sky, distant towers, street
at the bottom) and the tower itself drawn here as a dark vector slab, so the camera can travel 30 floors.
Physics is real time and real scale unless marked "slow motion": the fall uses quadratic drag (terminal velocity
55 m/s, factcheck_report.md row 1); the numbers on screen are the ones in script.md calc_notes.

The v1 scenes (speed levels) are kept in scenes_levels_v1.py as a reference for the DSL.
"""

import math

from studio.whatif import fx, overlay
from studio.whatif.comic import (
    Comic,
    card,
    chalk_arrow,
    chalk_line,
    chalk_note,
    label,
    punch,
    scrim,
)
from studio.whatif.scene import Seq, arrow, note, sketch

G = 745                      # street level (screen y at camera offset 0), on the painted sidewalk of bg/tower
VT, GR = 55.0, 9.81          # terminal velocity (m/s), gravity
FT_PER_M = 3.2808
FLOORS, FLOOR_FT = 30, 10    # ~300 ft


def fall_m(tau: float) -> float:
    """Metres fallen after tau seconds from rest, quadratic drag."""
    return VT * VT / GR * math.log(math.cosh(GR * max(tau, 0.0) / VT))


def fall_v(tau: float) -> float:
    return VT * math.tanh(GR * max(tau, 0.0) / VT)


def fall_time(m: float) -> float:
    lo, hi = 0.0, 20.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if fall_m(mid) < m else (lo, mid)
    return lo


def mph(v: float) -> float:
    return v * 2.23694


def ease(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


# ---------------------------------------------------------------- props (world coordinates)

def tower(S: float, wall: float, width: float = 900):
    """The tower's facade as a dark slab right of x=wall: floors of glass bands and concrete spandrels."""
    fh = FLOOR_FT * S
    top = G - FLOORS * fh

    def draw(ctx: dict) -> str:
        out = [f'<rect x="{wall:.0f}" y="{top - 0.5 * fh:.0f}" width="{width}" height="{G + 400 - top + 0.5 * fh:.0f}" '
               f'fill="#232B38"/>',
               f'<rect x="{wall - 8:.0f}" y="{top - 0.55 * fh:.0f}" width="{width + 8}" height="{0.12 * fh:.0f}" '
               f'fill="#3A4454"/>']
        for k in range(FLOORS):
            y = G - (k + 1) * fh
            out.append(f'<rect x="{wall:.0f}" y="{y + 0.12 * fh:.0f}" width="{width}" height="{0.62 * fh:.0f}" '
                       f'fill="#2E4561"/>')
            out.append(f'<rect x="{wall:.0f}" y="{y + 0.12 * fh:.0f}" width="{width}" height="{0.10 * fh:.0f}" '
                       f'fill="#4F7194" opacity="0.55"/>')
            for m in range(int(width / (5 * S)) + 1):
                mx = wall + 18 + m * 5 * S
                out.append(f'<rect x="{mx:.0f}" y="{y + 0.12 * fh:.0f}" width="{max(3, 0.25 * S):.0f}" '
                           f'height="{0.62 * fh:.0f}" fill="#1B2330"/>')
            out.append(f'<rect x="{wall - 6:.0f}" y="{y + 0.74 * fh:.0f}" width="{width + 6}" '
                       f'height="{max(3, 0.08 * fh):.0f}" fill="#3A4454"/>')
        out.append(f'<rect x="{wall - 3:.0f}" y="{top - 0.5 * fh:.0f}" width="6" height="{G - top + 0.5 * fh:.0f}" '
                   f'fill="#6B7A90"/>')
        out.append(f'<rect x="{wall:.0f}" y="{G - 0.9 * fh:.0f}" width="{width}" height="{0.9 * fh:.0f}" '
                   f'fill="#3E5878"/>')
        return "".join(out)
    return draw


def cradle(S: float, wall: float, y: float):
    """Window-cleaning platform hanging on two cables from the roof."""
    top = G - FLOORS * FLOOR_FT * S
    x0, x1 = wall - 9 * S, wall - 0.4 * S

    def draw(ctx: dict) -> str:
        rail = y - 3.4 * S
        return (f'<path d="M{x0 + 0.4 * S:.0f},{rail:.0f} L{x0 + 0.4 * S:.0f},{top:.0f} M{x1 - 0.4 * S:.0f},{rail:.0f} '
                f'L{x1 - 0.4 * S:.0f},{top:.0f}" stroke="#AEB6C2" stroke-width="2"/>'
                f'<rect x="{x0:.0f}" y="{y:.0f}" width="{x1 - x0:.0f}" height="{0.5 * S:.0f}" fill="#C9CED6"/>'
                f'<path d="M{x0:.0f},{y:.0f} L{x0:.0f},{rail:.0f} L{x1:.0f},{rail:.0f} L{x1:.0f},{y:.0f}" '
                f'stroke="#C9CED6" stroke-width="{max(3, 0.18 * S):.0f}" fill="none"/>')
    return draw


def tape(S: float, wall: float, feet: int, show_from):
    """Chalk measuring marks up the wall (every 10 ft), drawn upward from `show_from()` (clip seconds)."""
    from studio.whatif import overlay

    def draw(ctx: dict) -> str:
        u = ctx["t"] - show_from()
        if u <= 0:
            return ""
        x = wall - 40
        out = [overlay.chalk_line([(x, G), (x, G - feet * S)], u / 3.0, 5, seed=21, rough=False)]
        for k in range(10, feet + 1, 10):
            if u / 3.0 * feet > k:
                y = G - k * S
                out.append(overlay.chalk_line([(x - 22, y), (x + 4, y)], 1.0, 4, seed=k, rough=False))
                out.append(overlay.chalk_text(x - 34, y + 12, f"{k} ft", 34, 1.0, anchor="end"))
        return "".join(out)
    return draw


# ---------------------------------------------------------------- the arm catch (shots 3-5, replayed in 8-9)

def arm_catch(s: Seq, S: float, wall: float, zip_at, contact_at, start_x: float = 260):
    """You zip to the tower and catch the falling cleaner in your arms. zip_at / contact_at: motion-time getters.
    Returns (hero, cleaner)."""
    h = 6 * S
    xc = wall - 4.6 * S
    v_px = fall_v(fall_time(300 * 0.3048)) * FT_PER_M * S           # ~85 mph in px/s
    y_contact = G - 0.75 * h + h / 2                                  # cleaner's centre at your hands

    def hero_path(mt):
        u = ease((mt - zip_at()) / 0.22)
        return start_x + (xc - start_x) * u, G, 0.0

    def cleaner_path(mt):
        dt = min(0.0, mt - contact_at())
        return xc + 0.55 * h, y_contact + v_px * dt, -78.0 - 25 * dt

    hero = s.actor(x=start_x, h=h, hero=True).along(hero_path)
    hero.play("stand", at=0.0)
    cleaner = s.actor(x=xc, h=h * 0.97, name="cleaner", hat="vest").along(cleaner_path, pivot="center")
    cleaner.play("scared", at=0.0)
    return hero, cleaner


S2, W2 = 40.0, 1460.0


def shots_1_2():
    # 1-2  Cold open: the window cleaner slips off the 30th floor; the camera falls with them; freeze just above
    #      the street (never the impact).
    S1, W1 = 22.0, 1380.0
    s = Seq(shots=(1, 2), bg="tower", ground=G, tall=True, parallax_y=0.35, push=(1.0, 1.03))
    y30 = G - 300 * S1
    s.prop(tower(S1, W1))
    s.prop(cradle(S1, W1, y30))
    slip = s.at(1, 1.8)
    t_fall = fall_time((300 - 5) * 0.3048)                    # freeze ~5 ft above the street

    def cleaner_fall(mt):
        tau = mt - s.T(slip)
        if tau <= 0:
            return W1 - 4.6 * S1, y30, 0.0
        y = min(G, y30 + fall_m(tau) * FT_PER_M * S1)
        return W1 - 4.6 * S1 - 3.2 * S1 * ease(tau / 0.6), y, -min(75.0, 32 * tau)

    cl = s.actor(x=W1 - 100, h=6 * S1, name="cleaner", hat="vest").along(cleaner_fall, pivot="center")
    cl.play("look_around", at=0.0)
    cl.play("scared", at=slip, blend=0.15)
    cl.pose_arms("reach", at=s.at(1, 1.7), until=s.at(1, 2.6), blend=0.12)

    def cam1(mt):
        tau = mt - s.T(slip)
        y = y30 if tau <= 0 else min(G, y30 + fall_m(tau) * FT_PER_M * S1)
        return 0.0, max(0.0, 560 - (y - 3 * S1))
    s.camera(cam1)
    s.hud("FALLING", lambda mt: f"{mph(fall_v(mt - s.T(slip))):.0f} mph", "300 ft · 91 m drop", slip, s.end())
    s.freeze(s.at(1, 1.8 + t_fall), s.end(), [
        arrow(-300, -160, -60, -20, t=0.2, anchor="cleaner"),
        note(-560, -175, "≈ 85 mph · 135 km/h", 46, t=0.5, anchor="cleaner"),
        note(-560, -125, "after 4.5 seconds", 36, t=1.0, weight=500, anchor="cleaner"),
    ])
    return s


def shots_3_5():
    # 3-5  "But today, you're down there": you zip to the tower and catch them in your arms. Freeze at the
    #      moment of contact (never the outcome); "unbreakable" vs "not".
    s = Seq(shots=(3, 5), bg="tower", ground=G, tall=True, parallax_y=0.35, push=(1.0, 1.04))
    s.prop(tower(S2, W2))
    zip_b, contact_b = s.at(3, 2.0), s.at(4, 2.9)
    hero, cleaner = arm_catch(s, S2, W2, lambda: s.T(zip_b), lambda: s.T(contact_b))
    hero.run(zip_b, cadence=3.0, blend=0.05)
    hero.play("stand", at=s.at(3, 2.25), blend=0.15)
    hero.pose_arms("catch", at=s.at(4, 1.3))
    for x, hh, ph in ((-200, 225, 3), (520, 215, 11)):
        s.actor(x=x, h=hh, ground=G - 8).walk(0.0, phase=ph)
    s.cut(s.at(3, 2.6), 1.45, x=0.62, y=0.62)
    s.freeze(contact_b, s.end(), [
        arrow(-260, -250, -40, -60, t=0.2, anchor="cleaner"),
        note(-560, -265, "≈ 85 mph", 50, t=0.5, weight=800, family="Inter Display", anchor="cleaner"),
        note(-560, -215, "stops in about 1.5 ft", 38, t=1.0, anchor="cleaner"),
        note(-470, 40, "unbreakable", 46, t=2.0, anchor="hero"),
        note(130, 120, "not", 60, t=3.2, weight=800, family="Inter Display", anchor="cleaner"),
    ])
    return s


def shots_6_7():
    # 6-7  Title + the freeze-frame device, on the city street.
    s = Seq(shots=(6, 7), bg="city", ground=975, push=(1.0, 1.05))
    s.actor(x=520, h=250, hero=True).walk(0.0)
    s.actor(x=1500, h=215, ground=955, flip=True, hat="backpack").walk_b(0.0, phase=4)
    s.actor(x=1150, h=200, ground=945).walk(0.0, phase=12)
    s.title(["What if you had", "super speed?"], 0.4, s.at(7))
    s.freeze(s.at(7, 1.0), s.end(), [
        arrow(330, -170, 60, -40, t=0.2),
        note(345, -185, "freeze", 52, t=0.5, weight=800, family="Inter Display", anchor="hero"),
        note(345, -135, "= time to look at the physics", 38, t=0.9, anchor="hero"),
    ])
    return s


def shots_8_9():
    # 8-9  Rewind the catch, replay it, freeze at contact: 1.5 ft -> ~140 g.
    s = Seq(shots=(8, 9), bg="tower", ground=G, tall=True, parallax_y=0.35, push=(1.0, 1.04), t0=2.0)
    s.prop(tower(S2, W2))
    hero, cleaner = arm_catch(s, S2, W2, lambda: 0.9, lambda: 2.0)
    hero.run(0.9, cadence=3.0, blend=0.05)
    hero.play("stand", at=1.15, blend=0.15)
    hero.pose_arms("catch", at=0.0)
    s.freeze(0.0, 0.45, [])
    s.rewind(0.45, 1.45, speed=1.2)                    # motion 2.0 -> 0.8: the cleaner flies back up
    s.card("RESCUE 1", "The fall", 0.6, s.end())
    s.cut(0.0, 1.45, x=0.62, y=0.62)
    s.cut(2.0, 2.1, focus="cleaner", x=0.5, y=0.45)    # close on the catch
    s.freeze(2.65, s.end(), [                        # motion 2.0 = contact (after the rewind)
        arrow(-250, -230, -40, -50, t=0.2, anchor="cleaner"),
        note(-470, -245, "≈ 85 mph", 46, t=0.4, weight=800, family="Inter Display", anchor="cleaner"),
        sketch([[(-90, 95), (-90, 135)], [(-110, 95), (-70, 95)], [(-110, 135), (-70, 135)]], t=3.4, d=0.5,
               anchor="cleaner"),
        note(-60, 128, "1.5 ft", 40, t=3.8, anchor="cleaner"),
        note(-470, 230, "→ ≈ 140 g", 64, t=4.6, d=0.4, weight=800, family="Inter Display",
             anchor="cleaner"),
    ])
    return s


def shots_10_12():
    # 10-12  Chalkboard: Stapp's rocket sled (> 40 g, strapped in), then roller coasters (4-6 g, briefly).
    s = Seq(shots=(10, 12), bg="tower", ground=G, tall=True, parallax_y=0.35, push=(1.0, 1.05))
    s.prop(tower(S2, W2))
    s.actor(x=W2 - 4.6 * S2, h=6 * S2, hero=True).play("stand", at=0.0)
    s.board(0.2, s.end(), 0.62)
    rail = [[(150, 640), (1250, 640)]]
    sled = [[(600, 640), (600, 560), (880, 560), (930, 610), (930, 640)], [(700, 560), (700, 470), (760, 470)],
            [(580, 585), (500, 575)], [(580, 605), (470, 610)], [(580, 625), (510, 640)]]
    rider = [[(735, 470), (735, 400)], [(735, 400), (785, 425)], [(735, 455), (795, 500)]]
    s.freeze(0.3, s.at(12), [
        sketch(rail + sled + rider, t=0.2, d=2.0),
        note(150, 250, "John Paul Stapp · 1954", 44, t=1.6),
        note(150, 330, "> 600 mph → 0", 64, t=2.6, d=0.5, weight=800, family="Inter Display"),
        note(150, 400, "over 40 g · strapped in", 42, t=4.0),
        note(150, 780, "bruised · vision gone for minutes", 40, t=8.0),
    ])
    coaster = [[(180, 300), (330, 300), (420, 360), (520, 640), (600, 700), (760, 700), (880, 600), (980, 560),
                (1200, 560)]]
    s.freeze(s.at(12), s.end(), [
        sketch(coaster, t=0.1, d=1.4),
        note(180, 820, "biggest roller coasters:", 42, t=1.2),
        note(180, 900, "4 – 6 g, for a moment", 60, t=1.8, d=0.5, weight=800, family="Inter Display"),
    ])
    return s


def shots_13_13():
    # 13  "Almost sixty feet to slow them down": the camera tilts up a chalk tape on the wall.
    s = Seq(shots=(13, 13), bg="tower", ground=G, tall=True, parallax_y=0.35, push=(1.0, 1.0))
    s.prop(tower(S2, W2))
    tape_at = s.at(13, 0.3)
    s.prop(tape(S2, W2, 60, lambda: s.T(tape_at)), front=True)
    s.actor(x=W2 - 4.6 * S2, h=6 * S2, hero=True).play("stand", at=0.0)
    tilt0, tilt1 = s.at(13, 0.6), s.at(13, 4.2)

    def cam13(mt):
        u = ease((mt - s.T(tilt0)) / max(0.1, s.T(tilt1) - s.T(tilt0)))
        return 0.0, u * (60 * S2 - 520)
    s.camera(cam13)
    s.freeze(s.at(13, 4.4), s.end(), [
        note(1000, 200, "60 ft · 18 m", 64, t=0.1, d=0.5, weight=800, family="Inter Display"),
        note(1000, 270, "→ under 4 g", 50, t=0.7),
        note(1000, 340, "can't wait at the bottom", 40, t=1.4, weight=500),
    ])
    return s


def shots_14_17():
    # 14-17  The move (slow motion x3): super grip, up the wall, match their speed, brake over the last 60 ft.
    S3, W3 = 40.0, 1460.0
    SLOW = 3.0
    s = Seq(shots=(14, 17), bg="tower", ground=G, tall=True, parallax_y=0.19, push=(1.0, 1.03))
    s.prop(tower(S3, W3))
    h = 6 * S3
    y30 = G - 300 * S3
    s.prop(cradle(S3, W3, y30))
    m2 = FT_PER_M * S3
    go = s.at(14, 0.5)                              # the cleaner slips (off screen, far above)
    run_p = 0.45                                    # you start up the wall (physical seconds after the slip)
    U = 110.0 * m2                                  # up the wall at ~250 mph (px per physical second)

    FAST = 1.15                                     # after the freeze: close to real time, so you land in shot 16
    p_frz = None                                    # physical time of the freeze (set below, once p_match is known)

    def P(mt):                                      # physical seconds since the slip: x3 slow, then ~real time
        m = max(0.0, mt - s.T(go))
        mf = p_frz * SLOW
        return m / SLOW if m <= mf else p_frz + (m - mf) / FAST

    def yf(p):                                      # cleaner's centre height, free fall
        return y30 - h / 2 + fall_m(p) * m2

    def up(p):                                      # your body height on the wall on the way up
        return G - 0.62 * h - U * max(0.0, p - run_p)
    lo, hi = run_p, 8.0                             # turn point: you pass 4 m above them
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if up(mid) > yf(mid) - 4 * m2 else (lo, mid)
    p_turn = lo
    p_match = p_turn + 0.12
    p_grab = p_match + 0.25
    p_frz = p_match + 0.1
    v_g = fall_v(p_grab)                            # m/s when you take hold
    y_g = yf(p_grab)
    y_brake = G - 60 * S3 - 0.3 * h                 # brake over the last 60 ft
    p_brake = p_grab + (y_brake - y_g) / (v_g * m2)
    a_brake = v_g * v_g / (2 * (60 * 0.3048))
    p_stop = p_brake + v_g / a_brake

    def y_pair(p):                                  # height of the two of you after the grab
        if p <= p_brake:
            return y_g + v_g * m2 * (p - p_grab)
        q = min(p, p_stop) - p_brake
        return y_brake + (v_g * q - 0.5 * a_brake * q * q) * m2

    def hero_path(mt):
        p = P(mt)
        if p <= run_p:
            return W3 - 0.4 * S3, G, 0.0
        if p <= p_turn:                             # feet on the wall, facing up
            return W3, up(p), -90.0
        if p <= p_grab:                             # turned: facing down, closing on them
            k = ease((p - p_turn) / (p_match - p_turn))
            return W3, up(p_turn) * (1 - k) + yf(p) * k, -90.0, True
        y = y_pair(p)
        if p < p_stop:
            return W3, y, -90.0, True
        k = ease((p - p_stop) / 0.12)               # step off the wall onto the street
        return W3 - 2.2 * S3 * k, y + (G - y) * k, -90.0 * (1 - k), True

    def cleaner_path(mt):
        p = P(mt)
        if p <= p_grab:
            return W3 - 4.6 * S3 - 2.0 * S3 * ease(p / 0.6), yf(p) + h / 2, -min(75.0, 32 * p)
        y = y_pair(p)
        if p < p_stop:
            return W3 - 1.07 * h, y + h / 2, -80.0
        k = ease((p - p_stop) / 0.15)
        return W3 - 1.07 * h - 0.6 * h * k, y + h / 2 + (G - y - h / 2) * k, -80.0 * (1 - k)

    hero = s.actor(x=W3, h=h, hero=True).along(hero_path)
    hero.play("stand", at=0.0)

    def t_of(p):                                    # physical time -> clip time (the freeze ends at shot 16)
        return s.at(14, 0.5 + p * SLOW) if p <= p_frz else s.at(16, (p - p_frz) * FAST)
    hero.run(t_of(run_p), cadence=3.2, blend=0.05)
    hero.pose_arms("reach", at=t_of(p_match), until=t_of(p_grab), blend=0.1)
    hero.pose_arms("carry", at=t_of(p_grab), blend=0.15)
    hero.play("stand", at=t_of(p_stop), blend=0.3)
    cleaner = s.actor(x=W3 - 200, h=h * 0.97, name="cleaner", hat="vest").along(cleaner_path, pivot="center")
    cleaner.play("scared", at=0.0)
    cleaner.play("stand", at=t_of(p_stop + 0.1), blend=0.4)

    def cam14(mt):
        p = P(mt)
        if p <= run_p:
            y = G - 0.62 * h
        elif p <= p_turn:
            y = up(p)
        elif p <= p_grab:
            y = yf(p)
        else:
            y = y_pair(p)
        return 0.0, max(0.0, 540 - y)
    s.camera(cam14)

    def grip_label(ctx):
        op = max(0.0, min(1.0, (ctx["t"] - s.T(s.at(14, 1.2))) / 0.3)) * (1 - max(0.0, min(1.0, P(ctx["mt"]) - run_p)))
        return (f'<text x="{W3 - 30:.0f}" y="{G - 30:.0f}" font-family="Inter" font-weight="700" font-size="40" '
                f'fill="#F4F1E8" text-anchor="end" opacity="{op:.2f}">+ super grip</text>')
    s.prop(grip_label, front=True)
    s.hud("ON THEM", lambda mt: f"{(1 + a_brake / GR) if p_brake <= P(mt) < p_stop else 1.0:.1f} g",
          "keep it under 4 g", t_of(p_grab), s.at(17, 1.8))
    v_m = mph(fall_v(p_match))
    s.freeze(t_of(p_frz), s.at(16), [
        arrow(-300, -120, -80, -10, t=0.2, anchor="cleaner"),
        note(-620, -135, f"them: ↓ {v_m:.0f} mph", 46, t=0.4, weight=800, family="Inter Display",
             anchor="cleaner"),
        note(-620, -80, f"you: ↓ {v_m:.0f} mph", 40, t=1.0, anchor="cleaner"),
        note(-620, 0, "same speed = nothing hits", 40, t=1.8, anchor="cleaner"),
    ])
    s.title(["Lesson one:", "stop slowly."], s.at(17, 2.0), s.end())
    return s



# ---------------------------------------------------------------- motion comic (format approved 2026-11-22)

def cold_open():
    """Shots 1-5: the window cleaner slips; the fall is never shown landing; rewind; you catch them; YOU / THEM.
    Art: art/tower_plate(.png, _front.png), sprites hero0-7 and cleaner0-5 (sprites.json). Timings follow the
    narration (offsets inside each shot)."""
    c = Comic(shots=(1, 5), plate="tower_plate", fade_out=0.6)
    GR, FLOOR = 1362, (2085, 316)
    c.cast("hero", height=520 * 499 / 640, ref="hero7")
    c.cast("cleaner", height=520 * 499 / 640 * 0.98, ref="cleaner0", persp=(FLOOR[1], GR, 0.24))
    at = c.at

    # shot 1: on the platform, slip, over the rail -> freeze with the height
    c.key("cleaner", 0.0, "cleaner0", *FLOOR)
    c.key("cleaner", at(1, 1.4), "cleaner1", FLOOR[0] - 15, FLOOR[1] - 2)
    c.key("cleaner", at(1, 2.0), "cleaner2", FLOOR[0] - 60, FLOOR[1] + 40)
    c.key("cleaner", at(1, 3.4), "cleaner2", FLOOR[0] - 170, FLOOR[1] + 300, ang=-15, tween="ease")
    c.front(0.0, at(1, 2.6))
    c.sfx(at(1, 1.3), "sfx_slip", 0.45)
    c.shake(at(1, 1.35), 0.25, 10)
    c.cam(0.0, 2120, 330, 1050)
    c.cam(at(1, 2.3), 2080, 380, 1150)
    c.cam(at(1, 3.6), 1344, 760, 2688)
    c.freeze(at(1, 3.4), at(2, 0.15), [
        scrim(1450, 520, 700, 520),
        chalk_line([(1330, 230), (1330, 980)], 0.0, 0.8),
        chalk_line([(1300, 230), (1360, 230)], 0.0, 0.3, 5, 4),
        chalk_line([(1300, 980), (1360, 980)], 0.6, 0.3, 5, 5),
        chalk_note(1390, 560, "300 ft", 92, 0.5, 0.4, 800, "Inter Display"),
        chalk_note(1394, 630, "≈ 91 m · 30 floors", 40, 1.0, 0.5),
    ])

    # shot 2: the fall with a live speed counter; cut to black on 85 mph (never the impact)
    c.key("cleaner", at(2, 0.2), "cleaner3", 1915, 616)
    c.key("cleaner", at(2, 2.9), "cleaner3", 1875, 1316, tween="in")
    c.hide("cleaner", at(2, 2.9))
    c.sfx(at(2, 0.35), "sfx_fall", 0.4)
    c.cam(at(2, 0.8), 1500, 700, 2100)
    c.cam(at(2, 2.8), 1450, 1000, 1900)

    def falling(u: float, _t: float) -> str:
        k = min(1.0, u / 2.6)
        return overlay.hud("FALLING", f"{85 * math.tanh(2.2 * k) / math.tanh(2.2):.0f} mph", f"{4.5 * k:.1f} s",
                           1.0, 1.0)
    c.text(at(2, 0.3), at(2, 2.9), falling)
    c.flash(at(2, 2.9), 0.18)
    c.text(at(2, 3.0), at(3, 0.0), card("85 mph", "4.5 seconds after the slip"))

    # shot 3: rewind, you're down there, the dash, unbreakable
    c.cam(at(3, 0.0), 1344, 760, 2688, "hold")
    c.key("cleaner", at(3, 0.0), "cleaner3", 1875, 1316, ang=0)
    c.key("cleaner", at(3, 0.5), "cleaner3", 1915, 316, ang=180, tween="ease")
    c.hide("cleaner", at(3, 0.55))
    c.rewind(at(3, 0.0), at(3, 0.55))
    c.sfx(at(3, 0.0), "sfx_rewind", 0.35)
    c.key("hero", at(3, 0.6), "hero0", 560, GR)
    c.cam(at(3, 0.6), 760, 1020, 1450, "hold")
    c.text(at(3, 0.7), at(3, 2.1), label(110, 170, "TODAY:", "you're down there"))
    c.key("hero", at(3, 2.15), "hero1", 560, GR)
    c.cam(at(3, 2.2), 700, 1030, 1350)
    c.key("hero", at(3, 2.48), "hero2", 560, GR)
    c.key("hero", at(3, 2.75), "hero3", 1640, GR, tween="snap", smear=True)
    c.speed_lines(at(3, 2.45), at(3, 2.9))
    c.whip(at(3, 2.45), at(3, 2.85))
    c.sfx(at(3, 2.42), "sfx_dash", 0.5)
    c.sfx(at(3, 2.75), "sfx_skid", 0.45)
    c.draw(at(3, 2.75), at(4, 0.0), fx.dust(1640, GR, size=150, seed=44))
    c.draw(at(3, 2.48), at(4, 0.0), fx.dust(560, GR, size=110, seed=45))
    c.cam(at(3, 2.45), 760, 1020, 1450)
    c.cam(at(3, 2.8), 1500, 1000, 1550)
    c.key("hero", at(3, 4.1), "hero7", 1640, GR)
    c.cam(at(3, 4.0), 1480, 1000, 1450)

    def unbreakable(u: float, _t: float) -> str:
        return (overlay.chalk_text(1180, 360, "unbreakable", 70, u / 0.6, 800, "Inter Display")
                + overlay.chalk_line([(1180, 385), (1600, 385)], (u - 0.5) / 0.3, 5, seed=8, rough=False))
    c.text(at(3, 4.2), at(3, 5.6), unbreakable)
    c.cam(at(3, 5.5), 1520, 980, 1500)
    c.key("hero", at(3, 7.1), "hero4", 1640, GR)
    c.cam(at(3, 6.9), 1560, 800, 1900)
    c.key("cleaner", at(3, 5.6), "cleaner3", 1700, 120, scale=0.92, fixed=True)
    c.key("cleaner", at(4, 0.18), "cleaner3", 1700, 880, scale=0.92, fixed=True, tween="in")

    # shot 4: the catch -> flash, shake, freeze: 85 mph -> 0 in a foot and a half
    c.key("cleaner", at(4, 0.18), "cleaner4", 1675, GR - 330, ang=-8, scale=0.8, fixed=True)
    c.key("hero", at(4, 0.18), "hero5", 1640, GR)
    c.cam(at(3, 8.9), 1560, 900, 1700)
    c.cam(at(4, 0.3), 1600, 980, 1300)
    c.flash(at(4, 0.18), 0.10)
    c.shake(at(4, 0.18), 0.55, 34)
    c.sfx(at(4, 0.15), "sfx_catch", 0.55)
    c.draw(at(4, 0.18), at(5, 0.0), fx.cracks(1640, GR + 4, 320, seed=41), front=False)
    c.draw(at(4, 0.18), at(5, 0.0), fx.dust(1640, GR, size=170, seed=42))
    c.draw(at(4, 0.18), at(5, 0.0), fx.debris(1640, GR, n=22, power=0.9, seed=43))
    c.freeze(at(4, 0.45), at(4, 2.5), [
        scrim(700, 420, 760, 420),
        chalk_arrow(520, 300, 860, 470, 0.0, 0.5),
        chalk_note(120, 260, "85 mph → 0", 84, 0.3, 0.4, 800, "Inter Display"),
        chalk_note(124, 330, "in about a foot and a half", 46, 0.8, 0.6),
    ])
    c.key("hero", at(4, 2.55), "hero6", 1640, GR)
    c.hide("cleaner", at(4, 2.55))
    c.cam(at(4, 2.6), 1640, 1050, 900)
    c.cam(at(5, -0.05), 1640, 1060, 820)                # slow push until the cut (whatever shot 4 lasts)

    # shot 5: YOU unbreakable / THEM not
    c.key("hero", at(5, 0.0), "hero7", 1000, GR)
    c.key("cleaner", at(5, 0.0), "cleaner0", 1700, GR)
    c.cam(at(5, 0.0), 1344, 1000, 1600, "hold")          # hard cut to the wide two-shot
    c.cam(c.end(), 1344, 1010, 1520, "lin")
    c.text(at(5, 2.1), c.end(), punch(560, 150, "YOU", "unbreakable"))
    c.text(at(5, 4.2), c.end(), punch(1390, 150, "THEM", "not.", 96))
    c.music(0.0, "music", 0.13)
    return c


def _comic_scenes():
    import importlib.util
    from pathlib import Path
    f = Path(__file__).with_name("comic_scenes.py")
    spec = importlib.util.spec_from_file_location("whatif_super_speed_comic_scenes", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build(size):
    co = cold_open()
    co.sheet_ref = {"hero": 499, "cleaner": 481}                  # standing body height, original sheet px
    return [co, *_comic_scenes().build_all()]
