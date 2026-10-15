import io
import os

import requests
import pandas as pd
from openai import OpenAI

# Realizar la consulta GET para obtener datos de entrenamiento
request = requests.get("https://rapps.ine.cl:9292/get_training_data?classification=ciuo")

# Obtener datos
datos = request.json()

# Convertir a DataFrames
train = pd.DataFrame(datos['train'])

test = pd.DataFrame(datos['test'])


OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_API_BASE_URL = "https://openrouter.ai/api/v1"


client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE_URL)

# Serializar train como CSV y armar el prompt
table = train.sample(n=10_000, random_state=42).to_csv(index=False)
MODEL = "anthropic/claude-haiku-5.5"
prompt = f"format all of the following table in markdown: {table}\nDon't add anything else"

response = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": prompt}],
    temperature=0,
)
markdown = response.choices[0].message.content


def markdown_to_df(md: str) -> pd.DataFrame:
    """Parsea una tabla markdown (ignorando code fences u otro texto) a un DataFrame de strings."""
    lines = [line.strip() for line in md.strip().splitlines() if line.strip().startswith("|")]
    rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in lines]
    header, body = rows[0], rows[1:]
    # Eliminar la fila separadora (|---|:---:|...)
    body = [r for r in body if not all(c and set(c) <= set(":-") for c in r)]
    return pd.DataFrame(body, columns=header)


parsed = markdown_to_df(markdown)

# Comparar contra train tal como fue enviado (todo como string, NaN -> "")
expected = pd.read_csv(io.StringIO(table), dtype=str, keep_default_na=False)

merge_left = parsed.merge(expected, how="left", indicator=True)["_merge"]
is_subset = merge_left.eq('both').all()
distrib_merge = merge_left.value_counts()[:2]


if parsed.equals(expected):
    print("OK: la tabla markdown es idéntica a train")
else:
    print('Son iguales las tablas?')
    print("DIFERENTE")
    print(f"shape esperado: {expected.shape}, shape parseado: {parsed.shape}")
    print(f'Dataframe generado es subset de dataframe original? {is_subset}')
    if not is_subset:
        print(f'Distribución merge:\n{distrib_merge}')
    if list(parsed.columns) != list(expected.columns):
        print(f"columnas esperadas: {list(expected.columns)}")
        print(f"columnas parseadas: {list(parsed.columns)}")
    elif parsed.shape == expected.shape:
        print(expected.compare(parsed))


