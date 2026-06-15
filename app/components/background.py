"""
Utilidades para cómputo en segundo plano con barra de progreso.

Permite que cálculos pesados (FP-Growth, Random Forest, etc.) corran en
un hilo separado mientras el usuario navega a otras pestañas del dashboard.
Al volver, los resultados se muestran instantáneamente.

Uso típico en una página:
    task = get_task("mi_tarea")
    if needs_recompute(task, params_hash):
        task.start(_mi_funcion, arg1, arg2)
    if not show_progress_or_result(task):
        st.stop()
    resultado = task.result
"""

from __future__ import annotations

import threading
import time

import streamlit as st


class BackgroundTask:
    """Tarea en segundo plano con seguimiento de progreso."""

    __slots__ = (
        "_lock",
        "_notified",
        "error",
        "message",
        "params_hash",
        "progress",
        "result",
        "status",
    )

    def __init__(self) -> None:
        self.status: str = "idle"  # idle | running | done | error
        self.progress: float = 0.0
        self.message: str = ""
        self.result = None
        self.error: str | None = None
        self.params_hash: str = ""
        self._notified: bool = False
        self._lock = threading.Lock()

    def update(self, progress: float, message: str = "") -> None:
        """Actualiza progreso (llamar desde el hilo de trabajo)."""
        with self._lock:
            self.progress = min(progress, 0.99)
            if message:
                self.message = message

    def start(self, func, *args) -> None:
        """Inicia la función en un hilo separado. func recibe (task, *args)."""
        with self._lock:
            self.status = "running"
            self.progress = 0.0
            self.message = "Iniciando..."
            self.error = None
            self.result = None
            self._notified = False

        def _worker():
            try:
                res = func(self, *args)
                with self._lock:
                    self.result = res
                    self.status = "done"
                    self.progress = 1.0
                    self.message = "¡Completado!"
            except Exception as exc:
                with self._lock:
                    self.status = "error"
                    self.error = str(exc)

        threading.Thread(target=_worker, daemon=True).start()


def get_task(key: str) -> BackgroundTask:
    """Obtiene o crea una tarea en session_state."""
    sk = f"_bg_{key}"
    if sk not in st.session_state:
        st.session_state[sk] = BackgroundTask()
    return st.session_state[sk]


def needs_recompute(task: BackgroundTask, params_hash: str) -> bool:
    """True si los parámetros cambiaron y hay que recalcular."""
    if task.params_hash != params_hash:
        task.status = "idle"
        task.params_hash = params_hash
        return True
    return task.status == "idle"


def show_progress_or_result(task: BackgroundTask) -> bool:
    """
    Muestra barra de progreso si la tarea corre, toast si acaba de terminar.

    Returns True si el resultado está disponible en task.result.
    Si la tarea sigue corriendo, hace poll cada 1s con st.rerun().
    """
    if task.status == "running":
        st.progress(task.progress, text=task.message)
        st.info(
            "💡 Podés navegar a otra pestaña mientras se procesa. "
            "Los resultados se guardarán automáticamente."
        )
        time.sleep(1)
        st.rerun()
        return False  # unreachable, for type checker

    if task.status == "done":
        if not task._notified:
            st.toast("¡Cálculo completado!")
            task._notified = True
        return True

    if task.status == "error":
        st.error(f"Error en el cálculo: {task.error}")
        task.status = "idle"
        return False

    return False  # idle
