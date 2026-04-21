"""
Run once to produce icon.ico in the same directory.
  venv/Scripts/python generate_icon.py
"""
from PIL import Image, ImageDraw
import math, os

def draw_icon(size: int) -> Image.Image:
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s    = size

    # ── Background: rounded square, dark-blue gradient simulation ────────────
    r = max(4, s // 6)
    draw.rounded_rectangle([0, 0, s - 1, s - 1], radius=r,
                            fill=(30, 80, 160, 255))
    # subtle inner highlight (top edge)
    draw.rounded_rectangle([1, 1, s - 2, s // 2], radius=r,
                            fill=(60, 120, 210, 120))

    # ── Monitor / screen outline ──────────────────────────────────────────────
    pad  = max(3, s // 8)
    sw   = 2 if s >= 32 else 1          # stroke width
    mx1, my1 = pad, pad
    mx2, my2 = s - pad, s - int(s * 0.35)
    draw.rounded_rectangle([mx1, my1, mx2, my2], radius=max(2, s//16),
                            outline=(220, 235, 255, 255), width=sw)

    # ── Monitor stand ─────────────────────────────────────────────────────────
    cx    = s // 2
    base_y = my2 + 1
    foot_y = s - pad
    draw.rectangle([cx - sw, base_y, cx + sw, foot_y],
                   fill=(220, 235, 255, 200))
    foot_w = max(3, s // 6)
    draw.rectangle([cx - foot_w, foot_y - sw, cx + foot_w, foot_y],
                   fill=(220, 235, 255, 200))

    # ── Magnifying-glass eye inside the screen ────────────────────────────────
    screen_cx = (mx1 + mx2) // 2
    screen_cy = (my1 + my2) // 2
    er = max(2, (my2 - my1) // 4)      # eye-circle radius

    # outer ring
    draw.ellipse([screen_cx - er, screen_cy - er,
                  screen_cx + er, screen_cy + er],
                 outline=(255, 220, 60, 255), width=max(1, sw))
    # pupil fill
    pr = max(1, er // 2)
    draw.ellipse([screen_cx - pr, screen_cy - pr,
                  screen_cx + pr, screen_cy + pr],
                 fill=(255, 220, 60, 255))

    # magnifier handle (diagonal line bottom-right)
    angle = math.radians(40)
    hx1 = int(screen_cx + er * math.cos(angle))
    hy1 = int(screen_cy + er * math.sin(angle))
    hx2 = int(screen_cx + (er + max(2, s // 7)) * math.cos(angle))
    hy2 = int(screen_cy + (er + max(2, s // 7)) * math.sin(angle))
    draw.line([hx1, hy1, hx2, hy2],
              fill=(255, 220, 60, 255), width=max(1, sw))

    return img


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    out   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")

    # Draw at the largest size; PIL will downsample to each requested size.
    base = draw_icon(256)

    # PIL's ICO writer accepts a single RGBA image + a 'sizes' list.
    # It resamples the source to every requested (w, h) and bundles them all.
    base.save(out, format="ICO", sizes=[(s, s) for s in sizes])

    # Verify
    from PIL import Image
    check = Image.open(out)
    embedded = check.ico.sizes()
    print(f"Saved {out}")
    print(f"  Requested : {sizes}")
    print(f"  Embedded  : {sorted(embedded)}")


if __name__ == "__main__":
    main()
