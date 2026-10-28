"""
Backup de la base SQLite antes de operaciones riesgosas (ej. migrar al
arrancar la app de escritorio) y backup periódico de resguardo.
"""
import sqlite3
from datetime import datetime
from pathlib import Path


def respaldar_sqlite(db_path, backups_dir, mantener: int = 15) -> Path | None:
    """
    Copia la base SQLite de `db_path` a `backups_dir` con un timestamp,
    usando la API de backup online de SQLite (segura aunque la base esté
    siendo usada por otra conexión), y rota dejando solo los últimos
    `mantener` archivos.

    Devuelve el Path del backup creado, o None si no había nada que
    respaldar (primera vez que corre la app, todavía sin base).
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return None

    backups_dir = Path(backups_dir)
    backups_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = backups_dir / f"db_{timestamp}.sqlite3"

    origen = sqlite3.connect(str(db_path))
    try:
        copia = sqlite3.connect(str(destino))
        try:
            origen.backup(copia)
        finally:
            copia.close()
    finally:
        origen.close()

    _rotar_backups(backups_dir, mantener)
    return destino


def _rotar_backups(backups_dir: Path, mantener: int) -> None:
    backups = sorted(backups_dir.glob("db_*.sqlite3"), key=lambda p: p.stat().st_mtime)
    exceso = len(backups) - mantener
    for viejo in backups[:max(exceso, 0)]:
        viejo.unlink(missing_ok=True)
