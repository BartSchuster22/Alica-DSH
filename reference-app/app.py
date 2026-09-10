#!/usr/bin/env python3
"""Independent ALICA reference customer app; Python stdlib + SQLite only."""
from __future__ import annotations
import argparse, contextlib, hashlib, hmac, http.client, http.cookies, http.server, json, os
from pathlib import Path
import re, secrets, sqlite3, ssl, threading, time, urllib.error, urllib.parse, urllib.request, uuid
VERSION = 'alica-application/v1'
LIMIT = 131072
UUID = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')
SUBJECT = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')
FINAL = {'result-ready','rejected','cancelled','deleted'}
def encoded(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True)
def digest(x): return hashlib.sha256(x.encode() if isinstance(x,str) else x).hexdigest()
class Failure(Exception):
    def __init__(self, code, status=400): self.code,self.status=code,status

def require(x, code='invalid_request', status=400):
    if not x: raise Failure(code,status)
def strict_json(raw):
    def pairs(items):
        out={}
        for k,v in items:
            require(k not in out); out[k]=v
        return out
    try: return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:require(False))
    except (ValueError,UnicodeError): raise Failure('invalid_json')
def password_hash(password):
    require(isinstance(password,str) and 12<=len(password)<=1024,'password_policy')
    salt=secrets.token_hex(16)
    return 'scrypt$'+salt+'$'+hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
def password_ok(password, stored):
    if not isinstance(password,str) or len(password)>1024:return False
    _,salt,expected=stored.split('$')
    return hmac.compare_digest(hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex(),expected)
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*_): return None
class Core:
    """Operator-fixed HTTPS peer, no browser-driven URLs, headers or credentials."""
    def __init__(self,url,token,ca=None):
        u=urllib.parse.urlsplit(url)
        require(u.scheme=='https' and u.hostname and not u.username and not u.password and not u.query and not u.fragment and u.path in ('','/'),'core_https_required')
        require(re.fullmatch(r'dsha1_[A-Za-z0-9_-]{43}',token),'invalid_core_credential')
        self.url,self.token=url.rstrip('/'),token
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=ca)))
    def call(self,method,path,body=None,key=None):
        require(re.fullmatch(r'/api/v1/application/requests(?:/[a-f0-9-]{36}(?:/(?:cancel|export|retry-delivery))?)?',path),'invalid_core_path')
        headers={'Authorization':'Bearer '+self.token,'Accept':'application/json'}
        if body is not None:headers['Content-Type']='application/json'
        if key:headers['Idempotency-Key']=key
        req=urllib.request.Request(self.url+path,data=encoded(body).encode() if body is not None else None,headers=headers,method=method)
        try:
            with self.opener.open(req,timeout=12) as r:
                raw=r.read(LIMIT+1);require(len(raw)<=LIMIT,'core_response_limit',502)
                return strict_json(raw)
        except urllib.error.HTTPError as e:
            raise Failure('core_credential_expired_or_revoked' if e.code in (401,403) else 'core_http_'+str(e.code),502)
        except (OSError,urllib.error.URLError,http.client.HTTPException): raise Failure('core_outcome_unknown',502)

class Application:
    def __init__(self,path,application_id,customers,core,callback_secret=None,retention_days=7):
        require(UUID.fullmatch(application_id),'invalid_application_id')
        require(isinstance(customers,dict) and 1<=len(customers)<=1000,'invalid_customers')
        subjects=set()
        for name,c in customers.items():
            require(SUBJECT.fullmatch(name) and set(c)=={'subject','passwordHash'},'invalid_customer')
            require(SUBJECT.fullmatch(c['subject']) and c['subject'] not in subjects,'invalid_subject')
            require(re.fullmatch(r'scrypt\$[a-f0-9]{32}\$[a-f0-9]{128}',c['passwordHash']),'invalid_password_hash')
            subjects.add(c['subject'])
        require(type(retention_days) is int and 1<=retention_days<=30,'invalid_retention')
        require(callback_secret is None or (isinstance(callback_secret,str) and len(callback_secret)>=32),'invalid_callback_secret')
        self.path,self.id,self.customers,self.core=str(path),application_id,customers,core
        self.secret,self.retention=callback_secret,retention_days*86400
        self.lock=threading.Lock()
        self.dummy=password_hash(secrets.token_urlsafe(24))
        Path(path).parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with self.db() as db:
            db.executescript('''
CREATE TABLE IF NOT EXISTS identity(application_id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS accounts(customer TEXT PRIMARY KEY,subject TEXT NOT NULL,deleting INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS login_limits(customer TEXT PRIMARY KEY,failures INTEGER NOT NULL,until REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY,customer TEXT NOT NULL,csrf TEXT NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,customer TEXT NOT NULL,client_key TEXT NOT NULL,payload_hash TEXT NOT NULL,payload TEXT,receipt TEXT UNIQUE,state TEXT NOT NULL,result TEXT,error TEXT,attempt INTEGER NOT NULL DEFAULT 0,polls INTEGER NOT NULL DEFAULT 0,next_at REAL NOT NULL DEFAULT 0,created REAL NOT NULL,deleting INTEGER NOT NULL DEFAULT 0,UNIQUE(customer,client_key));
CREATE TABLE IF NOT EXISTS effects(receipt TEXT PRIMARY KEY,result_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS deliveries(id TEXT PRIMARY KEY,receipt TEXT NOT NULL,body_hash TEXT NOT NULL);
''')
            rows=db.execute('SELECT application_id FROM identity').fetchall()
            require(not rows or [r[0] for r in rows]==[self.id],'database_application_mismatch')
            db.execute('INSERT OR IGNORE INTO identity VALUES(?)',(self.id,))
            for existing in db.execute('SELECT customer,subject FROM accounts'):
                require(existing['customer'] in customers and customers[existing['customer']]['subject']==existing['subject'],'customer_subject_binding_changed')
            for c in customers:db.execute('INSERT OR IGNORE INTO accounts(customer,subject) VALUES(?,?)',(c,customers[c]['subject']))
        os.chmod(path,0o600)
    @contextlib.contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=10);db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA secure_delete=ON')
        try:
            with db:yield db
        finally:db.close()
    def login(self,name,password):
        require(isinstance(name,str) and len(name)<=128,'login_failed',401)
        known=name if name in self.customers else '_unknown'
        with self.lock,self.db() as db:
            now=time.time();rate=db.execute('SELECT * FROM login_limits WHERE customer=?',(known,)).fetchone()
            require(not rate or rate['until']<=now or rate['failures']<5,'login_rate_limited',429)
            c=self.customers.get(name)
            matched=password_ok(password,c['passwordHash'] if c else self.dummy)
            if not matched or not c:
                count=rate['failures']+1 if rate and rate['until']>now else 1
                db.execute('INSERT OR REPLACE INTO login_limits VALUES(?,?,?)',(known,count,now+900))
                # Commit failed-attempt counter before raising.
                db.commit();raise Failure('login_failed',401)
            db.execute('DELETE FROM login_limits WHERE customer=?',(known,))
            db.execute('DELETE FROM sessions WHERE expires<=?',(now,))
            db.execute('DELETE FROM sessions WHERE customer=?',(name,))
            token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(digest(token),name,csrf,now+3600))
            return token,csrf
    def session(self,token):
        require(isinstance(token,str) and len(token)<=128,'login_required',401)
        with self.db() as db:r=db.execute('SELECT * FROM sessions WHERE hash=? AND expires>?',(digest(token),time.time())).fetchone()
        require(r and r['customer'] in self.customers,'login_required',401);return dict(r)
    def logout(self,token):
        with self.db() as db:db.execute('DELETE FROM sessions WHERE hash=?',(digest(token),))
    def row(self,db,customer,id):
        r=db.execute('SELECT * FROM requests WHERE id=? AND customer=?',(id,customer)).fetchone()
        require(r,'not_found',404);return r
    def submit(self,customer,value):
        require(isinstance(value,dict) and set(value)<= {'key','operation','question','corrects'} and {'key','operation','question'}<=set(value))
        require(isinstance(value['key'],str) and UUID.fullmatch(value['key']))
        require(value['operation'] in ('answer','research','refresh','correction'))
        require(isinstance(value['question'],str) and 1<=len(value['question'].strip())<=4000 and '\0' not in value['question'])
        require((value['operation']=='correction')==('corrects' in value))
        with self.lock,self.db() as db:
            require(not db.execute('SELECT deleting FROM accounts WHERE customer=?',(customer,)).fetchone()[0],'account_deletion_pending',409)
            # App-local idempotency survives deletion of a correction target too.
            hash=digest(encoded(value));prior=db.execute('SELECT * FROM requests WHERE customer=? AND client_key=?',(customer,value['key'])).fetchone()
            if prior:
                require(prior['payload_hash']==hash,'idempotency_conflict',409);return self.public(prior)
            require(db.execute("SELECT count(*) FROM requests WHERE customer=? AND state!='deleted'",(customer,)).fetchone()[0]<100,'customer_storage_limit',429)
            require(db.execute("SELECT count(*) FROM requests WHERE state NOT IN ('result-ready','rejected','cancelled','deleted')").fetchone()[0]<32,'queue_full',429)
            p={'contractVersion':VERSION,'subject':self.customers[customer]['subject'],'operation':value['operation'],'question':value['question']}
            if 'corrects' in value:
                require(isinstance(value['corrects'],str) and UUID.fullmatch(value['corrects']))
                target=self.row(db,customer,value['corrects']);require(target['state']=='result-ready' and target['receipt'],'correction_target_unsettled',409)
                p['corrects']=target['receipt']
            id=str(uuid.uuid4())
            db.execute('INSERT INTO requests(id,customer,client_key,payload_hash,payload,state,created) VALUES(?,?,?,?,?,?,?)',(id,customer,value['key'],hash,encoded(p),'pending',time.time()))
            return self.public(self.row(db,customer,id))
    def public(self,r):
        p=json.loads(r['payload']) if r['payload'] else None
        return {'id':r['id'],'receiptId':r['receipt'],'state':r['state'],'operation':p['operation'] if p else None,'question':p['question'] if p else None,'result':json.loads(r['result']) if r['result'] else None,'error':r['error'],'deletionPending':bool(r['deleting']),'createdAt':r['created']}
    def listing(self,customer):
        with self.db() as db:
            return {'requests':[self.public(r) for r in db.execute('SELECT * FROM requests WHERE customer=? ORDER BY created DESC LIMIT 100',(customer,))], 'accountDeletionRequested':bool(db.execute('SELECT deleting FROM accounts WHERE customer=?',(customer,)).fetchone()[0]),'deletionComplete':not db.execute("SELECT 1 FROM requests WHERE customer=? AND state!='deleted' LIMIT 1",(customer,)).fetchone()}
    def effect(self,db,r,result):
        require(isinstance(result,dict) and isinstance(result.get('answer'),str) and len(encoded(result).encode())<=65536,'invalid_core_result',502)
        previous=db.execute('SELECT result_hash FROM effects WHERE receipt=?',(r['receipt'],)).fetchone();hash=digest(encoded(result))
        require(not previous or previous[0]==hash,'result_conflict',409)
        if r['state']=='deleted':return
        db.execute('INSERT OR IGNORE INTO effects VALUES(?,?)',(r['receipt'],hash))
        db.execute("UPDATE requests SET result=?,state='result-ready',error=NULL WHERE id=? AND state!='deleted'",(encoded(result),r['id']))
    def observe(self,db,r,envelope):
        require(isinstance(envelope,dict) and isinstance(envelope.get('receipt'),dict),'invalid_core_response',502)
        q=envelope['receipt'];p=q.get('payload')
        require(isinstance(q.get('id'),str) and UUID.fullmatch(q['id']) and q.get('application_id')==self.id,'core_scope_mismatch',502)
        require(not r['receipt'] or r['receipt']==q['id'],'core_scope_mismatch',502)
        state=q.get('phase');require(state in FINAL|{'accepted','dispatch-unknown','native-linked','cancel-requested','deletion-pending'},'invalid_core_state',502)
        if state!='deleted':require(isinstance(p,dict) and encoded(p)==r['payload'],'core_scope_mismatch',502)
        error=q.get('error_code')
        require(error is None or (isinstance(error,str) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,99}',error)),'invalid_core_response',502)
        db.execute('UPDATE requests SET receipt=?,state=?,error=?,attempt=0,next_at=? WHERE id=?',(q['id'],state,error,time.time()+10,r['id']))
        current=self.row(db,r['customer'],r['id'])
        if state=='result-ready':self.effect(db,current,q.get('result'))
        if state=='deleted':db.execute("UPDATE requests SET payload=NULL,result=NULL,error=NULL,deleting=0 WHERE id=?",(r['id'],))
    def callback(self,headers,raw):
        require(self.secret is not None,'callback_disabled',404)
        require(len(raw)<=LIMIT,'body_limit',413)
        delivery=headers.get('x-alica-delivery','');stamp=headers.get('x-alica-timestamp','');sig=headers.get('x-alica-signature','')
        require(UUID.fullmatch(delivery) and re.fullmatch(r'[0-9]{1,12}',stamp) and abs(time.time()-int(stamp))<=300,'callback_auth_failed',401)
        expected=hmac.new(self.secret.encode(),stamp.encode()+b'.'+delivery.encode()+b'.'+raw,hashlib.sha256).hexdigest()
        require(hmac.compare_digest(expected,sig),'callback_auth_failed',401)
        body=strict_json(raw)
        require(isinstance(body,dict) and set(body)=={'contractVersion','deliveryId','receiptId','applicationId','subject','result'} and body['contractVersion']==VERSION and body['deliveryId']==delivery and body['applicationId']==self.id,'callback_scope_mismatch',403)
        with self.lock,self.db() as db:
            r=db.execute('SELECT * FROM requests WHERE receipt=?',(body['receiptId'],)).fetchone()
            require(r and body['subject']==self.customers[r['customer']]['subject'],'callback_receipt_unknown',409)
            prior=db.execute('SELECT * FROM deliveries WHERE id=?',(delivery,)).fetchone();hash=digest(raw)
            require(not prior or (prior['body_hash']==hash and prior['receipt']==body['receiptId']),'callback_delivery_conflict',409)
            if not prior:
                if r['state']!='deleted':self.effect(db,r,body['result'])
                db.execute('INSERT INTO deliveries VALUES(?,?,?)',(delivery,body['receiptId'],hash))
        return {'acknowledged':True}
    def delete(self,customer,id=None):
        with self.lock,self.db() as db:
            if id:self.row(db,customer,id)
            else:
                db.execute('UPDATE accounts SET deleting=1 WHERE customer=?',(customer,))
            db.execute("UPDATE requests SET deleting=1,attempt=0,polls=0,next_at=0 WHERE customer=? AND state!='deleted'"+(' AND id=?' if id else ''),(customer,id) if id else (customer,))
        return {'deletionRequested':True,'complete':False,'backupExpiry':'operator-managed, not verified'}
    def retry(self,customer,id):
        with self.lock,self.db() as db:
            r=self.row(db,customer,id);require(r['state']!='deleted','already_deleted',409)
            db.execute('UPDATE requests SET attempt=0,polls=0,next_at=0,error=NULL WHERE id=?',(id,))
        return {'sameRequestRetained':True,'inferenceResubmission':False}
    def tick(self):
        # Transport queue only. Core owns admission; Hermes owns inference/work.
        if not self.lock.acquire(blocking=False):return False
        try:
            with self.db() as db:
                now=time.time();db.execute('DELETE FROM sessions WHERE expires<=?',(now,))
                db.execute("UPDATE requests SET error='polling_paused_retry_same_request' WHERE polls>=120 AND state NOT IN ('result-ready','rejected','cancelled','deleted') AND error IS NULL")
                db.execute("UPDATE requests SET deleting=1 WHERE created<? AND state!='deleted'",(now-self.retention,))
                r=db.execute("SELECT * FROM requests WHERE state!='deleted' AND attempt<5 AND polls<120 AND next_at<=? AND (receipt IS NULL OR state NOT IN ('result-ready','rejected','cancelled') OR deleting=1) ORDER BY next_at,created DESC LIMIT 1",(now,)).fetchone()
                if not r:return False
                # Commit attempt before network: process loss is a bounded same-key retry.
                db.execute('UPDATE requests SET attempt=attempt+1,polls=polls+1,next_at=? WHERE id=?',(now+30,r['id']));db.commit()
                try:
                    if not r['receipt']:
                        response=self.core.call('POST','/api/v1/application/requests',json.loads(r['payload']),'reference:'+r['id'])
                    else:
                        path='/api/v1/application/requests/'+r['receipt']
                        if r['deleting'] and r['state'] in FINAL-{'deleted'}:response=self.core.call('DELETE',path)
                        elif r['deleting'] and r['state'] not in {'cancel-requested','deletion-pending'}:response=self.core.call('POST',path+'/cancel',{})
                        else:response=self.core.call('GET',path)
                    self.observe(db,r,response)
                except Failure as e:
                    fatal=e.code in ('core_credential_expired_or_revoked','core_scope_mismatch','invalid_core_response','invalid_core_result','result_conflict') or e.code.startswith(('core_http_4',)) and e.code not in ('core_http_409','core_http_429')
                    db.execute('UPDATE requests SET error=?,attempt=?,next_at=? WHERE id=?',(e.code,5 if fatal else r['attempt']+1,now+min(300,5*2**r['attempt']),r['id']))
            return True
        finally:self.lock.release()
    def export(self,customer):
        data=self.listing(customer);data['contractVersion']=VERSION;data['customer']=customer;data['coreExports']=[]
        for r in data['requests']:
            if r['receiptId'] and r['state']!='deleted':
                x=self.core.call('GET','/api/v1/application/requests/'+r['receiptId']+'/export')
                q=x.get('receipt',{});require(q.get('id')==r['receiptId'] and q.get('application_id')==self.id,'core_scope_mismatch',502)
                require(q.get('phase')=='deleted' or q.get('payload',{}).get('subject')==self.customers[customer]['subject'],'core_scope_mismatch',502)
                data['coreExports'].append(x)
        require(len(encoded(data).encode())<=8*1024*1024,'export_limit',413)
        data['backupExpiry']='operator-managed, not verified';return data

class Handler(http.server.BaseHTTPRequestHandler):
    server_version='ALICA-Reference/1'
    def log_message(self,*_):pass # Do not log passwords, cookies, credentials or question paths.
    def handle(self):
        self.connection.settimeout(15)
        super().handle()
    def send(self,status,value,headers=None,content_type='application/json'):
        raw=value if isinstance(value,bytes) else encoded(value).encode()
        self.send_response(status)
        for k,v in {'Content-Type':content_type,'Content-Length':str(len(raw)),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",'Connection':'close',**(headers or {})}.items():self.send_header(k,v)
        self.end_headers();self.wfile.write(raw)
    def read(self):
        require(not self.headers.get('Transfer-Encoding'),'invalid_body')
        lengths=self.headers.get_all('Content-Length',[])
        require(len(lengths)==1 and lengths[0].isdigit(),'length_required',411)
        n=int(lengths[0]);require(n<=LIMIT,'body_limit',413)
        require(self.headers.get('Content-Type','').split(';')[0]=='application/json','json_required',415)
        raw=self.rfile.read(n);require(len(raw)==n,'incomplete_body');return raw
    def token(self):
        c=http.cookies.SimpleCookie()
        try:c.load(self.headers.get('Cookie',''))
        except http.cookies.CookieError:raise Failure('login_required',401)
        return c['__Host-reference'].value if '__Host-reference' in c else ''
    def route(self):
        app=self.server.application
        require(self.headers.get('Host')==urllib.parse.urlsplit(self.server.origin).netloc,'wrong_host',421)
        path=urllib.parse.urlsplit(self.path).path
        if self.command=='GET' and path in ('/','/app.js','/style.css'):
            name={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}[path]
            return self.send(200,(Path(__file__).parent/'static'/name).read_bytes(),content_type={'/':'text/html; charset=utf-8','/app.js':'text/javascript; charset=utf-8','/style.css':'text/css; charset=utf-8'}[path])
        if self.command=='POST' and path=='/callback':return self.send(200,app.callback(self.headers,self.read()))
        value={}
        if self.command=='POST':
            require(self.headers.get('Origin')==self.server.origin,'origin_denied',403)
            value=strict_json(self.read());require(isinstance(value,dict))
        if self.command=='POST' and path=='/api/login':
            require(set(value)=={'username','password'})
            token,csrf=app.login(value['username'],value['password'])
            return self.send(200,{'csrf':csrf}, {'Set-Cookie':'__Host-reference='+token+'; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=3600'})
        token=self.token();session=app.session(token);customer=session['customer']
        if self.command=='POST':require(hmac.compare_digest(self.headers.get('X-CSRF-Token',''),session['csrf']),'csrf_denied',403)
        if self.command=='GET' and path=='/api/state':return self.send(200,{**app.listing(customer),'customer':customer,'csrf':session['csrf']})
        if self.command=='GET' and path=='/api/export':return self.send(200,app.export(customer),{'Content-Disposition':'attachment; filename="customer-export.json"'})
        if self.command=='POST' and path=='/api/requests':return self.send(202,app.submit(customer,value))
        if self.command=='POST' and path=='/api/delete':
            require(not value);return self.send(202,app.delete(customer))
        if self.command=='POST' and path=='/api/logout':
            require(not value);app.logout(token);return self.send(200,{}, {'Set-Cookie':'__Host-reference=; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=0'})
        m=re.fullmatch(r'/api/requests/([a-f0-9-]{36})/(delete|retry)',path)
        if self.command=='POST' and m:
            require(not value);return self.send(202,getattr(app,m[2])(customer,m[1]))
        raise Failure('not_found',404)
    def do_GET(self):
        try:self.route()
        except Failure as e:self.send(e.status,{'error':e.code})
        except Exception:self.send(500,{'error':'internal_error'})
    do_POST=do_GET
class Server(http.server.ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,*a,**kw):self.slots=threading.BoundedSemaphore(24);super().__init__(*a,**kw)
    def process_request(self,request,address):
        if not self.slots.acquire(blocking=False):self.shutdown_request(request);return
        try:super().process_request(request,address)
        except BaseException:self.slots.release();raise
    def process_request_thread(self,*a):
        try:super().process_request_thread(*a)
        finally:self.slots.release()
def secret_file(name,required=True):
    p=os.environ.get(name+'_FILE')
    require(p or not required,'missing_'+name.lower())
    return Path(p).read_text().strip() if p else None

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--hash-password',action='store_true');a=parser.parse_args()
    if a.hash_password:
        import getpass
        print(password_hash(getpass.getpass('New customer password: ')));return
    origin=os.environ['REFERENCE_ORIGIN'];u=urllib.parse.urlsplit(origin)
    require(u.scheme=='https' and u.hostname and not u.path and not u.query and not u.fragment and not u.username and not u.password,'invalid_origin')
    customers=strict_json(Path(os.environ['REFERENCE_CUSTOMERS_FILE']).read_bytes())
    core=Core(os.environ['REFERENCE_CORE_URL'],secret_file('REFERENCE_CORE_TOKEN'),os.environ.get('REFERENCE_CORE_CA_FILE'))
    app=Application(os.environ.get('REFERENCE_DB','/data/reference.sqlite3'),os.environ['REFERENCE_APPLICATION_ID'],customers,core,secret_file('REFERENCE_CALLBACK_SECRET',False),int(os.environ.get('REFERENCE_RETENTION_DAYS','7')))
    host=os.environ.get('REFERENCE_BIND','127.0.0.1');port=int(os.environ.get('REFERENCE_PORT','8088'))
    cert,key=os.environ.get('REFERENCE_TLS_CERT'),os.environ.get('REFERENCE_TLS_KEY')
    require(bool(cert)==bool(key),'tls_pair_required')
    require(cert or (host=='127.0.0.1' and os.environ.get('REFERENCE_TLS_REVERSE_PROXY')=='true'),'tls_or_loopback_proxy_required')
    server=Server((host,port),Handler);server.application=app;server.origin=origin
    if cert:
        ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.minimum_version=ssl.TLSVersion.TLSv1_2;ctx.load_cert_chain(cert,key);server.socket=ctx.wrap_socket(server.socket,server_side=True)
    stop=threading.Event()
    def pump():
        while not stop.wait(1):
            try:app.tick()
            except Exception:pass # Durable pending remains visible; no raw upstream logging.
    thread=threading.Thread(target=pump,daemon=True);thread.start()
    try:server.serve_forever()
    finally:stop.set();server.server_close();thread.join(timeout=20)
if __name__=='__main__':main()
