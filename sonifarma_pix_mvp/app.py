import os, sqlite3, secrets, hashlib, hmac, csv, io, logging
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException, Header, Request, Response, Depends, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

BASE=os.path.dirname(os.path.abspath(__file__))
DB=os.getenv('PIX_DB',os.path.join(BASE,'pix_monitor.db'))
TOKEN=os.getenv('PIX_ADMIN_TOKEN','')
TZ=ZoneInfo('America/Sao_Paulo')
app=FastAPI(title='Sonifarma Pix Monitor V1.1', docs_url=None, redoc_url=None, openapi_url=None)
logging.basicConfig(level=logging.INFO)
log=logging.getLogger('sonifarma_pix')

def conn():
    db=sqlite3.connect(DB,timeout=15)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA busy_timeout=15000')
    return db

def hash_password(password, salt=None):
    salt=salt or secrets.token_bytes(16)
    dk=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,310000)
    return salt.hex()+':'+dk.hex()

def check_password(password, stored):
    try:
        salt,digest=stored.split(':')
        return hmac.compare_digest(hash_password(password,bytes.fromhex(salt)).split(':')[1],digest)
    except (ValueError,TypeError): return False

@app.on_event('startup')
def startup():
    os.makedirs(os.path.dirname(os.path.abspath(DB)),exist_ok=True)
    with conn() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE IF NOT EXISTS pix (end_to_end_id TEXT PRIMARY KEY, amount_cents INTEGER NOT NULL, payer TEXT, received_at TEXT NOT NULL, created_at TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN (\'caixa\',\'gerencia\')), active INTEGER NOT NULL DEFAULT 1)')
        db.execute('CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires_at TEXT NOT NULL)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_pix_received ON pix(received_at)')
        db.execute('DELETE FROM sessions WHERE expires_at < ?', (datetime.now(timezone.utc).isoformat(),))
        if db.execute('SELECT COUNT(*) FROM users').fetchone()[0]==0:
            log.warning('Nenhum usuario cadastrado. Execute criar_admin.py localmente.')

def auth(request:Request, role=None):
    token=request.cookies.get('sonifarma_session','')
    if not token: raise HTTPException(401,'Entre com usuario e senha')
    digest=hashlib.sha256(token.encode()).hexdigest()
    with conn() as db:
        user=db.execute('SELECT u.id,u.username,u.role FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.active=1',(digest,datetime.now(timezone.utc).isoformat())).fetchone()
    if not user: raise HTTPException(401,'Sessao expirada')
    if role and user['role']!=role: raise HTTPException(403,'Permissao insuficiente')
    return dict(user)

def check_origin(request):
    origin=request.headers.get('origin')
    if origin:
        from urllib.parse import urlsplit
        parsed=urlsplit(origin)
        host=request.headers.get('host','')
        if parsed.netloc!=host: raise HTTPException(403,'Origem nao autorizada')
    else:
        referer=request.headers.get('referer','')
        if referer and urlsplit(referer).netloc!=request.headers.get('host',''): raise HTTPException(403,'Origem nao autorizada')

class Login(BaseModel):
    username:str
    password:str

@app.post('/api/login')
def login(data:Login,request:Request,response:Response):
    check_origin(request)
    with conn() as db:
        user=db.execute('SELECT * FROM users WHERE username=? AND active=1',(data.username.strip().lower(),)).fetchone()
        if not user or not check_password(data.password,user['password_hash']): raise HTTPException(401,'Credenciais invalidas')
        token=secrets.token_urlsafe(40)
        expires=(datetime.now(timezone.utc)+timedelta(hours=10)).isoformat()
        db.execute('INSERT INTO sessions VALUES (?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],expires))
    response.set_cookie('sonifarma_session',token,httponly=True,samesite='strict',secure=os.getenv('PIX_SECURE_COOKIE','0')=='1',max_age=36000,path='/')
    return {'username':user['username'],'role':user['role']}

@app.post('/api/logout')
def logout(request:Request,response:Response):
    check_origin(request)
    token=request.cookies.get('sonifarma_session','')
    with conn() as db: db.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
    response.delete_cookie('sonifarma_session',path='/')
    return {'ok':True}

@app.get('/api/me')
def me(request:Request):return auth(request)

class PixIn(BaseModel):
    end_to_end_id:str=Field(min_length=10,max_length=100)
    amount:str
    payer:str|None=Field(default=None,max_length=200)
    received_at:datetime

@app.post('/internal/pix',status_code=201)
def ingest(data:PixIn,request:Request,x_admin_token:str|None=Header(default=None)):
    # Simulador SOMENTE para teste; nunca apontar webhook do banco para este endpoint.
    if os.getenv('PIX_ENABLE_SIMULATOR','0')!='1': raise HTTPException(404,'Simulador desabilitado')
    if not TOKEN or not x_admin_token or not secrets.compare_digest(TOKEN,x_admin_token): raise HTTPException(401,'Nao autorizado')
    try:
        val=Decimal(data.amount)
        if not val.is_finite() or val<=0 or val.as_tuple().exponent < -2: raise ValueError()
        cents=int((val*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    except (InvalidOperation,ValueError):raise HTTPException(422,'Valor invalido')
    received=data.received_at
    if received.tzinfo is None: raise HTTPException(422,'Data precisa conter fuso horario')
    with conn() as db:
        cur=db.execute('INSERT OR IGNORE INTO pix VALUES (?,?,?,?,?)',(data.end_to_end_id,cents,data.payer,received.astimezone(timezone.utc).isoformat(),datetime.now(timezone.utc).isoformat()))
    return {'inserted':cur.rowcount==1}

def bounds(start,end):
    try:
        a=date.fromisoformat(start) if start else datetime.now(TZ).date()
        b=date.fromisoformat(end) if end else a
        if b<a or (b-a).days>366: raise ValueError()
    except ValueError: raise HTTPException(422,'Periodo invalido (maximo 366 dias)')
    return a.isoformat(),b.isoformat(),datetime.combine(a,datetime.min.time(),TZ).astimezone(timezone.utc).isoformat(),datetime.combine(b+timedelta(days=1),datetime.min.time(),TZ).astimezone(timezone.utc).isoformat()

def filtered(db,start,end,search,limit,offset):
    _,_,a,b=bounds(start,end)
    where='received_at >= ? AND received_at < ?'; args=[a,b]
    if search:
        where+=' AND (payer LIKE ? OR end_to_end_id LIKE ?)';args+=['%'+search[:100]+'%']*2
    total=db.execute('SELECT COUNT(*) n, COALESCE(SUM(amount_cents),0) cents FROM pix WHERE '+where,args).fetchone()
    rows=db.execute('SELECT * FROM pix WHERE '+where+' ORDER BY received_at DESC LIMIT ? OFFSET ?',args+[limit,offset]).fetchall()
    return total,rows

def serialize(row):
    return {'id':row['end_to_end_id'],'amount_cents':row['amount_cents'],'payer':row['payer'],'received_at':row['received_at']}

@app.get('/api/pix')
def list_pix(request:Request,start:str|None=None,end:str|None=None,search:str='',page:int=Query(1,ge=1,le=100000)):
    auth(request)
    with conn() as db: total,rows=filtered(db,start,end,search,50,(page-1)*50)
    return {'total_cents':total['cents'],'count':total['n'],'page':page,'pages':max(1,(total['n']+49)//50),'items':[serialize(r) for r in rows]}

@app.get('/api/latest')
def latest(request:Request):
    auth(request)
    with conn() as db:row=db.execute('SELECT * FROM pix ORDER BY created_at DESC LIMIT 1').fetchone()
    return {'item':serialize(row) if row else None,'bank_connected':False,'simulator':os.getenv('PIX_ENABLE_SIMULATOR','0')=='1'}

@app.get('/api/report.csv')
def report(request:Request,start:str|None=None,end:str|None=None,search:str=''):
    auth(request,'gerencia')
    _,_,a,b=bounds(start,end)
    with conn() as db:
        where='received_at >= ? AND received_at < ?'; args=[a,b]
        if search:where+=' AND (payer LIKE ? OR end_to_end_id LIKE ?)';args+=['%'+search[:100]+'%']*2
        rows=db.execute('SELECT * FROM pix WHERE '+where+' ORDER BY received_at DESC LIMIT 100000',args).fetchall()
    output=io.StringIO();writer=csv.writer(output,delimiter=';');writer.writerow(['Data UTC','Pagador','Valor (R$)','EndToEndId'])
    for r in rows:
        payer=(r['payer'] or '').replace('\r',' ').replace('\n',' ')
        if payer.startswith(('=','+','-','@')):payer="'"+payer
        writer.writerow([r['received_at'],payer,f"{r['amount_cents']/100:.2f}".replace('.',','),r['end_to_end_id']])
    return Response(content='\ufeff'+output.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="sonifarma_pix_relatorio.csv"'})

class UserIn(BaseModel):
    username:str=Field(min_length=3,max_length=40,pattern=r'^[a-zA-Z0-9_.-]+$')
    password:str=Field(min_length=8,max_length=128)
    role:str=Field(pattern='^(caixa|gerencia)$')

@app.get('/api/users')
def users(request:Request):
    auth(request,'gerencia')
    with conn() as db: return [dict(r) for r in db.execute('SELECT id,username,role,active FROM users ORDER BY username')]

@app.post('/api/users',status_code=201)
def add_user(data:UserIn,request:Request):
    auth(request,'gerencia');check_origin(request)
    try:
        with conn() as db:db.execute('INSERT INTO users(username,password_hash,role) VALUES(?,?,?)',(data.username.lower(),hash_password(data.password),data.role))
    except sqlite3.IntegrityError:raise HTTPException(409,'Usuario ja existe')
    return {'ok':True}

@app.get('/health')
def health():return {'app':'ok','bank_connection':'not_configured','version':'1.1'}

@app.get('/',response_class=HTMLResponse)
def home():
    with open(os.path.join(BASE,'index.html'),encoding='utf-8') as f:return HTMLResponse(f.read(),headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"})

@app.get('/panel.js')
def js():
    from fastapi.responses import FileResponse
    return FileResponse(os.path.join(BASE,'panel.js'),media_type='application/javascript',headers={'Cache-Control':'no-store'})
