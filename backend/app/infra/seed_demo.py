"""Seed sintético de demonstração — dados fictícios para ambiente local/demo.

Idempotente: se ana.souza@demo.multik já existir, retorna sem fazer nada.
Executa dentro de transação com app.papel = 'admin' para bypassar RLS.
"""

import logging
import random
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

_log = logging.getLogger(__name__)

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.auth import TENANT_ID
from app.infra.auth_service import hash_senha
from app.infra.cpf import cpf_para_idx
from app.infra.cpf_gen import gerar_cpf
from app.infra.models import (
    Cliente,
    Cotacao,
    CotacaoJob,
    Imovel,
    Proposta,
    Usuario,
    Veiculo,
)

# ---------------------------------------------------------------------------
# Listas de nomes
# ---------------------------------------------------------------------------

_NOMES_M = [
    "Carlos",
    "João",
    "Pedro",
    "Lucas",
    "Marcos",
    "Rafael",
    "Eduardo",
    "Felipe",
    "Thiago",
    "André",
    "Bruno",
    "Diego",
    "Gustavo",
    "Henrique",
    "Roberto",
]
_NOMES_F = [
    "Ana",
    "Juliana",
    "Fernanda",
    "Patricia",
    "Camila",
    "Beatriz",
    "Mariana",
    "Carla",
    "Renata",
    "Sandra",
    "Cristiane",
    "Leticia",
    "Vanessa",
    "Priscila",
    "Monica",
]
_SOBRENOMES = [
    "Silva",
    "Santos",
    "Oliveira",
    "Souza",
    "Lima",
    "Costa",
    "Ferreira",
    "Rodrigues",
    "Almeida",
    "Nascimento",
    "Carvalho",
    "Pereira",
    "Araújo",
    "Gomes",
    "Martins",
]

# Veículos auto: (marca, modelo, combustivel)
_VEICULOS = [
    ("Chevrolet", "Onix", "FLEX"),
    ("Hyundai", "HB20", "FLEX"),
    ("Fiat", "Strada", "FLEX"),
    ("Fiat", "Toro", "DIESEL"),
    ("Toyota", "Corolla", "FLEX"),
    ("Jeep", "Compass", "FLEX"),
    ("Jeep", "Renegade", "FLEX"),
    ("Renault", "Kwid", "FLEX"),
    ("Volkswagen", "Polo", "FLEX"),
    ("Volkswagen", "T-Cross", "FLEX"),
    ("Hyundai", "Creta", "FLEX"),
]

# Motos: (marca, modelo, cilindrada, categoria)
_MOTOS = [
    ("Honda", "CG 160", 160, "urbana"),
    ("Honda", "CB 500F", 500, "esportiva"),
    ("Honda", "Biz 125", 125, "urbana"),
    ("Yamaha", "Fazer 250", 250, "urbana"),
    ("Yamaha", "MT-03", 300, "esportiva"),
    ("Yamaha", "Crosser 150", 150, "trail"),
    ("Kawasaki", "Ninja 400", 400, "esportiva"),
    ("Kawasaki", "Z400", 400, "esportiva"),
    ("Shineray", "Phoenix 50", 50, "scooter"),
    ("Dafra", "Speed 150", 150, "urbana"),
    ("BMW", "G 310 R", 310, "esportiva"),
    ("Royal Enfield", "Meteor 350", 350, "custom"),
]

# CEPs região Campinas
_CEPS = [
    "13013001",
    "13025000",
    "13070000",
    "13041000",
    "13023000",
    "13087000",
    "13036000",
    "13330000",
    "13347000",
    "13056000",
]

_ESTADOS_CIVIS = ["solteiro", "casado", "divorciado", "viuvo", "uniao_estavel"]
_PROFISSOES = [
    "autonomo",
    "assalariado",
    "empresario",
    "aposentado",
    "servidor_publico",
]

# Corretores demo
_CORRETORES = [
    ("Ana Beatriz Souza", "ana.souza@demo.multik"),
    ("Carlos Eduardo Mendes", "carlos.mendes@demo.multik"),
    ("Fernanda Lima", "fernanda.lima@demo.multik"),
]
_ADMIN_DEMO = ("Admin Demo", "admin@demo.multik")

# Distribuição de status: 60 sucesso, 15 restricao, 15 erro, 10 aguardando
_STATUS_POOL = (
    ["sucesso"] * 60 + ["restricao"] * 15 + ["erro"] * 15 + ["aguardando"] * 10
)


def _dec(valor: float, casas: int = 2) -> Decimal:
    """Converte float para Decimal com arredondamento — nunca float direto."""
    quantize = Decimal("0." + "0" * casas)
    return Decimal(str(valor)).quantize(quantize, rounding=ROUND_HALF_UP)


def _nome_aleatorio() -> tuple[str, str]:
    """Retorna (nome_completo, sexo)."""
    if random.random() < 0.5:
        return f"{random.choice(_NOMES_M)} {random.choice(_SOBRENOMES)}", "M"
    return f"{random.choice(_NOMES_F)} {random.choice(_SOBRENOMES)}", "F"


def _nascimento_aleatorio() -> date:
    """Gera data de nascimento entre 20 e 70 anos atrás."""
    hoje = date.today()
    anos = random.randint(20, 70)
    return hoje - timedelta(days=anos * 365 + random.randint(0, 364))


def _dados_risco_auto() -> dict[str, Any]:
    marca, modelo, comb = random.choice(_VEICULOS)
    ano = random.randint(2015, 2024)
    return {
        "ramo": "auto",
        "marca": marca,
        "modelo": modelo,
        "combustivel": comb,
        "ano_fabricacao": ano,
        "ano_modelo": ano + 1,
        "cep_pernoite": random.choice(_CEPS),
        "finalidade": "lazer",
    }


def _dados_risco_moto() -> dict[str, Any]:
    marca, modelo, cilindrada, categoria = random.choice(_MOTOS)
    ano = random.randint(2015, 2024)
    return {
        "ramo": "moto",
        "marca": marca,
        "modelo": modelo,
        "cilindrada": cilindrada,
        "categoria": categoria,
        "combustivel": "GASOLINA",
        "ano_fabricacao": ano,
        "ano_modelo": ano + 1,
        "cep_pernoite": random.choice(_CEPS),
        "finalidade": "pessoal",
    }


def _dados_risco_imovel() -> dict[str, Any]:
    return {
        "ramo": "imovel",
        "cep": random.choice(_CEPS),
        "tipo_imovel": random.choice(["casa", "apartamento"]),
        "tipo_construcao": "alvenaria",
        "valor_imovel": str(_dec(random.uniform(200_000, 800_000))),
    }


def _premio_auto() -> Decimal:
    return _dec(random.uniform(1800, 4500))


def _premio_moto() -> Decimal:
    return _dec(random.uniform(600, 2200))


def _premio_imovel() -> Decimal:
    return _dec(random.uniform(300, 900))


def _comissao_pct() -> Decimal:
    """Percentual de comissão entre 13% e 17%."""
    return _dec(random.uniform(0.13, 0.17), 4)


def _criado_em_aleatorio() -> datetime:
    """Data aleatória nos últimos 12 meses."""
    dias = random.randint(0, 365)
    return datetime.now(UTC) - timedelta(days=dias)


def _email_cliente(nome: str, idx: int) -> str:
    slug = nome.lower().replace(" ", ".").replace("ã", "a").replace("é", "e")
    return f"{slug}.{idx}@clientes.demo"


# ---------------------------------------------------------------------------
# Distribuição de datas de início de vigência para propostas
# ---------------------------------------------------------------------------


def _vigencias_especiais() -> list[date]:
    """
    Gera lista de início_vigência para propostas com janelas de renovação:
    - 15 com fim entre hoje e hoje+30 (janela D-30)
    - 10 com fim entre hoje+31 e hoje+45 (janela D-45)
    - 8 com fim entre hoje+46 e hoje+60 (janela D-60)
    """
    hoje = date.today()
    vigencias: list[date] = []
    # fim_vigencia = inicio + 365 → inicio = fim - 365
    for _ in range(15):
        dias_fim = random.randint(0, 30)
        fim = hoje + timedelta(days=dias_fim)
        vigencias.append(fim - timedelta(days=365))
    for _ in range(10):
        dias_fim = random.randint(31, 45)
        fim = hoje + timedelta(days=dias_fim)
        vigencias.append(fim - timedelta(days=365))
    for _ in range(8):
        dias_fim = random.randint(46, 60)
        fim = hoje + timedelta(days=dias_fim)
        vigencias.append(fim - timedelta(days=365))
    random.shuffle(vigencias)
    return vigencias


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------


async def criar_demo(factory: async_sessionmaker[AsyncSession]) -> None:
    """Popula o banco com dados sintéticos de demonstração. Idempotente."""
    async with factory() as db:
        # Idempotência: verifica e-mail sentinela
        res_u = await db.execute(
            select(Usuario).where(Usuario.email == "ana.souza@demo.multik")
        )
        if res_u.scalar_one_or_none() is not None:
            return  # já existe — nada a fazer

        await db.execute(text("SET LOCAL app.papel = 'admin'"))

        # ------------------------------------------------------------------
        # Cria usuários — senhas geradas aleatoriamente a cada seed
        # ------------------------------------------------------------------
        _raw_corretor = secrets.token_urlsafe(12)
        _raw_admin = secrets.token_urlsafe(12)
        senha_corretor = hash_senha(_raw_corretor)
        senha_admin = hash_senha(_raw_admin)
        _log.warning(
            "SEED DEMO — credenciais geradas (só visíveis aqui, nunca em prod):\n"
            "  corretores : %s\n"
            "  admin      : %s",
            _raw_corretor,
            _raw_admin,
        )

        corretores: list[Usuario] = []
        for nome, email in _CORRETORES:
            u = Usuario(
                id=uuid.uuid4(),
                email=email,
                nome=nome,
                senha_hash=senha_corretor,
                papel="corretor",
                ativo=True,
                tenant_id=TENANT_ID,
            )
            db.add(u)
            corretores.append(u)

        admin_uid = uuid.uuid4()
        admin = Usuario(
            id=admin_uid,
            email=_ADMIN_DEMO[1],
            nome=_ADMIN_DEMO[0],
            senha_hash=senha_admin,
            papel="admin",
            ativo=True,
            tenant_id=TENANT_ID,
        )
        db.add(admin)
        await db.flush()

        # Define contexto RLS — SET LOCAL não aceita parâmetros no Postgres
        await db.execute(
            text("SELECT set_config('app.usuario_id', :uid, true)"),
            {"uid": str(admin_uid)},
        )

        # ------------------------------------------------------------------
        # Cria ~40 clientes (~13 por corretor)
        # ------------------------------------------------------------------
        clientes_por_corretor: dict[uuid.UUID, list[Cliente]] = {
            c.id: [] for c in corretores
        }
        idx_global = 0
        for corretor in corretores:
            for _ in range(13):
                nome, sexo = _nome_aleatorio()
                cpf = gerar_cpf()
                cli = Cliente(
                    id=uuid.uuid4(),
                    nome=nome,
                    cpf_idx=cpf_para_idx(cpf),
                    email=_email_cliente(nome, idx_global),
                    telefone=f"1199{random.randint(1000000, 9999999)}",
                    data_nascimento=_nascimento_aleatorio(),
                    sexo=sexo,
                    estado_civil=random.choice(_ESTADOS_CIVIS),
                    profissao=random.choice(_PROFISSOES),
                    usuario_id=corretor.id,
                    tenant_id=TENANT_ID,
                )
                db.add(cli)
                clientes_por_corretor[corretor.id].append(cli)
                idx_global += 1

        await db.flush()

        # ------------------------------------------------------------------
        # Cria veículos e imóveis registrados (~60% / ~25% dos clientes)
        # ------------------------------------------------------------------
        todos_clientes = [c for lst in clientes_por_corretor.values() for c in lst]
        for cli in todos_clientes:
            if random.random() < 0.60:
                marca, modelo, comb = random.choice(_VEICULOS)
                ano = random.randint(2015, 2024)
                db.add(
                    Veiculo(
                        id=uuid.uuid4(),
                        cliente_id=cli.id,
                        marca=marca,
                        modelo=modelo,
                        ano_fabricacao=ano,
                        ano_modelo=ano + 1,
                        combustivel=comb,
                        finalidade="lazer",
                        cep_pernoite=random.choice(_CEPS),
                        tenant_id=TENANT_ID,
                    )
                )
            if random.random() < 0.25:
                db.add(
                    Imovel(
                        id=uuid.uuid4(),
                        cliente_id=cli.id,
                        cep=random.choice(_CEPS),
                        tipo_imovel=random.choice(["casa", "apartamento"]),
                        tipo_construcao="alvenaria",
                        tenant_id=TENANT_ID,
                    )
                )

        await db.flush()

        # ------------------------------------------------------------------
        # Cria ~120 cotações (~3 por cliente)  70% auto / 30% residência
        # ------------------------------------------------------------------
        status_pool = _STATUS_POOL.copy()
        random.shuffle(status_pool)
        status_iter = iter(status_pool * 10)  # pool infinito reciclado

        # Cotações aguardando precisam ter criado_em > 2 dias atrás
        _2_dias_atras = datetime.now(UTC) - timedelta(days=3)

        cotacoes_sucesso: list[tuple[Cotacao, uuid.UUID]] = []  # (cotacao, corretor_id)

        for corretor in corretores:
            for cli in clientes_por_corretor[corretor.id]:
                for _ in range(3):
                    status = next(status_iter)
                    ramo = random.choices(
                        ["auto", "moto", "imovel"], weights=[60, 25, 15]
                    )[0]

                    tem_premio = status in ("sucesso", "restricao")
                    if ramo == "auto":
                        dados = _dados_risco_auto()
                        premio = _premio_auto() if tem_premio else None
                    elif ramo == "moto":
                        dados = _dados_risco_moto()
                        premio = _premio_moto() if tem_premio else None
                    else:
                        dados = _dados_risco_imovel()
                        premio = _premio_imovel() if tem_premio else None

                    # Cotações "aguardando" ficam paradas há pelo menos 3 dias
                    if status == "aguardando":
                        criado_em = _2_dias_atras - timedelta(
                            days=random.randint(0, 30)
                        )
                    else:
                        criado_em = _criado_em_aleatorio()

                    cot = Cotacao(
                        id=uuid.uuid4(),
                        cliente_id=cli.id,
                        ramo=ramo,
                        status=status,
                        dados_risco=dados,
                        cotacao_id_cia=(
                            f"CIA-{uuid.uuid4().hex[:8].upper()}"
                            if status in ("sucesso", "restricao")
                            else None
                        ),
                        premio_total=premio,
                        restricoes=(
                            [{"codigo": "R01", "mensagem": "Risco elevado"}]
                            if status == "restricao"
                            else []
                        ),
                        mensagens=[],
                        necessita_vistoria=False,
                        usuario_id=corretor.id,
                        tenant_id=TENANT_ID,
                        criado_em=criado_em,
                    )
                    db.add(cot)

                    # Job sintético para que o comparativo tenha dados
                    if status in ("sucesso", "restricao", "erro"):
                        job_status_resultado = (
                            "restricao"
                            if status == "restricao"
                            else "sucesso"
                            if status == "sucesso"
                            else "erro"
                        )
                        db.add(
                            CotacaoJob(
                                id=uuid.uuid4(),
                                cotacao_id=cot.id,
                                cia="fake",
                                status="concluido",
                                tentativas=1,
                                criado_em=criado_em,
                                processado_em=criado_em,
                                cotacao_id_cia=cot.cotacao_id_cia,
                                premio_total=cot.premio_total,
                                restricoes=list(cot.restricoes or []),
                                mensagens=list(cot.mensagens or []),
                                necessita_vistoria=cot.necessita_vistoria,
                                status_resultado=job_status_resultado,
                                tenant_id=TENANT_ID,
                            )
                        )

                    if status in ("sucesso", "restricao"):
                        cotacoes_sucesso.append((cot, corretor.id))

        await db.flush()

        # ------------------------------------------------------------------
        # Cria ~60 propostas (~50% conversão das cotações com sucesso/restricao)
        # ------------------------------------------------------------------
        candidatas = cotacoes_sucesso.copy()
        random.shuffle(candidatas)
        # Aproximadamente metade vira proposta
        n_propostas = len(candidatas) // 2
        selecionadas = candidatas[:n_propostas]

        vigencias_especiais = _vigencias_especiais()
        vigencias_iter = iter(vigencias_especiais)

        for cotacao, corretor_id in selecionadas:
            pct = _comissao_pct()
            n_parc = random.choice([1, 2, 3, 6, 10, 12])
            premio = cotacao.premio_total or _dec(2000)
            valor_parcela = (premio / n_parc).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            comissao_parcela = (valor_parcela * pct).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            # Usa vigência especial (janela D-30/D-45/D-60) se disponível
            inicio: date | None
            try:
                inicio = next(vigencias_iter)
            except StopIteration:
                # Demais propostas: ativas ou vencidas aleatoriamente
                dias_inicio = random.randint(-400, 30)
                inicio = date.today() + timedelta(days=dias_inicio)

            prop = Proposta(
                id=uuid.uuid4(),
                cotacao_id=cotacao.id,
                protocolo=f"DEMO-{uuid.uuid4().hex[:8].upper()}",
                commissao_pct=pct,
                plano_pagamento=random.choice(
                    ["AVISTA", "2X", "3X", "6X", "10X", "12X"]
                ),
                n_parcelas=n_parc,
                valor_parcela=valor_parcela,
                comissao_parcela=comissao_parcela,
                inicio_vigencia=inicio,
                usuario_id=corretor_id,
                tenant_id=TENANT_ID,
            )
            db.add(prop)

        await db.commit()
