"""
App de carros - versao unica
-----------------------------
Faz tudo em um so lugar:
  1) Le o texto bruto da Tabela PBE (data/pbe_2024_raw.txt)
  2) Organiza os dados em uma lista de veiculos (e salva em data/veiculos.json)
  3) Valida os numeros (gasolina > etanol, faixa plausivel de km/l etc.)
  4) Gera o catalogo em catalogo_veiculos.html

Como rodar:
    python app_de_carros.py
(no Mac/Linux pode ser "python3" em vez de "python")
"""

import re
import json
import os

# Pasta onde este script esta salvo - assim funciona nao importa de onde
# voce chame "python app_de_carros.py"
PASTA_BASE = os.path.dirname(os.path.abspath(__file__))
CAMINHO_DADOS_BRUTOS = os.path.join(PASTA_BASE, "data", "pbe_2026_raw.txt")
CAMINHO_JSON = os.path.join(PASTA_BASE, "data", "veiculos.json")
CAMINHO_HTML = os.path.join(PASTA_BASE, "index.html")

# ---------------------------------------------------------------------------
# 1) PARSER: le o texto da Tabela PBE e organiza em registros estruturados
# ---------------------------------------------------------------------------

CATEGORIAS = [
    "Utilitário Esportivo Compacto 4x4",
    "Utilitário Esportivo Compacto",
    "Utilitário Esportivo Grande 4x4",
    "Utilitário Esportivo Grande",
    "Fora de Estrada Compacto",
    "Fora de Estrada Grande",
    "Sub Compacto",
    "Extra Grande",
    "Picape Compacta",
    "Picape",
    "Esportivo",
    "Compacto",
    "Médio",
    "Grande",
    "Minivan",
    "Comercial",
]
CATEGORIAS.sort(key=len, reverse=True)

# Mapeamento simplificado categoria PBE -> carroceria comum (para exibir no card)
CARROCERIA = {
    "Sub Compacto": "Hatch",
    "Compacto": "Hatch",
    "Médio": "Sedã/Hatch",
    "Grande": "Sedã",
    "Extra Grande": "Sedã/SUV",
    "Utilitário Esportivo Compacto": "SUV",
    "Utilitário Esportivo Compacto 4x4": "SUV 4x4",
    "Utilitário Esportivo Grande": "SUV",
    "Utilitário Esportivo Grande 4x4": "SUV 4x4",
    "Fora de Estrada Compacto": "SUV/Off-road",
    "Fora de Estrada Grande": "SUV/Off-road",
    "Minivan": "Minivan",
    "Comercial": "Comercial",
    "Picape Compacta": "Picape",
    "Picape": "Picape",
    "Esportivo": "Esportivo",
}

MARCAS = [
    "CAOA CHANGAN", "CAOACHANGAN", "CAOA CHERY", "LAND ROVER", "MERCEDES-BENZ",
    "CHEVROLET", "HYUNDAI", "TOYOTA", "NISSAN", "RENAULT", "PEUGEOT",
    "CITROEN", "MITSUBISHI", "VOLKSWAGEN", "VW", "HONDA", "FIAT", "JEEP",
    "KIA", "BMW", "AUDI", "PORSCHE", "SUBARU", "SUZUKI", "MASERATI",
    "JAGUAR", "ZEEKR", "DONFENG", "VOLVO", "BYD", "JAC", "NETA", "MINI",
    "GWM", "LEXUS", "MG", "GAC", "JAECOO", "JETOUR", "GEELY", "LEAPMOTOR",
    "RAM", "DENZA", "OMODA", "FARIZON", "FOTON", "FERRARI", "MCLAREN",
    "FORD",
]
MARCAS.sort(key=len, reverse=True)

TIPO_PROPULSAO = ["Combustão", "Híbrido", "Plug-in", "Elétrico"]

# Algumas marcas aparecem abreviadas na tabela; convertemos para o nome
# completo na exibicao (comparacao feita em maiusculas).
MARCA_NOME_COMPLETO = {
    "VW": "Volkswagen",
}


def formatar_marca(marca):
    nome_completo = MARCA_NOME_COMPLETO.get(marca.upper())
    if nome_completo:
        return nome_completo
    return marca.title() if marca.isupper() else marca


def parse_line(line):
    orig = line.strip()
    if not orig:
        return None

    categoria = None
    for c in CATEGORIAS:
        if orig.startswith(c + " "):
            categoria = c
            resto = orig[len(c):].strip()
            break
    if categoria is None:
        return None

    marca = None
    resto_upper = resto.upper()
    for m in MARCAS:
        if resto_upper.startswith(m + " "):
            marca = resto[:len(m)]
            resto = resto[len(m):].strip()
            break
    if marca is None:
        return None

    prop_idx = None
    prop_tipo = None
    for tp in TIPO_PROPULSAO:
        idx = resto.find(" " + tp + " ")
        if idx != -1 and (prop_idx is None or idx < prop_idx):
            prop_idx = idx
            prop_tipo = tp
    if prop_idx is None:
        return None

    bloco_modelo_motor = resto[:prop_idx].strip()
    resto2 = resto[prop_idx + len(prop_tipo) + 2:].strip()

    if prop_tipo == "Elétrico" and resto2.startswith("Elétrico "):
        # Em veiculos eletricos o Motor tambem aparece como "Elétrico",
        # entao a primeira ocorrencia de " Elétrico " encontrada acima
        # era na verdade o campo Motor, nao o Tipo de Propulsao. A
        # verdadeira coluna Tipo de Propulsao e a proxima palavra
        # "Elétrico" logo no inicio de resto2 - removemos ela aqui.
        motor = "Elétrico"
        modelo_versao = bloco_modelo_motor
        resto2 = resto2[len("Elétrico "):].strip()
    else:
        motor_match = re.search(
            r'(\d+[\.,]\d+\s*-?\s*\d*\s*V?T?|Elétrico)\s*$', bloco_modelo_motor)
        if motor_match:
            motor = motor_match.group(1).strip()
            modelo_versao = bloco_modelo_motor[:motor_match.start()].strip()
        else:
            motor = ""
            modelo_versao = bloco_modelo_motor

    partes_mv = modelo_versao.split(" ", 1)
    modelo = partes_mv[0] if partes_mv else ""
    versao = partes_mv[1] if len(partes_mv) > 1 else ""

    # Cambio: normalmente vem colado ("M-5", "CVT", "DCT-7"), mas em
    # varias linhas (sobretudo VW) vem com espacos ao redor do hifen
    # ("A - 6", "DCT - 7"). Tentamos primeiro o padrao com hifen espacado,
    # depois caimos para "uma palavra so" (cobre CVT, N.A., "--", etc.)
    # e por fim o caso "Automática (A)" usado em alguns eletricos.
    m_transm = re.match(r'^([A-Za-z]+)\s*-\s*(\d+[A-Za-z]*)\s+', resto2)
    if m_transm:
        transmissao = f"{m_transm.group(1)}-{m_transm.group(2)}"
        resto2 = resto2[m_transm.end():].strip()
    else:
        m_transm2 = re.match(r'^(\S+(?:\s+\([^)]+\))?)\s+', resto2)
        if m_transm2:
            transmissao = m_transm2.group(1)
            resto2 = resto2[m_transm2.end():].strip()
        else:
            transmissao = ""

    tokens = resto2.split()
    if len(tokens) < 5:
        return None

    idx = 0
    ar_cond = tokens[idx] if idx < len(tokens) else ""
    idx += 1
    direcao = tokens[idx] if idx < len(tokens) else ""
    idx += 1
    combustivel_map = {"G": "Gasolina", "F": "Flex", "D": "Diesel", "E": "Elétrico"}
    combustivel_letra = tokens[idx] if idx < len(tokens) else ""
    combustivel = combustivel_map.get(combustivel_letra, combustivel_letra)
    idx += 1

    resto_numeros = tokens[idx:]

    pbe_class = None
    for i, t in enumerate(resto_numeros):
        if t in ("A", "B", "C", "D", "E") and i >= len(resto_numeros) - 5:
            pbe_class = t
            break

    decimais = [t for t in resto_numeros if re.match(r'^\d+[\.,]\d$', t)]
    decimais = [d.replace(",", ".") for d in decimais]

    km_l = {}
    if combustivel == "Flex" and len(decimais) >= 6:
        # Tabela 2026: cada combustivel tem 3 valores (cidade/estrada/combinado).
        # A extracao do PDF embaralha a ordem visual das colunas, entao
        # comparamos os dois blocos e usamos a fisica como criterio:
        # gasolina sempre rende mais km/l que etanol (menor densidade
        # energetica do etanol).
        bloco1 = [float(x) for x in decimais[0:3]]
        bloco2 = [float(x) for x in decimais[3:6]]
        if sum(bloco1) >= sum(bloco2):
            gasolina, etanol = bloco1, bloco2
        else:
            gasolina, etanol = bloco2, bloco1
        km_l = {
            "cidade_gasolina": gasolina[0], "estrada_gasolina": gasolina[1],
            "combinado_gasolina": gasolina[2],
            "cidade_etanol": etanol[0], "estrada_etanol": etanol[1],
            "combinado_etanol": etanol[2],
        }
    elif combustivel in ("Gasolina", "Diesel") and len(decimais) >= 3:
        km_l = {
            "cidade": float(decimais[0]), "estrada": float(decimais[1]),
            "combinado": float(decimais[2]),
        }
    elif combustivel == "Elétrico":
        # Eletricos nao usam km/l: usam km/l equivalente (autonomia por
        # "litro" de energia) e autonomia total em km. Esses valores tem
        # 2 casas decimais (ex: "58,59"), por isso usamos uma regex mais
        # ampla aqui em vez do padrao de 1 casa usado para combustao.
        decimais_amplo = [t for t in resto_numeros if re.match(r'^\d+[\.,]\d+$', t)]
        if len(decimais_amplo) >= 2:
            cidade_kwh = float(decimais_amplo[0].replace(",", "."))
            estrada_kwh = float(decimais_amplo[1].replace(",", "."))
            # autonomia = primeiro numero inteiro (sem vírgula) logo apos
            # a ultima casa decimal encontrada na linha
            ultimo_decimal_tok = decimais_amplo[-1]
            pos = len(resto_numeros) - 1 - resto_numeros[::-1].index(ultimo_decimal_tok)
            autonomia = None
            for t in resto_numeros[pos + 1:]:
                if re.match(r'^\d+$', t):
                    autonomia = int(t)
                    break
                if t not in ("\\",):
                    break
            km_l = {
                "cidade_kwh_eq": cidade_kwh, "estrada_kwh_eq": estrada_kwh,
                "autonomia_km": autonomia,
            }

    return {
        "categoria_pbe": categoria,
        "carroceria": CARROCERIA.get(categoria, categoria),
        "marca": formatar_marca(marca),
        "modelo": modelo.title() if modelo.isupper() else modelo,
        "versao": versao,
        "motor": motor,
        "tipo_propulsao": prop_tipo,
        "transmissao": transmissao,
        "tracao": None,  # nao disponivel na Tabela PBE; a preencher depois via outra fonte
        "ar_condicionado": ar_cond == "S",
        "combustivel": combustivel,
        "km_l": km_l,
        "classificacao_pbe": pbe_class,
    }


def extrair_veiculos(caminho_txt):
    registros = []
    with open(caminho_txt, encoding="utf-8") as f:
        for line in f:
            reg = parse_line(line)
            if reg:
                registros.append(reg)
    return registros


# ---------------------------------------------------------------------------
# 2) VALIDACAO: checa se os numeros extraidos fazem sentido fisico
# ---------------------------------------------------------------------------

def validar_veiculos(veiculos):
    problemas = []

    for v in veiculos:
        nome = f"{v['marca']} {v['modelo']} {v['versao']}".strip()
        kl = v["km_l"]
        if not kl:
            continue

        def num(chave):
            return float(kl[chave]) if kl.get(chave) not in (None, "") else None

        if "cidade_gasolina" in kl:
            cg, eg = num("cidade_gasolina"), num("estrada_gasolina")
            ce, ee = num("cidade_etanol"), num("estrada_etanol")

            if cg is not None and ce is not None and cg <= ce:
                problemas.append(f"{nome}: gasolina cidade ({cg}) <= etanol cidade ({ce})")
            if eg is not None and ee is not None and eg <= ee:
                problemas.append(f"{nome}: gasolina estrada ({eg}) <= etanol estrada ({ee})")
            # obs: nao comparamos cidade x estrada aqui porque em veiculos
            # hibridos e comum a cidade render mais km/l que a estrada
            # (frenagem regenerativa) - isso nao e um erro de extracao.

            for chave, val in [("cidade_gasolina", cg), ("estrada_gasolina", eg),
                                ("cidade_etanol", ce), ("estrada_etanol", ee)]:
                if val is not None and not (3 <= val <= 25):
                    problemas.append(f"{nome}: {chave}={val} fora da faixa plausivel (3-25 km/l)")

        elif "cidade" in kl:
            c, e = num("cidade"), num("estrada")
            for chave, val in [("cidade", c), ("estrada", e)]:
                if val is not None and not (3 <= val <= 25):
                    problemas.append(f"{nome}: {chave}={val} fora da faixa plausivel (3-25 km/l)")

    return problemas


# ---------------------------------------------------------------------------
# 3) GERACAO DO HTML: monta o catalogo com os cards
# ---------------------------------------------------------------------------

BADGE_COLORS = {
    "Hatch": ("#E6F1FB", "#0C447C"),
    "Sedã": ("#EAF3DE", "#27500A"),
    "Sedã/Hatch": ("#EAF3DE", "#27500A"),
    "Sedã/SUV": ("#FAEEDA", "#633806"),
    "SUV": ("#E1F5EE", "#085041"),
    "SUV 4x4": ("#E1F5EE", "#085041"),
    "SUV/Off-road": ("#FAECE7", "#4A1B0C"),
    "Minivan": ("#FBEAF0", "#4B1528"),
    "Comercial": ("#F1EFE8", "#2C2C2A"),
    "Picape": ("#F5EEDC", "#5C4108"),
    "Esportivo": ("#FBEAEA", "#7A1414"),
}

# Fotos reais por modelo, pegas direto do site das montadoras (frontal e
# lateral/geral). A chave e "Marca|Modelo" (como aparecem em veiculos.json).
# Modelos que ainda nao tem foto aqui caem no placeholder de texto.
#
# IMPORTANTE: essas URLs so carregam de verdade quando voce abre o
# catalogo_veiculos.html LOCALMENTE no navegador (com internet). A
# pre-visualizacao publicada no chat do Claude bloqueia imagens externas
# por seguranca.
#
# Para adicionar mais modelos: entre no site da montadora, ache a pagina
# do carro, clique com o botao direito numa foto > "Copiar endereco da
# imagem" e cole aqui no formato "Marca|Modelo": {"frontal": "...", "lateral": "..."}.
FOTOS_POR_MODELO = {
    "Fiat|Strada": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Fiat_Strada_1.4_Endurance_cabina_simple_2023.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Fiat_Strada_1.4_Trekking_2011_(15156340481).jpg",
    },
    "Chevrolet|Equinox": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2025_Chevrolet_Equinox_EV,_front_left_4.26.25.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2025_Chevrolet_Equinox_EV,_rear_4.26.25.jpg",
    },
    "Chevrolet|Captiva": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2025_Chevrolet_Captiva_1.5_Premier_in_white,_front_right.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2025_Chevrolet_Captiva_1.5_Premier_in_white,_rear_right.jpg",
    },
    "Chevrolet|Silverado": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Chevrolet_Silverado_ZR2_2023.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2020_Chevrolet_Silverado_1500_de_4_portes_au_SIAM_2020.jpg",
    },
    "Chevrolet|Sonic": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2019_Chevrolet_Sonic_RS_in_Summit_White,_front_left,_5-7-2022.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2019_Chevrolet_Sonic_RS_in_%22Shock%22,_rear_left.jpg",
    },
    "Chevrolet|Spark": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Chevrolet_Spark_Electric_UV_BEV_Electric_2026_(4).jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Chevrolet_Spark_Electric_UV_BEV_Electric_2026_(4).jpg",
    },
    "Chevrolet|Blazer": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2024_Chevrolet_Blazer_EV_RS_AWD_in_Summit_White,_front_left,_2024-03-31.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2024_Chevrolet_Blazer_EV_RS_in_Summit_White,_rear_left.jpg",
    },
    "Fiat|Cronos": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2021_Fiat_Cronos_1.8_16v_Precision_(front_view).jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2021_Fiat_Cronos_1.8_16v_Precision_(rear_view).jpg",
    },
    "Fiat|Fastback": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2023_Fiat_Fastback_(Colombia)_front_view.png",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2023_Fiat_Fastback_(Colombia)_front_view.png",
    },
    "Fiat|Pulse": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2022_Fiat_Pulse_Impetus_T200_(Brazil)_front_view.png",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2022_Fiat_Pulse_Impetus_T200_(Brazil)_rear_view.png",
    },
    "Fiat|Fiorino": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Fiat_Fiorino_2008_front.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Fiat_Fiorino_2008_rear.jpg",
    },
    "Fiat|Titano": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2026_Fiat_Titano_Ranch_in_Argentina.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Fiat_Titano_Ranch.jpg",
    },
    "Fiat|500E": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Fiat_500e_(front).jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Fiat_500e_(front).jpg",
    },
    "Fiat|Ducato": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2002_Fiat_Ducato_Dethleffs_Globetrotter_Esprit_Motorhome_in_Bianco_Banchisa,_Front_Right,_07-06-2022.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2002_Fiat_Ducato_Dethleffs_Globetrotter_Esprit_Motorhome_in_Bianco_Banchisa,_Front_Right,_07-06-2022.jpg",
    },
    "Fiat|Scudo": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Vans,_Chatham_-_16_January_2018_(01).jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Vans,_Chatham_-_16_January_2018_(01).jpg",
    },
    "Chevrolet|Onix": {
        "frontal": "https://www.chevrolet.com.br/content/dam/chevrolet/south-america/brazil/portuguese/index/visid/cars/onix/refresh/myr27/onix-active/onix-grade-frontal.jpg?imwidth=960",
        "lateral": "https://www.chevrolet.com.br/content/dam/chevrolet/south-america/brazil/portuguese/index/visid/cars/onix/refresh/versions/versoes-onix-turbo-at.jpg?imwidth=960",
    },
    "Volkswagen|Virtus": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/VW_Virtus_MSI_(Brazil,_front_view).png",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2023_Volkswagen_Virtus_Topline_front_20230520.jpg",
    },
    "Volkswagen|Nivus": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Volkswagen_Nivus_Highline_(Brazil)_front_view_01.png",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Volkswagen_Nivus_Highline_(Brazil)_front_view_03.png",
    },
    "Volkswagen|Tera": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2025_Volkswagen_Tera_1.0_High_(Colombia)_front_view.png",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2025_Volkswagen_Tera_1.0_High_(Colombia)_rear_view_02.png",
    },
    "Volkswagen|Taos": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2022_Volkswagen_Taos_S_in_Pure_White,_front_left.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2022_Volkswagen_Taos_SE,_rear.jpg",
    },
    "Hyundai|I20": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Hyundai_i20_1.6_T-GDI_N_(2022)_(52571777625).jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Hyundai_i20_1.6_T-GDI_N_(2022)_(52571777625).jpg",
    },
    "Hyundai|Kona": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Hyundai_Kona_2.0_Inspiration_SX2_Cyber_Gray_Metallic_(1).jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Hyundai_Kona_2.0_Inspiration_SX2_Cyber_Gray_Metallic_(4).jpg",
    },
    "Hyundai|Hb20S": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Hyundai_HB20S_(second_generation)_front_view.png",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Hyundai_HB20S_(second_generation)_front_view.png",
    },
    "Hyundai|Ioniq": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2023_Hyundai_Ioniq_5_Signature_Front.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2023_Hyundai_Ioniq_5_Signature_Front.jpg",
    },
    "Hyundai|Palisade": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2023_Hyundai_Palisade_Ultimate_Calligraphy_in_Typhoon_Silver,_front_right,_2024-03-31.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2023_Hyundai_Palisade_Ultimate_Calligraphy_in_Typhoon_Silver,_rear_right,_2024-03-31.jpg",
    },
    "Toyota|Rav4": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2019_Toyota_RAV4_LE_2.5L_front_4.14.19.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2019_Toyota_RAV4_LE_2.5L_front_4.14.19.jpg",
    },
    "Toyota|Yaris": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Toyota_Yaris_front.JPG",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Toyota_Yaris_sedan_(rear).JPG",
    },
    "Toyota|Hiace": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2020_Toyota_HiAce_(front).jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2020_Toyota_HiAce_(rear).jpg",
    },
    "Toyota|Sw4": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2021_Toyota_Fortuner_4.0_SRV_4x4_(Colombia)_front_view.png",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Toyota_Fortuner_LTD_4x2_20221019.jpg",
    },
    "Toyota|Gr": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Toyota_GR_YARIS_RZ_High_performance_(4BA-GXPA16-AGFGZ(H))_front.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2023_Toyota_GR_Corolla,_front_NYIAS_2022.jpg",
    },
    "Chevrolet|Tracker": {
        "frontal": "https://www.chevrolet.com.br/content/dam/chevrolet/south-america/brazil/portuguese/index/visid/crossovers-and-suvs/2026-tracker/refresh/mh/03-images/tracekr-mh-desk.jpeg?imwidth=960",
        "lateral": "https://www.chevrolet.com.br/content/dam/chevrolet/south-america/brazil/portuguese/index/visid/crossovers-and-suvs/2026-tracker/refresh/design/carrossel/carrossel04.jpg?imwidth=960",
    },
    "Chevrolet|Montana": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2023_Chevrolet_Montana_Premier_(Brazil)_front_view_02.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Chevrolet_Montana_Turbo_RS_2024_(53354238079).jpg",
    },
    "Chevrolet|Spin": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2025_Chevrolet_Spin_1.8_LT.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Chevrolet_Spin_1.8_Premier_2022.jpg",
    },
    "Chevrolet|S10": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2022_Chevrolet_S10_Max_Crew_Cab_2.4_4x2_(Mexico)_front_view.png",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2022_Chevrolet_S10_Max_Crew_Cab_2.4_4x2_(Mexico)_front_view.png",
    },
    "Chevrolet|Trailblazer": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2023_Chevrolet_Trailblazer_RS_AWD_in_Fountain_Blue,_Front_Right,_07-11-2023.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Chevrolet_TrailBlazer_001.jpg",
    },
    "Hyundai|Hb20": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2023_Hyundai_HB20_1.0_T-GDi_Platinum_Plus_(Brazil)_front_view.png",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2023_Hyundai_HB20_1.0_T-GDi_Platinum_Plus_(Brazil)_rear_view.png",
    },
    "Fiat|Argo": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Fiat_Argo_2020_Trekking_in_Uruguay_(front).jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Frente_Fiat_Argo_1.0_2022.jpg",
    },
    "Toyota|Corolla": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Toyota_Corolla_nova.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Lateral_Toyota_Corolla_Hybrid_CRI_10_2021_1613.jpg",
    },
    "Volkswagen|Polo": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2018_Volkswagen_Polo_1.6_MSi_Trendline_(Brazil,_front).jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2018_Volkswagen_Polo_1.6_MSi_Trendline_(Brazil,_rear).jpg",
    },
    "Volkswagen|Saveiro": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/VW_Saveiro_1.6_doble_cabina_2020_front_(cropped).jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Saveiro_G6_Trend.jpg",
    },
    "Fiat|Mobi": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Fiat_Mobi_Like_1.0_Fire_flex.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Fiat_Mobi_Like_1.0_Fire_flex.jpg",
    },
    "Jeep|Renegade": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Brazilian_Jeep_Renegade.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Jeep_Renegade.jpg",
    },
    "Fiat|Toro": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Fiat_Toro_Freedom_front.JPG",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Fiat_Toro_Volcano_front.jpg",
    },
    "Hyundai|Creta": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2021_Hyundai_Creta_2.0_Ultimate_(Brazil)_front_view.png",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2021_Hyundai_Creta_2.0_Ultimate_(Brazil)_rear_view.png",
    },
    "Jeep|Compass": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2021_Jeep_Compass_Limited_4WD_in_Billet_Silver_Metallic,_front_left.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2021_Jeep_Compass_Limited_4WD_in_Billet_Silver_Metallic,_rear_left.jpg",
    },
    "Toyota|Hilux": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Toyota_Hilux_4x4_V_Conquest_2019_(2023_Front_Fascia).jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Toyota_Hilux_4x4_V_Conquest_2019_(2023_Front_Fascia).jpg",
    },
    "Renault|Kwid": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Renault_Kwid_Outsider_(Brazil,_front).png",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2018_Renault_Kwid_1.0_SCe_Iconic_(Brazil),_frontal_view.jpg",
    },
    "Volkswagen|T": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Volkswagen_T-Cross_(2023)_1X7A2499.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Volkswagen_T-Cross_IMG_4873.jpg",
    },
    "Honda|Hr-V": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2022_Honda_HR-V_1.8_EX_(Brazil).jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2021_Honda_HR-V_Touring_in_Aegean_Blue_Metallic,_rear_left,_2024-05-27.jpg",
    },
    "Nissan|Kicks": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/2021_Nissan_Kicks_SV_(facelift),_front_11.6.21.jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/2021_Nissan_Kicks_SV_(facelift),_rear_11.6.21.jpg",
    },
    "Renault|Duster": {
        "frontal": "https://commons.wikimedia.org/wiki/Special:FilePath/Renault_Duster_(51734863448).jpg",
        "lateral": "https://commons.wikimedia.org/wiki/Special:FilePath/Renault_Duster_(front),_Denpasar.jpg",
    },
}


def obter_fotos(marca, modelo, bg):
    """Retorna (html_frontal, html_lateral) - <img> real se tivermos a URL
    cadastrada, ou uma caixa de placeholder caso contrario."""
    chave = f"{marca}|{modelo}"
    fotos = FOTOS_POR_MODELO.get(chave)
    if fotos:
        frontal = f'<img src="{fotos["frontal"]}" alt="{marca} {modelo} - frontal" loading="lazy">'
        lateral = f'<img src="{fotos["lateral"]}" alt="{marca} {modelo} - lateral" loading="lazy">'
    else:
        frontal = '<span>Foto frontal</span>'
        lateral = '<span>Foto lateral</span>'
    return frontal, lateral


# Faixa de preco na Tabela FIPE por MODELO (nao por versao exata - ver
# explicacao dada ao usuario). Chave "Marca|Modelo", valor (preco_min, preco_max)
# em reais, para o ano-modelo 2026. Fonte: agregadores de mercado (napista,
# carzin, webmotors) que replicam a Tabela FIPE oficial.
PRECO_FIPE_POR_MODELO = {
    "Chevrolet|Onix": (80436, 119412),
    "Chevrolet|Tracker": (108106, 155320),
    "Chevrolet|Montana": (122365, 138213),
    "Chevrolet|Spin": (103932, 136481),
    "Chevrolet|S10": (225244, 287044),
    "Chevrolet|Trailblazer": (351461, 351461),
    "Hyundai|Hb20": (80983, 109694),
    "Fiat|Argo": (76857, 99154),
    "Fiat|Mobi": (66577, 70780),
    "Fiat|Toro": (144821, 192592),
    "Toyota|Corolla": (152193, 186792),
    "Toyota|Hilux": (232501, 313282),
    "Volkswagen|Polo": (80525, 110562),
    "Volkswagen|Saveiro": (87355, 114810),
    "Volkswagen|T": (110156, 164921),
    "Jeep|Renegade": (111453, 163457),
    "Jeep|Compass": (142306, 240879),
    "Hyundai|Creta": (112280, 173070),
    "Renault|Kwid": (63397, 69554),
    "Renault|Duster": (108372, 123162),
    "Honda|Hr-V": (150474, 186757),
    "Nissan|Kicks": (141755, 170262),
}


def obter_faixa_fipe(marca, modelo):
    """Retorna string formatada com a faixa de preco FIPE do modelo, ou
    None se nao tivermos o dado cadastrado para esse modelo."""
    faixa = PRECO_FIPE_POR_MODELO.get(f"{marca}|{modelo}")
    if not faixa:
        return None
    minimo, maximo = faixa
    if minimo == maximo:
        return f"R$ {minimo:,.0f}".replace(",", ".")
    return f"R$ {minimo:,.0f} a R$ {maximo:,.0f}".replace(",", ".")


# Depreciacao media anual por MODELO (nao por versao - mesma limitacao ja
# explicada para o preco FIPE). Calculada como: (preco medio 2026 - preco
# medio 2022) / preco medio 2026 / 4 anos, usando a faixa de preco anual
# da Tabela FIPE de cada modelo (fonte: tabelafipebrasil.com / webmotors).
# Valor em fracao (0.0694 = 6.94% ao ano).
DEPRECIACAO_POR_MODELO = {
    "Chevrolet|Onix": 0.0694,
    "Hyundai|Hb20": 0.0632,
    "Fiat|Argo": 0.0645,
    "Fiat|Mobi": 0.0569,
}


def obter_depreciacao(marca, modelo):
    """Retorna string formatada com a depreciacao media anual do modelo,
    ou None se nao tivermos o dado cadastrado para esse modelo."""
    dep = DEPRECIACAO_POR_MODELO.get(f"{marca}|{modelo}")
    if dep is None:
        return None
    return f"{dep * 100:.1f}% ao ano".replace(".", ",")


def fmt_km(v):
    kl = v["km_l"]
    if "cidade_gasolina" in kl:
        return (f'{kl["combinado_gasolina"]:.1f} km/l (gasolina) — '
                f'{kl["cidade_gasolina"]:.1f} cidade / {kl["estrada_gasolina"]:.1f} estrada<br>'
                f'{kl["combinado_etanol"]:.1f} km/l (etanol) — '
                f'{kl["cidade_etanol"]:.1f} cidade / {kl["estrada_etanol"]:.1f} estrada')
    elif "cidade" in kl:
        return f'{kl["combinado"]:.1f} km/l — {kl["cidade"]:.1f} cidade / {kl["estrada"]:.1f} estrada'
    elif "cidade_kwh_eq" in kl:
        autonomia = f' — Autonomia: {kl["autonomia_km"]} km' if kl.get("autonomia_km") else ""
        return (f'{kl["cidade_kwh_eq"]:.1f} / {kl["estrada_kwh_eq"]:.1f} km/l equiv. '
                f'(cidade/estrada){autonomia}')
    return "-"


def dados_consumo_calculadora(v):
    """Extrai os valores de consumo combinado no formato que a calculadora
    de custo precisa: (consumo_gasolina, consumo_etanol, consumo_unico_flex_ou_nao,
    consumo_kwh_equivalente). Campos nao aplicaveis ficam como string vazia."""
    kl = v["km_l"]
    if "combinado_gasolina" in kl:
        return kl["combinado_gasolina"], kl["combinado_etanol"], "", ""
    elif "combinado" in kl:
        return "", "", kl["combinado"], ""
    elif "cidade_kwh_eq" in kl:
        media = round((kl["cidade_kwh_eq"] + kl["estrada_kwh_eq"]) / 2, 1)
        return "", "", "", media
    return "", "", "", ""


def gerar_html(veiculos, caminho_saida):
    veiculos = [v for v in veiculos if v["km_l"] and v["modelo"]]
    marcas = sorted(set(v["marca"] for v in veiculos))
    modelos_unicos = sorted(set((v["marca"], v["modelo"]) for v in veiculos))

    cards_html = []
    for v in veiculos:
        bg, fg = BADGE_COLORS.get(v["carroceria"], ("#F1EFE8", "#2C2C2A"))
        frontal, lateral = obter_fotos(v["marca"], v["modelo"], bg)
        faixa_fipe = obter_faixa_fipe(v["marca"], v["modelo"])
        depreciacao = obter_depreciacao(v["marca"], v["modelo"])
        preco_faixa = PRECO_FIPE_POR_MODELO.get(f"{v['marca']}|{v['modelo']}")
        preco_min = preco_faixa[0] if preco_faixa else None
        preco_estimado = round((preco_faixa[0] + preco_faixa[1]) / 2) if preco_faixa else ""
        cons_gas, cons_etanol, cons_unico, cons_kwh = dados_consumo_calculadora(v)
        versao = v["versao"].strip()
        titulo = f'{v["marca"]} {v["modelo"]}'
        subtitulo = versao if versao else v["motor"]
        nome_completo_calc = f"{titulo} {versao}".strip()
        cards_html.append(f'''
    <div class="card" data-marca="{v['marca']}" data-modelo="{v['marca']}|{v['modelo']}" data-preco-min="{preco_min if preco_min is not None else ''}">
      <div class="imgs">
        <div class="imgph">{frontal}</div>
        <div class="imgph">{lateral}</div>
      </div>
      <div class="row-top">
        <p class="titulo">{titulo}</p>
        <span class="badge" style="background:{bg};color:{fg}">{v['carroceria']}</span>
      </div>
      <p class="subtitulo">{subtitulo}</p>
      <div class="grid-info">
        <div><p class="label">Motor</p><p class="valor">{v['motor'] or '-'}</p></div>
        <div><p class="label">Câmbio</p><p class="valor">{v['transmissao'] or '-'}</p></div>
        <div><p class="label">Combustível</p><p class="valor">{v['combustivel']}</p></div>
        <div><p class="label">Classificação PBE</p><p class="valor">{v['classificacao_pbe'] or '-'}</p></div>
      </div>
      <div class="consumo">
        <p class="label">Consumo (combinado)</p>
        <p class="valor">{fmt_km(v)}</p>
      </div>
      <div class="footer">
        <div><p class="label">Tabela FIPE (por modelo)</p><p class="valor{" muted" if not faixa_fipe else ""}">{faixa_fipe or "em breve"}</p></div>
        <div><p class="label">Depreciação média/ano</p><p class="valor{" muted" if not depreciacao else ""}">{depreciacao or "em breve"}</p></div>
        <div><p class="label">Preço médio</p><p class="valor muted">em breve</p></div>
      </div>
      <button class="calc-btn" onclick="abrirCalculadora(this)"
        data-nome="{nome_completo_calc}"
        data-preco="{preco_estimado}"
        data-combustivel="{v['combustivel']}"
        data-cons-gas="{cons_gas}"
        data-cons-etanol="{cons_etanol}"
        data-cons-unico="{cons_unico}"
        data-cons-kwh="{cons_kwh}">🧮 Calcular custo estimado</button>
    </div>''')

    options_html = "".join(f'<option value="{m}">{m}</option>' for m in marcas)
    options_modelo_html = "".join(
        f'<option value="{m}|{mo}">{m} {mo}</option>' for m, mo in modelos_unicos
    )

    html = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Catálogo de veículos</title>
<link rel="manifest" href="manifest.json">
<link rel="icon" href="icon-192.png">
<link rel="apple-touch-icon" href="icon-192.png">
<meta name="theme-color" content="#3B82F6">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Carros">
<style>
:root {{
  --surface-0: #f4f3ef;
  --surface-1: #ffffff;
  --surface-2: #ffffff;
  --text-primary: #1c1c1a;
  --text-secondary: #5f5e5a;
  --text-muted: #8a8880;
  --border: #e2e0d8;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --surface-0: #171715;
    --surface-1: #232320;
    --surface-2: #232320;
    --text-primary: #f1efe8;
    --text-secondary: #b4b2a9;
    --text-muted: #888780;
    --border: #38372f;
  }}
}}
:root[data-theme="dark"] {{
  --surface-0: #171715;
  --surface-1: #232320;
  --surface-2: #232320;
  --text-primary: #f1efe8;
  --text-secondary: #b4b2a9;
  --text-muted: #888780;
  --border: #38372f;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 24px; background: var(--surface-0);
  font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
  color: var(--text-primary);
}}
h1 {{ font-size: 20px; font-weight: 500; margin: 0 0 4px; }}
p.intro {{ color: var(--text-secondary); font-size: 14px; margin: 0 0 16px; }}
.filtros {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 8px; }}
select {{
  height: 36px; border-radius: 8px; border: 0.5px solid var(--border);
  background: var(--surface-1); color: var(--text-primary); padding: 0 10px;
  font-size: 14px; max-width: 260px;
}}
p.aviso-preco {{ color: var(--text-muted); font-size: 12px; margin: 0 0 20px; }}
.grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px; max-width: 1200px; margin: 0 auto;
}}
.card {{
  background: var(--surface-2); border: 0.5px solid var(--border);
  border-radius: 12px; padding: 16px 20px;
}}
.imgs {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }}
.imgph {{
  background: var(--surface-0); border-radius: 8px; height: 90px;
  display: flex; align-items: center; justify-content: center;
  overflow: hidden;
}}
.imgph img {{ width: 100%; height: 100%; object-fit: cover; }}
.imgph span {{ font-size: 11px; color: var(--text-muted); }}
.row-top {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 2px; }}
.titulo {{ font-weight: 500; font-size: 16px; margin: 0; }}
.badge {{ font-size: 12px; padding: 3px 10px; border-radius: 8px; white-space: nowrap; }}
.subtitulo {{ font-size: 13px; color: var(--text-secondary); margin: 0 0 12px; }}
.grid-info {{
  border-top: 0.5px solid var(--border); padding-top: 10px;
  display: grid; grid-template-columns: 1fr 1fr; gap: 8px 12px; font-size: 13px;
}}
.label {{ color: var(--text-muted); margin: 0 0 2px; font-size: 12px; }}
.valor {{ margin: 0; font-weight: 500; }}
.valor.muted {{ font-weight: 400; color: var(--text-muted); }}
.consumo {{ border-top: 0.5px solid var(--border); margin-top: 10px; padding-top: 10px; font-size: 13px; }}
.footer {{
  border-top: 0.5px solid var(--border); margin-top: 10px; padding-top: 10px;
  display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 8px; font-size: 13px;
}}
.calc-btn {{
  width: 100%; margin-top: 12px; height: 36px; border-radius: 8px;
  border: 0.5px solid var(--border); background: var(--surface-0);
  color: var(--text-primary); font-size: 13px; font-weight: 500; cursor: pointer;
}}
.calc-btn:hover {{ background: var(--border); }}
.calculadora-painel {{
  max-width: 720px; margin: 40px auto 0; padding: 20px 24px 28px;
  background: var(--surface-2); border: 0.5px solid var(--border); border-radius: 12px;
}}
.calculadora-painel h2 {{ font-size: 17px; font-weight: 500; margin: 0 0 8px; }}
.calc-veiculo {{ font-size: 14px; font-weight: 500; margin: 0 0 8px; }}
.calc-aviso {{ font-size: 12px; color: var(--text-muted); margin: 0 0 16px; line-height: 1.5; }}
.calc-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px 16px; margin-bottom: 12px;
}}
.calc-grid label {{ display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--text-secondary); }}
.calc-grid input, .calc-grid select {{
  height: 36px; border-radius: 8px; border: 0.5px solid var(--border);
  background: var(--surface-1); color: var(--text-primary); padding: 0 10px; font-size: 14px;
}}
.calc-checkbox {{ display: flex; align-items: center; gap: 8px; font-size: 13px; margin-bottom: 4px; }}
.calc-financiamento {{ margin-top: 8px; }}
.calc-botoes {{ display: flex; gap: 10px; margin-top: 8px; }}
.calc-botao-principal, .calc-botao-secundario {{
  height: 40px; border-radius: 8px; font-size: 14px; font-weight: 500; cursor: pointer; padding: 0 18px;
}}
.calc-botao-principal {{ background: var(--text-primary); color: var(--surface-0); border: none; }}
.calc-botao-secundario {{ background: transparent; color: var(--text-secondary); border: 0.5px solid var(--border); }}
.calc-resultado {{ margin-top: 20px; }}
.calc-resultado h3 {{ font-size: 15px; font-weight: 500; margin: 0 0 10px; }}
.calc-linhas {{ display: flex; flex-direction: column; gap: 6px; }}
.calc-linha {{
  display: flex; justify-content: space-between; font-size: 14px;
  padding-bottom: 6px; border-bottom: 0.5px solid var(--border);
}}
.calc-linha.calc-total {{ font-weight: 600; font-size: 15px; border-bottom: none; margin-top: 4px; }}
.calc-erro {{ color: #B3261E; font-size: 13px; }}
</style>
</head>
<body>
<h1>Catálogo de veículos</h1>
<p class="intro">Dados de consumo e eficiência energética da Tabela PBE Veicular (Inmetro). Fotos e preço FIPE disponíveis para os modelos mais comuns; os demais seguem sendo adicionados aos poucos.</p>
<div class="filtros">
  <select id="filtro-marca" onchange="filtrar()">
    <option value="">Todas as marcas</option>
    {options_html}
  </select>
  <select id="filtro-modelo" onchange="filtrar()">
    <option value="">Todos os modelos</option>
    {options_modelo_html}
  </select>
  <select id="filtro-preco" onchange="filtrar()">
    <option value="">Todas as faixas de preço</option>
    <option value="0-50000">Até R$ 50 mil</option>
    <option value="50000-100000">R$ 50 mil a R$ 100 mil</option>
    <option value="100000-150000">R$ 100 mil a R$ 150 mil</option>
    <option value="150000-200000">R$ 150 mil a R$ 200 mil</option>
    <option value="200000-999999999">Acima de R$ 200 mil</option>
  </select>
</div>
<p class="aviso-preco">A faixa de preço só filtra os veículos que já têm Tabela FIPE cadastrada (veja o rodapé de cada card); os demais ficam ocultos quando esse filtro está ativo.</p>
<div class="grid" id="grid">
{"".join(cards_html)}
</div>

<div class="calculadora-painel" id="calculadora">
  <h2>🧮 Calculadora de custo estimado</h2>
  <p class="calc-veiculo" id="calc-veiculo">Clique em "Calcular custo estimado" em algum veículo do catálogo acima.</p>
  <p class="calc-aviso">Inspirada na metodologia da calculadora de custo de veículo do CalculaBrasil. Os valores abaixo já vêm preenchidos com o que sabemos do veículo — ajuste o que fizer sentido pra sua realidade (preço pago, km rodados, seguro, estado etc.) antes de calcular.</p>
  <div class="calc-grid">
    <label>Valor do veículo (FIPE) R$
      <input type="number" id="calc-preco" step="100" placeholder="Ex: 95000">
    </label>
    <label>Ano do veículo
      <input type="number" id="calc-ano" value="2026">
    </label>
    <label>Combustível
      <select id="calc-combustivel" onchange="atualizarConsumoPadrao()">
        <option value="Gasolina">Gasolina</option>
        <option value="Etanol">Etanol</option>
        <option value="Diesel">Diesel</option>
        <option value="Elétrico">Elétrico</option>
      </select>
    </label>
    <label>Km rodados por mês
      <input type="number" id="calc-km" value="1200" step="50">
    </label>
    <label>Consumo médio (km/l, ou km/kWh se elétrico)
      <input type="number" id="calc-consumo" step="0.1" placeholder="Ex: 13.5">
    </label>
    <label>Preço do combustível (R$/l, ou R$/kWh se elétrico)
      <input type="number" id="calc-preco-combustivel" step="0.01" value="6.19">
    </label>
    <label>Seguro anual (R$)
      <input type="number" id="calc-seguro" step="50" placeholder="Ex: 4500">
    </label>
    <label>Estado (IPVA)
      <select id="calc-estado"></select>
    </label>
    <label>Estacionamento mensal (R$)
      <input type="number" id="calc-estacionamento" value="0" step="10">
    </label>
  </div>
  <label class="calc-checkbox">
    <input type="checkbox" id="calc-tem-financiamento" onchange="alternarFinanciamento()">
    Tem financiamento?
  </label>
  <div class="calc-grid calc-financiamento" id="calc-financiamento-campos" style="display:none">
    <label>Entrada (R$)
      <input type="number" id="calc-entrada" value="0" step="500">
    </label>
    <label>Taxa de juros (% ao mês)
      <input type="number" id="calc-juros" value="1.5" step="0.1">
    </label>
    <label>Prazo (meses)
      <input type="number" id="calc-prazo" value="48" step="1">
    </label>
  </div>
  <div class="calc-botoes">
    <button class="calc-botao-principal" onclick="calcularCusto()">Calcular custo real</button>
    <button class="calc-botao-secundario" onclick="limparCalculadora()">Limpar</button>
  </div>
  <div class="calc-resultado" id="calc-resultado"></div>
</div>
<script>
function filtrar() {{
  const marca = document.getElementById('filtro-marca').value;
  const modelo = document.getElementById('filtro-modelo').value;
  const preco = document.getElementById('filtro-preco').value;
  let precoMin = null, precoMax = null;
  if (preco) {{
    const partes = preco.split('-');
    precoMin = parseInt(partes[0], 10);
    precoMax = parseInt(partes[1], 10);
  }}
  document.querySelectorAll('.card').forEach(c => {{
    let ok = true;
    if (marca && c.dataset.marca !== marca) ok = false;
    if (modelo && c.dataset.modelo !== modelo) ok = false;
    if (preco) {{
      const p = c.dataset.precoMin ? parseInt(c.dataset.precoMin, 10) : null;
      if (p === null || p < precoMin || p > precoMax) ok = false;
    }}
    c.style.display = ok ? '' : 'none';
  }});
}}

// Aliquotas de IPVA por estado (automoveis de passeio) - valores de referencia,
// confira sempre o valor oficial do seu estado antes de decidir algo.
const IPVA_POR_ESTADO = {{
  AC: 0.02, AL: 0.03, AM: 0.03, AP: 0.03, BA: 0.025, CE: 0.03, DF: 0.035,
  ES: 0.02, GO: 0.0375, MA: 0.03, MG: 0.04, MS: 0.035, MT: 0.03, PA: 0.025,
  PB: 0.025, PE: 0.03, PI: 0.025, PR: 0.035, RJ: 0.04, RN: 0.03, RO: 0.03,
  RR: 0.025, RS: 0.03, SC: 0.02, SE: 0.03, SP: 0.04, TO: 0.03,
}};
const NOMES_ESTADO = {{
  AC: "Acre", AL: "Alagoas", AM: "Amazonas", AP: "Amapá", BA: "Bahia",
  CE: "Ceará", DF: "Distrito Federal", ES: "Espírito Santo", GO: "Goiás",
  MA: "Maranhão", MG: "Minas Gerais", MS: "Mato Grosso do Sul", MT: "Mato Grosso",
  PA: "Pará", PB: "Paraíba", PE: "Pernambuco", PI: "Piauí", PR: "Paraná",
  RJ: "Rio de Janeiro", RN: "Rio Grande do Norte", RO: "Rondônia", RR: "Roraima",
  RS: "Rio Grande do Sul", SC: "Santa Catarina", SE: "Sergipe", SP: "São Paulo",
  TO: "Tocantins",
}};

(function preencherEstados() {{
  const sel = document.getElementById('calc-estado');
  Object.keys(NOMES_ESTADO).sort((a, b) => NOMES_ESTADO[a].localeCompare(NOMES_ESTADO[b])).forEach(uf => {{
    const opt = document.createElement('option');
    opt.value = uf;
    opt.textContent = `${{uf}} — ${{NOMES_ESTADO[uf]}}`;
    if (uf === 'SP') opt.selected = true;
    sel.appendChild(opt);
  }});
}})();

const PRECO_COMBUSTIVEL_PADRAO = {{ Gasolina: 6.19, Etanol: 4.29, Diesel: 6.59, "Elétrico": 0.85 }};

function atualizarConsumoPadrao() {{
  const combustivel = document.getElementById('calc-combustivel').value;
  document.getElementById('calc-preco-combustivel').value = PRECO_COMBUSTIVEL_PADRAO[combustivel];
  const btn = window.__ultimoVeiculoBtn;
  if (!btn) return;
  const ds = btn.dataset;
  let consumo = '';
  if (combustivel === 'Gasolina' && ds.consGas) consumo = ds.consGas;
  else if (combustivel === 'Etanol' && ds.consEtanol) consumo = ds.consEtanol;
  else if (combustivel === 'Diesel' && ds.consUnico) consumo = ds.consUnico;
  else if (combustivel === 'Elétrico' && ds.consKwh) consumo = ds.consKwh;
  else if (ds.consUnico) consumo = ds.consUnico;
  if (consumo) document.getElementById('calc-consumo').value = consumo;
}}

function abrirCalculadora(btn) {{
  window.__ultimoVeiculoBtn = btn;
  const ds = btn.dataset;
  document.getElementById('calc-veiculo').textContent = 'Calculando para: ' + ds.nome;
  if (ds.preco) document.getElementById('calc-preco').value = ds.preco;
  if (ds.preco) document.getElementById('calc-seguro').value = Math.round(ds.preco * 0.06);

  let combustivelSelecionado = ds.combustivel;
  if (combustivelSelecionado === 'Flex') combustivelSelecionado = 'Gasolina';
  const selCombustivel = document.getElementById('calc-combustivel');
  if ([...selCombustivel.options].some(o => o.value === combustivelSelecionado)) {{
    selCombustivel.value = combustivelSelecionado;
  }}
  atualizarConsumoPadrao();
  document.getElementById('calc-resultado').innerHTML = '';
  document.getElementById('calculadora').scrollIntoView({{ behavior: 'smooth', block: 'start' }});
}}

function alternarFinanciamento() {{
  const marcado = document.getElementById('calc-tem-financiamento').checked;
  document.getElementById('calc-financiamento-campos').style.display = marcado ? 'grid' : 'none';
}}

function limparCalculadora() {{
  ['calc-preco', 'calc-km', 'calc-consumo', 'calc-seguro', 'calc-estacionamento'].forEach(id => {{
    document.getElementById(id).value = '';
  }});
  document.getElementById('calc-km').value = 1200;
  document.getElementById('calc-estacionamento').value = 0;
  document.getElementById('calc-ano').value = 2026;
  document.getElementById('calc-tem-financiamento').checked = false;
  alternarFinanciamento();
  document.getElementById('calc-resultado').innerHTML = '';
}}

function fmtReais(v) {{
  return 'R$ ' + v.toLocaleString('pt-BR', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
}}

function calcularCusto() {{
  const preco = parseFloat(document.getElementById('calc-preco').value) || 0;
  const ano = parseInt(document.getElementById('calc-ano').value, 10) || 2026;
  const combustivel = document.getElementById('calc-combustivel').value;
  const km = parseFloat(document.getElementById('calc-km').value) || 0;
  const consumo = parseFloat(document.getElementById('calc-consumo').value) || 0;
  const precoCombustivel = parseFloat(document.getElementById('calc-preco-combustivel').value) || 0;
  const seguroAnual = parseFloat(document.getElementById('calc-seguro').value) || 0;
  const estado = document.getElementById('calc-estado').value;
  const estacionamento = parseFloat(document.getElementById('calc-estacionamento').value) || 0;

  if (!preco) {{
    document.getElementById('calc-resultado').innerHTML =
      '<p class="calc-erro">Informe ao menos o valor do veículo (FIPE) pra calcular.</p>';
    return;
  }}

  const anoAtual = 2026;
  const idade = Math.max(0, anoAtual - ano);
  let taxaDepreciacao;
  if (idade === 0) taxaDepreciacao = 0.15;
  else if (idade <= 2) taxaDepreciacao = 0.11;
  else if (idade <= 4) taxaDepreciacao = 0.09;
  else taxaDepreciacao = 0.06;
  const depreciacaoMensal = (preco * taxaDepreciacao) / 12;

  const aliquotaIpva = combustivel === 'Elétrico' ? 0 : (IPVA_POR_ESTADO[estado] || 0.03);
  const ipvaMensal = (preco * aliquotaIpva) / 12;

  const seguroMensal = seguroAnual / 12;

  const combustivelMensal = consumo > 0 ? (km / consumo) * precoCombustivel : 0;

  let taxaManutencao;
  if (idade <= 3) taxaManutencao = 0.005;
  else if (idade <= 5) taxaManutencao = 0.009;
  else if (idade <= 8) taxaManutencao = 0.014;
  else taxaManutencao = 0.02;
  if (combustivel === 'Elétrico') taxaManutencao *= 0.5;
  const manutencaoMensal = (preco * taxaManutencao) / 12;

  const licenciamentoMensal = 30;

  let parcelaFinanciamento = 0;
  let temFinanciamento = document.getElementById('calc-tem-financiamento').checked;
  if (temFinanciamento) {{
    const entrada = parseFloat(document.getElementById('calc-entrada').value) || 0;
    const jurosMes = (parseFloat(document.getElementById('calc-juros').value) || 0) / 100;
    const prazo = parseInt(document.getElementById('calc-prazo').value, 10) || 0;
    const valorFinanciado = Math.max(0, preco - entrada);
    if (valorFinanciado > 0 && jurosMes > 0 && prazo > 0) {{
      parcelaFinanciamento = valorFinanciado * jurosMes / (1 - Math.pow(1 + jurosMes, -prazo));
    }} else if (valorFinanciado > 0 && prazo > 0) {{
      parcelaFinanciamento = valorFinanciado / prazo;
    }}
  }}

  const totalMensal = depreciacaoMensal + ipvaMensal + seguroMensal + combustivelMensal +
    manutencaoMensal + licenciamentoMensal + estacionamento + parcelaFinanciamento;
  const custoPorKm = km > 0 ? totalMensal / km : 0;

  const linhas = [
    ['Depreciação estimada', depreciacaoMensal],
    ['IPVA', ipvaMensal],
    ['Seguro', seguroMensal],
    [combustivel === 'Elétrico' ? 'Energia' : 'Combustível', combustivelMensal],
    ['Manutenção estimada', manutencaoMensal],
    ['Licenciamento', licenciamentoMensal],
    ['Estacionamento', estacionamento],
  ];
  if (temFinanciamento) linhas.push(['Parcela do financiamento', parcelaFinanciamento]);

  let html = '<h3>Custo mensal estimado</h3><div class="calc-linhas">';
  linhas.forEach(([label, valor]) => {{
    html += `<div class="calc-linha"><span>${{label}}</span><span>${{fmtReais(valor)}}</span></div>`;
  }});
  html += `<div class="calc-linha calc-total"><span>Total por mês</span><span>${{fmtReais(totalMensal)}}</span></div>`;
  html += `<div class="calc-linha calc-total"><span>Custo por km rodado</span><span>${{fmtReais(custoPorKm)}}</span></div>`;
  html += '</div>';
  html += '<p class="calc-aviso">Estimativa educativa — inspirada na metodologia do CalculaBrasil, com taxas médias de depreciação, manutenção e IPVA. Os valores reais dependem de cotações de seguro, manutenção específica do modelo e negociação do financiamento. Não substitui uma simulação com seguradora, banco ou concessionária.</p>';
  document.getElementById('calc-resultado').innerHTML = html;
}}
if ('serviceWorker' in navigator) {{
  window.addEventListener('load', () => {{
    navigator.serviceWorker.register('sw.js').catch(() => {{}});
  }});
}}
</script>
</body>
</html>'''

    with open(caminho_saida, "w", encoding="utf-8") as f:
        f.write(html)

    return len(veiculos)


# ---------------------------------------------------------------------------
# MAIN: roda os 3 passos em sequencia
# ---------------------------------------------------------------------------

def main():
    print("1) Lendo e organizando os dados da Tabela PBE...")
    veiculos = extrair_veiculos(CAMINHO_DADOS_BRUTOS)
    print(f"   -> {len(veiculos)} registros extraidos")

    with open(CAMINHO_JSON, "w", encoding="utf-8") as f:
        json.dump(veiculos, f, ensure_ascii=False, indent=2)

    print("\n2) Validando os dados...")
    problemas = validar_veiculos(veiculos)
    if problemas:
        print(f"   -> {len(problemas)} problema(s) encontrado(s):")
        for p in problemas:
            print("      -", p)
    else:
        print("   -> nenhum problema encontrado")

    print("\n3) Gerando o catalogo em HTML...")
    total = gerar_html(veiculos, CAMINHO_HTML)
    print(f"   -> index.html criado com {total} veiculos")

    print("\n4) Copiando arquivos do PWA (manifest, service worker, icones)...")
    pasta_pwa = os.path.join(PASTA_BASE, "pwa")
    for nome_arquivo in ("manifest.json", "sw.js", "icon-192.png", "icon-512.png"):
        origem = os.path.join(pasta_pwa, nome_arquivo)
        destino = os.path.join(PASTA_BASE, nome_arquivo)
        if os.path.exists(origem):
            with open(origem, "rb") as f_in, open(destino, "wb") as f_out:
                f_out.write(f_in.read())
    print("   -> pronto")

    print(f"\nPronto! Abra o arquivo {CAMINHO_HTML} no navegador.")


if __name__ == "__main__":
    main()
