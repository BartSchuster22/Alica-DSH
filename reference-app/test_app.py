"""Isolated SQLite and real loopback HTTP tests. Core/inference are explicitly MOCKED."""
import copy, hashlib, hmac, http.client, json, tempfile, threading, time, unittest, uuid
from pathlib import Path
from app import Application, Core, Failure, Handler, Server, VERSION, encoded, password_hash, strict_json
APP='00000000-0000-4000-8000-000000000001'
PASS='only-a-generated-test-fixture-password'
class MockCore:
    def __init__(self):self.calls=[];self.requests={};self.keys={};self.lose=False;self.deny=False;self.wrong=False
    def call(self,method,path,body=None,key=None):
        self.calls.append((method,path,copy.deepcopy(body),key))
        if self.deny:raise Failure('core_credential_expired_or_revoked',502)
        if key:
            if key not in self.keys:
                id=str(uuid.uuid4());self.keys[key]=id;self.requests[id]={'id':id,'application_id':APP,'payload':body,'phase':'accepted','result':None}
            r=self.requests[self.keys[key]]
            if self.lose:self.lose=False;raise Failure('core_outcome_unknown',502)
        else:
            id=path.split('/')[5];r=self.requests[id]
            if method=='DELETE':r['phase']='deletion-pending'
            if path.endswith('/cancel'):r['phase']='cancelled'
        result=copy.deepcopy(r)
        if self.wrong:result['application_id']=str(uuid.uuid4())
        return {'contractVersion':VERSION,'receipt':result}
class TestReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.hashed=password_hash(PASS)
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'app.db';self.core=MockCore();self.customers={n:{'subject':'customer-'+n,'passwordHash':self.hashed} for n in ('alice','bob')};self.secret='callback-fixture-only-'+'x'*32
        self.app=Application(self.path,APP,self.customers,self.core,self.secret)
    def tearDown(self):self.temp.cleanup()
    def value(self,**kw):return {'key':str(uuid.uuid4()),'operation':'answer','question':'Explicit test fixture question',**kw}
    def submit(self,**kw):return self.app.submit('alice',self.value(**kw))
    def advance(self):
        with self.app.db() as db:db.execute('UPDATE requests SET next_at=0')
        return self.app.tick()
    def settled(self):
        local=self.submit();self.advance();row=self.app.listing('alice')['requests'][0];r=self.core.requests[row['receiptId']];r.update(phase='result-ready',result={'answer':'MOCKED answer; not inference','knowledge':[],'uncertainty':True});self.advance();return local['id'],r
    def signed(self,r,delivery=None,**updates):
        body={'contractVersion':VERSION,'deliveryId':delivery or str(uuid.uuid4()),'receiptId':r['id'],'applicationId':APP,'subject':'customer-alice','result':r['result'],**updates}
        raw=encoded(body).encode();stamp=str(int(time.time()));sig=hmac.new(self.secret.encode(),stamp.encode()+b'.'+body['deliveryId'].encode()+b'.'+raw,hashlib.sha256).hexdigest()
        return {'x-alica-delivery':body['deliveryId'],'x-alica-timestamp':stamp,'x-alica-signature':sig},raw
    def test_native_rejection_code_is_visible_and_bounded(self):
        self.submit();self.advance();row=self.app.listing('alice')['requests'][0]
        r=self.core.requests[row['receiptId']];r.update(phase='rejected',error_code='NATIVE_EXECUTION_FAILED')
        self.advance();self.assertEqual(self.app.listing('alice')['requests'][0]['error'],'NATIVE_EXECUTION_FAILED')
        with self.app.db() as db:
            current=db.execute('SELECT * FROM requests WHERE id=?',(row['id'],)).fetchone()
            r['error_code']='unsafe raw upstream message with secret'
            with self.assertRaises(Failure):self.app.observe(db,current,{'receipt':r})
    def test_login_session_hash_and_logout(self):
        token,csrf=self.app.login('alice',PASS);self.assertEqual(self.app.session(token)['csrf'],csrf)
        with self.app.db() as db:self.assertNotEqual(db.execute('SELECT hash FROM sessions').fetchone()[0],token)
        self.app.logout(token)
        with self.assertRaises(Failure):self.app.session(token)
    def test_rate_limit_persisted(self):
        for _ in range(5):
            with self.assertRaises(Failure):self.app.login('alice','wrong')
        with self.assertRaises(Failure) as e:self.app.login('alice',PASS)
        self.assertEqual(e.exception.status,429)
    def test_expired_session(self):
        token,_=self.app.login('alice',PASS)
        with self.app.db() as db:db.execute('UPDATE sessions SET expires=0')
        with self.assertRaises(Failure):self.app.session(token)
    def test_operator_binding_cannot_change(self):
        c=copy.deepcopy(self.customers);c['alice']['subject']='different-customer'
        with self.assertRaises(Failure):Application(self.path,APP,c,self.core)
    def test_application_binding_cannot_change(self):
        with self.assertRaises(Failure):Application(self.path,str(uuid.uuid4()),self.customers,self.core)
    def test_idempotency_and_conflict(self):
        v=self.value();a=self.app.submit('alice',v);self.assertEqual(self.app.submit('alice',v)['id'],a['id'])
        with self.assertRaises(Failure):self.app.submit('alice',{**v,'question':'Different'})
    def test_lost_core_response_same_key_after_restart(self):
        self.submit();self.core.lose=True;self.advance();self.assertEqual(len(self.core.requests),1)
        self.app=Application(self.path,APP,self.customers,self.core,self.secret);self.advance()
        self.assertEqual(len(self.core.requests),1);self.assertEqual(self.core.calls[0][3],self.core.calls[1][3]);self.assertIsNotNone(self.app.listing('alice')['requests'][0]['receiptId'])
    def test_customer_isolation(self):
        r=self.submit()
        self.assertEqual(self.app.listing('bob')['requests'],[])
        for f in (self.app.delete,self.app.retry):
            with self.assertRaises(Failure):f('bob',r['id'])
    def test_forbidden_configuration_fields(self):
        for field in ('subject','callback','projectId','model','tools','profile'):
            with self.subTest(field=field),self.assertRaises(Failure):self.app.submit('alice',{**self.value(),field:'evil'})
    def test_correction_owned_completed_only(self):
        id,r=self.settled();x=self.submit(operation='correction',corrects=id);self.assertEqual(x['operation'],'correction')
        with self.assertRaises(Failure):self.app.submit('bob',self.value(operation='correction',corrects=id))
    def test_credential_error_pauses_without_discard(self):
        self.submit();self.core.deny=True;self.advance();self.assertFalse(self.advance())
        row=self.app.listing('alice')['requests'][0];self.assertEqual(row['error'],'core_credential_expired_or_revoked');self.assertIsNotNone(row['question'])
    def test_wrong_core_binding_rejected(self):
        self.submit();self.core.wrong=True;self.advance();r=self.app.listing('alice')['requests'][0];self.assertEqual(r['error'],'core_scope_mismatch');self.assertIsNone(r['receiptId'])
    def test_callback_duplicate_atomic_effect(self):
        id,r=self.settled();headers,raw=self.signed(r);self.app.callback(headers,raw);self.app=Application(self.path,APP,self.customers,self.core,self.secret);self.app.callback(headers,raw)
        with self.app.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM effects').fetchone()[0],1);self.assertEqual(db.execute('SELECT count(*) FROM deliveries').fetchone()[0],1)
    def test_callback_conflict_rolls_back_delivery(self):
        _,r=self.settled();h,raw=self.signed(r);self.app.callback(h,raw);h2,raw2=self.signed(r,delivery=h['x-alica-delivery'],result={'answer':'Changed fixture'})
        with self.assertRaises(Failure):self.app.callback(h2,raw2)
        self.assertEqual(self.app.listing('alice')['requests'][0]['result'],r['result'])
    def test_callback_unknown_customer_and_expiry(self):
        _,r=self.settled();h,raw=self.signed(r,subject='customer-bob')
        with self.assertRaises(Failure):self.app.callback(h,raw)
        h,raw=self.signed(r);h['x-alica-timestamp']='1000000000'
        with self.assertRaises(Failure):self.app.callback(h,raw)
    def test_callback_invalid_signature(self):
        _,r=self.settled();h,raw=self.signed(r);h['x-alica-signature']='0'*64
        with self.assertRaises(Failure):self.app.callback(h,raw)
    def test_deletion_waits_for_core_and_scrubs(self):
        id,r=self.settled();self.app.delete('alice',id);self.advance();self.assertIsNotNone(self.app.listing('alice')['requests'][0]['question'])
        r.update(phase='deleted',payload=None,result=None);self.advance();row=self.app.listing('alice')['requests'][0]
        self.assertEqual(row['state'],'deleted');self.assertIsNone(row['question']);self.assertIsNone(row['result'])
    def test_signed_callback_cannot_resurrect_deleted(self):
        id,r=self.settled();h,raw=self.signed(r);self.app.delete('alice',id);self.advance();r.update(phase='deleted',payload=None,result=None);self.advance();self.app.callback(h,raw)
        self.assertEqual(self.app.listing('alice')['requests'][0]['state'],'deleted');self.assertIsNone(self.app.listing('alice')['requests'][0]['result'])
    def test_delete_account_denies_new_admissions(self):
        self.submit();self.app.delete('alice')
        with self.assertRaises(Failure):self.submit()
        self.assertFalse(self.app.listing('alice')['deletionComplete'])
    def test_retention_never_silently_discards(self):
        self.submit()
        with self.app.db() as db:db.execute('UPDATE requests SET created=0')
        self.advance();row=self.app.listing('alice')['requests'][0];self.assertTrue(row['deletionPending']);self.assertIsNotNone(row['question'])
    def test_export_uses_scoped_core_export(self):
        _,r=self.settled();data=self.app.export('alice');self.assertEqual(data['coreExports'][0]['receipt']['id'],r['id']);self.assertNotIn('passwordHash',encoded(data));self.assertNotIn(self.secret,encoded(data))
    def test_polling_bound_visible(self):
        self.submit()
        with self.app.db() as db:db.execute('UPDATE requests SET polls=120')
        self.assertFalse(self.advance());self.assertEqual(self.app.listing('alice')['requests'][0]['error'],'polling_paused_retry_same_request')
    def test_json_duplicate_and_nonfinite_denied(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}'):
            with self.assertRaises(Failure):strict_json(raw)
    def test_core_rejects_insecure_url_and_bad_token(self):
        with self.assertRaises(Failure):Core('http://example.com','dsha1_'+'x'*43)
        with self.assertRaises(Failure):Core('https://example.com','not-a-service-token')
    def test_real_loopback_http_security_mock_core(self):
        server=Server(('127.0.0.1',0),Handler);server.application=self.app;server.origin='https://reference.example';t=threading.Thread(target=server.serve_forever);t.start()
        def request(method,path,body=None,**headers):
            c=http.client.HTTPConnection('127.0.0.1',server.server_port);data=encoded(body).encode() if body is not None else None
            c.request(method,path,data,{'Host':'reference.example',**({'Content-Type':'application/json'} if body is not None else {}),**headers});r=c.getresponse();out=(r.status,dict(r.getheaders()),r.read());c.close();return out
        try:
            self.assertEqual(request('POST','/api/login',{'username':'alice','password':PASS})[0],403)
            code,h,raw=request('POST','/api/login',{'username':'alice','password':PASS},Origin=server.origin);self.assertEqual(code,200);cookie=h['Set-Cookie'];self.assertIn('Secure; HttpOnly; SameSite=Strict',cookie)
            self.assertEqual(request('POST','/api/requests',self.value(),Origin=server.origin,Cookie=cookie)[0],403)
            csrf=json.loads(raw)['csrf'];code,_,_=request('POST','/api/requests',self.value(),Origin=server.origin,Cookie=cookie,**{'X-CSRF-Token':csrf});self.assertEqual(code,202)
            code,h,raw=request('GET','/');self.assertEqual(code,200);self.assertIn("frame-ancestors 'none'",h['Content-Security-Policy']);self.assertNotIn(self.secret.encode(),raw)
        finally:server.shutdown();server.server_close();t.join()
if __name__=='__main__':unittest.main(verbosity=2)
