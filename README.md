# Ashrise

Sprint 1 deja solamente el subset repo-local: Postgres 15, el schema SQL y una verificacion de sanidad del seed. La API de Ashrise queda explicitamente para Sprint 2.

## Requisitos

- Docker Desktop con `docker compose`
- GNU Make

## Windows

En Windows puede pasar que `make` este instalado via MSYS2 pero no aparezca en PowerShell o Codex, porque `C:\msys64\usr\bin` no siempre queda en el `PATH` de esas sesiones. Ademas, algunas instalaciones de PowerShell bloquean `.ps1` por `ExecutionPolicy`.

Opciones:

- usar MSYS2 directamente si preferis esa terminal
- si PowerShell bloquea scripts, correr `Set-ExecutionPolicy -Scope Process Bypass` en esa sesion; no requiere admin y no cambia la policy global
- correr `.\scripts\windows\ensure-make.ps1 -SessionOnly` para agregar `C:\msys64\usr\bin` solo al `PATH` de la sesion actual
- correr `powershell -ExecutionPolicy Bypass -File .\scripts\windows\ensure-make.ps1 -PersistUserPath` para agregar `C:\msys64\usr\bin` al `PATH` de usuario sin duplicarlo

Despues de cambiar el `PATH` persistente, puede hacer falta reiniciar PowerShell o Codex para que nuevas sesiones vean el cambio.

## Variables de entorno

`.env.example` documenta las variables compartidas de Ashrise y Langfuse:

- `ASHRISE_BASE_URL`
- `ASHRISE_TOKEN`
- `LANGFUSE_BASE_URL`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`

En Sprint 1 quedan solo documentadas; este repo todavia no levanta API.

## Comandos operativos

- `make up`: levanta Postgres 15 y espera a que el contenedor quede healthy.
- `make down`: apaga el stack y conserva el volumen persistente.
- `make logs`: sigue los logs del contenedor `db`.
- `make seed`: recrea la base `ashrise` desde cero y aplica `sql/001_init.sql`.
- `make verify`: valida conteos del seed y que cada `project_state_code` coincida con el seed actual.
- `make psql`: abre `psql` dentro del contenedor contra la base `ashrise`.

## Flujo recomendado

```powershell
make up
make seed
make verify
make psql
```

## Alcance real del sprint

- Postgres 15 local con volumen persistente
- `sql/001_init.sql` aplicado manualmente via `make seed`
- verificacion repo-local via `sql/verify_sanity.sql`

La API minima de Ashrise empieza en Sprint 2, no en este repo-local bootstrap.
