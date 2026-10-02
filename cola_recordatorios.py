"""
Medical Remember - Cola de recordatorios de tomas pendientes del día
====================================================================
Componente: Programación con Estructura de Datos - Primer Corte Evaluativo

Estructura lineal elegida: COLA (Queue, política FIFO), implementada desde
cero con nodos enlazados (sin usar collections.deque ni list.pop(0)) para que
encolar y desencolar sean operaciones O(1).

Relación con el sistema en C# Windows Forms:
  - Toma            <-> fila devuelta por HorarioRepositorio.ListarDeHoy()
  - EstadoToma      <-> enum EstadoToma (Tomado=1, Omitido=2, Tardio=3, Pendiente=4)
  - alertas_proximas() <-> HorarioRepositorio.ListarProximasSinRegistrar() (±5 min)
  - regla de "Tardío" (> 30 min) <-> trigger TR_Historial_MarcarTardio
  - GestorTomasDelDia <-> lógica que hoy vive en FrmPrincipal.Timer_Tick
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Iterator, List, Optional


# ─────────────────────────────────────────────────────────────
# Modelo (equivalente a MedicalRemember.Models en C#)
# ─────────────────────────────────────────────────────────────
class EstadoToma(IntEnum):
    """Mismos valores numéricos que el enum EstadoToma del sistema en C#."""
    TOMADO = 1
    OMITIDO = 2
    TARDIO = 3
    PENDIENTE = 4


@dataclass
class Toma:
    """Una toma programada de un medicamento para un paciente en una hora."""
    horario_id: int
    paciente: str
    medicamento: str
    dosis: str
    programada: datetime
    estado: EstadoToma = EstadoToma.PENDIENTE
    tomada_en: Optional[datetime] = None
    aplazamientos: int = 0

    def __str__(self) -> str:
        return (f"[{self.programada:%H:%M}] {self.paciente} - "
                f"{self.medicamento} {self.dosis} ({self.estado.name})")


# ─────────────────────────────────────────────────────────────
# Estructura de datos: COLA con nodos enlazados
# ─────────────────────────────────────────────────────────────
class _Nodo:
    __slots__ = ("dato", "siguiente")

    def __init__(self, dato):
        self.dato = dato
        self.siguiente: Optional["_Nodo"] = None


class Cola:
    """
    Cola FIFO con lista enlazada simple.

    Se guardan dos referencias: `_frente` (de donde se sale) y `_final`
    (donde se entra). Así ambas operaciones principales son O(1).
    """

    def __init__(self) -> None:
        self._frente: Optional[_Nodo] = None
        self._final: Optional[_Nodo] = None
        self._tamanio = 0

    # -- Operaciones principales ------------------------------------
    def encolar(self, dato) -> None:
        """Agrega un elemento al final de la cola. O(1)."""
        nuevo = _Nodo(dato)
        if self.esta_vacia():
            self._frente = nuevo
        else:
            self._final.siguiente = nuevo
        self._final = nuevo
        self._tamanio += 1

    def desencolar(self):
        """Quita y devuelve el elemento del frente. O(1)."""
        if self.esta_vacia():
            raise IndexError("La cola está vacía: no hay tomas pendientes.")
        nodo = self._frente
        self._frente = nodo.siguiente
        if self._frente is None:
            self._final = None
        self._tamanio -= 1
        return nodo.dato

    def frente(self):
        """Devuelve el elemento del frente SIN quitarlo (peek). O(1)."""
        if self.esta_vacia():
            raise IndexError("La cola está vacía: no hay tomas pendientes.")
        return self._frente.dato

    def esta_vacia(self) -> bool:
        return self._frente is None

    def tamanio(self) -> int:
        return self._tamanio

    def vaciar(self) -> None:
        self._frente = None
        self._final = None
        self._tamanio = 0

    # -- Utilidades -------------------------------------------------
    def __iter__(self) -> Iterator:
        """Recorre de frente a final sin modificar la cola."""
        actual = self._frente
        while actual is not None:
            yield actual.dato
            actual = actual.siguiente

    def __len__(self) -> int:
        return self._tamanio


# ─────────────────────────────────────────────────────────────
# Lógica de aplicación sobre la cola
# ─────────────────────────────────────────────────────────────
class GestorTomasDelDia:
    """
    Administra la cola de tomas pendientes de un día.

    Flujo (igual al del sistema en C#, pero explícito con la cola):
      1. cargar_del_dia()  -> ordena por hora y encola (como ListarDeHoy).
      2. alertas_proximas()-> tomas del frente dentro de ±5 min de "ahora".
      3. atender()         -> desencola y registra Tomado o Tardío.
      4. posponer()        -> reencola al final; tras N aplazamientos, Omitido.
    """

    MINUTOS_VENTANA_ALERTA = 5     # igual que ListarProximasSinRegistrar
    MINUTOS_LIMITE_TARDIO = 30     # igual que TR_Historial_MarcarTardio
    MAX_APLAZAMIENTOS = 2          # tras esto la toma pasa a Omitido

    def __init__(self) -> None:
        self.pendientes = Cola()
        self.historial: List[Toma] = []   # tomas ya resueltas (lo que iría a HistorialCumplimiento)

    # -- Carga ------------------------------------------------------
    def cargar_del_dia(self, tomas: List[Toma]) -> None:
        """Ordena las tomas por hora programada y las encola."""
        self.pendientes.vaciar()
        for toma in sorted(tomas, key=lambda t: t.programada):
            self.pendientes.encolar(toma)

    # -- Consultas --------------------------------------------------
    def siguiente(self) -> Optional[Toma]:
        return None if self.pendientes.esta_vacia() else self.pendientes.frente()

    def alertas_proximas(self, ahora: datetime) -> List[Toma]:
        """
        Tomas pendientes cuya hora está a ±5 minutos de `ahora`.
        Se recorre la cola sin modificarla (equivale a la consulta del timer).
        """
        ventana = timedelta(minutes=self.MINUTOS_VENTANA_ALERTA)
        return [t for t in self.pendientes
                if abs(t.programada - ahora) <= ventana]

    # -- Atender / posponer ----------------------------------------
    def atender(self, ahora: datetime) -> Toma:
        """
        Atiende la toma del frente: la saca de la cola y la registra.
        Si se registra con más de 30 min de retraso queda como TARDIO.
        """
        toma = self.pendientes.desencolar()
        toma.tomada_en = ahora
        retraso = ahora - toma.programada
        if retraso > timedelta(minutes=self.MINUTOS_LIMITE_TARDIO):
            toma.estado = EstadoToma.TARDIO
        else:
            toma.estado = EstadoToma.TOMADO
        self.historial.append(toma)
        return toma

    def posponer(self) -> Toma:
        """
        El paciente no puede tomarlo ahora: la toma vuelve al FINAL de la cola.
        Si ya se aplazó MAX_APLAZAMIENTOS veces, se registra como OMITIDA.
        """
        toma = self.pendientes.desencolar()
        if toma.aplazamientos >= self.MAX_APLAZAMIENTOS:
            toma.estado = EstadoToma.OMITIDO
            self.historial.append(toma)
        else:
            toma.aplazamientos += 1
            self.pendientes.encolar(toma)
        return toma

    # -- Resumen ----------------------------------------------------
    def porcentaje_cumplimiento(self) -> float:
        """Tomados / total resueltas (misma idea que HistorialServicio.CalcularCumplimiento)."""
        if not self.historial:
            return 0.0
        tomados = sum(1 for t in self.historial if t.estado == EstadoToma.TOMADO)
        return tomados * 100.0 / len(self.historial)


# ─────────────────────────────────────────────────────────────
# Demostración
# ─────────────────────────────────────────────────────────────
def _datos_de_ejemplo(dia: datetime) -> List[Toma]:
    def a(h, m):
        return dia.replace(hour=h, minute=m, second=0, microsecond=0)

    return [
        Toma(3, "Maria Garcia Lopez", "Metformina", "850 mg", a(20, 0)),
        Toma(1, "Maria Garcia Lopez", "Glibenclamida", "5 mg", a(8, 0)),
        Toma(2, "Maria Garcia Lopez", "Metformina", "850 mg", a(14, 0)),
        Toma(4, "Maria Garcia Lopez", "Insulina NPH", "10 UI", a(22, 0)),
    ]


def demo() -> None:
    dia = datetime(2026, 10, 2)
    g = GestorTomasDelDia()
    g.cargar_del_dia(_datos_de_ejemplo(dia))

    print("Cola cargada (ordenada por hora):")
    for t in g.pendientes:
        print("  ", t)

    print("\n08:03 -> alertas próximas:", [str(t) for t in g.alertas_proximas(dia.replace(hour=8, minute=3))])
    print("08:03 -> atender:", g.atender(dia.replace(hour=8, minute=3)))

    print("\n14:00 -> el paciente pospone la toma de las 14:00")
    print("   pospuesta:", g.posponer())
    print("   nuevo orden:", [f"{t.programada:%H:%M}" for t in g.pendientes])

    print("\n21:00 -> atender la de las 20:00 (1 h tarde):", g.atender(dia.replace(hour=21, minute=0)))
    print(f"\nCumplimiento parcial: {g.porcentaje_cumplimiento():.0f}%  |  pendientes: {len(g.pendientes)}")


if __name__ == "__main__":
    demo()
