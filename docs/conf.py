# SPDX-License-Identifier: MIT

project = "CrystalSweep"
author = "Christofanis Skordas"
copyright = "2026 GSECARS, University of Chicago, USA"

extensions = [
    "autoapi.extension",
    "myst_parser",
    "sphinx_design",
]

myst_enable_extensions = ["colon_fence"]
myst_heading_anchors = 3

autoapi_dirs = ["../crystalsweep"]
autoapi_type = "python"
autoapi_options = ["members", "undoc-members", "show-inheritance", "show-module-summary"]

html_theme = "pydata_sphinx_theme"
html_theme_options = {
    "github_url": "https://github.com/gsecars/crystalsweep",
    "navigation_with_keys": True,
    "show_toc_level": 2,
    "footer_start": ["crystalsweep-copyright"],
    "footer_center": [],
    "footer_end": [],
}

html_sidebars = {
    "index": [],
}

templates_path = ["_templates"]

exclude_patterns = ["_build"]
