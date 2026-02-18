"""Tokyo Night-inspired dark theme for the Claude output viewer."""

COLORS = {
    "bg_primary": "#1a1b26",
    "bg_secondary": "#24283b",
    "bg_input": "#1f2335",
    "text_primary": "#c0caf5",
    "text_muted": "#565f89",
    "text_dimmed": "#3b4261",
    "accent_blue": "#7aa2f7",
    "accent_green": "#9ece6a",
    "accent_yellow": "#e0af68",
    "accent_red": "#f7768e",
    "accent_cyan": "#7dcfff",
    "accent_magenta": "#bb9af7",
    "border": "#292e42",
    "badge_bg": "#292e42",
}

STYLESHEET = f"""
QMainWindow {{
    background-color: {COLORS['bg_primary']};
}}
QWidget#central {{
    background-color: {COLORS['bg_primary']};
}}
QLabel#header {{
    background-color: {COLORS['bg_secondary']};
    color: {COLORS['text_muted']};
    padding: 8px 14px;
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 14px;
    border-bottom: 1px solid {COLORS['border']};
}}
QTextBrowser {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text_primary']};
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 14px;
    border: none;
    padding: 12px;
    selection-background-color: {COLORS['bg_secondary']};
}}
QScrollBar:vertical {{
    background: {COLORS['bg_primary']};
    width: 8px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['border']};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QStatusBar {{
    background-color: {COLORS['bg_secondary']};
    color: {COLORS['text_muted']};
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 12px;
    border-top: 1px solid {COLORS['border']};
    padding: 4px 10px;
}}
"""
