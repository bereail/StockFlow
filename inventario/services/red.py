"""
Verificación de conectividad de red (ping) para equipos con IP asignada.
"""
import platform
import subprocess


def hacer_ping(ip: str, timeout_seg: float = 1.5) -> bool:
    """
    Hace un único ping a la IP dada y devuelve True si respondió.

    Usa el comando ping del sistema operativo, siempre con una lista de
    argumentos (sin shell=True): la IP llega desde un campo ya validado
    del modelo (GenericIPAddressField), nunca se arma un string de comando.
    """
    if not ip:
        return False

    if platform.system().lower() == "windows":
        comando = ["ping", "-n", "1", "-w", str(int(timeout_seg * 1000)), ip]
    else:
        comando = ["ping", "-c", "1", "-W", str(int(timeout_seg)), ip]

    try:
        resultado = subprocess.run(
            comando,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_seg + 2,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False

    return resultado.returncode == 0
