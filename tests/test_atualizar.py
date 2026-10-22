import importlib.util
from pathlib import Path
import socket
import sqlite3
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('maintenance', Path(__file__).parents[1] / 'sonifarma_pix_mvp' / 'atualizar.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.base, self.source, self.dest = root/'installed', root/'release', root/'backups'
        self.base.mkdir(); self.source.mkdir()
        for name in m.FILES:
            (self.base/name).write_text('# old\n' if name.endswith('.py') else 'old')
            (self.source/name).write_text('# new\n' if name.endswith('.py') else 'new')
        for folder in (self.base, self.source):
            (folder/'requirements.txt').write_text('fastapi>=0.115,<1\n')
        self.database = self.base/'pix_monitor.db'
        with sqlite3.connect(self.database) as db:
            db.execute('CREATE TABLE receipts(value INTEGER)')
            db.execute('INSERT INTO receipts VALUES (14990)')
        (self.base/'.env').write_text('LOCAL_CONFIGURATION=preserve')
        (self.source/'.env').write_text('LOCAL_CONFIGURATION=replace')

    def test_update_backup_and_code_restore_preserve_data(self):
        saved = m.update(self.base, self.source, self.dest, self.database, 0)
        data = m.verify(saved)
        self.assertIn('database.sqlite3', data)
        self.assertEqual((self.base/'index.html').read_text(), 'new')
        self.assertEqual((self.base/'.env').read_text(), 'LOCAL_CONFIGURATION=preserve')
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute('SELECT value FROM receipts').fetchone()[0],14990)
        m.replace(self.base,{n:data[n] for n in m.FILES})
        self.assertEqual((self.base/'index.html').read_text(),'old')

    def test_live_port_blocks_changes(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1',0)); s.listen()
            with self.assertRaises(ValueError):
                m.update(self.base,self.source,self.dest,self.database,s.getsockname()[1])
        self.assertEqual((self.base/'index.html').read_text(),'old')

    def test_bad_python_and_changed_dependencies_block_changes(self):
        (self.source/'app.py').write_text('def broken(')
        with self.assertRaises(SyntaxError):m.update(self.base,self.source,self.dest,self.database,0)
        (self.source/'app.py').write_text('# valid')
        (self.source/'requirements.txt').write_text('different')
        with self.assertRaises(ValueError):m.update(self.base,self.source,self.dest,self.database,0)
        self.assertFalse(self.dest.exists())

    def test_corrupted_archive_rejected(self):
        saved = m.backup(self.base,self.dest,self.database)
        with zipfile.ZipFile(saved) as z:data={n:z.read(n) for n in z.namelist()}
        data['app.py']=b'# tampered'
        with zipfile.ZipFile(saved,'w') as z:
            for n,c in data.items():z.writestr(n,c)
        with self.assertRaises(ValueError):m.verify(saved)

if __name__=='__main__':unittest.main()
