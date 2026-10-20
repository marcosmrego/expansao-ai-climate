from app.services import brasil_fire_service as svc

EXTRAS = {"24h": {"PA": {"total": 7, "referencia": 1}}, "bioma": {"PA": "Amazônia"}}


def test_montar_itens_includes_regions_without_hotspots_as_zero():
    atuais = {"PA": (300, 900.0), "MT": (100, 200.0)}
    base = {"PA": [8.0, 10.0, 12.0], "MT": [3.0, 4.0, 5.0], "AC": [1.0, 1.0, 2.0]}

    itens = svc._montar_itens("uf", atuais, base, 30, EXTRAS)

    assert len(itens) == 27
    acre = next(i for i in itens if i["codigo"] == "AC")
    assert acre["focos"] == 0
    assert acre["situacao"] == "abaixo"
    assert acre["ultimas_24h"] == {"total": 0, "referencia": 0}


def test_montar_itens_ranks_by_focos_and_adds_extras():
    itens = svc._montar_itens("uf", {"PA": (300, 1.0), "MT": (100, 1.0)}, {}, 30, EXTRAS)

    assert [i["codigo"] for i in itens[:2]] == ["PA", "MT"]
    assert [i["posicao"] for i in itens[:3]] == [1, 2, 3]
    assert itens[0]["ultimas_24h"]["total"] == 7
    assert itens[0]["bioma_predominante"] == "Amazônia"
    assert itens[-1]["focos"] == 0


def test_montar_itens_biome_level_has_no_predominant_biome_field():
    itens = svc._montar_itens("bioma", {"cerrado": (10, 1.0)}, {}, 30, {"24h": {}, "bioma": {}})

    assert len(itens) == 6
    assert "bioma_predominante" not in itens[0]
