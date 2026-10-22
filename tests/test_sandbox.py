"""Testes isolados; pip install httpx para usar o TestClient do FastAPI."""
import copy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sqlite3
import ssl
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
from fastapi.testclient import TestClient

spec=importlib.util.spec_from_file_location('pix_app_test',Path(__file__).parents[1]/'sonifarma_pix_mvp'/'app.py')
app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
PAYLOAD={'parametros':{'paginacao':{'paginaAtual':0,'quantidadeDePaginas':1,'quantidadeTotalDeItens':2}},'pix':[
 {'endToEndId':'E_FAKE_RECEIPT_0001','valor':'110.00','horario':'2020-09-10T13:03:33Z','infoPagador':'Descrição fictícia','devolucoes':[{'valor':'10.00','status':'DEVOLVIDO'},{'valor':'3.00','status':'EM_PROCESSAMENTO'}]},
 {'endToEndId':'E_FAKE_RECEIPT_0002','valor':'450.00','horario':'2020-09-10T13:03:33Z'}]}
QUERY={'token':'fictional-sandbox-token','inicio':'2026-10-21T00:00:00Z','fim':'2026-10-21T23:59:59Z','pagina':0,'itens':100}

class SandboxTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.dbpatch=patch.object(app,'DB',self.tmp.name+'/test.db');self.dbpatch.start();self.addCleanup(self.dbpatch.stop)
  app.startup()
  with app.conn() as db:
   for name,role in [('manager','gerencia'),('cashier','caixa')]:
    db.execute('INSERT INTO users(username,password_hash,role) VALUES(?,?,?)',(name,app.hash_password('test-password'),role))
  self.client=TestClient(app.app,client=('127.0.0.1',50000));self.addCleanup(self.client.close)
 def login(self,name='manager',client=None):
  response=(client or self.client).post('/api/login',json={'username':name,'password':'test-password'})
  self.assertEqual(response.status_code,200)
 def test_auth_role_origin_and_remote_clients(self):
  with patch.object(app,'fetch_sandbox') as fetch:
   self.assertEqual(self.client.post('/api/itau/sandbox',json=QUERY).status_code,401)
   self.login('cashier');self.assertEqual(self.client.post('/api/itau/sandbox',json=QUERY).status_code,403)
   self.login();self.assertEqual(self.client.post('/api/itau/sandbox',json=QUERY,headers={'Origin':'https://foreign.invalid'}).status_code,403)
   with TestClient(app.app,client=('192.168.0.5',50000)) as remote:
    self.login(client=remote);self.assertEqual(remote.post('/api/itau/sandbox',json=QUERY).status_code,403)
   fetch.assert_not_called()
 def test_results_refunds_and_no_database_writes(self):
  self.login()
  with patch.object(app,'fetch_sandbox',return_value=PAYLOAD):
   response=self.client.post('/api/itau/sandbox',json=QUERY)
  self.assertEqual(response.status_code,200);body=response.json()
  self.assertEqual(body['total_cents'],56000);self.assertEqual(body['returned_cents'],1000)
  self.assertFalse(body['bank_connected']);self.assertEqual(body['environment'],'sandbox')
  self.assertTrue(any('período' in w for w in body['warnings']))
  self.assertNotIn(QUERY['token'],response.text);self.assertEqual(response.headers['cache-control'],'no-store')
  with app.conn() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM pix').fetchone()[0],0)
 def test_bad_dates_and_token_not_echoed(self):
  self.login()
  for change in [{'fim':'2026-10-20T00:00:00Z'},{'inicio':'2026-10-21T00:00:00'},{'fim':'2026-12-21T00:00:00Z'},{'token':'secret token with spaces'}]:
   with patch.object(app,'fetch_sandbox') as fetch:
    response=self.client.post('/api/itau/sandbox',json={**QUERY,**change})
    self.assertEqual(response.status_code,422);fetch.assert_not_called()
    self.assertNotIn('secret token with spaces',response.text)
 def test_response_formats_inconsistency_and_malformed_amount(self):
  query=app.SandboxQuery(**QUERY)
  self.assertEqual(len(app.normalize_sandbox({'value':PAYLOAD},query)['items']),2)
  invalid=copy.deepcopy(PAYLOAD);invalid['parametros']['paginacao']['quantidadeTotalDeItens']=1
  self.assertTrue(any('paginação' in w for w in app.normalize_sandbox(invalid,query)['warnings']))
  for amount in ['NaN','Infinity','-1.00','1.001']:
   invalid=copy.deepcopy(PAYLOAD);invalid['pix'][0]['valor']=amount
   with self.assertRaises(app.HTTPException):app.normalize_sandbox(invalid,query)
 def test_transport_fixed_url_tls_and_sanitized_errors(self):
  query=app.SandboxQuery(**QUERY)
  with patch.object(app.urllib.request,'build_opener') as build:
   build.return_value.open.side_effect=urllib.error.HTTPError(app.SANDBOX_URL,401,'SECRET_FROM_REMOTE',{},None)
   with self.assertRaises(app.HTTPException) as error:app.fetch_sandbox(query)
   self.assertNotIn('SECRET_FROM_REMOTE',error.exception.detail)
   handlers=build.call_args.args
   self.assertIsInstance(handlers[0],app.NoSandboxRedirect)
   self.assertEqual(handlers[1]._context.verify_mode,ssl.CERT_REQUIRED)
   req=build.return_value.open.call_args.args[0]
   self.assertTrue(req.full_url.startswith(app.SANDBOX_URL+'?'))
   self.assertIn('inicio=2026-10-21T00%3A00%3A00Z',req.full_url)
   self.assertEqual(req.get_header('Authorization'),'Bearer '+QUERY['token'])
 def test_logout_with_referer(self):
  self.login();self.assertEqual(self.client.post('/api/logout',headers={'Referer':'http://testserver/'}).status_code,200)

if __name__=='__main__':unittest.main()
