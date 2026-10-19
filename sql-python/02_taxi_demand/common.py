"""Small, explicit helpers shared by the three independent project pipelines."""

from pathlib import Path
import hashlib, json, urllib.request, html, base64
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titleweight": "bold",
        "axes.titlepad": 16,
        "figure.facecolor": "#f7f7f0",
        "axes.facecolor": "#f7f7f0",
        "axes.labelcolor": "#213c38",
        "text.color": "#213c38",
        "axes.prop_cycle": plt.cycler(
            color=["#245a51", "#c47745", "#849c73", "#3b7795"]
        ),
    }
)


def download(name, url):
    p = ROOT / "data" / name
    p.parent.mkdir(exist_ok=True)
    compressed = p.with_suffix(p.suffix + ".gz")
    if not p.exists() and compressed.exists():
        import gzip, shutil

        with gzip.open(compressed, "rb") as source, p.open("wb") as target:
            shutil.copyfileobj(source, target)
    if not p.exists():
        temp = p.with_suffix(p.suffix + ".part")
        with urllib.request.urlopen(url, timeout=120) as response, open(
            temp, "wb"
        ) as target:
            import shutil

            shutil.copyfileobj(response, target)
        temp.replace(p)
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = json.loads((ROOT / "sources.json").read_text())
    spec = next(s for s in manifest["files"] if s["file"] == name)
    if digest != spec["sha256"]:
        raise ValueError(
            f"{name}: source has changed. Review the new data before updating sources.json."
        )
    return p


def sql(con, name):
    return con.execute((ROOT / "sql" / name).read_text())


def result(con, filename, query):
    df = con.execute(query).df()
    df.to_csv(OUT / (filename + ".csv"), index=False)
    return df


def chart(name):
    plt.tight_layout()
    plt.savefig(OUT / (name + ".png"), dpi=170, bbox_inches="tight")
    plt.close()


def save_json(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, default=str))


def report(title, subtitle, metrics, sections, figures, tables):
    cards = "".join(
        f'<div class="metric"><strong>{html.escape(str(v))}</strong><span>{html.escape(k)}</span></div>'
        for k, v in metrics
    )
    content = "".join(
        f"<section><h2>{html.escape(h)}</h2><p>{html.escape(p)}</p></section>"
        for h, p in sections
    )
    for filename, caption in figures:
        content += f'<figure><img src="{html.escape(filename)}" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>'
    for title_, df in tables:
        content += f'<section><h2>{html.escape(title_)}</h2><div class="table">{df.to_html(index=False,float_format=lambda x: f"{x:,.3f}",escape=True)}</div></section>'
    sources = json.loads((ROOT / "sources.json").read_text())
    links = "".join(
        f'<li><a href="{html.escape(s["url"])}">{html.escape(s["label"])}</a></li>'
        for s in sources["references"]
    )
    page = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;background:#f7f7f0;color:#213c38;font:16px/1.65 system-ui,sans-serif}main{max-width:1080px;margin:auto;padding:45px 5%}header{border-bottom:1px solid #ccd5c5;padding-bottom:30px}h1{font-size:clamp(32px,5vw,52px);line-height:1.12;letter-spacing:-2px;max-width:950px}h2{font-size:24px;line-height:1.3}header>p:first-child{font-size:12px;letter-spacing:2px}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:15px;margin:30px 0}.metric{padding:22px;background:#e6ebde;border-radius:8px}.metric strong{display:block;font-size:27px}.metric span{font-size:13px}section{max-width:850px;margin:32px 0}figure{margin:35px 0;border-top:1px solid #ccd5c5;padding-top:20px}img{width:100%;height:auto}figcaption{font-size:13px;color:#56675f}.table{overflow:auto}table{border-collapse:collapse;font-size:13px}th,td{padding:9px;text-align:left;border-bottom:1px solid #ccd5c5}a{color:#245a51}footer{font-size:13px;margin-top:45px}@media print{main{padding:10px}figure{break-inside:avoid}section{break-inside:avoid}}</style>'
        + f'<title>{html.escape(title)}</title></head><body><main><nav><a href="../../../index.html#sql-python-projects">Back to portfolio</a> · <a href="https://github.com/iDannie/iDannie.github.io/tree/main/sql-python/{ROOT.name}">View code on GitHub</a></nav><header><p>DANIEL UMEADI / SQL + PYTHON</p><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></header><div class="metrics">{cards}</div>{content}<footer><h2>Sources and scope</h2><ul>{links}</ul><p>Methods, definitions and reproducibility details are in the project README.</p></footer></main></body></html>'
    )
    (OUT / "technical_report.html").write_text(page)
    # Never publish reviewed narrative against results that have changed.
    import subprocess, sys
    subprocess.run(
        [sys.executable, str(ROOT.parent / "render_report.py"), str(ROOT)],
        check=True,
    )
