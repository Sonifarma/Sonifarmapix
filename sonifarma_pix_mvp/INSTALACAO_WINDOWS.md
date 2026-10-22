# Sonifarma Pix Monitor V1.1 — atualização segura

**Importante:** esta versão continua sem conexão com o Itaú. O endpoint de simulação fica desabilitado por padrão. O sistema usa HTTP na rede interna; **não utilize com dados bancários reais** até implantar HTTPS e controles de segurança apropriados.

## 1. Antes de atualizar

No servidor, salve o ZIP em uma pasta temporária e extraia. **Não copie nem substitua `pix_monitor.db`, `.venv` ou `iniciar_pix.bat`.** Não renomeie a pasta original.

No PowerShell **como administrador**, pare a tarefa:

```powershell
Stop-ScheduledTask -TaskName "Sonifarma Pix Monitor"
```

Aguarde até que a porta esteja livre:

```powershell
Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue
```

Se ainda houver um processo, confirme se é uma instância antiga antes de encerrá-lo. Faça backup consistente do SQLite com o Python do projeto:

```powershell
cd C:\SonifarmaPix\sonifarma_pix_mvp
New-Item -ItemType Directory -Force C:\SonifarmaPix\backup | Out-Null
.\.venv\Scripts\python.exe -c "import sqlite3; a=sqlite3.connect('pix_monitor.db'); b=sqlite3.connect(r'C:\SonifarmaPix\backup\pix_monitor_pre_v1_1.db'); a.backup(b); b.close(); a.close()"
```

## 2. Substituir somente os arquivos da aplicação

Copie do ZIP extraído os arquivos `app.py`, `index.html`, `panel.js`, `criar_admin.py`, `requirements.txt` para `C:\SonifarmaPix\sonifarma_pix_mvp`. O ZIP não inclui banco de dados. O programa cria apenas tabelas complementares na base existente.

No PowerShell:

```powershell
cd C:\SonifarmaPix\sonifarma_pix_mvp
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 3. Criar login de gerência

Inicie temporariamente a aplicação no PowerShell para criar as novas tabelas:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8080
```

Aguarde `Application startup complete`, pressione Ctrl+C e execute:

```powershell
.\.venv\Scripts\python.exe criar_admin.py
```

Informe um usuário e uma senha forte. **Não envie essa senha pelo chat.** A senha é armazenada como hash PBKDF2, não em texto puro.

## 4. Reiniciar a tarefa existente

```powershell
Start-ScheduledTask -TaskName "Sonifarma Pix Monitor"
Get-ScheduledTask -TaskName "Sonifarma Pix Monitor" | Select-Object TaskName,State
Invoke-WebRequest http://127.0.0.1:8080/health -UseBasicParsing
```

Acesse `http://192.168.0.239:8080` nos computadores autorizados. A tarefa e a porta 8080 não precisam ser recriadas.

## 5. Gerenciar caixas

Entre com o usuário da gerência, abra a aba **Gerência** e crie usuários com perfil **Caixa**. Caixas veem todos os Pix locais e não podem exportar CSV nem administrar usuários. A gerência pode exportar CSV e cadastrar usuários.

## 6. Recuperação em caso de erro

Pare a tarefa, restaure `app.py` da V1.0 e reinicie a tarefa. O banco foi preservado e as novas tabelas não afetam o funcionamento anterior. Caso precise restaurar o banco, faça isso somente com a tarefa parada e após confirmar que não existem lançamentos novos que devam ser preservados.

## Notas de segurança

- O `PIX_ADMIN_TOKEN` no arquivo `.bat` antigo não é usado para login; ele só vale para `/internal/pix` quando `PIX_ENABLE_SIMULATOR=1` é configurado explicitamente.
- Mantenha `PIX_ENABLE_SIMULATOR` desabilitado. Não abra a porta 8080 na internet.
- A aplicação não dispõe ainda de bloqueio por tentativas de login, redefinição de senhas, TLS, auditoria completa ou recuperação de conta. Exija acesso restrito à rede interna e prepare HTTPS antes de usar dados reais.
- O login expira após 10 horas. A opção `PIX_SECURE_COOKIE=1` deve ser ativada somente após colocar o painel atrás de HTTPS.
- Confirme com o Itaú as modalidades de Pix abrangidas pela API antes de conectar pagamentos reais.
