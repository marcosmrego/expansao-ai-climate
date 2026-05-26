# Schema SQL

Execute o script abaixo para criar o schema completo do zero:

```bash
psql -U postgres -d climate -f database/sql/001_schema.sql
```

O script é idempotente (`IF NOT EXISTS`) — pode ser executado em qualquer ordem sem efeito colateral.
