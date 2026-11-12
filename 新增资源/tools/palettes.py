"""Convert pinned upstream ColorBrewer schemes to local SVG swatches and tokens."""
from html import escape
import json
from pathlib import Path
import re
import shutil
import sys

source, output = map(Path, sys.argv[1:3])
revision = (source / "revision").read_text().strip()
assert re.fullmatch(r"[0-9a-f]{40}", revision)
source_url = f"https://github.com/axismaps/colorbrewer/blob/{revision}/colorbrewer_schemes.js"
license_url = f"https://github.com/axismaps/colorbrewer/blob/{revision}/LICENCE.txt"
original = (source / "colorbrewer_schemes.js").read_text()
authors = "Cynthia Brewer, Mark Harrower, and The Pennsylvania State University"

groups = (
    ("发散", "Diverging", 7, "Use for departures from a meaningful midpoint.", "RdBu RdYlGn PiYG PRGn RdYlBu BrBG RdGy PuOr Spectral"),
    ("定性", "Qualitative", 6, "Assign one swatch per category and keep the mapping consistent.", "Accent Dark2 Paired Pastel1 Pastel2 Set1 Set2 Set3"),
    ("顺序", "Sequential", 6, "Order colors from low to high. Keep the numeric scale explicit.", "Blues Greens Greys Oranges Purples Reds YlGnBu PuBuGn"),
)


def label_color(rgb):
    def linear(n):
        s = n/255
        return s/12.92 if s <= .04045 else ((s+.055)/1.055)**2.4
    luma = sum(linear(n)*w for n, w in zip(rgb, (.2126, .7152, .0722)))
    return "#000000" if (luma+.05)/.05 >= 1.05/(luma+.05) else "#ffffff"


def swatch(name, kind, guidance, rgb):
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="320" viewBox="0 0 1000 320" role="img"><title>{escape(name)} palette</title>',
             '<rect width="1000" height="320" fill="#fff"/>',
             f'<g font-family="Arial,sans-serif"><text x="36" y="53" font-size="33" font-weight="700" fill="#172b42">{escape(name)} · {kind}</text>',
             f'<text x="36" y="85" font-size="17" fill="#455b70">{escape(guidance)}</text>']
    width = 928/len(rgb)
    codes = []
    for i, color in enumerate(rgb):
        x = 36+i*width
        code = "#"+"".join(f"{n:02X}" for n in color)
        codes.append(code)
        parts.append(f'<rect x="{x:.2f}" y="118" width="{width-4:.2f}" height="117" rx="6" fill="{code}"/>')
        parts.append(f'<text x="{x+width/2:.2f}" y="184" text-anchor="middle" font-size="18" font-weight="700" fill="{label_color(color)}">{code}</text>')
    parts.append('<text x="36" y="278" font-size="13" fill="#455b70">Color specifications developed by Cynthia Brewer · colorbrewer.org</text></g></svg>')
    return "\n".join(parts)+"\n", codes


folder = output / "配色"
folder.mkdir(parents=True, exist_ok=True)
shutil.copyfile(source/"LICENCE.txt", output/"ColorBrewer-LICENSE.txt")
(output/"NOTICE.md").write_text(
    f"Color schemes copyright (c) 2002 {authors}.\n\n"
    "This product includes color specifications and designs developed by Cynthia Brewer (https://colorbrewer.org/). "
    "Palette values are unchanged. The SVG swatch sheets and machine-readable token presentation were added by PPT Toolbox.\n\n"
    f"[Pinned source]({source_url}) · [Upstream license]({license_url})\n")
rows = []
for zh, kind, count, guidance, names in groups:
    for name in names.split():
        match = re.search(rf"^\s*['\"]?{name}['\"]?\s*:\s*\{{([^}}]*)\}}", original, re.M)
        assert match, name
        scheme = re.search(rf"\b{count}\s*:\s*\[([^\]]+)\]", match[1])
        rgb = [tuple(map(int, values)) for values in re.findall(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", scheme[1])]
        assert len(set(rgb)) == count and all(0 <= v < 256 for triplet in rgb for v in triplet)
        svg, codes = swatch(name, kind, guidance, rgb)
        slug = name.lower()
        (folder/f"{slug}.svg").write_text(svg)
        token_path = f"配色/{slug}.json"
        (output/token_path).write_text(json.dumps({"name":name,"kind":kind.lower(),"colors":codes,
             "source":source_url,"original_id":name,"license":"Apache-2.0"}, indent=2)+"\n")
        rows.append({"id":f"pptb003-brewer-{slug}","name_zh":f"{name} {zh}色板","name_en":f"{name} {kind} palette",
                     "category":"配色","subcategory":zh,"keywords_zh":[zh,"色板","数据可视化"],"industries":["all"],
                     "motif_key":f"brewer-{slug}","file_path":f"配色/{slug}.svg","extra_paths":[token_path],
                     "editability":"SVG-path-editable","source_url":source_url,"source_page":name,
                     "original_resource_id":name,"source_project":"ColorBrewer","author":authors,
                     "license":"Apache-2.0","license_url":license_url,"attribution_required":True})
(output/"资源描述.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2)+"\n")
