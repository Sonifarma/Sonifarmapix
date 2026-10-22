# SonifarmaPix

Protótipo local de monitoramento de recebimentos Pix, com login, perfis de caixa e gerência, relatório CSV e simulador desabilitado por padrão. **Não está conectado ao Itaú e não confirma pagamentos bancários.**

## Baixar e atualizar por comando

Baixe o ZIP pelo botão **Code → Download ZIP** deste repositório e extraia em uma pasta separada da instalação atual.

Na primeira adoção, copie `sonifarma_pix_mvp/atualizar.py` e `sonifarma_pix_mvp/PIX_COMANDO.bat` para a pasta instalada que contém `app.py`. Pare o painel e sua supervisão antes de atualizar:

```bat
PIX_COMANDO.bat atualizar --origem "C:\Atualizacoes\Sonifarmapix-main\sonifarma_pix_mvp"
```

O atualizador cria backup verificado, substitui somente o código e preserva o banco e a configuração local. Reinicie o painel e execute `PIX_COMANDO.bat status`.

Consulte [os comandos de backup, verificação e restauração](sonifarma_pix_mvp/ATUALIZACAO_POR_COMANDO.md). O atualizador usa pacote local extraído; não faz download automático nem reinicia serviços.

## Desenvolvimento — Python 3.12

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r sonifarma_pix_mvp/requirements.txt
cd sonifarma_pix_mvp
../.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8080
```

A primeira inicialização cria as tabelas SQLite. Pare o processo e execute `../.venv/bin/python criar_admin.py` para cadastrar o primeiro gestor interativamente; reinicie o servidor e faça login. No Windows use `.venv\Scripts\python.exe` e os caminhos equivalentes. Não existe senha padrão.

Bancos, certificados, chaves, credenciais, backups e ambientes virtuais não estão incluídos. O README interno original descreve uma versão anterior; para autenticação V1.1, siga as instruções acima. As orientações de rede e tarefa agendada em `INSTALACAO_WINDOWS.md` descrevem a instalação original e precisam ser adaptadas à máquina local.

## Testes e limitações

```sh
python -m unittest discover -s tests -v
```

Quatro testes do atualizador passaram no Linux. O lançador BAT e a operação da tarefa agendada ainda precisam de validação no Windows. Verificações locais da aplicação confirmaram login, permissões, simulador, totais, CSV e usuários, com dados fictícios.

Defeito conhecido na aplicação importada: logout com `Referer` e sem `Origin` pode retornar HTTP 500. A identidade visual do SonifarmaCRM ainda não foi aplicada. Não exponha este protótipo na internet ou use seus registros como confirmação bancária.
