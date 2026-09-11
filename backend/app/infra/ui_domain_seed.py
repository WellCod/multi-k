"""Existing form options moved into domain-table bootstrap data (ADR-010)."""


def ui_domain_rows() -> list[dict[str, str]]:
    groups = {
        "sexo": [("M", "Masculino"), ("F", "Feminino")],
        "parentesco": [
            ("conjuge", "Cônjuge"),
            ("filho", "Filho(a)"),
            ("pai", "Pai / Mãe"),
            ("irmao", "Irmão(ã)"),
            ("outro", "Outro"),
        ],
        "categoria_moto": [
            ("urbana", "Urbana"),
            ("esportiva", "Esportiva"),
            ("trail", "Trail / Adventure"),
            ("custom", "Custom / Touring"),
            ("scooter", "Scooter"),
        ],
        "finalidade_auto": [
            ("pessoal", "Pessoal / Lazer"),
            ("comercial", "Comercial"),
            ("app", "Aplicativo de transporte"),
            ("taxi", "Táxi"),
        ],
        "finalidade_moto": [
            ("pessoal", "Pessoal / Lazer"),
            ("comercial", "Comercial / Delivery"),
            ("app", "Aplicativo de transporte"),
            ("taxi", "Táxi"),
        ],
        "bonus": [(str(i), "Sem bônus" if i == 0 else str(i)) for i in range(11)],
    }
    return [
        {"tipo": tipo, "codigo": code, "descricao": label}
        for tipo, values in groups.items()
        for code, label in values
    ]
