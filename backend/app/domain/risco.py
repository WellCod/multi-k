from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class Combustivel(StrEnum):
    GASOLINA = "gasolina"
    ETANOL = "etanol"
    FLEX = "flex"
    DIESEL = "diesel"
    ELETRICO = "eletrico"
    GNV = "gnv"


class TipoImovel(StrEnum):
    CASA = "casa"
    APARTAMENTO = "apartamento"
    CONDOMINIO = "condominio"


class Proponente(BaseModel):
    cpf: str = Field(pattern=r"^\d{11}$")
    nome: str
    nascimento: date
    sexo: str = Field(pattern=r"^[MF]$")
    estado_civil: str
    profissao: str
    email: str
    telefone: str


class Vigencia(BaseModel):
    inicio: date
    fim: date


class RiscoAuto(BaseModel):
    proponente: Proponente
    vigencia: Vigencia
    fipe_codigo: str
    ano_modelo: int = Field(ge=1900, le=2100)
    placa: str | None = None
    chassi: str | None = None
    combustivel: Combustivel
    blindado: bool = False
    alienado: bool = False
    cep_pernoite: str = Field(pattern=r"^\d{8}$")
    garagem: bool = True
    km_mes: int = Field(ge=0)
    condutor_principal_idade: int = Field(ge=18, le=100)
    condutores_menores: bool = False
    bonus: int = Field(ge=0, le=10, default=0)
    coberturas: list[str]


class RiscoResidencia(BaseModel):
    proponente: Proponente
    vigencia: Vigencia
    tipo: TipoImovel
    cep: str = Field(pattern=r"^\d{8}$")
    valor_imovel: Decimal = Field(gt=Decimal("0"))
    valor_conteudo: Decimal = Field(ge=Decimal("0"), default=Decimal("0"))
    alarme: bool = False
    cerca_eletrica: bool = False
    grades: bool = False
    coberturas: list[str]
