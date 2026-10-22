"""Manutenção local do SonifarmaPix; não modifica credenciais ou dependências."""
import argparse
import ast
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import socket
import sqlite3
import tempfile
import urllib.request
import zipfile

FILES = ('app.py', 'index.html', 'panel.js', 'criar_admin.py')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def stopped(port):
    with socket.socket() as sock:
        sock.settimeout(1)
        if sock.connect_ex(('127.0.0.1', port)) == 0:
            raise ValueError('Porta ocupada. Pare o painel e a supervisão antes de continuar.')


def verify(archive):
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read('manifest.json'))
        files = manifest['files']
        if not files or not set(files) <= set(FILES) | {'database.sqlite3'}:
            raise ValueError('Manifesto inválido')
        names = z.namelist()
        if len(names) != len(set(names)) or set(names) != set(files) | {'manifest.json'}:
            raise ValueError('Conteúdo inesperado')
        data = {name: z.read(name) for name in files}
        for name, content in data.items():
            if digest(content) != files[name]:
                raise ValueError('Checksum inválido: ' + name)
        if 'database.sqlite3' in data:
            with tempfile.TemporaryDirectory() as work:
                path = Path(work) / 'test.db'
                path.write_bytes(data['database.sqlite3'])
                with closing(sqlite3.connect(path)) as db:
                    if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                        raise ValueError('Banco inválido')
        return data


def backup(base, destination, database):
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / ('pix_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f') + '.zip')
    with tempfile.TemporaryDirectory(dir=destination) as work:
        work = Path(work)
        data = {name: (base / name).read_bytes() for name in FILES if (base / name).is_file()}
        if database.exists():
            with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as src:
                with closing(sqlite3.connect(work / 'database.sqlite3')) as dst:
                    src.backup(dst)
            data['database.sqlite3'] = (work / 'database.sqlite3').read_bytes()
        if not data:
            raise ValueError('Nenhum arquivo para backup')
        pending = work / 'backup.zip'
        with zipfile.ZipFile(pending, 'w', zipfile.ZIP_DEFLATED) as z:
            for name, content in data.items():
                z.writestr(name, content)
            z.writestr('manifest.json', json.dumps({'version': 1, 'files': {n: digest(c) for n, c in data.items()}}))
        verify(pending)
        pending.replace(target)
    return target


def replace(base, data):
    previous = {name: (base / name).read_bytes() if (base / name).exists() else None for name in data}
    try:
        for name, content in data.items():
            with tempfile.NamedTemporaryFile(dir=base, delete=False) as f:
                pending = Path(f.name)
                f.write(content)
            try:
                pending.replace(base / name)
            finally:
                pending.unlink(missing_ok=True)
    except Exception:
        for name, content in previous.items():
            if content is None:
                (base / name).unlink(missing_ok=True)
            else:
                (base / name).write_bytes(content)
        raise


def update(base, source, destination, database, port):
    stopped(port)
    if base.resolve() == source.resolve():
        raise ValueError('Origem e instalação devem ser diferentes')
    data = {}
    for name in FILES:
        path = source / name
        if not path.is_file() or path.is_symlink():
            raise ValueError('Pacote incompleto ou link simbólico: ' + name)
        data[name] = path.read_bytes()
        if name.endswith('.py'):
            ast.parse(data[name].decode('utf-8-sig'))
    # Mudanças de dependências exigem instalação separada; nunca deixar ambiente incompatível.
    if not (source / 'requirements.txt').is_file() or (source / 'requirements.txt').read_bytes() != (base / 'requirements.txt').read_bytes():
        raise ValueError('Dependências diferentes ou ausentes: prepare-as separadamente antes da atualização.')
    saved = backup(base, destination, database)
    replace(base, data)
    return saved


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('comando', choices=['status', 'backup', 'verificar', 'atualizar', 'restaurar'])
    p.add_argument('--base', type=Path, default=Path(__file__).resolve().parent)
    p.add_argument('--origem', type=Path)
    p.add_argument('--arquivo', type=Path)
    p.add_argument('--destino', type=Path)
    p.add_argument('--banco', type=Path)
    p.add_argument('--porta', type=int, default=8080)
    args = p.parse_args()
    base = args.base.resolve()
    import os
    database = args.banco or Path(os.environ.get('PIX_DB', str(base / 'pix_monitor.db')))
    destination = args.destino or base.parent / 'backups_pix'
    try:
        if args.comando == 'status':
            with urllib.request.urlopen(f'http://127.0.0.1:{args.porta}/health', timeout=5) as r:
                data = json.load(r)
                if data.get('app') != 'ok':
                    raise ValueError('Saúde inesperada')
                print(json.dumps(data, ensure_ascii=False))
        elif args.comando == 'backup':
            print('Backup verificado:', backup(base, destination, database))
        elif args.comando == 'verificar':
            if not args.arquivo:
                p.error('Informe --arquivo')
            print('Integridade verificada:', ', '.join(verify(args.arquivo)))
        elif args.comando == 'atualizar':
            if not args.origem:
                p.error('Informe --origem (pasta extraída de uma versão confiável)')
            print('Código atualizado. Backup:', update(base, args.origem, destination, database, args.porta))
        else:
            if not args.arquivo:
                p.error('Informe --arquivo')
            stopped(args.porta)
            data = verify(args.arquivo)
            if not set(FILES) <= set(data):
                raise ValueError('Backup sem código completo')
            print('Backup antes da restauração:', backup(base, destination, database))
            replace(base, {n: data[n] for n in FILES})
            print('Código restaurado; banco atual preservado.')
    except Exception as e:
        p.exit(1, 'Falha: ' + str(e) + '\n')


if __name__ == '__main__':
    main()
