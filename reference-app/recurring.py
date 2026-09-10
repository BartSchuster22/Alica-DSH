"""App-owned, revocable recurring admission capability; never a scheduler."""
import hashlib,hmac,json,secrets,time,uuid

class Recurring:
    def __init__(self,app,require,project_id=None):
        self.a,self.require,self.project=app,require,project_id
        with app.db() as db:
            db.executescript('''
CREATE TABLE IF NOT EXISTS recurring_grants(id TEXT PRIMARY KEY,customer TEXT NOT NULL,token_hash TEXT NOT NULL,payload TEXT,max_runs INTEGER NOT NULL,used INTEGER NOT NULL DEFAULT 0,expires REAL NOT NULL,revoked INTEGER NOT NULL DEFAULT 0,min_interval INTEGER NOT NULL,last_new REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS recurring_events(grant_id TEXT NOT NULL,event_key TEXT NOT NULL,request_id TEXT,cancelled INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(grant_id,event_key));
''')
            if 'cancelled' not in {r[1] for r in db.execute('PRAGMA table_info(recurring_events)')}:db.execute('ALTER TABLE recurring_events ADD COLUMN cancelled INTEGER NOT NULL DEFAULT 0')
    def issue(self,customer,value):
        q=self.require
        q(self.project is not None,'recurring_not_configured',503)
        q(isinstance(value,dict) and set(value)=={'operation','question','maxRuns','minIntervalSeconds','expiresInSeconds'})
        q(value['operation'] in ('answer','research','refresh'))
        q(isinstance(value['question'],str) and 1<=len(value['question'].strip())<=4000 and '\0' not in value['question'])
        for k,lo,hi in [('maxRuns',1,100),('minIntervalSeconds',60,86400),('expiresInSeconds',60,2592000)]:
            q(type(value[k]) is int and lo<=value[k]<=hi)
        token=secrets.token_urlsafe(32);id=str(uuid.uuid4())
        with self.a.lock,self.a.db() as db:
            q(not db.execute('SELECT deleting FROM accounts WHERE customer=?',(customer,)).fetchone()[0],'account_deletion_pending',409)
            q(db.execute('SELECT count(*) FROM recurring_grants WHERE customer=? AND revoked=0 AND expires>?',(customer,time.time())).fetchone()[0]<8,'recurring_grant_limit',429)
            db.execute('INSERT INTO recurring_grants(id,customer,token_hash,payload,max_runs,expires,min_interval) VALUES(?,?,?,?,?,?,?)',(id,customer,hashlib.sha256(token.encode()).hexdigest(),json.dumps({'operation':value['operation'],'question':value['question']}),value['maxRuns'],time.time()+value['expiresInSeconds'],value['minIntervalSeconds']))
        return {'grantId':id,'token':token,'scope':'this grant only; no Core credentials','projectId':self.project}
    def authorize(self,db,id,token,allow_revoked=False):
        self.require(isinstance(token,str) and len(token)<=128,'recurring_auth_denied',401)
        r=db.execute('SELECT * FROM recurring_grants WHERE id=?',(id,)).fetchone()
        self.require(r and hmac.compare_digest(r['token_hash'],hashlib.sha256(token.encode()).hexdigest()),'recurring_auth_denied',401)
        deleting=db.execute('SELECT deleting FROM accounts WHERE customer=?',(r['customer'],)).fetchone()[0]
        self.require(allow_revoked or not(r['revoked'] or deleting or r['expires']<=time.time()),'recurring_revoked_or_expired',403)
        return r
    def info(self,id,token):
        with self.a.db() as db:
            r=self.authorize(db,id,token)
            return {'grantId':id,'applicationId':self.a.id,'subject':self.a.customers[r['customer']]['subject'],'projectId':self.project,'maxRuns':r['max_runs'],'used':r['used'],'minIntervalSeconds':r['min_interval'],'expiresAt':r['expires']}
    def event(self,id,token,key,dispatch=False,cancel=False):
        with self.a.lock:return self._event(id,token,key,dispatch,cancel)
    def _event(self,id,token,key,dispatch=False,cancel=False):
        self.require(not(dispatch and cancel))
        self.require(isinstance(key,str) and len(key)<=128 and key and all(c.isalnum() or c in '-_:.' for c in key))
        with self.a.lock:
            with self.a.db() as db:
                db.execute('BEGIN IMMEDIATE')
                r=self.authorize(db,id,token,allow_revoked=not dispatch)
                event=db.execute('SELECT * FROM recurring_events WHERE grant_id=? AND event_key=?',(id,key)).fetchone()
                if not event and dispatch:
                    self.require(r['used']<r['max_runs'],'recurring_budget_exhausted',429)
                    self.require(time.time()-r['last_new']>=r['min_interval'],'recurring_rate_limit',429)
                    db.execute('INSERT INTO recurring_events(grant_id,event_key) VALUES(?,?)',(id,key))
                    db.execute('UPDATE recurring_grants SET used=used+1,last_new=? WHERE id=?',(time.time(),id))
                if event and not event['request_id']:
                    found=db.execute('SELECT id FROM requests WHERE customer=? AND client_key=?',(r['customer'],str(uuid.uuid5(uuid.UUID(id),key)))).fetchone()
                    if found:
                        db.execute('UPDATE recurring_events SET request_id=? WHERE grant_id=? AND event_key=?',(found['id'],id,key))
                        event=db.execute('SELECT * FROM recurring_events WHERE grant_id=? AND event_key=?',(id,key)).fetchone()
                if dispatch and event:self.require(not event['cancelled'],'recurring_occurrence_cancelled',410)
                if cancel:
                    if not event:
                        self.require(r['used']<r['max_runs'],'recurring_budget_exhausted',429)
                        db.execute('UPDATE recurring_grants SET used=used+1 WHERE id=?',(id,))
                    db.execute('INSERT INTO recurring_events(grant_id,event_key,cancelled) VALUES(?,?,1) ON CONFLICT(grant_id,event_key) DO UPDATE SET cancelled=1',(id,key))
                if event and event['request_id']:
                    request=self.a.public(self.a.row(db,r['customer'],event['request_id']))
                else:request=None
            # Reservation commits first; deterministic app key repairs any lost response.
            if request is None and dispatch:
                value=json.loads(r['payload']);value['key']=str(uuid.uuid5(uuid.UUID(id),key))
                request=self.a.submit(r['customer'],value)
                with self.a.db() as db:
                    db.execute('UPDATE recurring_events SET request_id=? WHERE grant_id=? AND event_key=? AND request_id IS NULL',(request['id'],id,key))
            if cancel and request and request['state']!='deleted':
                self.a.delete(r['customer'],request['id'])
            # Never return research text or a service credential to the coordinator.
            return {'request':None if request is None else {k:request[k] for k in ('id','receiptId','state','error','deletionPending')},'cancelRequested':bool(cancel),'cancelConfirmed':bool(cancel and request is None)}
    def revoke(self,customer,id=None):
        with self.a.lock,self.a.db() as db:
            if id:self.require(db.execute('SELECT 1 FROM recurring_grants WHERE id=? AND customer=?',(id,customer)).fetchone(),'not_found',404)
            db.execute('UPDATE recurring_grants SET revoked=1,payload=NULL WHERE customer=?'+(' AND id=?' if id else ''),(customer,id) if id else (customer,))
        return {'revoked':True}
