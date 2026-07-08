"""
Objetos compartilhados entre main.py e as rotas (webapp/rotas/*), separados
num modulo proprio so para evitar import circular (main.py importa as rotas,
as rotas precisam do objeto `templates`).
"""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from estilo_painel import CSS

RAIZ_WEBAPP = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(RAIZ_WEBAPP / "templates"))
# CSS disponivel em todos os templates (base.html) sem cada rota precisar
# passar no contexto - mesma folha de estilo usada por report_generator.py.
# Markup() marca como "seguro" para o autoescape do Jinja2 (ligado por
# padrao para templates .html) nao converter aspas do proprio CSS (ex:
# font-family: "Segoe UI", content: "") em &#34; - CSS estatico definido no
# codigo, nunca input de usuario, entao nao ha risco de XSS em marcar assim.
templates.env.globals["css"] = Markup(CSS)
