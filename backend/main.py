"""AI Career Launchpad API. Provider credentials and document text stay server-side."""
from __future__ import annotations
import json, os, re, sqlite3
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError
from pypdf import PdfReader

load_dotenv(Path(__file__).parent / '.env')
DATABASE_URL=os.getenv('DATABASE_URL','sqlite:///./career_launchpad.db')
MAX_BYTES=int(os.getenv('MAX_UPLOAD_MB','5'))*1024*1024
app=FastAPI(title='AI Career Launchpad API',version='1.0.0')
origins=[x.strip() for x in os.getenv('FRONTEND_ORIGIN','http://localhost:3000').split(',') if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=False,allow_methods=['GET','POST','OPTIONS'],allow_headers=['Content-Type','X-User-Id','Authorization'])

class Task(BaseModel):
    title:str
    skill:str
    priority:str='Medium'
    effort:str='2–3 hours'
    completed:bool=False
class Analysis(BaseModel):
    summary:str
    skills:list[str]=[]
    matching_skills:list[str]=[]
    missing_skills:list[str]=[]
    evidence:list[str]=[]
    improvements:list[str]=[]
    roadmap:list[Task]=[]
    readiness_score:int=Field(ge=0,le=100)
    score_explanation:str
class MentorRequest(BaseModel):
    message:str=Field(min_length=1,max_length=4000)
    history:list[dict[str,str]]=Field(default_factory=list,max_length=12)
class InterviewStart(BaseModel):
    role:str=Field(min_length=2,max_length=120)
    mode:str=Field(pattern='^(Technical|HR)$')
class FeedbackRequest(InterviewStart):
    question:str=Field(min_length=1,max_length=2000)
    answer:str=Field(min_length=1,max_length=6000)
class AskRequest(BaseModel):
    question:str=Field(min_length=1,max_length=2000)
class RoadmapUpdate(BaseModel):
    task_index:int=Field(ge=0,le=100)
    completed:bool

def db_path()->str:
    if DATABASE_URL.startswith('sqlite:///'):
        p=DATABASE_URL[len('sqlite:///'):]
        return str((Path(__file__).parent/p).resolve()) if not Path(p).is_absolute() else p
    raise RuntimeError('This MVP currently uses SQLite. Use a persistent volume or migrate to managed PostgreSQL before production.')
@contextmanager
def connect():
    con=sqlite3.connect(db_path(),timeout=10); con.row_factory=sqlite3.Row
    try:
        yield con
        con.commit()
    finally: con.close()
def init_db():
    with connect() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS analyses(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS roadmap(user_id TEXT NOT NULL,task_index INTEGER NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(user_id,task_index));
        CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,filename TEXT NOT NULL,chunks TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS interviews(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);''')
init_db()

def current_user(x_user_id:str|None,authorization:str|None)->str:
    supa=os.getenv('SUPABASE_URL'); anon=os.getenv('SUPABASE_ANON_KEY')
    if os.getenv('APP_REQUIRE_AUTH','true').strip().lower() in ('false','0','no'):
        return x_user_id or 'local-user'
    if not supa or not anon:
        raise HTTPException(503,'Authentication is required but Supabase is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY in backend/.env, then restart the API.')
    if supa and anon:
        if not authorization or not authorization.lower().startswith('bearer '): raise HTTPException(401,'Sign in is required.')
        import httpx
        try:
            r=httpx.get(supa.rstrip('/')+'/auth/v1/user',headers={'apikey':anon,'Authorization':authorization},timeout=8); r.raise_for_status(); return str(r.json()['id'])
        except Exception as e: raise HTTPException(401,'Your sign-in session could not be verified.') from e
    raise HTTPException(401,'Sign in is required.')
def ai_client()->OpenAI:
    key=os.getenv('NEXUS_API_KEY'); model=os.getenv('NEXUS_MODEL')
    if not key or not model: raise HTTPException(503,'AI is not configured. Set NEXUS_API_KEY and NEXUS_MODEL in backend/.env.')
    return OpenAI(api_key=key,base_url=os.getenv('NEXUS_BASE_URL','https://nexusapi.navigatelabs.ai').rstrip('/'),timeout=45,max_retries=1)
def completion(messages:list[dict[str,str]],json_mode:bool=False)->str:
    try:
        kwargs={'model':os.getenv('NEXUS_MODEL'),'messages':messages,'temperature':0.25}
        if json_mode: kwargs['response_format']={'type':'json_object'}
        return ai_client().chat.completions.create(**kwargs).choices[0].message.content or ''
    except HTTPException: raise
    except Exception as e:
        if json_mode:
            try: return ai_client().chat.completions.create(model=os.getenv('NEXUS_MODEL'),messages=messages,temperature=0.2).choices[0].message.content or ''
            except Exception: pass
        raise HTTPException(502,'The AI provider could not complete this request. Check the configured Nexus model and API access.') from e

def extract_text(filename:str,data:bytes)->str:
    if len(data)>MAX_BYTES: raise HTTPException(413,f'File exceeds the {MAX_BYTES//1048576} MB upload limit.')
    ext=Path(filename or '').suffix.lower()
    try:
        if ext=='.txt': text=data.decode('utf-8-sig')
        elif ext=='.pdf':
            # Read directly from memory. Reopening a still-open NamedTemporaryFile by path
            # fails on Windows because the original handle may deny shared access.
            text='\n'.join((p.extract_text() or '') for p in PdfReader(BytesIO(data),strict=False).pages)
        else: raise HTTPException(415,'Only PDF and TXT files are supported.')
    except UnicodeDecodeError as e: raise HTTPException(400,'Text file must use UTF-8 encoding.') from e
    except HTTPException: raise
    except Exception as e: raise HTTPException(400,'Could not read this file. Check that the PDF is valid and contains selectable text.') from e
    text=re.sub(r'\s+',' ',text).strip()
    if not text: raise HTTPException(400,'No readable text was found in this file.')
    return text[:60000]
def parse_json(raw:str)->dict[str,Any]:
    try:
        match=re.search(r'\{.*\}',raw,re.S)
        if not match: raise ValueError('JSON object missing')
        return json.loads(match.group(0))
    except Exception as e: raise HTTPException(502,'The AI returned an unreadable response. Please try again.') from e

@app.get('/health')
def health(): return {'status':'ok','ai_configured':bool(os.getenv('NEXUS_API_KEY') and os.getenv('NEXUS_MODEL')),'auth_required':os.getenv('APP_REQUIRE_AUTH','true').strip().lower() not in ('false','0','no'),'database':'sqlite-local','auth_mode':'supabase' if os.getenv('SUPABASE_URL') and os.getenv('SUPABASE_ANON_KEY') else 'unconfigured'}

@app.post('/api/analyze',response_model=Analysis)
async def analyze(resume:UploadFile=File(...),job_description:str=Form(...),x_user_id:str|None=Header(None),authorization:str|None=Header(None)):
    uid=current_user(x_user_id,authorization); jd=job_description.strip()
    if not jd: raise HTTPException(422,'Add a target job description.')
    resume_text=extract_text(resume.filename or '',await resume.read())
    instructions='Assess resume evidence against the job description. Do not infer lack of a skill merely because the resume omits it. Score is indicative, not a hiring prediction. Return ONLY JSON matching {"summary":"...","skills":["..."],"matching_skills":["..."],"missing_skills":["skills with limited resume evidence"],"evidence":["brief resume evidence"],"improvements":["specific truthful edits"],"roadmap":[{"title":"...","skill":"...","priority":"High|Medium|Low","effort":"...","completed":false}],"readiness_score":0,"score_explanation":"..."}. Provide 3-5 concise tasks. Never invent qualifications.'
    data=parse_json(completion([{'role':'system','content':instructions},{'role':'user','content':f'RESUME:\n{resume_text}\n\nJOB DESCRIPTION:\n{jd}'}],True))
    try: result=Analysis.model_validate(data)
    except ValidationError as e: raise HTTPException(502,'The AI response did not match the expected analysis format. Please retry.') from e
    with connect() as c:
        c.execute('INSERT INTO analyses(id,user_id,payload) VALUES(?,?,?)',(str(uuid4()),uid,result.model_dump_json()))
        c.execute('DELETE FROM roadmap WHERE user_id=?',(uid,))
        c.executemany('INSERT INTO roadmap(user_id,task_index,payload) VALUES(?,?,?)',[(uid,i,t.model_dump_json()) for i,t in enumerate(result.roadmap)])
    return result

@app.post('/api/mentor')
def mentor(req:MentorRequest,x_user_id:str|None=Header(None),authorization:str|None=Header(None)):
    uid=current_user(x_user_id,authorization)
    history=[{'role':m['role'],'content':m['content'][:4000]} for m in req.history[-8:] if m.get('role') in ('user','assistant') and 'content' in m]
    answer=completion([{'role':'system','content':'You are a supportive, practical career mentor. Be accurate, clear, nonjudgmental, and specific. Give actionable next steps; do not promise hiring outcomes.'},*history,{'role':'user','content':req.message}])
    with connect() as c: c.execute('INSERT INTO conversations(id,user_id,payload) VALUES(?,?,?)',(str(uuid4()),uid,json.dumps({'history':history,'answer':answer})))
    return {'answer':answer}

@app.post('/api/interview/start')
def interview_start(req:InterviewStart,x_user_id:str|None=Header(None),authorization:str|None=Header(None)):
    uid=current_user(x_user_id,authorization)
    q=completion([{'role':'system','content':'Generate one realistic interview question for the target role and mode. Output only the question.'},{'role':'user','content':f'Role: {req.role}\nMode: {req.mode}'}])
    with connect() as c: c.execute('INSERT INTO interviews(id,user_id,payload) VALUES(?,?,?)',(str(uuid4()),uid,json.dumps({'role':req.role,'mode':req.mode,'question':q})))
    return {'question':q}
@app.post('/api/interview/feedback')
def interview_feedback(req:FeedbackRequest,x_user_id:str|None=Header(None),authorization:str|None=Header(None)):
    uid=current_user(x_user_id,authorization)
    spec='{"score":1,"strengths":["..."],"improvements":["..."],"missing_concepts":["..."],"clarity":"..."}'
    data=parse_json(completion([{'role':'system','content':f'Give constructive practice feedback. Score 1-10, a practice guide only. Return JSON {spec}.'},{'role':'user','content':f'Role: {req.role}; mode: {req.mode}\nQuestion: {req.question}\nAnswer: {req.answer}'}],True))
    if not isinstance(data.get('score'),int) or not 1<=data['score']<=10: raise HTTPException(502,'The AI returned invalid interview feedback.')
    with connect() as c: c.execute('INSERT INTO interviews(id,user_id,payload) VALUES(?,?,?)',(str(uuid4()),uid,json.dumps({'feedback':data,'question':req.question})))
    return data

def chunks(text:str,size:int=900,overlap:int=120)->list[str]:
    out=[]; start=0
    while start<len(text) and len(out)<100: out.append(text[start:start+size]); start+=size-overlap
    return out
def tokenize(s:str)->set[str]: return set(re.findall(r'[a-z0-9]{3,}',s.lower()))
@app.post('/api/documents')
async def add_document(file:UploadFile=File(...),x_user_id:str|None=Header(None),authorization:str|None=Header(None)):
    uid=current_user(x_user_id,authorization); parts=chunks(extract_text(file.filename or '',await file.read())); name=(file.filename or 'study-material')[:255]; docid=str(uuid4())
    with connect() as c: c.execute('INSERT INTO documents(id,user_id,filename,chunks) VALUES(?,?,?,?)',(docid,uid,name,json.dumps(parts)))
    return {'document_id':docid,'filename':name,'chunk_count':len(parts),'retrieval_mode':'keyword retrieval (embeddings not configured)'}
@app.post('/api/documents/ask')
def ask_document(req:AskRequest,x_user_id:str|None=Header(None),authorization:str|None=Header(None)):
    uid=current_user(x_user_id,authorization); terms=tokenize(req.question)
    with connect() as c: rows=c.execute('SELECT filename,chunks FROM documents WHERE user_id=?',(uid,)).fetchall()
    ranked=[]
    for row in rows:
        for part in json.loads(row['chunks']):
            score=len(terms & tokenize(part))
            if score: ranked.append((score,row['filename'],part))
    ranked.sort(reverse=True); chosen=ranked[:4]
    mode='keyword retrieval (no embeddings configured)'
    if not chosen: return {'answer':'I could not find an answer in your uploaded study materials. Try uploading a relevant document or rephrasing your question.','sources':[],'retrieval_mode':mode}
    context='\n\n'.join(f'SOURCE {i+1} ({n}): {p}' for i,(_,n,p) in enumerate(chosen))
    answer=completion([{'role':'system','content':'Answer using only provided source excerpts. If they do not answer the question, say so clearly. Do not add outside facts. Cite filenames.'},{'role':'user','content':f'QUESTION: {req.question}\n\nEXCERPTS:\n{context}'}])
    return {'answer':answer,'sources':[{'filename':n,'excerpt':p[:450]} for _,n,p in chosen],'retrieval_mode':mode}

@app.post('/api/roadmap/update')
def roadmap_update(req:RoadmapUpdate,x_user_id:str|None=Header(None),authorization:str|None=Header(None)):
    uid=current_user(x_user_id,authorization)
    with connect() as c:
        row=c.execute('SELECT payload FROM roadmap WHERE user_id=? AND task_index=?',(uid,req.task_index)).fetchone()
        if not row: raise HTTPException(404,'That roadmap task was not found for this user.')
        task=json.loads(row['payload']); task['completed']=req.completed
        c.execute('UPDATE roadmap SET payload=? WHERE user_id=? AND task_index=?',(json.dumps(task),uid,req.task_index))
    return {'task_index':req.task_index,'completed':req.completed}
@app.get('/api/dashboard')
def dashboard(x_user_id:str|None=Header(None),authorization:str|None=Header(None)):
    uid=current_user(x_user_id,authorization)
    with connect() as c:
        a=c.execute('SELECT payload FROM analyses WHERE user_id=? ORDER BY created_at DESC LIMIT 1',(uid,)).fetchone()
        tasks=c.execute('SELECT payload FROM roadmap WHERE user_id=? ORDER BY task_index',(uid,)).fetchall()
        chats=c.execute('SELECT payload FROM conversations WHERE user_id=? ORDER BY created_at DESC LIMIT 5',(uid,)).fetchall()
        ints=c.execute('SELECT payload FROM interviews WHERE user_id=? ORDER BY created_at DESC LIMIT 10',(uid,)).fetchall()
    return {'latest_analysis':json.loads(a['payload']) if a else None,'roadmap':[json.loads(r['payload']) for r in tasks],'recent_conversations':[json.loads(r['payload']) for r in chats],'interview_history':[json.loads(r['payload']) for r in ints]}
