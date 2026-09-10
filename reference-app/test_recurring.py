import json,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
from app import Application,Failure,password_hash
class RecurringTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'app.db';self.application_id=str(uuid.uuid4());self.customers={'alice':{'subject':'a','passwordHash':password_hash('test-password')},'bob':{'subject':'b','passwordHash':password_hash('other-password')}}
        self.a=Application(self.path,self.application_id,self.customers,None,native_project_id='test-project')
        self.value={'operation':'answer','question':'Approved-source fact?','maxRuns':2,'minIntervalSeconds':60,'expiresInSeconds':3600};self.g=self.a.recurring.issue('alice',self.value)
    def tearDown(self):self.tmp.cleanup()
    def event(self,key='one',**kw):return self.a.recurring.event(self.g['grantId'],self.g['token'],key,**kw)
    def test_duplicate_is_one_charge_and_request(self):
        x=self.event(dispatch=True);y=self.event(dispatch=True);self.assertEqual(x,y)
        self.assertEqual(self.a.recurring.info(self.g['grantId'],self.g['token'])['used'],1)
        self.assertEqual(len(self.a.listing('alice')['requests']),1)
    def test_reserved_before_lost_submission_repaired_after_restart(self):
        with patch.object(self.a,'submit',side_effect=OSError('fixture process loss')):
            with self.assertRaises(OSError):self.event(dispatch=True)
        self.a=Application(self.path,self.application_id,self.customers,None,native_project_id='test-project')
        self.assertIsNone(self.event()['request']);self.assertIsNotNone(self.event(dispatch=True)['request'])
        self.assertEqual(self.a.recurring.info(self.g['grantId'],self.g['token'])['used'],1)
    def test_post_effect_lost_response_reuses_same_app_key(self):
        original=self.a.submit
        def lost(*a):original(*a);raise OSError('response lost')
        with patch.object(self.a,'submit',side_effect=lost):
            with self.assertRaises(OSError):self.event(dispatch=True)
        self.event(dispatch=True);self.assertEqual(len(self.a.listing('alice')['requests']),1)
    def test_wrong_token_and_cross_customer_revoke(self):
        with self.assertRaises(Failure):self.a.recurring.info(self.g['grantId'],'invalid')
        with self.assertRaises(Failure):self.a.recurring.revoke('bob',self.g['grantId'])
    def test_budget_and_rate_denied(self):
        self.event(dispatch=True)
        with self.assertRaises(Failure):self.event('two',dispatch=True)
        with self.a.db() as db:db.execute('UPDATE recurring_grants SET last_new=0')
        self.event('two',dispatch=True)
        with self.assertRaises(Failure):self.event('three',dispatch=True)
        self.assertEqual(len(self.a.listing('alice')['requests']),2)
    def test_delete_revokes_and_removes_question(self):
        self.a.delete('alice')
        with self.assertRaises(Failure):self.event(dispatch=True)
        with self.a.db() as db:self.assertIsNone(db.execute('SELECT payload FROM recurring_grants').fetchone()[0])
        self.assertFalse(self.a.listing('bob')['accountDeletionRequested'])
    def test_revoke_prevents_new_but_permits_existing_cleanup(self):
        self.event(dispatch=True);self.a.recurring.revoke('alice',self.g['grantId'])
        with self.assertRaises(Failure):self.event('two',dispatch=True)
        self.assertTrue(self.event(cancel=True)['cancelRequested'])
    def test_invalid_overrides_and_bool_budget(self):
        for key,value in [('projectId','evil'),('tools',['terminal']),('maxRuns',True),('minIntervalSeconds',1)]:
            with self.subTest(key=key),self.assertRaises(Failure):self.a.recurring.issue('alice',{**self.value,key:value})
    def test_expiry(self):
        with self.a.db() as db:db.execute('UPDATE recurring_grants SET expires=0')
        with self.assertRaises(Failure):self.event(dispatch=True)
    def test_cancel_before_dispatch_fences_late_owner(self):
        self.assertTrue(self.event(cancel=True)['cancelConfirmed'])
        with self.assertRaises(Failure):self.event(dispatch=True)
        self.assertEqual(len(self.a.listing('alice')['requests']),0)
    def test_cancel_repairs_lost_post_without_dispatch(self):
        original=self.a.submit
        def lost(*a):original(*a);raise OSError('response lost')
        with patch.object(self.a,'submit',side_effect=lost):
            with self.assertRaises(OSError):self.event(dispatch=True)
        with patch.object(self.a,'submit',side_effect=AssertionError('must not dispatch')):
            result=self.event(cancel=True)
        self.assertIsNotNone(result['request'])
        self.assertTrue(self.a.listing('alice')['requests'][0]['deletionPending'])
        with self.assertRaises(Failure):self.event(dispatch=True)
    def test_concurrent_replays(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(8) as pool:values=list(pool.map(lambda _:self.event(dispatch=True),range(8)))
        self.assertEqual(len({x['request']['id'] for x in values}),1)
if __name__=='__main__':unittest.main()
