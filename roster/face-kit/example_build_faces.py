"""Builds the four v2 sample faces into faces-v2/. Plain SVG out; this script is only a drawing aid."""
import math
import random
import re
from pathlib import Path

OUT = Path(__file__).parent / "faces-v2"
OUT.mkdir(exist_ok=True)
INK = "#15172B"


def form(cid, tag, base, shade, extra="", dx=-5, dy=-6, sw=4.8, stroke=INK):
    """Cel-shaded form: shade fill, base fill shifted to the light side, clipped detail, contour."""
    return (
        f"<clipPath id='{cid}'><{tag}/></clipPath><{tag} fill='{shade}'/>"
        f"<g clip-path='url(#{cid})'><{tag} fill='{base}' transform='translate({dx} {dy})'/>{extra}</g>"
        f"<{tag} fill='none' stroke='{stroke}' stroke-width='{sw}'/>"
    )


def fur(cx, cy, rx, ry, n, amp, seed, exp=2.0, droop=0.0):
    """Zigzag furry outline (polygon points) around a superellipse."""
    rnd = random.Random(seed)
    pts = []
    for i in range(n):
        for half in (0, 1):
            a = 2 * math.pi * (i + half * 0.5) / n
            c, s = math.cos(a), math.sin(a)
            r = (abs(c / rx) ** exp + abs(s / ry) ** exp) ** (-1 / exp)
            if half:
                r += amp * rnd.uniform(0.65, 1.25)
            x, y = cx + r * c, cy + r * s
            if half:
                y += droop * amp
            pts.append(f"{x:.1f},{y:.1f}")
    return " ".join(pts)


def ticks(n, seed, box, length, colour, width=2.2, angle=(60, 120), avoid=()):
    rnd = random.Random(seed)
    d = []
    tries = 0
    while len(d) < n and tries < 4000:
        tries += 1
        x, y = rnd.uniform(box[0], box[2]), rnd.uniform(box[1], box[3])
        if any(((x - ax) / arx) ** 2 + ((y - ay) / ary) ** 2 < 1 for ax, ay, arx, ary in avoid):
            continue
        a = math.radians(rnd.uniform(*angle))
        d.append(f"M{x:.1f} {y:.1f} l{length * math.cos(a):.1f} {length * math.sin(a):.1f}")
    return f"<path d='{' '.join(d)}' fill='none' stroke='{colour}' stroke-width='{width}'/>"


def save(slug, label, body):
    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200' role='img' aria-label='{label}' "
        f"stroke-linejoin='round' stroke-linecap='round'>{body}</svg>\n"
    )
    svg = re.sub(r"\s*\n\s*", " ", svg.strip()) + "\n"
    (OUT / f"{slug}.svg").write_text(svg, encoding="utf-8")


# ------------------------------------------------------------------ TED
def ted():
    F, FS, FH, FD = "#C99052", "#A26C34", "#E0AE6E", "#7E5226"
    M, MS = "#F3E0BE", "#D8BB90"
    b = ""
    for i, ex in enumerate((41, 159)):
        ear = f"polygon points='{fur(ex, 50, 22, 22, 13, 4.5, 3 + i)}'"
        inner = (
            f"<ellipse cx='{ex}' cy='53' rx='12.5' ry='13' fill='#E9C898'/>"
            f"<path d='M{ex - 12.5} 53 a12.5 13 0 0 1 25 0 a12.5 9 0 0 0 -25 0Z' fill='#BF925C'/>"
        )
        b += form(f"ted-e{i}", ear, F, FS, inner, dx=-3, dy=-4)
    avoid = [(100, 142, 50, 40), (74, 98, 17, 17), (126, 98, 17, 17), (100, 60, 6, 30), (74, 78, 18, 9), (128, 80, 18, 9)]
    head = f"polygon points='{fur(100, 110, 84, 74, 34, 5.5, 11, exp=2.25, droop=0.25)}'"
    tex = (
        "<path d='M30 78 Q50 44 92 40 Q60 52 44 84Z' fill='" + FH + "'/>"
        + ticks(34, 5, (22, 44, 180, 182), 6.5, FS, avoid=avoid)
        + ticks(16, 8, (26, 44, 110, 120), 6, FH, avoid=avoid)
        + "<ellipse cx='52' cy='126' rx='13' ry='8' fill='#DE8E62' opacity='.55'/>"
        + "<ellipse cx='147' cy='124' rx='12' ry='8' fill='#DE8E62' opacity='.45'/>"
        # worn patch + centre seam
        + f"<path d='M100 38 V84' fill='none' stroke='{FD}' stroke-width='2.4' stroke-dasharray='5 5'/>"
        + f"<path d='M146 58 l17 4 l-4 17 l-17 -4Z' fill='#B57B3E' stroke='{FD}' stroke-width='2.2' stroke-dasharray='3.5 3.5'/>"
    )
    b += form("ted-h", head, F, FS, tex, dx=-6, dy=-7)
    # muzzle
    muz = "path d='M100 106 C126 106 146 120 146 142 C146 164 126 178 100 178 C74 178 54 164 54 142 C54 120 74 106 100 106Z'"
    mtex = (
        "<ellipse cx='84' cy='124' rx='20' ry='10' fill='#FBF0D8'/>"
        + ticks(10, 21, (62, 138, 138, 170), 4.5, MS, width=2)
    )
    b += form("ted-m", muz, M, MS, mtex, dx=-4, dy=-5, sw=3.2, stroke=FD)
    # mouth: seam down from nose, cheeky lopsided smirk
    b += (
        f"<path d='M100 134 V147' fill='none' stroke='{INK}' stroke-width='3.6'/>"
        f"<path d='M78 148 Q90 158 100 147 Q112 160 131 141' fill='none' stroke='{INK}' stroke-width='4.2'/>"
        f"<path d='M127 136 q7 2 7 9' fill='none' stroke='{INK}' stroke-width='3'/>"
        f"<path d='M104 153 Q114 160 124 151 Q116 166 105 160Z' fill='#E8707C' stroke='{INK}' stroke-width='2.6'/>"
    )
    # nose
    nose = "path d='M84 119 Q84 110 100 110 Q116 110 116 119 Q116 128 100 134 Q84 128 84 119Z'"
    b += form("ted-n", nose, "#4A2E20", "#2A1810", "<ellipse cx='94' cy='116' rx='7' ry='3.2' fill='#8C6A58'/>", dx=-2, dy=-3, sw=4)
    # eyes
    for i, (ex, lid) in enumerate(((74, 93.5), (126, 96.5))):
        dxl = math.sqrt(11 ** 2 - (98 - lid) ** 2)
        b += (
            f"<circle cx='{ex}' cy='98' r='11' fill='#2A1810' stroke='{INK}' stroke-width='4'/>"
            f"<circle cx='{ex}' cy='98.5' r='8' fill='#8A5425'/><path d='M{ex - 8} 99 a8 8 0 0 0 16 0 a8 5 0 0 1 -16 0Z' fill='#B87A3A'/>"
            f"<circle cx='{ex}' cy='98.5' r='4.6' fill='{INK}'/>"
            f"<circle cx='{ex - 3.4}' cy='95.6' r='2.7' fill='#fff'/><circle cx='{ex + 3.2}' cy='101.6' r='1.2' fill='#fff'/>"
            f"<path d='M{ex - dxl:.1f} {lid} A11 11 0 0 1 {ex + dxl:.1f} {lid}Z' fill='{FS}' stroke='{INK}' stroke-width='3.4'/>"
        )
    # brows: left cocked up, right pressed down
    b += (
        f"<path d='M57 80 Q66 66 88 70 Q90 76 86 78 Q70 75 62 85 Q56 86 57 80Z' fill='#5A3716' stroke='{INK}' stroke-width='3'/>"
        f"<path d='M112 82 Q128 76 144 84 Q147 89 142 91 Q128 85 115 89 Q110 88 112 82Z' fill='#5A3716' stroke='{INK}' stroke-width='3'/>"
        "<path d='M64 76 Q72 71 82 72 M120 83 Q129 81 138 85' fill='none' stroke='#8A5A2E' stroke-width='1.8'/>"
    )
    # prop: beer bottle held up in a paw
    bottle = "path d='M153 118 H167 V146 Q176 152 176 166 V196 Q176 202 170 202 H150 Q144 202 144 196 V166 Q144 152 153 146Z'"
    btex = (
        "<path d='M149 152 q-2 8 -2 16 V230 h5 V166 q0 -8 3 -14Z' fill='#D08A45'/>"
        "<rect x='140' y='176' width='40' height='30' fill='#F6ECD2'/>"
        "<rect x='140' y='186' width='40' height='8' fill='#C63B32'/>"
        "<rect x='150' y='122' width='20' height='14' fill='#F6ECD2'/>"
        "<path d='M170 118 V230 h8 V118Z' fill='#5E2F0E' opacity='.45'/>"
    )
    b += "<g transform='translate(-17 -21) translate(160 180) scale(.86) translate(-160 -180)'>"
    b += "<g transform='rotate(22 160 180)'>"
    b += form("ted-b", bottle, "#9A5420", "#703A12", btex, dx=0, dy=0, sw=4.2)
    b += f"<rect x='150.5' y='111' width='19' height='8.5' rx='2.5' fill='#F2C23E' stroke='{INK}' stroke-width='3.6'/>"
    b += "<path d='M154 113.5 h5' stroke='#FBE49A' stroke-width='2' fill='none'/></g>"
    paw = f"polygon points='{fur(164, 190, 27, 17, 13, 4, 31)}'"
    ptex = f"<path d='M150 182 q-3 9 2 18 M163 180 q-3 10 1 20 M176 181 q-2 10 2 18' fill='none' stroke='{FD}' stroke-width='2.4'/>"
    b += form("ted-p", paw, F, FS, ptex, dx=-3, dy=-4, sw=4.4)
    b += '</g>'
    save("ted", "Ted", b)


# ------------------------------------------------------------------ YODA
def yoda():
    G, GS, GH, GD = "#A3BC60", "#7F9B46", "#C0D683", "#566F2C"
    R, RS, RH, RD = "#CDB98E", "#A8936A", "#E3D4AE", "#7A683F"
    b = ""
    b += "<clipPath id='yoda-c'><circle cx='100' cy='100' r='97'/></clipPath><g clip-path='url(#yoda-c)'>"
    # robe bust
    robe = "path d='M3 214 Q8 162 58 146 L142 146 Q193 162 197 214Z'"
    rtex = (
        f"<path d='M30 176 q8 14 6 30 M168 174 q-10 14 -8 30 M48 160 q4 8 2 16' fill='none' stroke='{RS}' stroke-width='3'/>"
        f"<path d='M24 170 Q40 152 62 148 L58 158 Q40 162 30 178Z' fill='{RH}'/>"
    )
    b += form("yoda-r", robe, R, RS, rtex, dx=-6, dy=-5)
    b += f"<path d='M78 150 L100 186 L122 150Z' fill='#6E5C3A' stroke='{INK}' stroke-width='4'/>"
    b += f"<path d='M86 152 L100 174 L114 152' fill='none' stroke='#4F4127' stroke-width='2.4'/>"
    b += '</g>'
    # ears (drawn once, mirrored)
    ear = "path d='M62 64 Q32 50 5 57 Q10 82 30 100 Q44 112 64 120Z'"
    etex = (
        "<path d='M58 78 Q36 66 14 65 Q20 82 36 95 Q46 103 62 108Z' fill='#E8ACA4'/>"
        "<path d='M58 78 Q36 66 14 65 Q17 72 22 79 Q40 76 60 90Z' fill='#C4847E'/>"
        f"<path d='M58 78 Q36 66 14 65 Q20 82 36 95 Q46 103 62 108' fill='none' stroke='{GD}' stroke-width='2.4'/>"
        "<path d='M28 80 Q40 86 52 99 M38 80 Q48 86 58 95' fill='none' stroke='#B5746F' stroke-width='1.8'/>"
        f"<path d='M12 60 Q34 56 58 67' fill='none' stroke='{GH}' stroke-width='3'/>"
    )
    one = form("yoda-e", ear, G, GS, etex, dx=0, dy=-5)
    b += one + "<g transform='translate(200 0) scale(-1 1)'>" + one.replace("yoda-e", "yoda-f") + "</g>"
    # wispy hair behind the head
    locks = [
        "M62 44 Q48 32 31 37 Q47 38 57 52Z", "M58 53 Q40 42 20 51 Q40 48 53 62Z",
    ]
    hair = ""
    for d in locks:
        hair += f"<path d='{d}' fill='#F5F4EC' stroke='{INK}' stroke-width='2.4'/>"
    b += hair + "<g transform='translate(200 0) scale(-1 1)'>" + hair + "</g>"
    # head
    head = "path d='M100 30 C140 30 158 56 158 86 C158 110 148 130 129 143 Q114 152 100 152 Q86 152 71 143 C52 130 42 110 42 86 C42 56 60 30 100 30Z'"
    htex = (
        f"<path d='M48 62 Q58 38 90 33 Q66 44 56 70Z' fill='{GH}'/>"
        # brow ridge shadow
        f"<path d='M48 84 Q74 64 98 80 Q100 84 102 80 Q126 64 152 84 Q156 98 150 102 Q124 84 104 92 Q100 96 96 92 Q76 84 50 102 Q44 98 48 84Z' fill='{GS}'/>"
        # forehead wrinkles
        f"<path d='M70 45 Q100 37 130 45 M62 56 Q100 47 138 56 M58 68 Q100 58 142 68' fill='none' stroke='{GD}' stroke-width='2.6'/>"
        f"<path d='M96 70 q-2 6 1 11 M104 70 q2 6 -1 11' fill='none' stroke='{GD}' stroke-width='2.2'/>"
        # cheeks
        "<ellipse cx='58' cy='120' rx='11' ry='7' fill='#D7C46A' opacity='.55'/><ellipse cx='142' cy='120' rx='11' ry='7' fill='#D7C46A' opacity='.4'/>"
        f"<path d='M60 106 Q74 114 92 108 M108 108 Q126 114 140 106' fill='none' stroke='{GD}' stroke-width='2'/>"
        f"<path d='M43 98 l6 3 M43 105 l7 0 M157 98 l-6 3 M157 105 l-7 0' fill='none' stroke='{GD}' stroke-width='2'/>"
        # under-lip / chin
        f"<path d='M90 139 Q100 144 110 139' fill='none' stroke='{GD}' stroke-width='2.2'/>"
        f"<path d='M76 122 q-4 5 -2 10 M124 122 q4 5 2 10' fill='none' stroke='{GD}' stroke-width='2.2'/>"
    )
    b += form("yoda-h", head, G, GS, htex, dx=-6, dy=-6)
    # top wisps over the head
    b += (
        f"<path d='M80 33 Q96 16 118 22 Q100 24 88 37Z M98 30 Q112 20 128 30 Q112 27 104 35Z' fill='#F5F4EC' stroke='{INK}' stroke-width='2.6'/>"
    )
    # eyes
    for i, ex in enumerate((75, 125)):
        s = 1 if i == 0 else -1
        b += (
            f"<clipPath id='yoda-y{i}'><ellipse cx='{ex}' cy='97' rx='18' ry='14'/></clipPath>"
            f"<ellipse cx='{ex}' cy='97' rx='18' ry='14' fill='#F6F2DC'/>"
            f"<g clip-path='url(#yoda-y{i})'>"
            f"<circle cx='{ex + s * 2}' cy='98' r='10' fill='#7B6A22'/><circle cx='{ex + s * 2}' cy='98' r='10' fill='none' stroke='#4E4212' stroke-width='2'/>"
            f"<path d='M{ex + s * 2 - 8} 100 a8 8 0 0 0 16 0 a8 5 0 0 1 -16 0Z' fill='#B59A32'/>"
            f"<circle cx='{ex + s * 2}' cy='98' r='5.2' fill='{INK}'/>"
            f"<circle cx='{ex + s * 2 - 4}' cy='95.5' r='2.8' fill='#fff'/><circle cx='{ex + s * 2 + 4}' cy='102' r='1.3' fill='#fff'/>"
            # heavy upper lid
            f"<path d='M{ex - 20} 80 H{ex + 20} V{96 if s == 1 else 96} Q{ex} {86} {ex - 20} {96}Z' fill='{G}'/>"
            f"<path d='M{ex - 20} 96 Q{ex} 86 {ex + 20} 96' fill='none' stroke='{INK}' stroke-width='3.6'/>"
            f"<path d='M{ex - 20} 92 Q{ex} 82 {ex + 20} 92' fill='none' stroke='{GD}' stroke-width='1.8'/>"
            "</g>"
            f"<ellipse cx='{ex}' cy='97' rx='18' ry='14' fill='none' stroke='{INK}' stroke-width='3.8'/>"
            f"<path d='M{ex - 14} 113 Q{ex} 119 {ex + 14} 113' fill='none' stroke='{GD}' stroke-width='2.2'/>"
        )
    # brows
    b += (
        f"<path d='M50 86 Q72 70 95 82 M150 86 Q128 70 105 82' fill='none' stroke='{GD}' stroke-width='3.6'/>"
    )
    # nose + mouth
    b += (
        f"<path d='M92 112 Q92 104 100 104 Q108 104 108 112 Q108 119 100 120 Q92 119 92 112Z' fill='{G}' stroke='{GD}' stroke-width='2.8'/>"
        f"<path d='M101 105 Q108 105 108 112 Q108 119 100 120 Q105 114 101 105Z' fill='{GS}'/>"
        f"<ellipse cx='97' cy='109' rx='3' ry='2' fill='{GH}'/>"
        f"<path d='M96 116 h.1 M104 116 h.1' stroke='{GD}' stroke-width='2.6' fill='none'/>"
        f"<path d='M78 127 Q100 138 123 126' fill='none' stroke='{INK}' stroke-width='3.8'/>"
        f"<path d='M120 122 q5 2 5 7' fill='none' stroke='{INK}' stroke-width='2.8'/>"
    )
    b += "<g clip-path='url(#yoda-c)'>"
    # robe collar over the chin base
    lap = "path d='M52 150 Q72 140 90 148 L104 214 L62 214 Q48 180 52 150Z'"
    ltex = f"<path d='M60 152 Q76 148 86 154 L98 214' fill='none' stroke='{RD}' stroke-width='2' stroke-dasharray='4 4.5'/><path d='M56 152 Q66 146 80 147 L84 152 Q70 150 60 158Z' fill='{RH}'/>"
    b += form("yoda-l", lap, "#DCCAA2", RS, ltex, dx=-4, dy=-3, sw=4.4)
    lap2 = "path d='M148 150 Q128 140 110 148 L92 214 L138 214 Q152 180 148 150Z'"
    ltex2 = f"<path d='M140 152 Q124 148 114 154 L100 214' fill='none' stroke='{RD}' stroke-width='2' stroke-dasharray='4 4.5'/>"
    b += form("yoda-k", lap2, "#DCCAA2", RS, ltex2, dx=-4, dy=-3, sw=4.4)
    b += '</g>'
    b += f"<path d='M26.5 163.3 A97 97 0 0 0 173.5 163.3' fill='none' stroke='{INK}' stroke-width='4.8'/>"
    save("yoda", "Yoda", b)


# ------------------------------------------------------------------ GANDALF
def gandalf():
    H, HS, HH, HD = "#7F879A", "#5E6579", "#9EA6B8", "#434A5C"
    B, BS, BD = "#EEF0F5", "#C6CBD8", "#9AA1B3"
    SK, SKS, SKH = "#EFC0A0", "#D49B7A", "#F9DCC4"
    b = ""
    # back hair + beard mass
    back = ("path d='M100 84 L44 84 Q19 118 21 162 L33 151 Q33 172 40 185 L50 170 Q52 185 61 194 L70 181 Q74 192 84 196 L100 190Z'")
    bt = (
        f"<path d='M40 104 Q32 130 34 148 M50 100 Q42 136 48 166 M60 150 Q62 170 68 182' fill='none' stroke='{BD}' stroke-width='2.2'/>"
        "<path d='M40 96 Q30 118 30 140 Q36 118 46 98Z' fill='#F4F6FA'/>"
    )
    one = form("gan-bk", back, "#D9DDE6", "#B3B9C8", bt, dx=0, dy=-6)
    b += one + "<g transform='translate(200 0) scale(-1 1)'>" + one.replace("gan-bk", "gan-bl") + "</g>"
    # face
    face = "path d='M60 78 Q58 126 100 134 Q142 126 140 78Z'"
    ft = (
        f"<path d='M56 76 H144 V95 Q100 86 56 95Z' fill='{SKS}'/>"
        "<ellipse cx='70' cy='117' rx='10' ry='6.5' fill='#EE8F84' opacity='.7'/><ellipse cx='130' cy='117' rx='10' ry='6.5' fill='#EE8F84' opacity='.6'/>"
        f"<path d='M64 106 l5 2 M64 111 l6 -1 M136 106 l-5 2 M136 111 l-6 -1' fill='none' stroke='{SKS}' stroke-width='1.8'/>"
        f"<path d='M72 112 Q80 116 90 113 M110 113 Q120 116 128 112' fill='none' stroke='{SKS}' stroke-width='2'/>"
    )
    b += form("gan-f", face, SK, SKS, ft, dx=-4, dy=-3, sw=4)
    b += "<g transform='translate(0 4)'>"
    # eyes
    for i, ex in enumerate((81, 119)):
        b += (
            f"<clipPath id='gan-y{i}'><ellipse cx='{ex}' cy='106' rx='10' ry='7.6'/></clipPath>"
            f"<ellipse cx='{ex}' cy='106' rx='10' ry='7.6' fill='#fff'/>"
            f"<g clip-path='url(#gan-y{i})'><circle cx='{ex}' cy='105.5' r='6' fill='#3F74AA'/>"
            f"<path d='M{ex - 6} 106.5 a6 6 0 0 0 12 0 a6 3.6 0 0 1 -12 0Z' fill='#8CBCE6'/>"
            f"<circle cx='{ex}' cy='105.5' r='3.1' fill='{INK}'/><circle cx='{ex - 2.4}' cy='103.2' r='2.1' fill='#fff'/>"
            f"<circle cx='{ex + 2.6}' cy='108' r='1' fill='#fff'/>"
            f"<path d='M{ex - 11} 118 Q{ex} 109.5 {ex + 11} 118Z' fill='{SK}'/></g>"
            f"<path d='M{ex - 11} 106.5 Q{ex} 94 {ex + 11} 106.5' fill='none' stroke='{INK}' stroke-width='3.4'/>"
            f"<path d='M{ex - 8} 113.4 Q{ex} 110.6 {ex + 8} 113.4' fill='none' stroke='#B77C5E' stroke-width='2'/>"
        )
    b += '</g>'
    # front beard
    front = ("path d='M62 126 Q49 158 66 188 L75 174 Q79 190 86 196 L93 184 L100 198 L107 184 L114 196 Q121 190 125 174 L134 188 "
             "Q151 158 138 126 Q100 150 62 126Z'")
    frt = (
        f"<path d='M74 146 Q76 166 84 180 M88 150 Q88 170 91 182 M112 150 Q112 170 109 182 M126 146 Q124 166 118 178 M100 152 V186' "
        f"fill='none' stroke='{BD}' stroke-width='2.2'/>"
        "<path d='M68 136 Q64 156 72 172 Q72 154 78 142Z' fill='#fff'/>"
    )
    b += form("gan-bf", front, B, BS, frt, dx=-5, dy=-4)
    b += "<g transform='translate(0 4)'>"
    # pipe
    b += (
        f"<path d='M112 141 Q134 152 156 146' fill='none' stroke='{INK}' stroke-width='8'/>"
        f"<path d='M112 141 Q134 152 156 146' fill='none' stroke='#6B3F22' stroke-width='3.6'/>"
    )
    bowl = "path d='M152 132 H174 Q176 152 163 154 Q150 152 152 132Z'"
    b += form("gan-pb", bowl, "#8A5430", "#5F3519", "<path d='M155 134 q-1 10 4 16' fill='none' stroke='#B97B4C' stroke-width='2.4'/>", dx=-2, dy=-2, sw=4)
    b += f"<ellipse cx='163' cy='132' rx='11' ry='3.4' fill='#F08A2E' stroke='{INK}' stroke-width='3.2'/>"
    b += (
        f"<path d='M163 124 q-8 -8 0 -14 q8 -6 2 -13' fill='none' stroke='{BD}' stroke-width='6.5'/>"
        "<path d='M163 124 q-8 -8 0 -14 q8 -6 2 -13' fill='none' stroke='#fff' stroke-width='3.4'/>"
    )
    # moustache lobes
    ml = "path d='M100 127 Q84 119 66 131 Q52 141 46 160 Q62 160 78 152 Q92 146 100 137Z'"
    mlt = f"<path d='M90 128 Q72 134 58 152 M96 133 Q82 140 70 152' fill='none' stroke='{BD}' stroke-width='2'/>"
    b += form("gan-ml", ml, "#FAFBFD", BS, mlt, dx=-3, dy=-4, sw=4.2)
    mr = "path d='M100 127 Q116 119 134 131 Q148 141 154 160 Q138 160 122 152 Q108 146 100 137Z'"
    mrt = f"<path d='M110 128 Q128 134 142 152 M104 133 Q118 140 130 152' fill='none' stroke='{BD}' stroke-width='2'/>"
    b += form("gan-mr", mr, "#FAFBFD", BS, mrt, dx=-3, dy=-4, sw=4.2)
    # nose
    nose = "path d='M95 100 Q86 120 92 127 Q100 133 108 127 Q114 120 105 100Z'"
    b += f"<path d='M96 104 Q88 120 92 127 Q100 133 108 127 Q112 120 104 104Z' fill='{SK}'/>"
    b += f"<path d='M102 104 Q108 116 104 124 Q100 130 94 128 Q100 133 108 127 Q112 120 104 104Z' fill='{SKS}'/>"
    b += f"<ellipse cx='96' cy='119' rx='3.4' ry='4.6' fill='{SKH}'/>"
    b += f"<path d='M96 106 Q88 120 92 127 Q100 133 108 127 Q112 120 104 106' fill='none' stroke='{INK}' stroke-width='3.6'/>"
    b += '</g>'
    b += "<g transform='translate(0 -4)'>"
    # hat brim
    brim = "path d='M5 80 Q18 58 60 59 Q100 53 140 57 Q184 58 195 76 Q186 95 140 90 Q100 85 60 92 Q16 98 5 80Z'"
    brt = (
        f"<path d='M14 76 Q40 64 70 64' fill='none' stroke='{HH}' stroke-width='3.4'/>"
        f"<path d='M24 88 Q60 82 100 80 Q146 80 180 84' fill='none' stroke='{HD}' stroke-width='2' stroke-dasharray='5 5'/>"
        f"<path d='M170 62 l6 8 l-9 2Z' fill='{HD}'/>"
    )
    b += form("gan-br", brim, H, HS, brt, dx=-2, dy=-6)
    # hat cone with bent tip
    cone = "path d='M55 68 Q68 42 84 24 Q100 6 124 7 Q138 9 146 22 Q130 16 120 26 Q134 44 145 66 Q100 79 55 68Z'"
    ct = (
        f"<path d='M62 62 Q76 38 92 22 Q104 12 118 12 Q100 22 90 38 Q80 52 76 66Z' fill='{HH}'/>"
        f"<path d='M52 70 Q100 82 148 66 L142 54 Q100 68 60 58Z' fill='{HD}'/>"
        f"<path d='M60 60 Q100 70 141 56' fill='none' stroke='#6A7186' stroke-width='2'/>"
        f"<path d='M96 30 Q108 34 120 27 M88 42 Q104 48 126 40' fill='none' stroke='{HD}' stroke-width='2.6'/>"
        f"<path d='M104 46 l12 -2 l3 10 l-13 2Z' fill='{HS}' stroke='{HD}' stroke-width='1.8' stroke-dasharray='3 3'/>"
    )
    b += form("gan-c", cone, H, HS, ct, dx=-6, dy=-3)
    b += '</g>'
    # bushy brows
    b += (
        f"<path d='M53 108 L58 98 L55 91 L65 90 L71 82 L80 86 L89 83 L96 91 Q84 90 74 93 Q64 97 60 105Z' fill='#E3E6ED' stroke='{INK}' stroke-width='3.4'/>"
        f"<path d='M147 108 L142 98 L145 91 L135 90 L129 82 L120 86 L111 83 L104 91 Q116 90 126 93 Q136 97 140 105Z' fill='#E3E6ED' stroke='{INK}' stroke-width='3.4'/>"
        f"<path d='M68 93 l6 -3 M78 92 l6 -1 M132 93 l-6 -3 M122 92 l-6 -1' fill='none' stroke='{BD}' stroke-width='1.8'/>"
    )
    save("gandalf", "Gandalf", b)


# ------------------------------------------------------------------ MICHAEL SCOTT
def michael():
    SK, SKS, SKH, SKD = "#F2C6A4", "#D9A27E", "#FADCC4", "#B97C5A"
    SU, SUS, SUH = "#3D465C", "#2A3145", "#56617C"
    HA, HAS, HAH = "#46332A", "#2C1F1A", "#6E5241"
    b = ""
    b += "<clipPath id='ms-c'><circle cx='100' cy='100' r='97'/></clipPath><g clip-path='url(#ms-c)'>"
    suit = "path d='M2 214 Q4 160 48 150 L78 140 L122 140 L152 150 Q196 160 198 214Z'"
    st = f"<path d='M14 178 Q24 160 50 153 L46 162 Q28 168 20 184Z' fill='{SUH}'/><path d='M34 186 q4 10 2 20 M168 180 q-6 12 -4 24' fill='none' stroke='{SUS}' stroke-width='3'/>"
    b += form("ms-s", suit, SU, SUS, st, dx=-6, dy=-5)
    # shirt
    b += f"<path d='M78 138 L122 138 L110 214 L90 214Z' fill='#F4F7FC' stroke='{INK}' stroke-width='4'/>"
    b += "<path d='M112 140 L122 140 L110 214 L104 214Z' fill='#CBD5E6'/>"
    # tie
    tie = "path d='M93 149 H107 L105.5 163 L112 214 H88 L94.5 163Z'"
    tt = (
        "<path d='M84 176 l32 -14 M84 190 l32 -14 M84 204 l32 -14 M84 218 l32 -14' fill='none' stroke='#D4606C' stroke-width='4.5'/>"
        "<path d='M94.5 163 H105.5' fill='none' stroke='#6E1622' stroke-width='2.4'/>"
        "<path d='M104 149 h4 l-1.5 14 l6 51 h-6Z' fill='#7A1C29' opacity='.6'/>"
    )
    b += form("ms-t", tie, "#A62B3C", "#A62B3C", tt, dx=0, dy=0, sw=4)
    # lapels
    b += (
        f"<path d='M76 140 L52 152 L66 171 L57 177 L86 214 H95Z' fill='#4B5570' stroke='{INK}' stroke-width='4'/>"
        f"<path d='M124 140 L148 152 L134 171 L143 177 L114 214 H105Z' fill='#353D52' stroke='{INK}' stroke-width='4'/>"
        f"<path d='M60 154 L72 170' fill='none' stroke='{SUH}' stroke-width='2.4'/>"
    )
    # neck
    b += f"<path d='M84 112 V140 L100 152 L116 140 V112Z' fill='{SK}' stroke='{INK}' stroke-width='4'/>"
    b += f"<path d='M84 124 Q100 138 116 124 V140 L100 152 L84 140Z' fill='{SKS}'/>"
    # collar
    b += (
        f"<path d='M82 130 L100 151 L89 164 L74 142Z' fill='#fff' stroke='{INK}' stroke-width='4'/>"
        f"<path d='M118 130 L100 151 L111 164 L126 142Z' fill='#DCE4F1' stroke='{INK}' stroke-width='4'/>"
    )
    b += f"<path d='M93 149 H107 L105.5 163 H94.5Z' fill='#B8384A' stroke='{INK}' stroke-width='3.6'/>"
    b += '</g>'
    b += f"<path d='M24.4 160.7 A97 97 0 0 0 175.6 160.7' fill='none' stroke='{INK}' stroke-width='4.8'/>"
    b += "<g transform='translate(100 134) scale(1.07) translate(-100 -134)'>"
    # ears
    for i, ex in enumerate((55, 145)):
        s = 1 if i == 0 else -1
        b += (
            f"<ellipse cx='{ex}' cy='84' rx='9' ry='14' fill='{SK if i == 0 else SKS}' stroke='{INK}' stroke-width='4.4'/>"
            f"<path d='M{ex - s * 2} 77 q{-s * 5} 6 {s * 1} 14' fill='none' stroke='{SKD}' stroke-width='2.2'/>"
        )
    # head
    head = "path d='M58 72 Q56 42 74 30 Q100 18 126 30 Q144 42 142 72 Q142 102 129 118 Q116 132 100 132 Q84 132 71 118 Q58 102 58 72Z'"
    ht = (
        "<ellipse cx='72' cy='101' rx='10' ry='6.5' fill='#F08F86' opacity='.34'/><ellipse cx='129' cy='99' rx='9' ry='6' fill='#F08F86' opacity='.28'/>"
        f"<path d='M70 50 Q84 42 98 48 Q82 50 72 62Z' fill='{SKH}'/>"
        f"<path d='M76 56 Q100 50 124 56 M80 49 Q100 45 118 49' fill='none' stroke='{SKS}' stroke-width='1.8'/>"
        # nose shadow + smile fold
        f"<path d='M103 78 Q108 96 112 103 Q108 110 100 110 Q106 104 103 92Z' fill='{SKS}'/>"
        f"<path d='M84 124 Q100 131 118 122' fill='none' stroke='{SKS}' stroke-width='2.4'/>"
    )
    b += form("ms-h", head, SK, SKS, ht, dx=-5, dy=-4)
    # hair
    hair = ("path d='M55 76 Q46 38 72 21 Q100 7 130 19 Q155 33 145 76 Q143 60 135 48 Q116 53 96 47 Q84 44 77 37 "
            "Q66 47 62 60 Q59 68 55 76Z'")
    hrt = (
        f"<path d='M70 30 Q90 16 116 20 Q96 24 82 36Z' fill='{HAH}'/>"
        f"<path d='M78 36 Q100 24 130 30 M86 42 Q108 34 136 42 M64 44 Q68 34 76 28 M60 58 Q62 48 68 42' fill='none' stroke='{HAS}' stroke-width='2.2'/>"
        f"<path d='M92 28 Q108 24 124 28' fill='none' stroke='{HAH}' stroke-width='2.4'/>"
    )
    b += form("ms-ha", hair, HA, HAS, hrt, dx=-5, dy=-4)
    # brows (right one cocked)
    b += (
        f"<path d='M64 70 Q76 61 91 67 L90 72 Q77 68 66 75Z' fill='{HAS}' stroke='{INK}' stroke-width='2.6'/>"
        f"<path d='M109 64 Q124 54 138 62 L136 68 Q123 61 111 69Z' fill='{HAS}' stroke='{INK}' stroke-width='2.6'/>"
    )
    # eyes
    for i, (ex, ey) in enumerate(((78, 82), (122, 80))):
        b += (
            f"<clipPath id='ms-y{i}'><ellipse cx='{ex}' cy='{ey}' rx='9' ry='6.6'/></clipPath>"
            f"<ellipse cx='{ex}' cy='{ey}' rx='9' ry='6.6' fill='#fff'/>"
            f"<g clip-path='url(#ms-y{i})'><circle cx='{ex + 1}' cy='{ey}' r='5.6' fill='#6E4A28'/>"
            f"<path d='M{ex - 4.6} {ey + 1} a5.6 5.6 0 0 0 11.2 0 a5.6 3.4 0 0 1 -11.2 0Z' fill='#A87840'/>"
            f"<circle cx='{ex + 1}' cy='{ey}' r='2.9' fill='{INK}'/><circle cx='{ex - 1.2}' cy='{ey - 2}' r='1.9' fill='#fff'/>"
            f"<path d='M{ex - 10} {ey + 9} Q{ex} {ey + 2} {ex + 10} {ey + 9}Z' fill='{SK}'/></g>"
            f"<path d='M{ex - 10} {ey} Q{ex} {ey - 9} {ex + 10} {ey}' fill='none' stroke='{INK}' stroke-width='3.4'/>"
            f"<path d='M{ex - 8} {ey + 5.5} Q{ex} {ey + 2.6} {ex + 8} {ey + 5.5}' fill='none' stroke='{SKD}' stroke-width='2'/>"
        )
    # nose
    b += f"<path d='M98 84 Q95 98 90 103 Q94 110 101 109 Q108 110 111 103' fill='none' stroke='{SKD}' stroke-width='3'/>"
    b += f"<ellipse cx='97' cy='101' rx='3' ry='2.4' fill='{SKH}'/>"
    # smug closed grin
    b += (
        f"<path d='M80 113 Q98 124 124 108' fill='none' stroke='{INK}' stroke-width='4'/>"
        f"<path d='M121 103 q7 3 6 10' fill='none' stroke='{INK}' stroke-width='3'/>"
        f"<path d='M77 109 q-2 3 1 6' fill='none' stroke='{SKD}' stroke-width='2.4'/>"
    )
    b += '</g>'
    b += "<g clip-path='url(#ms-c)'><path d='M100 214 Q98 186 116 178 L126 187 Q118 196 120 214Z' fill='#fff' stroke='" + INK + "' stroke-width='4'/></g>"
    b += "<g transform='translate(-10 -5)'>"
    # mug, raised
    b += f"<path d='M168 150 Q186 150 186 165 Q186 180 168 180' fill='none' stroke='{INK}' stroke-width='12'/>"
    b += "<path d='M168 150 Q186 150 186 165 Q186 180 168 180' fill='none' stroke='#F4F6FA' stroke-width='4.5'/>"
    mug = "path d='M132 140 H170 V184 Q170 194 160 194 H142 Q132 194 132 184Z'"
    mt = "<path d='M162 140 h10 v56 h-10Z' fill='#C5CDDD'/><path d='M138 150 v30' fill='none' stroke='#fff' stroke-width='3.4'/>"
    b += form("ms-m", mug, "#F6F8FC", "#F6F8FC", mt, dx=0, dy=0)
    b += f"<ellipse cx='151' cy='140' rx='19' ry='5.4' fill='#5A3620' stroke='{INK}' stroke-width='4'/>"
    b += "<path d='M138 140 q6 -3 13 -3' fill='none' stroke='#8A5A3A' stroke-width='2'/>"
    # steam
    b += (
        "<path d='M152 128 q-5 -6 0 -11 q5 -5 1 -10 M164 128 q-4 -5 0 -9' fill='none' stroke='#9AA6BE' stroke-width='6'/>"
        "<path d='M152 128 q-5 -6 0 -11 q5 -5 1 -10 M164 128 q-4 -5 0 -9' fill='none' stroke='#fff' stroke-width='3'/>"
    )
    # hand: fingers wrapped round the mug
    for i, fy in enumerate((158, 168, 178)):
        b += f"<rect x='{126 + i}' y='{fy}' width='{26 - i * 2}' height='11' rx='5.5' fill='{SK}' stroke='{INK}' stroke-width='3.6'/>"
        b += f"<path d='M{132 + i} {fy + 8.6} h{14 - i * 2}' stroke='{SKS}' stroke-width='2' fill='none'/>"
    b += '</g>'
    save("michael-scott", "Michael Scott", b)


ted(); yoda(); gandalf(); michael()
print("built")
