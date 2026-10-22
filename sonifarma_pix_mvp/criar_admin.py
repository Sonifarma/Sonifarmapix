import getpass,sqlite3,sys,os
from app import DB,hash_password
print('Configuração local do primeiro gestor - Sonifarma Pix V1.1')
if not os.path.isfile(DB):
 print('Banco não encontrado:',DB,'\nCopie o pix_monitor.db original antes de continuar.');sys.exit(1)
with sqlite3.connect(DB) as db:
 try:
  count=db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
 except sqlite3.OperationalError:
  print('Inicie a aplicação V1.1 uma vez para criar a tabela users, pare e execute novamente.');sys.exit(1)
 if count:
  print('Já existem usuários. Não será criado outro administrador automaticamente.');sys.exit(1)
 username=input('Usuário da gerência (ex: gerente): ').strip().lower()
 if len(username)<3 or not all(c.isalnum() or c in '_.-' for c in username):sys.exit('Nome inválido')
 password=getpass.getpass('Senha forte (mínimo 8 caracteres): ')
 if len(password)<8:sys.exit('Senha muito curta')
 if password!=getpass.getpass('Confirme a senha: '):sys.exit('Senhas diferentes')
 db.execute('INSERT INTO users(username,password_hash,role) VALUES(?,?,?)',(username,hash_password(password),'gerencia'))
 print('Gestor cadastrado. Reinicie a aplicação e entre pelo navegador.')
