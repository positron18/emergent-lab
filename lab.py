#!/usr/bin/env python3
"""Emergent Lab: small, logged multi-agent FinQA research commons (stdlib only)."""
import argparse, datetime as dt, json, os, pathlib, random, re, sqlite3, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
DATA_URL = 'https://raw.githubusercontent.com/czyssrs/FinQA/0f16e2867befa6840783e58be38c9efb9229d742/dataset/dev.json'
SYSTEM = '''You are an independent financial reasoning agent. Your goal is to answer your assigned numerical question correctly using the provided evidence. You have a private workspace and a general-purpose shared artifact store. You can inspect and create artifacts and use them however you consider useful. You are not required to communicate with anyone. Only use documented tools. Reply with exactly one JSON object for one action, no markdown. Actions: {"action":"list","scope":"shared"}, {"action":"read","scope":"shared"|"private","name":"filename.txt"}, {"action":"write","scope":"shared"|"private","name":"filename.txt","content":"text"}, {"action":"answer","value":"number or percent"}, {"action":"think","note":"brief thoughts"}. Avoid putting question answers into shared files unless you decide to; the lab does not impose a social policy. Do not assume shared artifacts are correct.'''

def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
def emit(db, agent, typ, detail):
    db.execute('INSERT INTO events(ts,agent,kind,detail) VALUES(?,?,?,?)',(now(),agent,typ,json.dumps(detail,ensure_ascii=False)));db.commit()
def db_init(run):
    run.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(run/'events.sqlite3')
    db.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,ts TEXT,agent TEXT,kind TEXT,detail TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS scores(agent TEXT, task TEXT, predicted TEXT, expected TEXT, correct INTEGER)')
    db.commit()
    return db

def safe_name(s):
    if not isinstance(s,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,75}',s) or s in ('.','..'):
        raise ValueError('Invalid flat file name')
    return s

def get_artifact(run,agent,scope,name):
    name=safe_name(name)
    if scope not in ('shared','private'): raise ValueError('Invalid scope')
    folder=run/'shared' if scope=='shared' else run/'private'/agent
    folder.mkdir(parents=True,exist_ok=True)
    return folder/name

def request_llm(messages,model,endpoint,key):
    if not endpoint.startswith('https://') and not endpoint.startswith('http://localhost:') and not endpoint.startswith('http://127.0.0.1:'):
        raise ValueError('Endpoint must be HTTPS, or local HTTP')
    body=json.dumps({'model':model,'messages':messages,'temperature':0.5,'max_tokens':600}).encode()
    req=urllib.request.Request(endpoint,data=body,headers={'Content-Type':'application/json','Authorization':f'Bearer {key}'},method='POST')
    with urllib.request.urlopen(req,timeout=90) as resp: data=json.load(resp)
    content=data['choices'][0]['message']['content']
    if isinstance(content,list): content=''.join(x.get('text','') for x in content if isinstance(x,dict))
    content=re.sub(r'^```(?:json)?\s*|\s*```$','',content.strip())
    return json.loads(content)

def demo_action(agent,step,task):
    # Scripted infrastructure test; explicitly NOT AI emergence.
    choices=[{'action':'list','scope':'shared'},
             {'action':'write','scope':'shared','name':f'observations_{agent}.txt','content':'Demonstration-only note; created by a scripted dummy, not an LLM.'},
             {'action':'answer','value':'0'}]
    return choices[min(step,len(choices)-1)]

def numeric(v):
    s=str(v).strip().lower().replace(',','').replace('$','').replace(' ','')
    pct='%' in s
    s=s.replace('%','')
    scale=1
    for unit,mult in [('billion',1e9),('million',1e6),('thousand',1e3),('bn',1e9)]:
        if s.endswith(unit): scale=mult;s=s[:-len(unit)];break
    try:return float(s)*scale,pct
    except ValueError:return None,pct

def check_answer(pred,expected):
    a,ap=numeric(pred); b,bp=numeric(expected)
    if a is None or b is None:return False
    if ap!=bp:
        # FinQA often uses percentages as '8.9%' vs 8.9; allow unitless equivalent.
        if ap and not bp: return abs(a-b)<max(0.01,0.01*abs(b)) or abs(a/100-b)<max(0.0001,0.01*abs(b))
        if bp and not ap: return abs(a-b)<max(0.01,0.01*abs(b)) or abs(a-b/100)<max(0.0001,0.01*abs(b/100))
    return abs(a-b)<=max(0.01,0.01*abs(b))

def sample_tasks():
    return [
      {'id':'DEMO-1','pre_text':['Example fictional annual report.'],'post_text':[],'table':[['Year','Revenue'],['2023','$120 million'],['2024','$150 million']],'qa':{'question':'What was the percent change in revenue from 2023 to 2024?','exe_ans':'25%'}},
      {'id':'DEMO-2','pre_text':['Example fictional annual report.'],'post_text':[],'table':[['Year','Net income'],['2023','80'],['2024','100']],'qa':{'question':'What was the percent change in net income?','exe_ans':'25%'}},
      {'id':'DEMO-3','pre_text':['Example fictional financial statement.'],'post_text':[],'table':[['Revenue','200'],['Cost','140']],'qa':{'question':'What is the gross profit?','exe_ans':'60'}}]

def load_tasks(path,count,seed):
    if path is None:return sample_tasks()[:count]
    tasks=json.loads(path.read_text())
    random.Random(seed).shuffle(tasks)
    return tasks[:count]

def task_prompt(t, history):
    qa=t['qa']; table=t.get('table') or []
    evidence={'question':qa.get('question',''), 'pre_text':t.get('pre_text',[]),'table':table, 'post_text':t.get('post_text',[])}
    s='FINANCIAL DOCUMENT (reference answer hidden):\n'+json.dumps(evidence,ensure_ascii=False)[:18000]
    return s+'\n\nPrevious actions and outcomes in this task:\n'+json.dumps(history[-7:],ensure_ascii=False)[:7000]

def main():
    p=argparse.ArgumentParser(description='Research commons proof of concept')
    p.add_argument('--mode',choices=['demo','llm'],default='demo')
    p.add_argument('--dataset',type=pathlib.Path)
    p.add_argument('--agents',type=int,default=6)
    p.add_argument('--tasks',type=int,default=12)
    p.add_argument('--turns',type=int,default=5)
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--model',default=os.getenv('LAB_MODEL',''))
    p.add_argument('--endpoint',default=os.getenv('LAB_ENDPOINT','https://api.openai.com/v1/chat/completions'))
    p.add_argument('--run-dir',type=pathlib.Path)
    p.add_argument('--fetch-dev',action='store_true')
    args=p.parse_args()
    if args.fetch_dev:
        dest=ROOT/'finqa_dev.json'
        print('Downloading official FinQA dev.json:',dest)
        urllib.request.urlretrieve(DATA_URL,dest)
        print('Ready. Run with --dataset finqa_dev.json --mode llm');return
    if args.agents<1 or args.tasks<1 or not 1<=args.turns<=30:p.error('agents/tasks must be positive, turns 1..30')
    if args.mode=='llm' and (not args.model or not os.getenv('LAB_API_KEY')):p.error('LLM mode requires --model/LAB_MODEL and LAB_API_KEY')
    if args.mode=='llm' and not args.dataset:p.error('LLM mode requires official FinQA JSON via --dataset (to avoid confusing demo data with a benchmark)')
    run=args.run_dir or ROOT/'runs'/dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    if run.exists():p.error('Run directory exists: use a new path to keep experiments immutable')
    db=db_init(run)
    tasks=load_tasks(args.dataset,args.tasks,args.seed)
    if not tasks: p.error('Dataset empty')
    (run/'metadata.json').write_text(json.dumps({'mode':args.mode,'model':args.model,'seed':args.seed,'agents':args.agents,'tasks':len(tasks),'turns':args.turns,'created':now()},indent=2))
    agents=[f'A{i:02d}' for i in range(1,args.agents+1)]
    queue=[(agents[i%len(agents)],task) for i,task in enumerate(tasks)]
    random.Random(args.seed).shuffle(queue)
    for agent,task in queue:
        tid=str(task.get('id','unnamed'))
        history=[];pred=None
        emit(db,agent,'task_assigned',{'task':tid})
        for step in range(args.turns):
            try:
                if args.mode=='demo':act=demo_action(agent,step,task)
                else:
                    personal=(run/'private'/agent/'memory.txt')
                    memory=personal.read_text()[:6000] if personal.exists() else ''
                    messages=[{'role':'system','content':SYSTEM},{'role':'user','content':'Private memory:\n'+memory+'\n\n'+task_prompt(task,history)}]
                    act=request_llm(messages,args.model,args.endpoint,os.environ['LAB_API_KEY'])
                if not isinstance(act,dict): raise ValueError('Action must be JSON object')
                kind=act.get('action');detail={'task':tid,'turn':step,'action':kind}
                if kind=='list':
                    if act.get('scope')!='shared':raise ValueError('Only shared listing permitted')
                    found=sorted(x.name for x in (run/'shared').glob('*') if x.is_file())[:100] if (run/'shared').exists() else []
                    outcome={'files':found};emit(db,agent,'list_shared',dict(detail,files=found))
                elif kind=='read':
                    scope=act.get('scope');name=act.get('name');path=get_artifact(run,agent,scope,name)
                    content=path.read_text()[:12000] if path.is_file() else '(not found)'
                    outcome={'content':content}
                    emit(db,agent,'read',dict(detail,scope=scope,name=name,exists=path.is_file()))
                elif kind=='write':
                    scope=act.get('scope');name=act.get('name');content=act.get('content')
                    if not isinstance(content,str) or len(content)>12000:raise ValueError('Content too long')
                    path=get_artifact(run,agent,scope,name)
                    if path.exists() and path.stat().st_size>12000:raise ValueError('Existing file too long')
                    path.write_text(content)
                    outcome={'status':'saved'}
                    emit(db,agent,'write',dict(detail,scope=scope,name=name,bytes=len(content)))
                elif kind=='answer':
                    pred=str(act.get('value',''));outcome={'status':'submitted'}
                    emit(db,agent,'answer',dict(detail,value=pred));history.append({'action':act,'outcome':outcome});break
                elif kind=='think':
                    outcome={'status':'thought recorded'}
                    emit(db,agent,'think',dict(detail,note=str(act.get('note',''))[:500]))
                else: raise ValueError('Unsupported action')
                history.append({'action':act,'outcome':outcome})
            except Exception as exc:
                emit(db,agent,'error',{'task':tid,'turn':step,'error':str(exc)[:500]})
                history.append({'error':str(exc)[:300]})
                if args.mode=='llm' and isinstance(exc,urllib.error.HTTPError):
                    print('HTTP error from provider:',exc, file=sys.stderr)
                    break
        expected=str(task.get('qa',{}).get('exe_ans',task.get('qa',{}).get('answer','')))
        correct=int(check_answer(pred,expected)) if pred is not None else 0
        db.execute('INSERT INTO scores VALUES (?,?,?,?,?)',(agent,tid,pred,expected,correct));db.commit()
        print(f'{agent} | {tid} | answer={pred!r} | correct={bool(correct)}')
    total,success=db.execute('SELECT COUNT(*),COALESCE(SUM(correct),0) FROM scores').fetchone()
    shared=db.execute("SELECT COUNT(*) FROM events WHERE kind='write' AND json_extract(detail,'$.scope')='shared'").fetchone()[0]
    print(f'\nRun: {run}\nResults: {success}/{total} correct; shared writes: {shared}\nInspect with: python3 report.py {run}')
    db.close()

if __name__=='__main__':main()
