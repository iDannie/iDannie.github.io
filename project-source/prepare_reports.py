"""Create review copies from original PBIX files without changing the data model.
Run: python project-source/prepare_reports.py /path/to/originals /path/to/output
Open and save the resulting files in Power BI Desktop before final publication.
"""
from pathlib import Path
import sys, json, zipfile, hashlib

source_dir, output_dir = map(Path, sys.argv[1:3])
output_dir.mkdir(parents=True, exist_ok=True)
log = {}
for source in source_dir.glob('*.pbix'):
    changed = []
    target = output_dir / (source.stem.replace(' ', '_') + '_review.pbix')
    with zipfile.ZipFile(source) as zin, zipfile.ZipFile(target,'w') as zout:
        for entry in zin.infolist():
            raw=zin.read(entry.filename)
            if entry.filename.startswith('Report/definition/') and entry.filename.endswith('.json'):
                d=json.loads(raw); before=json.dumps(d)
                if entry.filename.endswith('/page.json'):
                    names={'spotify':{'Page 6':'Music Overview'},'apple product':{'Page 1':'Product Performance'},'Product Dashboard':{'Page 1':'Order Fulfilment'}}
                    d['displayName']=names.get(source.stem,{}).get(d.get('displayName'),d.get('displayName'))
                def walk(x):
                    if isinstance(x,dict):
                        for k,v in list(x.items()):
                            if isinstance(v,str):
                                if source.stem=='Product Dashboard' and v=="'ReportSectiona70e59135dfbaae71f14'":x[k]="'e3bac61c205d4308d870'"
                                if source.stem=='spotify':
                                    x[k]=x[k].replace('"title": "Orders"','"title": "Tracks"')
                                    if v=='Take a look at your daily report ':x[k]='Explore tracks and release patterns'
                                if source.stem=='apple product' and v=="'Total Quality'":x[k]="'Total Quantity'"
                                if source.stem=='business_insight 360':x[k]=x[k].replace('profitability/ Growth matrix/ Growth matrix','profitability and growth matrix')
                            else:walk(v)
                    elif isinstance(x,list):
                        for v in x:walk(v)
                walk(d)
                # Clarify unavailable home-page options without removing report objects.
                if source.stem=='business_insight 360' and 'ReportSection83bf87fca58bbb50be50/visuals/' in entry.filename:
                    vid=entry.filename.split('/')[-2]
                    replacements={
                      'a53b1a4095019052e4aa':'Executive View',
                      'a4f7b4fc30e805005098':'Not included in this version. Use Finance, Sales, Marketing and Supply Chain views.',
                      'b09d26b54a05026bacc3':'Portfolio report. Explore the four analytical views using the navigation icons.',
                      'ccd4a6e3bc747b8a6042':'For project questions, contact Daniel through the portfolio website.'}
                    if vid in replacements:
                        paragraphs=d['visual']['objects']['general'][0]['properties']['paragraphs']
                        style=paragraphs[0]['textRuns'][0].get('textStyle',{})
                        paragraphs[:]=[{'textRuns':[{'value':replacements[vid],'textStyle':style}],'horizontalTextAlignment':'center'}]
                    if vid in ['07f8b16cb4237259da64','91f932878eea32335d0a','bfe1d6f6e3d01320707b']:
                        d.get('visual',{}).get('visualContainerObjects',{}).pop('visualLink',None)
                if json.dumps(d)!=before:
                    changed.append(entry.filename);raw=(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode()
            zout.writestr(entry,raw)
    with zipfile.ZipFile(source) as a,zipfile.ZipFile(target) as b:
        assert b.testzip() is None
        assert a.namelist()==b.namelist()
        for n in a.namelist():
            if n not in changed:assert hashlib.sha256(a.read(n)).digest()==hashlib.sha256(b.read(n)).digest()
        pages={json.loads(b.read(n))['name'] for n in b.namelist() if n.endswith('/page.json')}
        def check_nav(x):
            if isinstance(x,dict):
                for k,v in x.items():
                    if k=='navigationSection':assert v['expr']['Literal']['Value'].strip("'") in pages
                    check_nav(v)
            elif isinstance(x,list):
                for v in x:check_nav(v)
        for n in b.namelist():
            if n.startswith('Report/definition/') and n.endswith('.json'):check_nav(json.loads(b.read(n)))
    log[source.name]={'output':target.name,'changes':changed,'unchanged_entries_verified':True,'page_navigation_checked':True,'desktop_validation':'pending'}
(output_dir/'changes.json').write_text(json.dumps(log,indent=2))
print({k:len(v['changes']) for k,v in log.items()})
