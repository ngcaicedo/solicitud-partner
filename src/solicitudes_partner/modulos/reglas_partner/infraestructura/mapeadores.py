from solicitudes_partner.modulos.reglas_partner.dominio.entidades import EvaluacionReglasPartner
from solicitudes_partner.modulos.reglas_partner.dominio.objetos_valor import (
    PoliticaPartner,
    TipoRedProveedores,
)
from solicitudes_partner.modulos.reglas_partner.infraestructura.orm import (
    EvaluacionSQL,
    PoliticaSQL,
)
from solicitudes_partner.modulos.reglas_partner.infraestructura.serializacion import decodificar


def cargar_evaluacion(fila: EvaluacionSQL) -> EvaluacionReglasPartner:
    return EvaluacionReglasPartner(id=fila.id, evento=decodificar(fila.evento))


def cargar_politica(fila: PoliticaSQL) -> PoliticaPartner:
    return PoliticaPartner(
        id=fila.id,
        id_partner=fila.id_partner,
        version=fila.version,
        tipo_red=TipoRedProveedores(fila.tipo_red),
    )
