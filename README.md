# Atualizador de VGV

Starter Streamlit para analise de arquivos Excel, com foco em:

- upload e mapeamento de colunas
- KPIs e visualizacao de dados
- qualidade e exportacao de dados tratados
- padrao visual Brain (tokens e CSS centralizados)

## Rodar localmente

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Estrutura

```text
app.py
pages/
  1_Upload.py
  2_Analises.py
  3_Qualidade.py
src/
  theme.py
  io_excel.py
  analytics.py
.streamlit/config.toml
```

## Convencoes

- Ajustes de estilo: `src/theme.py`
- Leitura e mapeamento do Excel: `src/io_excel.py`
- Regras de KPI e qualidade: `src/analytics.py`
