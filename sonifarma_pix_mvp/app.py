import os, sqlite3, secrets, hashlib, hmac, csv, io, logging
import json, ssl, urllib.request, urllib.error
from urllib.parse import urlencode, urlsplit
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException, Header, Request, Response, Depends, Query
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field

BASE=os.path.dirname(os.path.abspath(__file__))
DB=os.getenv('PIX_DB',os.path.join(BASE,'pix_monitor.db'))
TOKEN=os.getenv('PIX_ADMIN_TOKEN','')
TZ=ZoneInfo('America/Sao_Paulo')
app=FastAPI(title='Sonifarma Pix Monitor V1.2', docs_url=None, redoc_url=None, openapi_url=None)
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


# Sandbox somente: URL fixa, sem redirecionamentos e sem persistir tokens ou resultados.
SANDBOX_URL = 'https://sandbox.devportal.itau.com.br/itau-ep9-api-regulatorio-pix-v2-externo/v2/pix'

class SandboxQuery(BaseModel):
    token: str = Field(min_length=10, max_length=8192, repr=False, pattern=r'^[A-Za-z0-9._~+/-]+=*$')
    inicio: datetime
    fim: datetime
    pagina: int = Field(default=0, ge=0, le=100000)
    itens: int = Field(default=100, ge=1, le=100)

class NoSandboxRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, 'Redirecionamento bloqueado', headers, fp)

def fetch_sandbox(data):
    query = urlencode({'inicio': data.inicio.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
                       'fim': data.fim.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
                       'paginacao.paginaAtual': data.pagina, 'paginacao.itensPorPagina': data.itens})
    req = urllib.request.Request(SANDBOX_URL + '?' + query, headers={
        'Authorization': 'Bearer ' + data.token, 'Accept': 'application/json'})
    opener = urllib.request.build_opener(NoSandboxRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(req, timeout=30) as response:
            body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise HTTPException(502, 'Resposta do sandbox excedeu o limite permitido')
            return json.loads(body.decode('utf-8'))
    except urllib.error.HTTPError as exc:
        messages = {401: 'Token do sandbox inválido ou expirado. Gere outro no portal.',
                    403: 'Acesso negado pelo sandbox. Confira as permissões da aplicação.',
                    400: 'O sandbox rejeitou os parâmetros da consulta.',
                    429: 'Limite de consultas do sandbox atingido. Aguarde e tente novamente.'}
        status = exc.code
        exc.close()
        raise HTTPException(502, messages.get(status, 'Sandbox indisponível ou resposta HTTP inesperada.') + f' (HTTP {status})') from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise HTTPException(502, 'Não foi possível conectar ao sandbox com TLS validado. Confira rede, certificado de confiança e tente novamente.') from None
    except (ValueError, UnicodeError):
        raise HTTPException(502, 'O sandbox retornou uma resposta JSON inválida.') from None

def sandbox_cents(value):
    if not isinstance(value, str):
        raise ValueError('Valor monetário deve ser texto')
    amount = Decimal(value)
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2 or amount > Decimal('999999999999.99'):
        raise ValueError('Valor monetário inválido')
    return int(amount * 100)

def normalize_sandbox(payload, data):
    try:
        body = payload.get('value', payload)
        rows = body['pix']
        if not isinstance(rows, list) or len(rows) > 1000:
            raise ValueError('Lista inválida')
        items, warnings, seen = [], [], set()
        for row in rows:
            identity = row['endToEndId']
            if not isinstance(identity, str) or not 10 <= len(identity) <= 100:
                raise ValueError('Identificador inválido')
            if identity in seen:
                warnings.append('A resposta contém identificadores repetidos; confira os dados do sandbox.')
            seen.add(identity)
            moment = datetime.fromisoformat(row['horario'].replace('Z', '+00:00'))
            if moment.tzinfo is None:
                raise ValueError('Data sem fuso')
            if not data.inicio <= moment <= data.fim:
                warnings.append('O sandbox retornou registros fora do período solicitado. São dados de teste.')
            refunds = row.get('devolucoes', [])
            if not isinstance(refunds, list):
                raise ValueError('Devoluções inválidas')
            returned = sum(sandbox_cents(r['valor']) for r in refunds if r.get('status') == 'DEVOLVIDO')
            description = row.get('infoPagador') or ''
            if not isinstance(description, str):
                description = str(description)
            items.append({'id': identity, 'amount_cents': sandbox_cents(row['valor']),
                          'received_at': moment.isoformat(), 'description': description[:500],
                          'returned_cents': returned})
        pagination = body.get('parametros', {}).get('paginacao', {})
        current, pages, total = (pagination[k] for k in ('paginaAtual', 'quantidadeDePaginas', 'quantidadeTotalDeItens'))
        if any(type(n) is not int or n < 0 for n in (current, pages, total)):
            raise ValueError('Paginação inválida')
        if total < len(items) or (pages <= 1 and total != len(items)) or current != data.pagina:
            warnings.append('A paginação informada pelo sandbox não confere com os registros retornados.')
        return {'environment': 'sandbox', 'bank_connected': False, 'items': items,
                'page': current, 'pages': pages, 'reported_total': total,
                'total_cents': sum(r['amount_cents'] for r in items),
                'returned_cents': sum(r['returned_cents'] for r in items),
                'warnings': list(dict.fromkeys(warnings))}
    except (ValueError, KeyError, TypeError, AttributeError, InvalidOperation, OverflowError):
        raise HTTPException(502, 'Resposta do sandbox incompatível com o formato de recebimentos esperado.') from None

@app.exception_handler(RequestValidationError)
async def safe_validation_error(request: Request, exc: RequestValidationError):
    # Nunca devolver o token recebido, mesmo em caso de erro de validação.
    if request.url.path == '/api/itau/sandbox':
        return JSONResponse(status_code=422, content={'detail': 'Confira o token, as datas com fuso e a paginação da consulta.'}, headers={'Cache-Control': 'no-store'})
    from fastapi.exception_handlers import request_validation_exception_handler
    return await request_validation_exception_handler(request, exc)

@app.post('/api/itau/sandbox')
def query_sandbox(data: SandboxQuery, request: Request, response: Response):
    auth(request, 'gerencia')
    check_origin(request)
    # O painel original usa HTTP: só aceite credenciais no próprio computador servidor.
    if not request.client or request.client.host not in ('127.0.0.1', '::1'):
        raise HTTPException(403, 'Abra o painel no próprio servidor por http://localhost:8080 para testar o sandbox.')
    if data.inicio.tzinfo is None or data.fim.tzinfo is None or data.fim < data.inicio or data.fim - data.inicio > timedelta(days=31):
        raise HTTPException(422, 'Informe datas com fuso e período de até 31 dias.')
    response.headers['Cache-Control'] = 'no-store'
    return normalize_sandbox(fetch_sandbox(data), data)

@app.get('/health')
def health():return {'app':'ok','bank_connection':'not_configured','version':'1.2'}

@app.get('/',response_class=HTMLResponse)
def home():
    with open(os.path.join(BASE,'index.html'),encoding='utf-8') as f:return HTMLResponse(f.read(),headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"})

@app.get('/panel.js')
def js():
    from fastapi.responses import FileResponse
    return FileResponse(os.path.join(BASE,'panel.js'),media_type='application/javascript',headers={'Cache-Control':'no-store'})
