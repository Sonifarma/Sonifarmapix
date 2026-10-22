# Sonifarma Pix Monitor — protótipo local V1.0

**Atenção:** este é um protótipo para teste local, NÃO conectado ao Itaú. Os pagamentos inseridos são simulados; não servem como confirmação bancária. Não expor na internet nem usar em produção.

## Executar (Windows PowerShell)

```powershell
cd sonifarma_pix_mvp
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PIX_ADMIN_TOKEN = 'TROQUE-POR-UM-TOKEN-ALEATORIO-LONGO'
python -m uvicorn app:app --host 127.0.0.1 --port 8080
```

Abra http://127.0.0.1:8080 e digite o mesmo token. Para simular um recebimento em outro PowerShell:

```powershell
$headers = @{ 'X-Admin-Token' = 'TROQUE-POR-UM-TOKEN-ALEATORIO-LONGO' }
$body = @{ end_to_end_id = 'E1234567890123456789012345678901'; amount = '149.90'; payer = 'Cliente Teste'; received_at = (Get-Date).ToUniversalTime().ToString('o') } | ConvertTo-Json
Invoke-RestMethod -Uri 'http://127.0.0.1:8080/internal/pix' -Method Post -Headers $headers -ContentType 'application/json' -Body $body
```

## Próximas etapas antes de produção

1. Confirmar com Itaú os produtos de API e a cobertura de Pix por chave e QR Code, inclusive QR de maquininha/adquirente.
2. Provisionar aplicação e credenciais oficiais no portal do Itaú, certificados mTLS e OAuth; não enviar segredos pelo chat.
3. Implementar adaptador Itaú com validação/autenticidade de webhook e consulta paginada de recebimentos, respeitando os contratos oficiais.
4. Migrar SQLite para PostgreSQL, usar contas individuais, HTTPS, auditoria, retenção de dados e proteção LGPD.
5. Adicionar conciliação, reconexão e alertas de indisponibilidade; testar com pagamentos reais de baixo valor autorizados pela empresa.

## Limitações atuais

- Endpoint `/internal/pix` é uma entrada de simulação protegida por token, **não** um webhook bancário.
- A lista retorna somente os 100 recebimentos mais recentes; o total da interface é apenas desses registros, não o total diário.
- O alerta sonoro pode depender da interação inicial do usuário com a página.
- Sem integração real com banco, não há confirmação oficial de pagamentos.
