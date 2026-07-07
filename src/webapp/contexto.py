"""
Objetos compartilhados entre main.py e as rotas (webapp/rotas/*), separados
num modulo proprio so para evitar import circular (main.py importa as rotas,
as rotas precisam do objeto `templates`).
"""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

from estilo_painel import CSS

RAIZ_WEBAPP = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(RAIZ_WEBAPP / "templates"))
# CSS disponivel em todos os templates (base.html) sem cada rota precisar
# passar no contexto - mesma folha de estilo usada por report_generator.py.
templates.env.globals["css"] = CSS
