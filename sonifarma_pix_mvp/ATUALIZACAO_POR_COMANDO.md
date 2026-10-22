# Atualização por comando — SonifarmaPix

Na primeira instalação, copie `atualizar.py` e `PIX_COMANDO.bat` para a pasta que contém `app.py`. Requer Python 3.12. O utilitário usa apenas a biblioteca padrão e também funciona no Linux com `python atualizar.py`.

## Consultar e fazer backup

No terminal da pasta do painel:

```bat
PIX_COMANDO.bat status
PIX_COMANDO.bat backup
PIX_COMANDO.bat verificar --arquivo "C:\SonifarmaPix\backups_pix\pix_DATA.zip"
```

O backup usa a API SQLite, inclui transações confirmadas no WAL e valida a integridade em uma restauração temporária. Inclui código anterior e banco; contém dados pessoais e hashes de senhas. Restrinja o acesso à pasta. Os hashes detectam corrupção, mas não comprovam a procedência de um pacote recebido.

## Atualizar

Baixe uma versão de procedência confiável e extraia em outra pasta. A origem deve conter `app.py`, `index.html`, `panel.js`, `criar_admin.py` e `requirements.txt`. O comando não baixa automaticamente do GitHub nem modifica o Git local.

Se usa a tarefa agendada original, pare-a no PowerShell com as permissões necessárias:

```powershell
Stop-ScheduledTask -TaskName 'Sonifarma Pix Monitor'
```

Pare também qualquer supervisão que reinicie o aplicativo. Aguarde a saída do processo. Não encerre processos desconhecidos.

```bat
PIX_COMANDO.bat atualizar --origem "C:\Atualizacoes\SonifarmaPix\sonifarma_pix_mvp"
```

Se retornar erro, não prossiga sem examinar a mensagem. Se retornar sucesso, reinicie e verifique:

```powershell
Start-ScheduledTask -TaskName 'Sonifarma Pix Monitor'
.\PIX_COMANDO.bat status
```

O atualizador verifica a sintaxe Python, exige os quatro arquivos e dependências idênticas, cria backup verificado e substitui somente o código. Preserva banco, `.env`, certificados, credenciais, inicializadores e ambiente virtual. O backup padrão fica em `backups_pix` na pasta acima do painel. Use `--destino` para outro local. Se usa `PIX_DB`, mantenha essa variável também no terminal de manutenção ou informe `--banco` com o caminho real. Para porta diferente, informe `--porta`.

Não há migração automática de dependências. Se `requirements.txt` mudar, o comando recusa o pacote; prepare uma atualização específica com teste de compatibilidade. Os próprios arquivos de manutenção não são substituídos automaticamente.

## Restaurar código

Com painel e supervisão parados:

```bat
PIX_COMANDO.bat restaurar --arquivo "C:\SonifarmaPix\backups_pix\pix_DATA.zip"
```

O comando verifica o backup, salva outro backup do estado atual e restaura apenas o código. O banco atual é preservado para não apagar recebimentos posteriores. Não oferece downgrade de esquema ou restauração automática de dados. Reinicie e execute `status`; faça também login e confira os recebimentos. Se a nova versão tiver alterado o esquema de modo incompatível, a recuperação exige análise separada.

## Limites e validação

A troca é atômica por arquivo e tenta reverter o código em caso de erro durante a cópia; não é uma transação contra queda de energia. Não execute duas manutenções ao mesmo tempo. Backup não substitui cópia externa protegida. A verificação da porta usa loopback IPv4 e pressupõe o painel original, na porta informada; confirme que não há instância em outra porta/máquina ou com banco compartilhado.

Testes automatizados no Linux: atualização, preservação de dados e configuração, restauração de código, integridade do backup e rejeição de porta ocupada, sintaxe inválida e dependências alteradas. O lançador BAT e a tarefa agendada precisam de validação no Windows da instalação. Este utilitário não instala tarefas, não reinicia automaticamente serviços e não conecta ao Itaú.
