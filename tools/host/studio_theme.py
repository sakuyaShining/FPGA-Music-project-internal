"""工作台配色。QSS 与自绘图形共用语义色，切换不改任何乐器参数。"""
from PyQt5.QtGui import QColor

THEMES = {
    "paper": dict(name="暖纸 · 朱砂", bg="#F4F1EA", panel="#FFFDFA", inset="#EDE8DF",
        text="#292723", muted="#716B61", border="#DAD3C7", accent="#AE422A",
        soft="#F4E0D5", secondary="#A78F78", on_accent="#FFFFFF", sidebar="#E8E2D7"),
    "night": dict(name="午夜 · 鸢尾", bg="#151823", panel="#1E2231", inset="#282D40",
        text="#EBEDF7", muted="#ADB3CB", border="#383F56", accent="#BAACF5",
        soft="#39324F", secondary="#768FB8", on_accent="#191427", sidebar="#10131C"),
    "grove": dict(name="苔庭 · 松绿", bg="#EFF1E8", panel="#FCFDF7", inset="#E2E8DC",
        text="#263A30", muted="#607367", border="#CDD7CA", accent="#28664F",
        soft="#DCEADD", secondary="#91A879", on_accent="#FFFFFF", sidebar="#DFE6D9"),
}


def palette(widget):
    return THEMES.get(widget.window().property("studioTheme"), THEMES["paper"])


def color(widget, role):
    return QColor(palette(widget)[role])


def stylesheet(template, key, base_points=12.0, text_size="comfortable", font_family=None, mono_family=None):
    template = template.replace("@ui_family@", 'font-family: "%s";' % font_family if font_family else "")
    template = template.replace("@mono_family@", 'font-family: "%s";' % mono_family if mono_family else "")
    base = max(12.0, base_points) * (1.2 if text_size == "large" else 1.0)
    for role, factor in {"body": 1, "hint": .94, "navigation": 1.06,
                         "brand": 1.55, "title": 1.85, "name": 1.22}.items():
        template = template.replace("@" + role + "_font@", "%.2fpt" % (base * factor))
    for role, value in THEMES[key].items():
        template = template.replace("@" + role + "@", value)
    return template
