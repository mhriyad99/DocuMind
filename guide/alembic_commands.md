# Alembic Command Reference

Alembic is the database migration tool for SQLAlchemy. Below are the most important commands you'll use day-to-day.

---

## Initialization

```bash
alembic init <directory>
```
Bootstraps a new Alembic environment. Creates the `alembic.ini` config file and a migrations directory (commonly named `alembic/`).

---

## Creating Migrations

### Auto-generate a migration
```bash
alembic revision --autogenerate -m "describe your change"
```
Compares your SQLAlchemy models against the current database state and generates a migration script automatically. Always review the generated file before applying.

### Create a blank migration
```bash
alembic revision -m "describe your change"
```
Creates an empty migration script with `upgrade()` and `downgrade()` stubs for you to fill in manually.

---

## Running Migrations

### Upgrade to the latest revision
```bash
alembic upgrade head
```
Applies all pending migrations up to the latest.

### Upgrade by a relative number of steps
```bash
alembic upgrade +2
```
Applies the next 2 pending migrations.

### Upgrade to a specific revision
```bash
alembic upgrade <revision_id>
```
Migrates up to (and including) the specified revision.

---

## Rolling Back Migrations

### Downgrade one step
```bash
alembic downgrade -1
```
Rolls back the most recently applied migration.

### Downgrade to a specific revision
```bash
alembic downgrade <revision_id>
```
Rolls back to the specified revision.

### Downgrade all the way to the base (empty database)
```bash
alembic downgrade base
```
Reverts all migrations. Use with caution.

---

## Inspecting State

### Show current revision(s)
```bash
alembic current
```
Displays which revision(s) the database is currently at.

### Show migration history
```bash
alembic history
```
Lists all revisions in chronological order.

### Show history with more detail
```bash
alembic history --verbose
```

### Show pending migrations (head vs current)
```bash
alembic heads
```
Shows all head revisions (useful when there are branch points).

### Show the full revision tree
```bash
alembic branches
```
Displays any branch points in the revision history.

---

## Stamping (Without Running Migrations)

### Stamp the database at a specific revision
```bash
alembic stamp <revision_id>
```
Marks the database as being at a given revision **without** running any migration scripts. Useful when setting up Alembic on an existing database.

### Stamp to head without migrating
```bash
alembic stamp head
```

---

## Showing Migration SQL (Dry Run)

```bash
alembic upgrade head --sql
```
Prints the raw SQL that *would* be executed without actually running it. Useful for review or for applying migrations manually.

```bash
alembic downgrade -1 --sql
```

---

## Editing & Merging

### Edit a revision file
```bash
alembic edit <revision_id>
```
Opens the migration script in your default editor.

### Merge two branch heads
```bash
alembic merge -m "merge branches" <revision_id_1> <revision_id_2>
```
Creates a new merge revision that combines two diverging migration branches.

---

## Quick Reference Table

| Command | What It Does |
|---|---|
| `alembic init <dir>` | Set up a new Alembic environment |
| `alembic revision -m "msg"` | Create a blank migration |
| `alembic revision --autogenerate -m "msg"` | Auto-generate migration from model changes |
| `alembic upgrade head` | Apply all pending migrations |
| `alembic upgrade +N` | Apply next N migrations |
| `alembic downgrade -1` | Roll back one migration |
| `alembic downgrade base` | Roll back everything |
| `alembic current` | Show current DB revision |
| `alembic history` | List all revisions |
| `alembic heads` | Show head revision(s) |
| `alembic stamp head` | Mark DB as up-to-date without migrating |
| `alembic upgrade head --sql` | Preview SQL without applying |
| `alembic merge -m "msg" <r1> <r2>` | Merge two branch heads |

---

## Tips

- Always review auto-generated migrations — Alembic can miss certain changes (e.g., column constraints, server defaults, index names).
- Use `--sql` in production to review SQL before applying.
- Keep migration messages descriptive: `"add user email index"` beats `"update"`.
- Never edit an already-applied migration; create a new one instead.
