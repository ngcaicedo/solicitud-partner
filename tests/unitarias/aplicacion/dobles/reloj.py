from dataclasses import dataclass
from datetime import datetime, timedelta

from tests.unitarias.dominio.datos import INSTANTE


@dataclass
class RelojSecuencial:
    instante: datetime = INSTANTE

    def ahora(self) -> datetime:
        actual = self.instante
        self.instante += timedelta(seconds=1)
        return actual
