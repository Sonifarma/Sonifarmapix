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
python -m pip install httpx
python -m unittest discover -s tests -v
```

Dez testes de backend e atualização passaram no Linux, incluindo autenticação, isolamento do sandbox, datas, devoluções, TLS e erros. O lançador BAT e a operação da tarefa agendada ainda precisam de validação no Windows. Verificações locais da aplicação confirmaram login, permissões, simulador, totais, CSV e usuários, com dados fictícios.

Corrigido o logout com `Referer` e sem `Origin`, com teste de regressão. A interface usa a identidade visual do SonifarmaCRM: logo incorporado, turquesa e laranja, navegação lateral e telas responsivas. Não exponha este protótipo na internet ou use seus registros como confirmação bancária.


## Tema SonifarmaCRM

Esta versão mantém as funções de recebimentos e gerência e aplica a identidade visual do CRM. O logo está incorporado no HTML e a política de conteúdo permite essas imagens locais, dispensando novos arquivos na atualização. Atualize pelo procedimento acima e pressione **Ctrl+F5** no navegador.

A navegação, o login, o logo, o estado sem recebimentos, as cores e o layout em desktop, tablet e celular foram verificados em Chromium. O teste `tests/test_visual.cjs` requer Playwright, Chromium e servidor de teste na porta 8080 com usuário fictício `visual`, perfil gerência e senha na variável `PIX_TEST_PASSWORD`; use banco isolado. `PLAYWRIGHT_MODULE` e `CHROMIUM_EXECUTABLE` podem indicar as instalações dessas ferramentas. Não execute com contas ou dados reais.


## V1.2 — consulta Itaú sandbox

No próprio servidor, abra **http://localhost:8080**, entre com um usuário de **Gerência** e abra **Gerência → Itaú · Teste de consulta no sandbox**. Gere um token novo no portal Itaú, preencha início/fim em **UTC** (até 31 dias), cole apenas o token e clique em **Consultar sandbox**. A página da API começa em zero; uma página é consultada por vez, com até 100 itens solicitados. Para outra página, informe seu número e um token válido novamente.

A aplicação consulta somente `GET https://sandbox.devportal.itau.com.br/itau-ep9-api-regulatorio-pix-v2-externo/v2/pix`. O certificado do servidor é validado pelo contexto TLS padrão do Python. Não aceita URL arbitrária nem segue redirecionamentos. Requer saída HTTPS para esse domínio no computador do painel. Se houver erro TLS, verifique a cadeia de confiança usada pelo Python; não desative a verificação.

O token é usado apenas na consulta, não é salvo em banco ou arquivo e não é devolvido nos erros de validação; o campo visual é limpo. Não use token de produção. Como o painel original usa HTTP, a consulta aceita apenas clientes em loopback IPv4/IPv6; não encaminhe essa rota por proxy reverso. Um acesso pelo IP da rede pode usar o painel normalmente, mas não consultar o sandbox.

Os resultados aparecem apenas nessa seção, sem gravação no histórico principal, sem avisos sonoros de recebimento e sem alterar o status de conexão com produção. `infoPagador` é descrição, não identidade do pagador. Os totais são da página retornada; devoluções contam apenas quando têm status `DEVOLVIDO`. O sandbox já retornou exemplos fora do período e paginação inconsistente; ambos geram avisos visíveis. Não use esses registros como confirmação bancária.

Não há integração de produção, renovação automática de token, webhook, emissão de cobrança ou devolução financeira. A chamada externa foi validada pelo usuário no PowerShell com HTTP 200. Nesta implementação, o backend e a interface foram testados com respostas simuladas; a conexão real por dentro do aplicativo Windows ainda precisa ser verificada após instalar a versão.

A atualização mantém `requirements.txt` e os quatro arquivos de código reconhecidos pelo atualizador antigo, sem dependências adicionais em produção. Para executar a suíte de desenvolvimento, instale também `httpx`, necessário ao TestClient do FastAPI; para navegador, Playwright e Chromium, conforme instruções acima.
