# Atualizador de VGV

Starter Streamlit para analise de arquivos Excel, com foco em:

- analise temporal e espacial em pagina unica (nativa)
- filtros, KPIs e series mensais
- calculo e exportacao de reajuste INCC-DI
- padrao visual Brain (tokens e CSS centralizados)
- comparacao entre experiencia nativa e POC React

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
  5_React_POC.py
src/
  theme.py
  io_excel.py
  analytics.py
  vgv_core.py
  react_component.py
frontend/
  react_workspace/index.html
.streamlit/config.toml
```

## Convencoes

- Ajustes de estilo: `src/theme.py`
- Leitura e mapeamento do Excel: `src/io_excel.py`
- Regras de KPI e qualidade: `src/analytics.py`
