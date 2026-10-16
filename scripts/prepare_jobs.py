"""Clean the IT job postings dataset for Visualization 6.
Usage: python scripts/prepare_jobs.py   (run from the project root)
Source: https://data.mendeley.com/datasets/8b62nm2gmv/1
Writes data/jobs_postings.csv: one row per posting (title, skills, salary) with a parsed salary midpoint.
Salaries are treated as thousands of US dollars; descriptions are not used.
"""
import csv,re
from pathlib import Path

src=Path('data/Job Dataset for IT Professionals/Dataset_jotpars.csv')
dest=Path('data/jobs_postings.csv')

def decode(raw):
    # The export mixes UTF-8 with stray Windows-1252 bytes; decode line by line.
    for line in raw.splitlines(keepends=True):
        try: yield line.decode('utf-8')
        except UnicodeDecodeError: yield line.decode('cp1252',errors='replace')

def bound(text):
    # "75k" -> 75, "1lac" / "1 lac" (one lakh = 100,000) -> 100
    text=text.strip().lower().replace(' ','')
    if m:=re.fullmatch(r'([\d.]+)k',text): return float(m[1])
    if m:=re.fullmatch(r'([\d.]+)lac',text): return float(m[1])*100
    raise ValueError(text)

rows=list(csv.DictReader(decode(src.read_bytes())))
out=[]
for r in rows:
    low,high=(bound(v) for v in r['salary_range'].split('-'))
    skills=[s.strip() for s in r['requirment'].split(',') if s.strip()]
    out.append({'title':r['name'].strip(),'requirements':' , '.join(skills),
                'experience':int(float(r['experience'])),'salary_range':r['salary_range'].strip(),
                'salary_low_k':low,'salary_high_k':high,'salary_mid_k':round((low+high)/2,2)})
assert len(out)==8797,len(out)
with dest.open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
print(f'{len(out)} postings, {len({r["title"] for r in out})} titles -> {dest}')
